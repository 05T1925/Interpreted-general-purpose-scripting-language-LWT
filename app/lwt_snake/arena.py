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
from app.lwt_snake.strategy import encode_snapshot, parse_advice
from app.lwt_snake.replay import Recorder, load, reconstruct, save, source_digest, command_parts
from app.lwt_snake.protocol import parse_response

ROOT=Path(__file__).resolve().parents[2]
STRATEGIES={'baseline':Path(__file__).with_name('strategy_baseline.lwt'),'bfs':SOURCE}
MAX_RESULT=1024*1024
MAX_DECISIONS=1024*1024
CASE_KEYS={'strategy_id','strategy_sha256','game_sha256','seed','ticks','phase','stop_reason',
           'score','replay_path','replay_sha256','verified','error_category','error_message'}
CASE_V2_KEYS=(CASE_KEYS-{'verified'})|{'game_verified','policy_verified','decision_path','decision_sha256'}
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
        good=[item['score'] for item in rows if item['stop_reason']!='failed' and
              item.get('policy_verified',item.get('verified',False))]
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
    decisions=[]
    def expire():
        cancel.set();strategy.cancel();game.cancel()
    timer=threading.Timer(deadline_seconds,expire)
    timer.start()
    try:
        if cancel.is_set():raise ArenaError('match cancelled')
        state=game.start();state=game.request('START');strategy.start()
        while ticks<max_ticks:
            if cancel.is_set():raise ArenaError('match deadline/cancel reached')
            preceding=len(recorder.snapshot().transactions)
            advice=strategy.query(state,cancel)
            sequence=len(decisions)+1
            request=encode_snapshot(state,sequence)[:-1].decode('ascii')
            response=(f'LWA1|{sequence:06d}|NONE|-|TRAPPED' if advice.direction is None else
                      f'LWA1|{sequence:06d}|MOVE|{advice.direction}|{advice.reason}')
            decisions.append({'sequence':sequence,'game_transaction':preceding,
                              'request':request,'response':response})
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
    replay_hash=None;game_verified=False
    if replay.transactions:
        save(target,replay)
        replay_hash=hashlib.sha256(target.read_bytes()).hexdigest()
        try:
            reconstructed=reconstruct(load(target),total_timeout=60)
            game_verified=True
            # A completed bridge transaction can precede a transport/UI fault.
            state=reconstructed.states[-1]
            ticks=sum(command_parts(tx)[0]=='TICK' for tx in replay.transactions)
        except Exception as error:
            reason='failed';category=type(error).__name__;message=f'replay verification: {error}'[:512]
    decision_relative=f'decisions/{strategy_id}-{seed}.json'
    decision_hash=None
    if replay_hash:
        document={'schema_version':1,'protocol_version':'LWA1','strategy_id':strategy_id,
                  'strategy_sha256':digest_file(strategy_path),'game_sha256':digest_file(GAME_SOURCE),
                  'replay_sha256':replay_hash,'decisions':decisions}
        decision_target=folder/decision_relative
        decision_target.parent.mkdir(exist_ok=True)
        atomic_json(decision_target,document)
        decision_hash=hashlib.sha256(decision_target.read_bytes()).hexdigest()
    return {'strategy_id':strategy_id,'strategy_sha256':digest_file(strategy_path),
            'game_sha256':digest_file(GAME_SOURCE),'seed':seed,'ticks':ticks,
            'phase':state.phase if state else None,'stop_reason':reason,
            'score':state.score if state else None,'replay_path':relative if replay_hash else None,
            'replay_sha256':replay_hash,'game_verified':game_verified,
            'policy_verified':False,'decision_path':decision_relative if decision_hash else None,
            'decision_sha256':decision_hash,
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
    (args.output/'decisions').mkdir()
    cases=[]
    cancellation=threading.Event()
    pool=ThreadPoolExecutor(max_workers=args.workers)
    try:
        futures={pool.submit(run_case,name,seed,args.width,args.height,args.max_ticks,args.output,cancel=cancellation): (name,seed)
                 for name,seed in paths}
        for future in as_completed(futures):cases.append(future.result())
    except BaseException:
        cancellation.set()
        for future in futures:future.cancel()
        raise
    finally:pool.shutdown(wait=True,cancel_futures=True)
    cases.sort(key=lambda case:(case['strategy_id'],case['seed']))
    result={'schema_version':2,'protocol_version':'LWS1','board':{'width':args.width,'height':args.height},
            'seeds':seeds,'max_ticks':args.max_ticks,
            'strategies':{name:{'path':str(STRATEGIES[name].relative_to(ROOT)).replace('\\','/'),
                                'sha256':digest_file(STRATEGIES[name]),'protocol':'LWA1'} for name in sorted(ids)},
            'cases':cases,'summary':{}}
    # Re-run each independent LWT strategy and game before recording proof flags.
    for row in cases:
        if row['replay_path'] is not None:
            try:
                verify_case_v2(args.output/'result.json',result,row,check_flags=False)
                row['policy_verified']=True
            except Exception as error:
                if row['stop_reason']!='failed':
                    row['stop_reason']='failed';row['error_category']='VerificationError'
                    row['error_message']=str(error)[:512]
    result['summary']=summary(cases)
    atomic_json(args.output/'result.json',result)
    show(result)
    return 1 if any(row['stop_reason']=='failed' for row in cases) else 0


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ArenaError(f'duplicate JSON field {key}')
        result[key]=value
    return result


def _json_integer(raw):
    if len(raw.lstrip('-'))>10:raise ArenaError('oversized JSON integer')
    return int(raw)


def _read_json(path,limit):
    with path.open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ArenaError(f'{path.name}: JSON exceeds size limit')
    return json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_pairs,
                      parse_int=_json_integer,
                      parse_float=lambda _:(_ for _ in ()).throw(ArenaError('JSON floats are unsupported')),
                      parse_constant=lambda _:(_ for _ in ()).throw(ArenaError('non-finite JSON number')))


