"""Check the black-box test inventory and references in its coverage matrix."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_RELATIVE_PATH = Path("docs/test-matrix.md")
CASE_ROOT_RELATIVE_PATH = Path("tests/cases")
MATRIX_CASE_PREFIX = "../tests/cases/"
MARKDOWN_LINK_RE = re.compile(r"\]\((<[^>]+>|[^)\s]+)\)")

# tools/run_tests.py already owns and tests the strict case pairing, metadata,
# identifier syntax, duplicate-ID, and source-readability rules. Reuse it here
# so the durable project check has one implementation of those rules.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from tools.run_tests import ConfigurationError, discover_cases  # noqa: E402


@dataclass(frozen=True)
class IntegrityResult:
    case_count: int
    matrix_link_count: int
    referenced_case_count: int
    errors: tuple[str, ...]


def inspect_project(repo_root: Path = REPO_ROOT) -> IntegrityResult:
    """Validate case inventory and the test-matrix links that point into it."""

    root = repo_root.resolve()
    case_root = root / CASE_ROOT_RELATIVE_PATH
    matrix_path = root / MATRIX_RELATIVE_PATH
    try:
        cases = discover_cases(case_root)
    except ConfigurationError as error:
        return IntegrityResult(0, 0, 0, (f"test inventory: {error}",))

    known_files: dict[Path, str] = {}
    for case in cases:
        known_files[case.source.resolve()] = case.case_id
        known_files[case.source.with_suffix(".json").resolve()] = case.case_id

    try:
        matrix_text = matrix_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return IntegrityResult(
            len(cases),
            0,
            0,
            (f"{MATRIX_RELATIVE_PATH.as_posix()}: cannot read matrix: {error}",),
        )

    errors: list[str] = []
    matrix_link_count = 0
    referenced_ids: set[str] = set()
    for line_number, line in enumerate(matrix_text.splitlines(), start=1):
        for match in MARKDOWN_LINK_RE.finditer(line):
            destination = match.group(1)
            if destination.startswith("<") and destination.endswith(">"):
                destination = destination[1:-1]
            path_part = unquote(urlsplit(destination).path)
            if not path_part.startswith(MATRIX_CASE_PREFIX):
                continue

            matrix_link_count += 1
            relative_path = Path(path_part.removeprefix(MATRIX_CASE_PREFIX))
            candidate = (matrix_path.parent / MATRIX_CASE_PREFIX / relative_path).resolve()
            location = f"{MATRIX_RELATIVE_PATH.as_posix()}:{line_number}"
            try:
                candidate.relative_to(case_root.resolve())
            except ValueError:
                errors.append(
                    f"{location}: test-case link escapes "
                    f"{CASE_ROOT_RELATIVE_PATH.as_posix()}: {destination}"
                )
                continue
            case_id = known_files.get(candidate)
            if case_id is None:
                errors.append(f"{location}: test-case link does not name a discovered case file: {destination}")
                continue
            referenced_ids.add(case_id)

    if not matrix_link_count:
        errors.append(
            f"{MATRIX_RELATIVE_PATH.as_posix()}: no links to "
            f"{CASE_ROOT_RELATIVE_PATH.as_posix()} were found"
        )
    return IntegrityResult(len(cases), matrix_link_count, len(referenced_ids), tuple(errors))


def main(repo_root: Path = REPO_ROOT) -> int:
    result = inspect_project(repo_root)
    if result.errors:
        print("Project integrity: FAILED", file=sys.stderr)
        for error in result.errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(
        "Project integrity: OK; "
        f"cases={result.case_count}; matrix_links={result.matrix_link_count}; "
        f"referenced_cases={result.referenced_case_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
