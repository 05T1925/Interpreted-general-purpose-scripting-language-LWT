"""Static loader and linker for LWT function-library modules."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PureWindowsPath

from .ast_nodes import ImportDeclaration, Program
from .errors import LwtError
from .lexer import scan
from .parser import parse


@dataclass(slots=True, eq=False)
class ModuleUnit:
    """One canonical source file and its importer-local aliases."""

    canonical_path: Path
    display_path: str | None
    program: Program
    imports: dict[str, ModuleUnit] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModuleGraph:
    entry: ModuleUnit
    modules: tuple[ModuleUnit, ...]


def load_module_graph(entry_path: str) -> ModuleGraph:
    """Read, scan, parse, and link all static imports before execution."""

    try:
        entry_canonical = Path(entry_path).resolve()
        entry_text = _decode_file(entry_canonical, entry=True)
    except LwtError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise LwtError("FileError", "cannot read source file", 4) from None

    entry = ModuleUnit(entry_canonical, None, _parse(entry_text, None, module_mode=False))
    by_path: dict[Path, ModuleUnit] = {entry_canonical: entry}
    ordered: list[ModuleUnit] = [entry]
    visiting: list[ModuleUnit] = [entry]

    def visit(unit: ModuleUnit) -> None:
        aliases: set[str] = set()
        for item in unit.program.items:
            if not isinstance(item, ImportDeclaration):
                continue
            alias_name = item.alias.name
            if alias_name in aliases:
                raise LwtError(
                    "SyntaxError",
                    f"duplicate import alias {alias_name!r}",
                    2,
                    item.alias.location,
                )
            aliases.add(alias_name)
            target = _resolve_import(unit, item)
            if target in [active.canonical_path for active in visiting]:
                start = next(
                    index
                    for index, active in enumerate(visiting)
                    if active.canonical_path == target
                )
                cycle_labels = [_label(node) for node in visiting[start:]]
                cycle_labels.append(_display_path(target, entry_canonical.parent))
                rendered = " -> ".join(cycle_labels)
                raise LwtError(
                    "ImportError",
                    f"cyclic module import: {rendered}",
                    4,
                    item.location,
                )

            imported = by_path.get(target)
            if imported is None:
                display = _display_path(target, entry_canonical.parent)
                try:
                    source = _decode_file(target, entry=False)
                except LwtError as error:
                    raise LwtError(
                        "ImportError",
                        f"cannot load module {item.path!r}: {error.message}",
                        4,
                        item.location,
                    ) from None
                program = _parse(source, display, module_mode=True)
                imported = ModuleUnit(target, display, program)
                by_path[target] = imported
                ordered.append(imported)
                unit.imports[alias_name] = imported
                visiting.append(imported)
                visit(imported)
                visiting.pop()
            else:
                unit.imports[alias_name] = imported

    try:
        visit(entry)
    except RecursionError:
        raise LwtError("ImportError", "module import graph is too deeply nested", 4) from None
    return ModuleGraph(entry, tuple(ordered))


def _resolve_import(unit: ModuleUnit, declaration: ImportDeclaration) -> Path:
    raw_path = declaration.path
    windows_path = PureWindowsPath(raw_path)
    if (
        Path(raw_path).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
    ):
        raise LwtError(
            "ImportError", "module path must be relative", 4, declaration.location
        )
    base = unit.canonical_path.parent
    try:
        target = (base / raw_path).resolve()
    except (OSError, ValueError, RuntimeError):
        raise LwtError(
            "ImportError", f"invalid module path {raw_path!r}", 4, declaration.location
        ) from None
    try:
        is_file = target.is_file()
    except (OSError, ValueError):
        is_file = False
    if not is_file:
        raise LwtError(
            "ImportError",
            f"module path {raw_path!r} is not a readable file",
            4,
            declaration.location,
        )
    return target


def _decode_file(path: Path, *, entry: bool) -> str:
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        message = "cannot read source file" if entry else "cannot read module file"
        raise LwtError("FileError", message, 4) from None
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        message = "source file is not valid UTF-8" if entry else "module file is not valid UTF-8"
        raise LwtError("FileError", message, 4) from None


def _parse(source: str, display_path: str | None, *, module_mode: bool) -> Program:
    return parse(scan(source, display_path), module_mode=module_mode)


def _display_path(path: Path, entry_dir: Path) -> str:
    try:
        return Path(os.path.relpath(path, entry_dir)).as_posix()
    except ValueError:
        return path.as_posix()


def _label(unit: ModuleUnit) -> str:
    return unit.display_path or unit.canonical_path.name
