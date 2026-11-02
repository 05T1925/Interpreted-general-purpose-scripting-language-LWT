"""Bounded, reproducible matches between whitelisted LWT Snake strategies."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

from app.lwt_snake.bridge import GAME_SOURCE, LwtSnakeBridge
from app.lwt_snake.strategy import SOURCE, StrategyBridge
from app.lwt_snake.replay import Recorder, load, reconstruct, save, source_digest, command_parts

ROOT=Path(__file__).resolve().parents[2]
STRATEGIES={'baseline':Path(__file__).with_name('strategy_baseline.lwt'),'bfs':SOURCE}
MAX_RESULT=1024*1024
CASE_KEYS={'strategy_id','strategy_sha256','game_sha256','seed','ticks','phase','stop_reason',
           'score','replay_path','replay_sha256','verified','error_category','error_message'}
RESULT_KEYS={'schema_version','protocol_version','board','seeds','max_ticks','strategies','cases','summary'}


class ArenaError(ValueError): pass


def digest_file(path):return source_digest(path.read_bytes())


def parse_csv(raw, allowed=None):
    values=raw.split(',')
    if not values or any(not value for value in values) or len(set(values))!=len(values):
        raise ArenaError('list must contain unique nonempty values')
    if allowed is not None and any(value not in allowed for value in values):
        raise ArenaError('unknown strategy ID')
    return values


def config(args):
    ids=parse_csv(args.strategies,STRATEGIES)
    seeds=[]
    for value in parse_csv(args.seeds):
        if not value.isascii() or not value.isdecimal() or str(int(value))!=value:
            raise ArenaError('seed must be a canonical decimal integer')
        seed=int(value)
        if not 1<=seed<=2147483646:raise ArenaError('seed outside allowed range')
        seeds.append(seed)
    if len(seeds)>8 or len(ids)*len(seeds)>16:raise ArenaError('too many seeds or matches')
    if not 4<=args.width<=24 or not 1<=args.height<=18 or args.width*args.height>432:
        raise ArenaError('board dimensions outside game limits')
    if not 1<=args.max_ticks<=100 or args.workers not in (1,2,4) or args.workers>len(ids)*len(seeds):
        raise ArenaError('tick/worker limit invalid')
    if args.output.exists():raise ArenaError('output path already exists')
    if any(not path.is_file() for path in (GAME_SOURCE,*(STRATEGIES[name] for name in ids))):
        raise ArenaError('a whitelisted LWT source file is missing')
    return ids,sorted(seeds)


def summary(cases):
    result={}
    for name in sorted({item['strategy_id'] for item in cases}):
        rows=[item for item in cases if item['strategy_id']==name]
        counts={reason:sum(item['stop_reason']==reason for item in rows)
                for reason in ('won','game_over','trapped','limit','failed')}
        good=[item['score'] for item in rows if item['stop_reason']!='failed' and item['verified']]
        result[name]={'count':len(rows),'reasons':counts,'completed':len(good),
                      'score_median':statistics.median(good) if good else None,
                      'score_min':min(good) if good else None,'score_max':max(good) if good else None}
    return result


def run_case(strategy_id,seed,width,height,max_ticks,folder,*,strategy_factory=StrategyBridge,
             game_factory=LwtSnakeBridge,cancel=None,deadline_seconds=60):
    cancel=cancel or threading.Event()
    strategy_path=STRATEGIES[strategy_id]
    recorder=Recorder(width,height,seed)
    game=game_factory(repository_root=ROOT,width=width,height=height,seed=seed,on_transaction=recorder.append,timeout=5)
    strategy=strategy_factory(repository_root=ROOT,source_path=strategy_path,timeout=5)
    state=None;ticks=0;reason=None;category=None;message=None
    def expire():
        cancel.set();strategy.cancel();game.cancel()
    timer=threading.Timer(deadline_seconds,expire)
    timer.start()
    try:
        if cancel.is_set():raise ArenaError('match cancelled')
        state=game.start();state=game.request('START');strategy.start()
        while ticks<max_ticks:
            if cancel.is_set():raise ArenaError('match deadline/cancel reached')
            advice=strategy.query(state,cancel)
            if advice.direction is None:reason='trapped';break
            if advice.direction!=state.direction:state=game.request('TURN',advice.direction)
            state=game.request('TICK');ticks+=1
            if state.phase in ('GAME_OVER','WON'):
                reason={'GAME_OVER':'game_over','WON':'won'}[state.phase];break
        if reason is None:reason='limit'
    except Exception as error:
        reason='failed';category=type(error).__name__;message=str(error)[:512]
        recorder.interrupt(f'{category}: {message}')
    finally:
        timer.cancel()
        # First release the strategy, then the game owner; both calls are bounded.
        for owner in (strategy,game):
            try:owner.close()
            except Exception as error:
                if reason!='failed':
                    reason='failed';category=type(error).__name__;message=str(error)[:512]
                    recorder.interrupt(f'{category}: {message}')
        timer.join(timeout=5)
    replay=recorder.snapshot()
    relative=f'replays/{strategy_id}-{seed}.json'
    target=folder/relative
    replay_hash=None;verified=False
    if replay.transactions:
        save(target,replay)
        replay_hash=hashlib.sha256(target.read_bytes()).hexdigest()
        try:
            reconstructed=reconstruct(load(target),total_timeout=60)
            verified=True
            if state is None:state=reconstructed.states[-1]
        except Exception as error:
            reason='failed';category=type(error).__name__;message=f'replay verification: {error}'[:512]
    return {'strategy_id':strategy_id,'strategy_sha256':digest_file(strategy_path),
            'game_sha256':digest_file(GAME_SOURCE),'seed':seed,'ticks':ticks,
            'phase':state.phase if state else None,'stop_reason':reason,
            'score':state.score if state else None,'replay_path':relative if replay_hash else None,
            'replay_sha256':replay_hash,'verified':verified,
            'error_category':category,'error_message':message}


def atomic_json(path,data):
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if len(raw)>MAX_RESULT:raise ArenaError('result exceeds 1 MiB')
    temporary=None
    try:
        fd,temporary=tempfile.mkstemp(prefix='.arena-',suffix='.tmp',dir=path.parent)
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush()
        os.replace(temporary,path)
    finally:
        if temporary is not None:Path(temporary).unlink(missing_ok=True)


def run(args):
    ids,seeds=config(args)
    paths=[(name,seed) for name in sorted(ids) for seed in seeds]
    args.output.mkdir(parents=False)
    (args.output/'replays').mkdir()
    cases=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,name,seed,args.width,args.height,args.max_ticks,args.output): (name,seed)
                 for name,seed in paths}
        for future in as_completed(futures):cases.append(future.result())
    cases.sort(key=lambda case:(case['strategy_id'],case['seed']))
    result={'schema_version':1,'protocol_version':'LWS1','board':{'width':args.width,'height':args.height},
            'seeds':seeds,'max_ticks':args.max_ticks,
            'strategies':{name:{'path':str(STRATEGIES[name].relative_to(ROOT)).replace('\\','/'),
                                'sha256':digest_file(STRATEGIES[name]),'protocol':'LWA1'} for name in sorted(ids)},
            'cases':cases,'summary':summary(cases)}
    atomic_json(args.output/'result.json',result)
    show(result)
    return 1 if any(row['stop_reason']=='failed' for row in cases) else 0


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ArenaError(f'duplicate JSON field {key}')
        result[key]=value
    return result


def verify(path):
    raw=path.read_bytes()
    if len(raw)>MAX_RESULT:raise ArenaError('result exceeds 1 MiB')
    data=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_pairs)
    if type(data)!=dict or set(data)!=RESULT_KEYS or data['schema_version']!=1 or data['protocol_version']!='LWS1':
        raise ArenaError('result schema/version invalid')
    board=data['board'];ids=list(data['strategies']);seeds=data['seeds']
    if type(board)!=dict or set(board)!={'width','height'} or ids!=sorted(ids) or any(name not in STRATEGIES for name in ids):
        raise ArenaError('result board/strategy inventory invalid')
    if type(seeds)!=list or any(type(seed)!=int for seed in seeds) or seeds!=sorted(set(seeds)):
        raise ArenaError('result seed inventory invalid')
    if len(data['cases'])!=len(ids)*len(seeds) or len(data['cases'])>16:raise ArenaError('result case inventory invalid')
    for name in ids:
        spec=data['strategies'][name]
        if type(spec)!=dict or set(spec)!={'path','sha256','protocol'} or spec['path']!=str(STRATEGIES[name].relative_to(ROOT)).replace('\\','/') or spec['protocol']!='LWA1' or spec['sha256']!=digest_file(STRATEGIES[name]):
            raise ArenaError(f'{name}: strategy source digest/path mismatch')
    expected=[(name,seed) for name in ids for seed in seeds]
    for row,(name,seed) in zip(data['cases'],expected):
        label=f'{name}/{seed}'
        if type(row)!=dict or set(row)!=CASE_KEYS or row['strategy_id']!=name or row['seed']!=seed:
            raise ArenaError(f'{label}: case identity/schema mismatch')
        if row['strategy_sha256']!=data['strategies'][name]['sha256'] or row['game_sha256']!=digest_file(GAME_SOURCE):
            raise ArenaError(f'{label}: strategy/game digest mismatch')
        relative=f'replays/{name}-{seed}.json'
        if row['replay_path']!=relative:raise ArenaError(f'{label}: replay path mismatch')
        file=path.parent/relative
        if not file.is_file():raise ArenaError(f'{label}: missing replay')
        if row['replay_sha256']!=hashlib.sha256(file.read_bytes()).hexdigest():raise ArenaError(f'{label}: replay digest mismatch')
        record=load(file)
        if (record.width,record.height,record.seed)!=(board['width'],board['height'],seed):
            raise ArenaError(f'{label}: replay board/seed mismatch')
        try:actual=reconstruct(record,total_timeout=60)
        except Exception as error:raise ArenaError(f'{label}: {error}') from error
        last=actual.states[-1]
        ticks=sum(command_parts(tx)[0]=='TICK' for tx in record.transactions)
        if ticks!=row['ticks'] or ticks>data['max_ticks']:
            raise ArenaError(f'{label}: TICK count mismatch')
        if last.score!=row['score'] or last.phase!=row['phase']:
            raise ArenaError(f'{label}: final score/phase mismatch')
        reason=row['stop_reason']
        if reason not in ('won','game_over','trapped','limit','failed') or type(row['verified'])!=bool or not row['verified']:
            raise ArenaError(f'{label}: stop/verification status invalid')
        if reason in ('won','game_over') and last.phase!={'won':'WON','game_over':'GAME_OVER'}[reason]:
            raise ArenaError(f'{label}: terminal phase mismatch')
        if reason=='limit' and (ticks!=data['max_ticks'] or last.phase!='RUNNING'):
            raise ArenaError(f'{label}: limit reason mismatch')
        if reason=='trapped':
            if last.phase!='RUNNING':raise ArenaError(f'{label}: trapped phase mismatch')
            strategy=StrategyBridge(repository_root=ROOT,source_path=STRATEGIES[name])
            try:
                strategy.start()
                if strategy.query(last).direction is not None:raise ArenaError(f'{label}: trapped reason mismatch')
            finally:strategy.close()
        if (reason=='failed') != (row['error_category'] is not None and row['error_message'] is not None):
            raise ArenaError(f'{label}: error fields mismatch')
    if data['summary']!=summary(data['cases']):raise ArenaError('summary mismatch')
    return data


def show(result):
    print('strategy seed score ticks reason verified')
    for row in result['cases']:
        print(f"{row['strategy_id']} {row['seed']} {row['score']} {row['ticks']} {row['stop_reason']} {str(row['verified']).lower()}")
    for name,stats in result['summary'].items():
        print(f"{name}: completed={stats['completed']} failed={stats['reasons']['failed']} median={stats['score_median']} min={stats['score_min']} max={stats['score_max']}")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--strategies',default='baseline,bfs')
    parser.add_argument('--seeds',default='4,7,11')
    parser.add_argument('--width',type=int,default=8)
    parser.add_argument('--height',type=int,default=5)
    parser.add_argument('--max-ticks',type=int,default=40)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.verify:
            result=verify(args.verify);show(result);print(f"Verified {len(result['cases'])} matches.");return 0
        if args.output is None:raise ArenaError('--output is required to run matches')
        return run(args)
    except (ArenaError,OSError,ValueError,UnicodeError) as error:
        print(f'arena: {error}',file=sys.stderr)
        return 3 if args.verify else 2


if __name__=='__main__':raise SystemExit(main())
