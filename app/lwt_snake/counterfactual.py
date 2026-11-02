"""Verify LWT policy answers on one shared observation trace and branch one tick."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from app.lwt_snake import arena
from app.lwt_snake.catalog import load_catalog
from app.lwt_snake.replay import ROOT, document, load, reconstruct, save
from app.lwt_snake.strategy import StrategyBridge, encode_snapshot

MAX_ANALYSIS = 1024 * 1024
DEADLINE = 120.0
IDS = re.compile(r'[a-z][a-z0-9-]{0,31}\Z')


class CounterfactualError(ValueError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _inside(path):
    resolved = path.resolve()
    if path.is_symlink() or not resolved.is_relative_to(ROOT):
        raise CounterfactualError('input must be a regular repository-local file')
    return resolved.relative_to(ROOT).as_posix()


def _read(path, limit=MAX_ANALYSIS):
    if path.is_symlink() or not path.is_file():
        raise CounterfactualError(f'missing or linked file: {path.name}')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise CounterfactualError(f'file too large: {path.name}')
    return raw


def _request(data, case, step, names):
    if data['schema_version'] != 3:
        raise CounterfactualError('counterfactual requires S39 v3')
    row = next((r for r in data['cases'] if f"{r['strategy_id']}/{r['seed']}" == case), None)
    if row is None or row['stop_reason'] == 'failed' or row['game_verified'] is not True or row['policy_verified'] is not True:
        raise CounterfactualError(f'{case}: missing or incomplete double-verified case')
    if type(step) is not int or step < 1:
        raise CounterfactualError('step must be a positive integer')
    if not 1 <= len(names) <= 3 or len(set(names)) != len(names) or any(not IDS.fullmatch(n) or n not in data['strategies'] for n in names):
        raise CounterfactualError('candidate IDs must be 1..3 distinct verified strategies')
    return row


def compute(result_path, catalog_path, case, step, names):
    """All policy choices and game transitions come from fresh LWT processes."""
    started = time.monotonic()
    result_path = Path(result_path)
    catalog_path = Path(catalog_path)
    result_rel, catalog_rel = _inside(result_path), _inside(catalog_path)
    raw = _read(result_path)
    catalog = load_catalog(catalog_path)
    data = arena.verify(result_path, catalog_path=catalog_path)
    row = _request(data, case, step, names)
    decisions = arena._read_json(result_path.parent / row['decision_path'], arena.MAX_DECISIONS)['decisions']
    if step > len(decisions):
        raise CounterfactualError(f'{case}: step {step} exceeds decision count')
    index = decisions[step - 1]['game_transaction']
    replay = load(result_path.parent / row['replay_path'])
    states = reconstruct(replay, total_timeout=60).states
    observation = []
    for number, entry in enumerate(decisions[:step], 1):
        state = states[entry['game_transaction'] - 1]
        if encode_snapshot(state, number)[:-1].decode('ascii') != entry['request']:
            raise CounterfactualError(f'{case}: observation {number} differs from verified game')
        observation.append(state)
    if time.monotonic() - started >= DEADLINE:
        raise CounterfactualError('analysis total deadline exceeded')
    paths = dict(arena.STRATEGIES)
    paths.update({name: item.path for name, item in catalog.entries.items()})
    candidates, branches = [], {}
    for name in names:
        if time.monotonic() - started >= DEADLINE:
            raise CounterfactualError('analysis total deadline exceeded')
        catalog.assert_unchanged()
        policy = StrategyBridge(repository_root=ROOT, source_path=paths[name])
        try:
            policy.start()
            for state in observation:
                advice = policy.query(state)
        finally:
            policy.close()
        catalog.assert_unchanged()
        if arena.digest_file(paths[name]) != data['strategies'][name]['sha256']:
            raise CounterfactualError(f'{name}: strategy source changed during consultation')
        response = arena._advice_frame(advice, step)
        item = {'strategy_id': name, 'strategy_sha256': data['strategies'][name]['sha256'],
                'request': decisions[step - 1]['request'], 'response': response,
                'replay_path': None, 'replay_sha256': None,
                'before_score': observation[-1].score, 'after_score': None, 'after_phase': None}
        if advice.direction is not None:
            branch = reconstruct(replay, prefix=index, keep=True, total_timeout=60)
            try:
                if advice.direction != observation[-1].direction:
                    branch.bridge.request('TURN', advice.direction)
                after = branch.bridge.request('TICK')
                branch_replay = branch.recorder.snapshot()
            finally:
                branch.bridge.close()
            check = reconstruct(branch_replay, total_timeout=60)
            if check.states[-1] != after:
                raise CounterfactualError(f'{name}: branch replay disagrees with LWT tick')
            item.update(replay_path=f'branches/{name}.json', after_score=after.score,
                        after_phase=after.phase)
            branches[name] = branch_replay
        candidates.append(item)
    analysis = {'schema_version': 1, 'result_path': result_rel, 'result_sha256': _sha(raw),
                'catalog_path': catalog_rel, 'catalog_sha256': catalog.sha256,
                'case': case, 'step': step, 'game_transaction': index,
                'candidates': candidates}
    return analysis, branches


def _json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise CounterfactualError(f'duplicate JSON key: {key}')
            obj[key] = value
        return obj
    def number(value):
        if len(value.lstrip('-')) > 10:
            raise CounterfactualError('oversized JSON integer')
        return int(value)
    return json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs,
                      parse_int=number, parse_float=lambda _: (_ for _ in ()).throw(CounterfactualError('floating JSON number')),
                      parse_constant=lambda _: (_ for _ in ()).throw(CounterfactualError('nonfinite JSON number')))


def analyze(result, catalog, case, step, strategies, output):
    if output.exists():
        raise CounterfactualError('output directory must be new')
    names = strategies.split(',')
    data, branches = compute(result, catalog, case, step, names)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'branches').mkdir()
    for item in data['candidates']:
        if item['replay_path'] is not None:
            path = output / item['replay_path']
            save(path, branches[item['strategy_id']])
            item['replay_sha256'] = _sha(path.read_bytes())
    arena.atomic_json(output / 'analysis.json', data)
    verify(output, catalog)
    return data


def verify(directory, catalog_path):
    directory = Path(directory)
    raw = _read(directory / 'analysis.json')
    data = _json(raw)
    keys = {'schema_version', 'result_path', 'result_sha256', 'catalog_path', 'catalog_sha256',
            'case', 'step', 'game_transaction', 'candidates'}
    if type(data) is not dict or set(data) != keys or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise CounterfactualError('analysis schema/version invalid')
    if type(data['step']) is not int or type(data['game_transaction']) is not int or type(data['candidates']) is not list:
        raise CounterfactualError('analysis step/transaction/candidates invalid')
    if not isinstance(data['result_path'], str) or not isinstance(data['catalog_path'], str):
        raise CounterfactualError('analysis source paths invalid')
    def safe(relative):
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != relative:
            raise CounterfactualError('analysis path escapes repository')
        return ROOT / path
    result_path = safe(data['result_path'])
    if data['catalog_path'] != _inside(Path(catalog_path)):
        raise CounterfactualError('explicit catalog path mismatch')
    if _sha(_read(result_path)) != data['result_sha256']:
        raise CounterfactualError('original result byte digest mismatch')
    names = []
    item_keys = {'strategy_id', 'strategy_sha256', 'request', 'response', 'replay_path',
                 'replay_sha256', 'before_score', 'after_score', 'after_phase'}
    for item in data['candidates']:
        if type(item) is not dict or set(item) != item_keys or type(item['strategy_id']) is not str:
            raise CounterfactualError('candidate schema invalid')
        names.append(item['strategy_id'])
    expected, branches = compute(result_path, catalog_path, data['case'], data['step'], names)
    if expected['catalog_sha256'] != data['catalog_sha256']:
        raise CounterfactualError('catalog digest mismatch')
    if expected['game_transaction'] != data['game_transaction']:
        raise CounterfactualError('game transaction mismatch')
    for actual, candidate in zip(data['candidates'], expected['candidates']):
        name = candidate['strategy_id']
        if candidate['replay_path'] is not None:
            path = directory / candidate['replay_path']
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise CounterfactualError(f'{name}: linked or escaped branch path')
            raw_branch = _read(path, 16 * 1024 * 1024)
            candidate['replay_sha256'] = _sha(raw_branch)
            if document(load(path)) != document(branches[name]):
                raise CounterfactualError(f'{name}: branch replay differs from LWT recomputation')
        if actual != candidate:
            difference = next((key for key in item_keys if actual[key] != candidate[key]), 'candidate')
            raise CounterfactualError(f'{name}: {difference} evidence mismatch')
    if data != expected:
        difference = next((key for key in keys if data[key] != expected[key]), 'analysis')
        raise CounterfactualError(f'{difference} evidence mismatch')
    return data


def explain(directory, catalog):
    data = verify(directory, catalog)
    print(f"case={data['case']} step={data['step']} before_tx={data['game_transaction']}")
    print('same verified observation trace; one-step branch only')
    for item in data['candidates']:
        print(f"{item['strategy_id']}: {item['response']} score={item['before_score']}->{item['after_score']} phase={item['after_phase']} replay={item['replay_path']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--analyze', type=Path)
    group.add_argument('--verify', type=Path)
    group.add_argument('--explain', type=Path)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--case')
    parser.add_argument('--step', type=int)
    parser.add_argument('--strategies')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.analyze:
            if not all((args.case, args.step, args.strategies, args.output)):
                raise CounterfactualError('analyze requires case, step, strategies and output')
            result = analyze(args.analyze, args.catalog, args.case, args.step, args.strategies, args.output)
            print(f"Analyzed {result['case']} step {result['step']}: {len(result['candidates'])} LWT strategies; evidence verified.")
        else:
            if any((args.case, args.step, args.strategies, args.output)):
                raise CounterfactualError('verify/explain accept only directory and catalog')
            if args.verify:
                data = verify(args.verify, args.catalog)
                print(f"Verified {data['case']} step {data['step']}: original game/policy and {len(data['candidates'])} one-step branches.")
            else:
                explain(args.explain, args.catalog)
        return 0
    except KeyboardInterrupt:
        print('CounterfactualError: cancelled', file=sys.stderr)
        return 130
    except (CounterfactualError, arena.ArenaError, OSError, UnicodeError, ValueError,
            RuntimeError, RecursionError, KeyError, TypeError) as error:
        print(f'CounterfactualError: {error}', file=sys.stderr)
        return 3


def supervised_main():
    """Bound the complete proof, including legacy arena verification, by a process tree."""
    if os.environ.get('LWT_S40_WORKER') == '1':
        return main()
    env = os.environ.copy()
    env['LWT_S40_WORKER'] = '1'
    options = {'cwd': ROOT, 'env': env, 'shell': False,
               'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
    if os.name == 'nt':
        options['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    else:
        options['start_new_session'] = True
    process = subprocess.Popen([sys.executable, '-m', 'app.lwt_snake.counterfactual', *sys.argv[1:]], **options)
    try:
        stdout, stderr = process.communicate(timeout=DEADLINE)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)],
                           capture_output=True, timeout=5, shell=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
        print('CounterfactualError: total deadline exceeded or cancelled; process tree reclaimed', file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 3
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(supervised_main())