def _strict_file(base,relative,expected,limit,label):
    if relative!=expected:raise ArenaError(f'{label}: file path mismatch')
    file=base/relative
    if not file.is_file():raise ArenaError(f'{label}: missing {relative}')
    if file.is_symlink() or not file.resolve().is_relative_to(base.resolve()):
        raise ArenaError(f'{label}: file path escapes result directory')
    with file.open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ArenaError(f'{label}: file exceeds size limit')
    return file,raw


def _advice_frame(advice,sequence):
    return (f'LWA1|{sequence:06d}|NONE|-|TRAPPED' if advice.direction is None else
            f'LWA1|{sequence:06d}|MOVE|{advice.direction}|{advice.reason}')


def verify_case_v2(path,data,row,*,check_flags=True):
    name=row['strategy_id'];seed=row['seed'];label=f'{name}/{seed}'
    relative=f'replays/{name}-{seed}.json'
    if row['replay_path'] is None:
        if row['stop_reason']!='failed' or row['game_verified'] or row['policy_verified'] or row['replay_sha256'] is not None or row['decision_path'] is not None or row['decision_sha256'] is not None:
            raise ArenaError(f'{label}: missing replay proof fields inconsistent')
        return False
    file,raw=_strict_file(path.parent,row['replay_path'],relative,16*1024*1024,label)
    if hashlib.sha256(raw).hexdigest()!=row['replay_sha256']:
        raise ArenaError(f'{label}: replay digest mismatch')
    record=load(file)
    board=data['board']
    if (record.width,record.height,record.seed)!=(board['width'],board['height'],seed):
        raise ArenaError(f'{label}: replay board/seed mismatch')
    try:actual=reconstruct(record,total_timeout=60)
    except Exception as error:raise ArenaError(f'{label}: game transaction: {error}') from error
    states=actual.states;transactions=record.transactions
    if not states:raise ArenaError(f'{label}: empty game replay')
    last=states[-1]
    ticks=sum(command_parts(tx)[0]=='TICK' for tx in transactions)
    if ticks!=row['ticks'] or ticks>data['max_ticks']:raise ArenaError(f'{label}: TICK count mismatch')
    if last.score!=row['score'] or last.phase!=row['phase']:
        raise ArenaError(f'{label}: final score/phase mismatch')
    if row['decision_path'] is None or row['decision_sha256'] is None:
        raise ArenaError(f'{label}: missing decision evidence')
    dfile,draw=_strict_file(path.parent,row['decision_path'],f'decisions/{name}-{seed}.json',MAX_DECISIONS,label)
    if hashlib.sha256(draw).hexdigest()!=row['decision_sha256']:
        raise ArenaError(f'{label}: decision digest mismatch')
    document=_read_json(dfile,MAX_DECISIONS)
    if type(document)!=dict or set(document)!={'schema_version','protocol_version','strategy_id','strategy_sha256','game_sha256','replay_sha256','decisions'}:
        raise ArenaError(f'{label}: decision schema mismatch')
    if type(document['schema_version'])!=int or document['schema_version']!=1 or document['protocol_version']!='LWA1' or document['strategy_id']!=name or document['strategy_sha256']!=row['strategy_sha256'] or document['game_sha256']!=row['game_sha256'] or document['replay_sha256']!=row['replay_sha256']:
        raise ArenaError(f'{label}: decision metadata mismatch')
    entries=document['decisions']
    if type(entries)!=list or len(entries)>data['max_ticks']+1:
        raise ArenaError(f'{label}: decision count invalid')
    if len(transactions)<2 or [command_parts(tx)[0] for tx in transactions[:2]]!=['INIT','START'] or states[1].phase!='RUNNING':
        raise ArenaError(f'{label}: game must start with INIT and START')
    cursor=2;trapped=False;pending=False
    strategy=StrategyBridge(repository_root=ROOT,source_path=STRATEGIES[name])
    try:
        strategy.start()
        for number,entry in enumerate(entries,1):
            where=f'{label}: decision {number}'
            if type(entry)!=dict or set(entry)!={'sequence','game_transaction','request','response'} or type(entry['sequence'])!=int or type(entry['game_transaction'])!=int or type(entry['request'])!=str or type(entry['response'])!=str:
                raise ArenaError(f'{where}: decision fields invalid')
            if entry['sequence']!=number or entry['game_transaction']!=cursor:
                raise ArenaError(f'{where}: sequence/game_transaction mismatch')
            before=states[cursor-1]
            if before.phase!='RUNNING':raise ArenaError(f'{where}: consultation after terminal state')
            expected_request=encode_snapshot(before,number)[:-1].decode('ascii')
            if entry['request']!=expected_request:raise ArenaError(f'{where}: query-before-TURN snapshot/request mismatch')
            try:advice=strategy.query(before)
            except Exception as error:raise ArenaError(f'{where}: fresh LWT strategy: {error}') from error
            expected_response=_advice_frame(advice,number)
            if entry['response']!=expected_response:
                raise ArenaError(f'{where}: LWT strategy response/direction/reason mismatch')
            # parse_advice also checks protocol bounds and direction, independent of stored metadata.
            parse_advice(entry['response'].encode('ascii'),number,before)
            if advice.direction is None:
                trapped=True
                if number!=len(entries) or cursor!=len(transactions):
                    raise ArenaError(f'{where}: TRAPPED must be the final consultation')
                break
            if advice.direction!=before.direction:
                if cursor==len(transactions):
                    if row['stop_reason']!='failed':raise ArenaError(f'{where}: missing TURN')
                    pending=True;break
                command,args=command_parts(transactions[cursor])
                if command!='TURN' or args!=(advice.direction,):
                    raise ArenaError(f'{where}: TURN direction/transaction mismatch')
                cursor+=1
                if states[cursor-1].direction!=advice.direction:
                    raise ArenaError(f'{where}: TURN response mismatch')
            if cursor==len(transactions):
                if row['stop_reason']!='failed':raise ArenaError(f'{where}: missing TICK')
                pending=True;break
            command,_=command_parts(transactions[cursor])
            if command!='TICK':raise ArenaError(f'{where}: expected TICK transaction {cursor+1}')
            cursor+=1
    finally:
        strategy.close()
    if cursor!=len(transactions):raise ArenaError(f'{label}: extra game transaction {cursor+1}')
    reason=row['stop_reason']
    if reason=='trapped' and (not trapped or last.phase!='RUNNING'):
        raise ArenaError(f'{label}: trapped reason/consultation mismatch')
    if reason=='limit' and (trapped or pending or len(entries)!=ticks or ticks!=data['max_ticks'] or last.phase!='RUNNING'):
        raise ArenaError(f'{label}: limit consultation/TICK mismatch')
    if reason in ('won','game_over') and (trapped or pending or len(entries)!=ticks or last.phase!={'won':'WON','game_over':'GAME_OVER'}[reason]):
        raise ArenaError(f'{label}: terminal consultation/phase mismatch')
    if reason=='failed' and last.phase in ('WON','GAME_OVER') and not pending:
        raise ArenaError(f'{label}: failed reason conceals completed terminal')
    policy=bool(entries)
    if check_flags and (row['game_verified'] is not True or row['policy_verified'] is not policy):
        raise ArenaError(f'{label}: game_verified/policy_verified flag mismatch')
    return policy


