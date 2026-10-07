"""Count substantive LWT source lines without rewriting the input file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def is_effective_line(line: str) -> bool:
    """Count code/declaration lines, excluding blanks, comments, and bare braces."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    return any(character.isalnum() or character in '_"' for character in stripped)


def count_effective_lines(source: str) -> int:
    return sum(1 for line in source.splitlines() if is_effective_line(line))


def main() -> int:
    parser = argparse.ArgumentParser(description="Count effective LWT source lines.")
    parser.add_argument("source", type=Path, help="path to an UTF-8 LWT source file")
    args = parser.parse_args()
    try:
        source = args.source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"count_lwt_lines: {error}", file=sys.stderr)
        return 2
    count = count_effective_lines(source)
    print(f"Effective LWT lines: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
