"""Strict opt-in catalog for trusted, single-file local LWT strategies.

The checks prevent accidental path selection; they do not sandbox LWT code.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from app.lwt_snake.replay import source_digest
from app.lwt_snake.protocol import GameSnapshot
from app.lwt_snake.strategy import StrategyBridge, encode_snapshot
from lwt.ast_nodes import ImportDeclaration
from lwt.lexer import scan
from lwt.parser import parse

ROOT = Path(__file__).resolve().parents[2]
TRUSTED_DIR = Path(__file__).with_name('strategies')
MAX_CATALOG_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 64 * 1024
ID_PATTERN = re.compile(r'[a-z][a-z0-9-]{0,31}\Z')
SHA_PATTERN = re.compile(r'[0-9a-f]{64}\Z')
BUILTIN_IDS = frozenset({'baseline', 'bfs'})


class CatalogError(ValueError):
    """Malformed or changed trusted strategy directory."""


@dataclass(frozen=True)
class Entry:
    id: str
    path: Path
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class Catalog:
    path: Path
    relative_path: str
    sha256: str
    entries: dict[str, Entry]

    def assert_unchanged(self) -> None:
        current = load_catalog(self.path)
        if current.sha256 != self.sha256 or current.entries != self.entries:
            raise CatalogError('catalog/source changed during match')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f'duplicate manifest field {key}')
        result[key] = value
    return result


def _reject_number(_):
    raise CatalogError('manifest number is not a bounded integer')


def _source(path: Path, expected: str) -> None:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(TRUSTED_DIR.resolve()):
        raise CatalogError('strategy source must be a regular file inside the trusted directory')
    with path.open('rb') as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise CatalogError('strategy source exceeds 64 KiB')
    try:
        actual = source_digest(raw)
        text = raw.decode('utf-8', 'strict')
    except UnicodeError as error:
        raise CatalogError('strategy source is not strict UTF-8') from error
    if actual != expected:
        raise CatalogError('strategy source digest mismatch')
    if text.startswith('\ufeff'):
        text = text[1:]
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    try:
        program = parse(scan(text, str(path)))
    except Exception as error:
        raise CatalogError(f'strategy syntax/AST failed: {error}') from error
    if any(isinstance(item, ImportDeclaration) for item in program.items):
        raise CatalogError('custom strategy import is unsupported; use one LWT source file')


def load_catalog(path: Path) -> Catalog:
    """Validate a manifest and every referenced source before any execution."""
    if path.is_symlink() or not path.is_file() or path.suffix != '.json' or path.parent.resolve() != TRUSTED_DIR.resolve():
        raise CatalogError('catalog must be a regular .json file in the trusted strategy directory')
    path = path.resolve()
    with path.open('rb') as stream:
        raw = stream.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise CatalogError('catalog exceeds 64 KiB')
    try:
        digest = source_digest(raw)
        data = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=_pairs,
                          parse_int=lambda text: int(text) if len(text.lstrip('-')) <= 10 else _reject_number(text),
                          parse_float=_reject_number, parse_constant=_reject_number)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CatalogError(f'catalog JSON/UTF-8 invalid: {error}') from error
    if type(data) is not dict or set(data) != {'schema_version', 'strategies'} or type(data['schema_version']) is not int or data['schema_version'] != 1 or type(data['strategies']) is not list or len(data['strategies']) > 8:
        raise CatalogError('catalog schema/version/entry count invalid')
    entries = {}
    for index, item in enumerate(data['strategies'], 1):
        label = f'catalog entry {index}'
        if type(item) is not dict or set(item) != {'id', 'path', 'sha256', 'protocol'}:
            raise CatalogError(f'{label}: fields invalid')
        name, filename, sha = item['id'], item['path'], item['sha256']
        if type(name) is not str or not ID_PATTERN.fullmatch(name) or name in BUILTIN_IDS or name in entries:
            raise CatalogError(f'{label}: duplicate, reserved or invalid strategy ID')
        if type(filename) is not str or filename in ('.', '..') or '..' in filename or '/' in filename or '\\' in filename or not filename.endswith('.lwt') or Path(filename).is_absolute():
            raise CatalogError(f'{label}: source path must be one local .lwt filename')
        if type(sha) is not str or not SHA_PATTERN.fullmatch(sha) or item['protocol'] != 'LWA1':
            raise CatalogError(f'{label}: source digest or protocol invalid')
        source_path = TRUSTED_DIR / filename
        try:
            _source(source_path, sha)
        except CatalogError as error:
            raise CatalogError(f'{label} ({name}): {error}') from error
        relative = source_path.relative_to(ROOT).as_posix()
        entries[name] = Entry(name, source_path, relative, sha)
    return Catalog(path, path.relative_to(ROOT).as_posix(), digest, entries)


def static_check(entry: Entry) -> None:
    """Run the public LWT static checker after AST validation."""
    try:
        result = subprocess.run([sys.executable, '-m', 'lwt', '--check', entry.relative_path],
                                cwd=ROOT, shell=False, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CatalogError(f'{entry.id}: public LWT static check could not finish: {error}') from error
    if result.returncode != 0:
        detail = result.stderr[:300].decode('utf-8', 'backslashreplace').strip()
        raise CatalogError(f'{entry.id}: public LWT static check failed: {detail}')


def _fixed_states() -> tuple[tuple[GameSnapshot, set[str | None]], ...]:
    # The allowed answers are fixture expectations, not a second game-rule engine.
    return (
        (GameSnapshot(2, 'RUNNING', 0, 'R', (6, 2), ((4, 2), (3, 2), (2, 2)), 8, 5), {'U', 'R', 'D'}),
        (GameSnapshot(2, 'RUNNING', 0, 'L', (3, 1), ((1, 0), (1, 1), (0, 1), (0, 0)), 4, 2), {'L'}),
        (GameSnapshot(2, 'RUNNING', 0, 'U', (3, 2), ((0, 0), (1, 0), (1, 1), (0, 1), (0, 2)), 4, 3), {None}),
    )


def smoke_check(entry: Entry) -> list[str]:
    """Exercise fixed LWA1 frames through real public CLI sessions."""
    static_check(entry)
    observations = []
    bridge = StrategyBridge(repository_root=ROOT, source_path=entry.path, timeout=5)
    try:
        bridge.start()
        for index, (state, allowed) in enumerate(_fixed_states(), 1):
            try:
                advice = bridge.query(state)
            except Exception as error:
                raise CatalogError(f'{entry.id}: smoke frame {index} response/timeout: {error}') from error
            if advice.direction not in allowed:
                raise CatalogError(f'{entry.id}: smoke frame {index} legal direction: expected {sorted(str(v) for v in allowed)}, actual {advice.direction}')
            observations.append(f'frame {index}: {advice.direction or "NONE"}/{advice.reason}')
    except CatalogError:
        raise
    except Exception as error:
        raise CatalogError(f'{entry.id}: smoke LWA1 startup/protocol: {error}') from error
    finally:
        try:
            bridge.close()  # EOF must exit successfully and leave no child.
        except Exception as error:
            raise CatalogError(f'{entry.id}: smoke EOF/close: {error}') from error
    invalid = (b'LWA2|000001|8|5|R|6|2|3|4,2;3,2;2,2\n' +
               encode_snapshot(_fixed_states()[0][0], 2))
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        options = {'args': [sys.executable, '-u', '-m', 'lwt', str(entry.path)],
                   'cwd': ROOT, 'stdin': subprocess.PIPE, 'stdout': out, 'stderr': err, 'shell': False}
        if os.name == 'nt':
            options['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        process = subprocess.Popen(**options)
        try:
            process.communicate(input=invalid, timeout=5)
        except subprocess.TimeoutExpired as error:
            process.kill(); process.communicate()
            raise CatalogError(f'{entry.id}: smoke malformed frame/EOF timed out') from error
        out.seek(0); err.seek(0)
        actual = out.read(512)
        if process.returncode != 0 or err.read(1) or actual != b'LWA1|ERR|000001|BAD_FRAME\nLWA1|ERR|000002|BAD_SEQUENCE\n' or out.read(1):
            raise CatalogError(f'{entry.id}: smoke malformed frames 1-2 expected BAD_FRAME/BAD_SEQUENCE; actual {actual[:160]!r}')
    observations.append('frames 4-5: BAD_FRAME/BAD_SEQUENCE; EOF clean')
    return observations