def verify(path,*,game_only=False):
    data=_read_json(path,MAX_RESULT)
    if type(data)!=dict or set(data)!=RESULT_KEYS or type(data['schema_version'])!=int or data['schema_version'] not in (1,2) or data['protocol_version']!='LWS1':
        raise ArenaError('result schema/version invalid')
    version=data['schema_version']
    if version==2 and game_only:
        raise ArenaError('--game-only is only for legacy v1 results')
    if type(data['strategies'])!=dict or type(data['cases'])!=list or type(data['summary'])!=dict:
        raise ArenaError('result inventory/summary field type invalid')
    board=data['board'];ids=list(data['strategies']);seeds=data['seeds']
    if type(board)!=dict or set(board)!={'width','height'} or type(board['width'])!=int or type(board['height'])!=int or not 4<=board['width']<=24 or not 1<=board['height']<=18 or board['width']*board['height']>432 or not ids or len(ids)>2 or ids!=sorted(ids) or any(name not in STRATEGIES for name in ids):
        raise ArenaError('result board/strategy inventory invalid')
    if type(data['max_ticks'])!=int or not 1<=data['max_ticks']<=100:
        raise ArenaError('result tick limit invalid')
    if type(seeds)!=list or not 1<=len(seeds)<=8 or any(type(seed)!=int or not 1<=seed<=2147483646 for seed in seeds) or seeds!=sorted(set(seeds)):
        raise ArenaError('result seed inventory invalid')
    if len(data['cases'])!=len(ids)*len(seeds) or not data['cases'] or len(data['cases'])>16:raise ArenaError('result case inventory invalid')
    if version==1 and not game_only:
        raise ArenaError('v1 game replay only; strategy decisions unverified; use --game-only --verify')
    for name in ids:
        spec=data['strategies'][name]
        if type(spec)!=dict or set(spec)!={'path','sha256','protocol'} or spec['path']!=str(STRATEGIES[name].relative_to(ROOT)).replace('\\','/') or spec['protocol']!='LWA1' or spec['sha256']!=digest_file(STRATEGIES[name]):
            raise ArenaError(f'{name}: strategy source digest/path mismatch')
    expected=[(name,seed) for name in ids for seed in seeds]
    for row,(name,seed) in zip(data['cases'],expected):
        label=f'{name}/{seed}'
        if type(row)!=dict or set(row)!=(CASE_V2_KEYS if version==2 else CASE_KEYS):raise ArenaError(f'{label}: case schema mismatch')
        if row['strategy_id']!=name:raise ArenaError(f'{label}: strategy_id mismatch')
        if row['seed']!=seed:raise ArenaError(f'{label}: seed mismatch')
        if type(row['ticks'])!=int or not 0<=row['ticks']<=data['max_ticks'] or (row['score'] is not None and (type(row['score'])!=int or not 0<=row['score']<=4320)) or (row['phase'] is not None and (type(row['phase'])!=str or row['phase'] not in ('READY','RUNNING','WON','GAME_OVER'))):
            raise ArenaError(f'{label}: tick/score/phase field type invalid')
        if row['strategy_sha256']!=data['strategies'][name]['sha256'] or row['game_sha256']!=digest_file(GAME_SOURCE):
            raise ArenaError(f'{label}: strategy/game digest mismatch')
        if row['stop_reason'] not in ('won','game_over','trapped','limit','failed'):
            raise ArenaError(f'{label}: stop reason invalid')
        if (row['stop_reason']=='failed')!=(type(row['error_category']) is str and type(row['error_message']) is str):
            raise ArenaError(f'{label}: error fields mismatch')
        if row['error_category'] is not None and (len(row['error_category'])>80 or len(row['error_message'])>512):
            raise ArenaError(f'{label}: error fields too long')
        if version==2:
            if type(row['game_verified'])!=bool or type(row['policy_verified'])!=bool:
                raise ArenaError(f'{label}: proof flags invalid')
            verify_case_v2(path,data,row)
            continue
        relative=f'replays/{name}-{seed}.json'
        if row['replay_path']!=relative:raise ArenaError(f'{label}: replay path mismatch')
        file,raw=_strict_file(path.parent,row['replay_path'],relative,16*1024*1024,label)
        if row['replay_sha256']!=hashlib.sha256(raw).hexdigest():raise ArenaError(f'{label}: replay digest mismatch')
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
        if type(row['verified'])!=bool or not row['verified']:
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
    print('strategy seed score ticks reason game_verified policy_verified')
    for row in result['cases']:
        game=row.get('game_verified',row.get('verified',False))
        policy=row.get('policy_verified',False)
        print(f"{row['strategy_id']} {row['seed']} {row['score']} {row['ticks']} {row['stop_reason']} {str(game).lower()} {str(policy).lower()}")
    for name,stats in result['summary'].items():
        print(f"{name}: completed={stats['completed']} failed={stats['reasons']['failed']} median={stats['score_median']} min={stats['score_min']} max={stats['score_max']}")


