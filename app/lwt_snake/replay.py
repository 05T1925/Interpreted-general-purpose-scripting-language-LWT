"""Bounded replay codec, transaction recorder and real LWT reconstruction CLI."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import sys

from app.lwt_snake.bridge import GAME_SOURCE, LwtSnakeBridge
from app.lwt_snake.protocol import CommandRejected, GameSnapshot, ProtocolError, format_request, parse_response

MAX_TRANSACTIONS = 5000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_INTEGER_DIGITS = 10
TOTAL_TIMEOUT = 30.0
HASH_ALGORITHM = 'lwt-utf8-lf-sha256-v1'
ROOT = Path(__file__).resolve().parents[2]


class ReplayError(ValueError): pass
class VerificationError(RuntimeError): pass


@dataclass(frozen=True)
class Transaction:
    request: str
    response: str


@dataclass(frozen=True)
class Origin:
    parent_sha256: str
    prefix_count: int


@dataclass(frozen=True)
class Replay:
    width: int
    height: int
    seed: int
    source_sha256: str
    transactions: tuple[Transaction, ...]
    interruption: str | None = None
    origin: Origin | None = None


def source_digest(raw: bytes) -> str:
    text = raw.decode('utf-8', 'strict')
    if text.startswith('\ufeff'): text = text[1:]
    return hashlib.sha256(text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')).hexdigest()


def document(replay: Replay) -> dict:
    return {'schema_version': 1, 'protocol_version': 'LWS1',
            'source': {'algorithm': HASH_ALGORITHM, 'sha256': replay.source_sha256},
            'settings': {'width': replay.width, 'height': replay.height, 'seed': replay.seed},
            'transactions': [{'request': t.request, 'response': t.response} for t in replay.transactions],
            'interruption': replay.interruption,
            'origin': None if replay.origin is None else {'parent_sha256': replay.origin.parent_sha256, 'prefix_count': replay.origin.prefix_count}}


def replay_digest(replay: Replay) -> str:
    return hashlib.sha256(json.dumps(document(replay), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ReplayError('missing or unknown replay object fields')
    return value


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high: raise ReplayError('integer field outside allowed range (bool is not an integer)')
    return value


def _digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value): raise ReplayError('invalid SHA-256 digest')
    return value


def command_parts(transaction: Transaction):
    fields = transaction.request.split('|')
    if len(fields) != 6 or fields[0] != 'LWS1' or not re.fullmatch('[0-9]{6}', fields[1]):
        raise ReplayError('invalid request frame')
    command = fields[2]
    if command == 'INIT':
        if not all(re.fullmatch('[0-9]{1,10}', v) for v in fields[3:]): raise ReplayError('invalid INIT arguments')
        args = tuple(int(v) for v in fields[3:])
    elif command == 'TURN': args = (fields[3],)
    elif command in {'START', 'TICK', 'PAUSE', 'RESUME', 'RESET'}: args = ()
    else: raise ReplayError('record contains an unsupported command (QUIT is transport-only)')
    try:
        canonical = format_request(int(fields[1]), command, LwtSnakeBridge._command_fields(command, args))[:-1].decode('ascii')
    except (ProtocolError, ValueError, TypeError) as error: raise ReplayError(str(error)) from error
    if canonical != transaction.request: raise ReplayError('request frame is not canonical')
    return command, args


def decode_document(data, *, compatible=True) -> Replay:
    _object(data, ('schema_version', 'protocol_version', 'source', 'settings', 'transactions', 'interruption', 'origin'))
    if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['protocol_version'] != 'LWS1': raise ReplayError('unsupported replay/protocol version')
    source = _object(data['source'], ('algorithm', 'sha256'))
    if source['algorithm'] != HASH_ALGORITHM: raise ReplayError('unsupported source digest algorithm')
    digest = _digest(source['sha256'])
    if compatible and digest != source_digest(GAME_SOURCE.read_bytes()): raise ReplayError('game source digest is incompatible')
    settings = _object(data['settings'], ('width', 'height', 'seed'))
    width = _integer(settings['width'], 4, 24); height = _integer(settings['height'], 1, 18); seed = _integer(settings['seed'], 1, 2147483646)
    transactions = data['transactions']
    if type(transactions) is not list or not 1 <= len(transactions) <= MAX_TRANSACTIONS: raise ReplayError('record must contain 1..5000 transactions')
    parsed = []
    for index, item in enumerate(transactions, 1):
        _object(item, ('request', 'response'))
        if any(type(item[k]) is not str for k in item): raise ReplayError('frames must be strings')
        tx = Transaction(item['request'], item['response'])
        try:
            if len(tx.request.encode('ascii')) > 128 or len(tx.response.encode('ascii')) > 4096 or '\n' in tx.response or '\r' in tx.response: raise ReplayError('invalid frame size/encoding')
            if re.search('[0-9]{11}', tx.response): raise ReplayError('oversized protocol integer')
            command, args = command_parts(tx)
            if tx.request.split('|')[1] != f'{index:06d}': raise ReplayError('transaction sequence is not continuous')
            if (index == 1) != (command == 'INIT'): raise ReplayError('INIT must occur exactly once as the first transaction')
            if index == 1 and args != (width, height, seed): raise ReplayError('INIT disagrees with settings')
            try: parse_response(tx.response.encode('ascii'), expected_sequence=index, width=width, height=height)
            except CommandRejected:
                if index == 1: raise ReplayError('INIT must succeed')
        except (UnicodeError, ProtocolError, TypeError, ValueError) as error:
            raise ReplayError(f'transaction {index}: {error}') from error
        parsed.append(tx)
    interruption = data['interruption']
    if interruption is not None and (type(interruption) is not str or len(interruption) > 512): raise ReplayError('invalid interruption reason')
    origin = data['origin']
    if origin is not None:
        _object(origin, ('parent_sha256', 'prefix_count'))
        origin = Origin(_digest(origin['parent_sha256']), _integer(origin['prefix_count'], 1, len(parsed)))
    return Replay(width, height, seed, digest, tuple(parsed), interruption, origin)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ReplayError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _parse_integer(text):
    if len(text.lstrip('-')) > MAX_INTEGER_DIGITS: raise ReplayError('oversized JSON integer')
    return int(text)


def load(path: Path) -> Replay:
    try:
        with path.open('rb') as stream: raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES: raise ReplayError('replay file exceeds 16 MiB')
        data = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=_pairs, parse_int=_parse_integer,
                          parse_constant=lambda value: (_ for _ in ()).throw(ReplayError('non-finite JSON number')))
        return decode_document(data)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ReplayError(f'cannot load replay: {error}') from error


def save(path: Path, replay: Replay) -> None:
    decode_document(document(replay))
    raw = (json.dumps(document(replay), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(raw) > MAX_FILE_BYTES: raise ReplayError('serialized replay exceeds 16 MiB')
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.lwt-replay-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush()
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try: Path(temporary).unlink(missing_ok=True)
            except OSError: pass


class Recorder:
    def __init__(self, width=24, height=18, seed=1, *, source=GAME_SOURCE, origin=None):
        self.settings = width, height, seed
        self.digest = source_digest(source.read_bytes())
        self.origin = origin
        self.items = []
        self.reason = None
        self.lock = threading.Lock()

    def append(self, request, response):
        with self.lock:
            if len(self.items) >= MAX_TRANSACTIONS:
                self.reason = f'仅保存到第 {MAX_TRANSACTIONS} 条：达到录制上限'
            else: self.items.append(Transaction(request, response))

    def interrupt(self, reason):
        with self.lock:
            if self.reason is None: self.reason = str(reason)[:512]

    def snapshot(self):
        with self.lock: return Replay(*self.settings, self.digest, tuple(self.items), self.reason, self.origin)


@dataclass
class Verified:
    replay: Replay
    states: tuple[GameSnapshot, ...]
    bridge: LwtSnakeBridge | None = None
    recorder: Recorder | None = None


def reconstruct(replay: Replay, *, prefix=None, keep=False, cancel=None, progress=None, total_timeout=TOTAL_TIMEOUT, on_bridge=None) -> Verified:
    if not math.isfinite(total_timeout) or total_timeout <= 0: raise VerificationError('total deadline must be finite and positive')
    deadline = time.monotonic() + total_timeout
    replay = decode_document(document(replay))
    count = len(replay.transactions) if prefix is None else _integer(prefix, 1, len(replay.transactions))
    cancel = cancel or threading.Event()
    recorder = Recorder(replay.width, replay.height, replay.seed,
                        origin=Origin(replay_digest(replay), count) if keep else replay.origin)
    bridge = LwtSnakeBridge(repository_root=ROOT, width=replay.width, height=replay.height, seed=replay.seed, on_transaction=recorder.append)
    if on_bridge: on_bridge(bridge)
    stopped = threading.Event()
    def watchdog():
        while not stopped.wait(.02):
            if cancel.is_set() or time.monotonic() >= deadline:
                bridge.cancel(); return
    monitor = threading.Thread(target=watchdog, name='lwt-replay-deadline')
    monitor.start(); states = []; last = None
    try:
        for index, tx in enumerate(replay.transactions[:count], 1):
            if cancel.is_set() or time.monotonic() >= deadline: raise VerificationError('verification cancelled or total deadline exceeded')
            command, args = command_parts(tx)
            try: last = bridge.start() if index == 1 else bridge.request(command, *args)
            except CommandRejected: pass
            actual = bridge.last_response
            if actual != tx.response:
                expected_fields = tx.response.split('|'); actual_fields = (actual or '').split('|')
                mismatch = next((i for i in range(max(len(expected_fields),len(actual_fields))) if expected_fields[i:i+1] != actual_fields[i:i+1]), 0)
                raise VerificationError(f'transaction {index}, sequence {index:06d}, command {command}, field {mismatch}: expected {tx.response[:180]!r}; actual {(actual or "")[:180]!r}')
            states.append(last)
            if progress: progress(index, count)
        if cancel.is_set() or time.monotonic() >= deadline: raise VerificationError('verification cancelled or total deadline exceeded')
        if keep and last.phase in {'GAME_OVER', 'WON'}: raise VerificationError('terminal prefix cannot be taken over; select an earlier prefix')
        if not keep: bridge.close()
        return Verified(replay, tuple(states), bridge if keep else None, recorder if keep else None)
    except BaseException as error:
        bridge.cancel()
        try: bridge.close()
        except Exception: pass
        if isinstance(error, KeyboardInterrupt): raise VerificationError('verification cancelled') from error
        if not isinstance(error, Exception): raise
        if cancel.is_set(): raise VerificationError('verification cancelled') from error
        if time.monotonic() >= deadline: raise VerificationError('verification total deadline exceeded') from error
        raise VerificationError(str(error)) from error
    finally:
        stopped.set()
        # Windows tree termination itself has a bounded 2s subprocess wait.
        # Wait past that cleanup budget before returning ownership to the caller.
        monitor.join(timeout=5)
        if monitor.is_alive(): raise VerificationError('verification cleanup monitor did not finish')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify a Snake replay through a fresh public LWT CLI process.')
    parser.add_argument('--verify', required=True, type=Path)
    options = parser.parse_args(argv)
    try: replay = load(options.verify)
    except KeyboardInterrupt: print('verification cancelled', file=sys.stderr); return 3
    except (ReplayError, OSError) as error: print(str(error), file=sys.stderr); return 2
    try: result = reconstruct(replay)
    except KeyboardInterrupt: print('verification cancelled', file=sys.stderr); return 3
    except (ReplayError, OSError) as error: print(str(error), file=sys.stderr); return 2
    except VerificationError as error: print(str(error), file=sys.stderr); return 3
    sys.stdout.buffer.write(f'Verified {len(result.states)} transactions.\n'.encode('ascii'))
    return 0


if __name__ == '__main__': raise SystemExit(main())
