"""S36 local latency sample only; stdout JSON, never updates S11 evidence."""
from pathlib import Path
import argparse
import json
import platform
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.lwt_snake.bridge import LwtSnakeBridge
from app.lwt_snake.strategy import StrategyBridge
from app.lwt_snake.replay import Recorder


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='write only this new S36 evidence path')
    options=parser.parse_args()
    samples=[]
    for width,height in ((8,5),(24,18)):
        game=LwtSnakeBridge(repository_root=ROOT,width=width,height=height,seed=4)
        strategy=StrategyBridge(repository_root=ROOT)
        try:
            game.start();state=game.request('START');strategy.start()
            pid=strategy.pid;elapsed=[];decisions=[]
            for _ in range(9):
                started=time.perf_counter();advice=strategy.query(state)
                elapsed.append(round((time.perf_counter()-started)*1000,3))
                decisions.append([advice.direction,advice.reason])
                if strategy.pid!=pid:raise RuntimeError('strategy PID changed')
            samples.append(dict(width=width,height=height,pid=pid,pid_stable=True,
                                request_ms=elapsed,median_ms=statistics.median(elapsed),
                                max_ms=max(elapsed),decisions=decisions))
        finally:strategy.close();game.close()
    recorder=Recorder(8,5,4)
    game=LwtSnakeBridge(repository_root=ROOT,width=8,height=5,seed=4,on_transaction=recorder.append)
    strategy=StrategyBridge(repository_root=ROOT)
    try:
        game.start();state=game.request('START');strategy.start()
        durations=[];max_queued=0;last=None
        for _ in range(24):
            started=time.perf_counter();advice=strategy.query(state)
            if advice.direction is None:break
            if advice.direction!=state.direction:state=game.request('TURN',advice.direction)
            state=game.request('TICK')
            durations.append(round((time.perf_counter()-started)*1000,3))
            max_queued=max(max_queued,strategy._stdout_events.qsize(),game._stdout_events.qsize())
            last=game.last_response
            if state.phase!='RUNNING':break
        auto=dict(ticks=len(durations),chain_ms=durations,max_queued_responses=max_queued,
                  phase=state.phase,score=state.score,transactions=len(recorder.snapshot().transactions),
                  final_response=last,game_pid=game.pid,strategy_pid=strategy.pid)
    finally:strategy.close();game.close()
    text=json.dumps(dict(schema_version=1,purpose='S36 local strategy latency; not S11 interpreter benchmark',
                         python=sys.version,os=platform.platform(),samples=samples,serial_auto=auto),indent=2)
    if options.output:
        options.output.write_text(text+'\n',encoding='utf-8')
        print('Saved S36 strategy samples.')
    else: print(text)


if __name__=='__main__':main()