def explain(path,case,step):
    data=verify(path)
    if data['schema_version']!=2:raise ArenaError('explain requires v2 policy proof')
    if type(step)!=int or step<1:raise ArenaError('step must be positive')
    row=next((item for item in data['cases'] if f"{item['strategy_id']}/{item['seed']}"==case),None)
    if row is None:raise ArenaError('case ID is not in the result')
    if not row['game_verified'] or not row['policy_verified'] or row['stop_reason']=='failed':
        raise ArenaError(f'{case}: incomplete case cannot be explained as confirmed policy')
    decisions=_read_json(path.parent/row['decision_path'],MAX_DECISIONS)['decisions']
    if step>len(decisions):raise ArenaError(f'{case}: step outside decision range')
    entry=decisions[step-1]
    record=load(path.parent/row['replay_path'])
    actual=reconstruct(record,total_timeout=60)
    before=actual.states[entry['game_transaction']-1]
    next_index=(decisions[step]['game_transaction'] if step<len(decisions) else len(record.transactions))
    next_commands=[command_parts(tx)[0] for tx in record.transactions[entry['game_transaction']:next_index]]
    after=actual.states[next_index-1] if next_index>entry['game_transaction'] else before
    print(f'case={case} step={step} strategy_sha256={row["strategy_sha256"]}')
    print(f'before_tx={entry["game_transaction"]} phase={before.phase} score={before.score} direction={before.direction} head={before.snake[0]} food={before.food}')
    print(f'LWT_advice={entry["response"]} commands={",".join(next_commands) or "none"}')
    print(f'after_tx={next_index} phase={after.phase} score={after.score} delta={after.score-before.score} head={after.snake[0]}')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--game-only',action='store_true')
    parser.add_argument('--explain',type=Path)
    parser.add_argument('--case')
    parser.add_argument('--step',type=int)
    parser.add_argument('--strategies',default='baseline,bfs')
    parser.add_argument('--seeds',default='4,7,11')
    parser.add_argument('--width',type=int,default=8)
    parser.add_argument('--height',type=int,default=5)
    parser.add_argument('--max-ticks',type=int,default=40)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.explain:
            if args.verify or args.game_only or args.output or args.case is None or args.step is None:
                raise ArenaError('--explain requires --case ID/seed and --step N only')
            explain(args.explain,args.case,args.step);return 0
        if args.verify:
            if args.case is not None or args.step is not None:raise ArenaError('--case/--step require --explain')
            result=verify(args.verify,game_only=args.game_only);show(result)
            if result['schema_version']==1:print('game replay only; strategy decisions unverified')
            elif all(row['game_verified'] and row['policy_verified'] for row in result['cases']):
                print(f"Verified {len(result['cases'])} matches: game and policy decisions.")
            else:
                print(f"Checked {len(result['cases'])} matches; partial proof: game_verified={sum(row['game_verified'] for row in result['cases'])}, policy_verified={sum(row['policy_verified'] for row in result['cases'])}.")
            return 0
        if args.game_only or args.case is not None or args.step is not None:
            raise ArenaError('--game-only requires --verify; --case/--step require --explain')
        if args.output is None:raise ArenaError('--output is required to run matches')
        return run(args)
    except KeyboardInterrupt:
        print('arena: cancelled; active processes are being reaped',file=sys.stderr)
        return 130
    except (ArenaError,OSError,ValueError,UnicodeError,RecursionError,TypeError) as error:
        print(f'arena: {error}',file=sys.stderr)
        return 3 if args.verify or args.explain else 2


if __name__=='__main__':raise SystemExit(main())
