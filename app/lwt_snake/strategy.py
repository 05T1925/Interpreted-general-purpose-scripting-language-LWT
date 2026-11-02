"""Bounded LWA1 transport and worker; all decisions live in strategy.lwt."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import os
import queue
import subprocess
import threading
import time

from app.lwt_snake.bridge import LwtSnakeBridge, BridgeFailure, _EOF, _ReaderFault
from app.lwt_snake.protocol import GameSnapshot, ProtocolError, parse_response

SOURCE = Path(__file__).with_name('strategy.lwt')


@dataclass(frozen=True)
class Advice:
    direction: str | None
    reason: str


def encode_snapshot(state: GameSnapshot, sequence: int) -> bytes:
    if state.phase != 'RUNNING' or not 1 <= sequence <= 999999:
        raise ProtocolError('strategy requires RUNNING and a valid sequence')
    if not 4 <= state.width <= 24 or not 1 <= state.height <= 18 or state.food is None:
        raise ProtocolError('strategy board dimensions or food are invalid')
    body = ';'.join(f'{x},{y}' for x,y in state.snake)
    # Reuse the game's structural validator, not its transition rules.
    parse_response((f'LWS1|000001|STATE|RUNNING|{state.score}|{state.direction}|'
                    f'{state.food[0]}|{state.food[1]}|{len(state.snake)}|{body}').encode('ascii'),
                   expected_sequence=1, width=state.width, height=state.height)
    frame=(f'LWA1|{sequence:06d}|{state.width}|{state.height}|{state.direction}|'
           f'{state.food[0]}|{state.food[1]}|{len(state.snake)}|{body}').encode('ascii')
    if len(frame)>4096: raise ProtocolError('strategy request exceeds 4096 bytes')
    return frame+b'\n'


def parse_advice(frame: bytes, sequence: int, state: GameSnapshot) -> Advice:
    if not frame or len(frame)>128 or b'\r' in frame or b'\n' in frame:
        raise ProtocolError('strategy response must be a bounded LF frame')
    try: fields=frame.decode('ascii','strict').split('|')
    except UnicodeDecodeError as error: raise ProtocolError('strategy response is not ASCII') from error
    if len(fields)!=5 or fields[:2]!=['LWA1',f'{sequence:06d}']:
        raise ProtocolError('strategy response fields, version or sequence are invalid')
    if fields[2:]==['NONE','-','TRAPPED']: return Advice(None,'TRAPPED')
    if fields[2]!='MOVE' or fields[3] not in {'U','R','D','L'} or fields[4] not in {'FOOD','SPACE'}:
        raise ProtocolError('strategy response direction or reason is invalid')
    if fields[3]=={'U':'D','D':'U','L':'R','R':'L'}[state.direction]:
        raise ProtocolError('strategy returned a directly reversed direction')
    return Advice(fields[3],fields[4])


class StrategyBridge(LwtSnakeBridge):
    """Reuse only the game's bounded pipe readers/termination, not rule logic."""
    def __init__(self, *, repository_root: Path, source_path: Path=SOURCE,
                 timeout: float=5.0, **options):
        super().__init__(repository_root=repository_root,source_path=source_path,timeout=timeout,**options)

    def start(self):
        if self._started or self._closed: raise BridgeFailure('strategy already started or closed')
        if not math.isfinite(self.timeout) or self.timeout<=0: raise BridgeFailure('invalid strategy timeout')
        if not self.source_path.is_file(): raise BridgeFailure('strategy source does not exist')
        options=dict(args=list(self.command),cwd=str(self.repository_root),stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,bufsize=-1)
        if os.name=='nt':
            options['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
        try: self._process=self._process_factory(**options)
        except (OSError,ValueError) as error: raise BridgeFailure(f'could not start strategy: {error}') from error
        process=self._process
        if any(stream is None for stream in (process.stdin,process.stdout,process.stderr)):
            self.close();raise BridgeFailure('strategy pipes unavailable')
        self._stdout_thread=threading.Thread(target=self._read_stdout,args=(process.stdout,),name='strategy-stdout',daemon=True)
        self._stderr_thread=threading.Thread(target=self._read_stderr,args=(process.stderr,),name='strategy-stderr',daemon=True)
        self._stdout_thread.start();self._stderr_thread.start();self._started=True

    def query(self, state: GameSnapshot, cancel: threading.Event | None=None) -> Advice:
        with self._request_lock:
            if not self._started or self._closed or self._broken: raise BridgeFailure('strategy is not running')
            sequence=self._next_sequence
            frame=encode_snapshot(state,sequence)
            try:
                if cancel and cancel.is_set(): raise BridgeFailure('strategy request cancelled')
                if self._process.poll() is not None: raise self._process_failure('strategy exited')
                self._reject_pending_output(sequence)
                self._process.stdin.write(frame);self._process.stdin.flush()
                end=time.monotonic()+self.timeout
                while True:
                    if cancel and cancel.is_set(): raise BridgeFailure('strategy request cancelled')
                    remaining=end-time.monotonic()
                    if remaining<=0: raise BridgeFailure('strategy response timed out')
                    try: event=self._stdout_events.get(timeout=min(0.05,remaining));break
                    except queue.Empty: pass
                if event is _EOF: raise self._process_failure('strategy reached EOF')
                if isinstance(event,_ReaderFault): raise BridgeFailure(event.message)
                if not isinstance(event,bytes): raise BridgeFailure('invalid strategy reader event')
                advice=parse_advice(event,sequence,state)
                self._reject_extra_after_response('QUERY')
                self._next_sequence+=1
                return advice
            except (ProtocolError,OSError,ValueError) as error:
                self._abort_process()
                raise self._process_failure(str(error)) from error

    def _read_stdout(self, stream):
        while not self._reader_stop.is_set():
            try: line=stream.readline(130)
            except (OSError,ValueError) as error:
                self._publish_stdout(_ReaderFault(f'strategy stdout read failed: {error}'));return
            if not line:self._publish_stdout(_EOF);return
            if not line.endswith(b'\n') or len(line)>129:
                self._publish_stdout(_ReaderFault('strategy stdout is overlong or missing LF'));return
            self._publish_stdout(line[:-1])

    def close(self):
        if self._closed:return
        process=self._process
        pending=None
        if process is not None and process.poll() is None and not self._broken:
            try:
                process.stdin.close()  # EOF, not an invented strategy QUIT request.
                process.wait(timeout=1)
                if process.returncode!=0: raise self._process_failure('strategy exited unsuccessfully')
                self._check_only_eof_after_exit()
            except (OSError,ValueError,ProtocolError,subprocess.TimeoutExpired) as error: pending=error
        self._terminate_process()
        self._reader_stop.set()
        if process is not None:
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream is not None:
                    try:stream.close()
                    except OSError:pass
        for thread in (self._stdout_thread,self._stderr_thread):
            if thread is not None:thread.join(timeout=1)
        self._closed=True
        if pending:raise BridgeFailure(str(pending))


@dataclass(frozen=True)
class StrategyReply:
    generation: int
    state: GameSnapshot
    advice: Advice | None=None
    error: str | None=None


class StrategyWorker(threading.Thread):
    def __init__(self, root: Path, replies: queue.Queue, generation: int, *, factory=StrategyBridge):
        super().__init__(name='lwt-strategy-worker',daemon=False)
        self.bridge=factory(repository_root=root)
        self.replies=replies;self.generation=generation
        self.commands=queue.Queue(maxsize=1)
        self.stopping=threading.Event();self.finished=threading.Event()

    def submit(self,state):
        if self.stopping.is_set() or self.finished.is_set():return False
        try:self.commands.put_nowait(state);return True
        except queue.Full:return False

    def stop(self):self.stopping.set()

    def run(self):
        state=None
        try:
            self.bridge.start()
            while not self.stopping.is_set():
                try:state=self.commands.get(timeout=0.05)
                except queue.Empty:continue
                result=self.bridge.query(state,self.stopping)
                if not self.stopping.is_set():self.replies.put_nowait(StrategyReply(self.generation,state,result))
        except Exception as error:
            if state is None:
                try:state=self.commands.get_nowait()
                except queue.Empty:pass
            if not self.stopping.is_set():self.replies.put_nowait(StrategyReply(self.generation,state,error=str(error)))
        finally:
            try:self.bridge.close()
            except Exception:pass  # Request errors are already delivered; cancelled owners have no UI target.
            self.finished.set()
