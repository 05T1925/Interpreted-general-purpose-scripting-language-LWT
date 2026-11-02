"""Find the first bounded LWT strategy direction disagreement on one verified trace."""
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
import tempfile
import time

from app.lwt_snake import arena, counterfactual
from app.lwt_snake.catalog import load_catalog
from app.lwt_snake.replay import ROOT, load, reconstruct
from app.lwt_snake.strategy import StrategyBridge, encode_snapshot

MAX_WITNESS = 1024 * 1024
DEADLINE = 120.0
ID = re.compile(r'[a-z][a-z0-9-]{0,31}\Z')


class WitnessError(ValueError):
    pass


class WitnessUsageError(WitnessError):
    """Invalid command configuration or output destination."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _source(result, catalog, reference, challengers, budget):
    result, catalog = Path(result), Path(catalog)
    result_rel = counterfactual._inside(result)
    catalog_rel = counterfactual._inside(catalog)
    original = counterfactual._read(result)
    trusted = load_catalog(catalog)
    data = arena.verify(result, catalog_path=catalog)
    if data['schema_version'] != 3:
        raise WitnessError('S41 requires a fully verified S39 v3 result')
    if (type(reference) is not str or not ID.fullmatch(reference) or reference not in data['strategies']
            or type(challengers) is not list or not 1 <= len(challengers) <= 2
            or len(set(challengers)) != len(challengers)
            or any(type(name) is not str or not ID.fullmatch(name) or name == reference
                   or name not in data['strategies'] for name in challengers)):
        raise WitnessUsageError('reference/challengers must be distinct bound strategy IDs')
    if type(budget) is not int or not 1 <= budget <= 32:
        raise WitnessUsageError('max-observations must be 1..32')
    return result, catalog, data, trusted, result_rel, catalog_rel, _sha(original)


def search(result, catalog, reference, challengers, budget):
    result, catalog, data, trusted, result_rel, catalog_rel, result_sha = _source(
        result, catalog, reference, challengers, budget)
    challengers = sorted(challengers)
    names = [reference, *challengers]
    paths = dict(arena.STRATEGIES)
    paths.update({name: entry.path for name, entry in trusted.entries.items()})
    scanned = 0
    match = None
    eligible = 0
    for row in sorted((row for row in data['cases'] if row['strategy_id'] == reference),
                      key=lambda row: row['seed']):
        if row['stop_reason'] == 'failed' or row['game_verified'] is not True or row['policy_verified'] is not True:
            continue
        eligible += 1
        decisions = arena._read_json(result.parent / row['decision_path'], arena.MAX_DECISIONS)['decisions']
        states = reconstruct(load(result.parent / row['replay_path']), total_timeout=60).states
        policies = {name: StrategyBridge(repository_root=ROOT, source_path=paths[name]) for name in names}
        try:
            for policy in policies.values():
                policy.start()
            for step, decision in enumerate(decisions, 1):
                if scanned >= budget:
                    break
                state = states[decision['game_transaction'] - 1]
                if encode_snapshot(state, step)[:-1].decode('ascii') != decision['request']:
                    raise WitnessError(f"{reference}/{row['seed']} step {step}: observation disagrees with LWT replay")
                answers = {}
                for name, policy in policies.items():
                    advice = policy.query(state)
                    answers[name] = (advice.direction, arena._advice_frame(advice, step))
                trusted.assert_unchanged()
                for name in names:
                    if arena.digest_file(paths[name]) != data['strategies'][name]['sha256']:
                        raise WitnessError(f'{name}: source changed during witness search')
                if answers[reference][1] != decision['response']:
                    raise WitnessError(f"{reference}/{row['seed']} step {step}: reference response mismatch")
                scanned += 1
                for challenger in challengers:
                    if answers[challenger][0] != answers[reference][0]:
                        match = (f"{reference}/{row['seed']}", step, challenger,
                                 answers[reference][1], answers[challenger][1])
                        break
                if match:
                    break
        finally:
            for policy in policies.values():
                policy.close()
        if match or scanned >= budget:
            break
    if eligible == 0:
        raise WitnessError('no completed double-verified reference match to scan')
    found = match is not None
    return {'schema_version': 1, 'result_path': result_rel, 'result_sha256': result_sha,
            'catalog_path': catalog_rel, 'catalog_sha256': trusted.sha256,
            'reference': reference, 'challengers': challengers, 'max_observations': budget,
            'scanned': scanned, 'found': found,
            'case': match[0] if found else None, 'step': match[1] if found else None,
            'challenger': match[2] if found else None,
            'reference_response': match[3] if found else None,
            'challenger_response': match[4] if found else None,
            'analysis_path': 'analysis/analysis.json' if found else None,
            'analysis_sha256': None}, result, catalog


def feedback(data):
    common = {'schema_version': 1, 'result_sha256': data['result_sha256'],
              'catalog_sha256': data['catalog_sha256'], 'reference': data['reference'],
              'challengers': data['challengers'], 'scanned': data['scanned'],
              'max_observations': data['max_observations'], 'found': data['found'],
              'meaning': 'same verified observation trace; prior observations retained; one-step evidence only'}
    common.update(case=data['case'], step=data['step'], challenger=data['challenger'],
                  reference_response=data['reference_response'], challenger_response=data['challenger_response'],
                  question=('Which LWT decision condition explains this direction difference on the recorded observation prefix?'
                            if data['found'] else 'No direction difference in this bounded scan; inspect the budget or source policy if needed.'))
    return common


def human(data):
    header = '# LWT strategy direction witness\n\n'
    limits = f"Search: seed ascending, step ascending, challenger ID ascending; scanned {data['scanned']}/{data['max_observations']} observations.\n"
    if not data['found']:
        return header + limits + 'No direction disagreement within this bounded scan. This does not prove strategy equivalence.\n'
    return (header + limits + f"Found {data['case']} step {data['step']}; challenger {data['challenger']}.\n"
            + f"Reference: `{data['reference_response']}`\nChallenger: `{data['challenger_response']}`\n"
            + 'Both responses use the same verified observation prefix; consult analysis/analysis.json for the reverified one-tick branches. No whole-game superiority is inferred.\n')


def _atomic_text(path, value):
    raw = value.encode('utf-8')
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.witness-')
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def create(result, catalog, reference, challengers, budget, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise WitnessUsageError('output directory must be new')
    data, result, catalog = search(result, catalog, reference, challengers, budget)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise WitnessUsageError('cannot create output directory') from error
    if data['found']:
        counterfactual.analyze(result, catalog, data['case'], data['step'],
                               f"{reference},{data['challenger']}", output / 'analysis')
        data['analysis_sha256'] = _sha((output / data['analysis_path']).read_bytes())
    try:
        arena.atomic_json(output / 'witness.json', data)
        arena.atomic_json(output / 'agent-feedback.json', feedback(data))
        _atomic_text(output / 'report.md', human(data))
    except OSError as error:
        raise WitnessUsageError('cannot write output files') from error
    verify(output, catalog)
    return data


def verify(directory, catalog):
    directory = Path(directory)
    raw = counterfactual._read(directory / 'witness.json', MAX_WITNESS)
    data = counterfactual._json(raw)
    keys = {'schema_version', 'result_path', 'result_sha256', 'catalog_path', 'catalog_sha256',
            'reference', 'challengers', 'max_observations', 'scanned', 'found', 'case', 'step',
            'challenger', 'reference_response', 'challenger_response', 'analysis_path', 'analysis_sha256'}
    if type(data) is not dict or set(data) != keys or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise WitnessError('witness schema/version invalid')
    if type(data['result_path']) is not str or type(data['catalog_path']) is not str or type(data['found']) is not bool:
        raise WitnessError('witness source path/found type invalid')
    path = Path(data['result_path'])
    if path.is_absolute() or '..' in path.parts or path.as_posix() != data['result_path']:
        raise WitnessError('witness result path escapes repository')
    if data['catalog_path'] != counterfactual._inside(Path(catalog)):
        raise WitnessError('explicit catalog path mismatch')
    expected, _, _ = search(ROOT / path, catalog, data['reference'], data['challengers'], data['max_observations'])
    if expected['found']:
        analysis = directory / 'analysis'
        counterfactual.verify(analysis, catalog)
        expected['analysis_sha256'] = _sha(counterfactual._read(analysis / 'analysis.json'))
    elif (directory / 'analysis').exists() or (directory / 'analysis').is_symlink():
        raise WitnessError('no-witness result must not contain branch analysis')
    if data != expected:
        difference = next((key for key in keys if data[key] != expected[key]), 'witness')
        raise WitnessError(f'{difference} witness evidence mismatch')
    if counterfactual._json(counterfactual._read(directory / 'agent-feedback.json')) != feedback(expected):
        raise WitnessError('agent feedback evidence mismatch')
    if counterfactual._read(directory / 'report.md') != human(expected).encode('utf-8'):
        raise WitnessError('human report evidence mismatch')
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--reference')
    parser.add_argument('--challengers')
    parser.add_argument('--max-observations', type=int, default=32)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            if any((args.result, args.reference, args.challengers, args.output)):
                raise WitnessUsageError('verify accepts only directory and explicit catalog')
            data = verify(args.verify, args.catalog)
        else:
            if not all((args.result, args.reference, args.challengers, args.output)):
                raise WitnessUsageError('search requires result, reference, challengers and new output')
            data = create(args.result, args.catalog, args.reference,
                          args.challengers.split(','), args.max_observations, args.output)
        print(f"found={str(data['found']).lower()} scanned={data['scanned']}/{data['max_observations']} case={data['case']} step={data['step']} challenger={data['challenger']}")
        return 0
    except KeyboardInterrupt:
        print('WitnessError: cancelled', file=sys.stderr)
        return 130
    except WitnessUsageError as error:
        print(f'WitnessError: {error}', file=sys.stderr)
        return 2
    except (WitnessError, arena.ArenaError, ValueError, OSError, UnicodeError, RuntimeError,
            RecursionError, KeyError, TypeError) as error:
        print(f'WitnessError: {error}', file=sys.stderr)
        return 3


def supervised_main():
    if os.environ.get('LWT_S41_WORKER') == '1':
        return main()
    env = os.environ.copy()
    env['LWT_S41_WORKER'] = '1'
    options = {'cwd': ROOT, 'env': env, 'shell': False,
               'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
    if os.name == 'nt':
        options['creationflags'] = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    else:
        options['start_new_session'] = True
    process = subprocess.Popen([sys.executable, '-m', 'app.lwt_snake.witness', *sys.argv[1:]], **options)
    try:
        stdout, stderr = process.communicate(timeout=DEADLINE)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)],
                           capture_output=True, timeout=5, shell=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)
        print('WitnessError: total deadline or cancellation; process tree reclaimed', file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 3
    sys.stdout.buffer.write(stdout)
    sys.stderr.buffer.write(stderr)
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(supervised_main())
