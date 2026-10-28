"""Run deterministic, bounded semantic properties through the public LWT CLI.

This is supplementary evidence. It deliberately builds a tiny expression tree
and computes expected values from that tree; it never evaluates generated LWT
source with Python ``eval`` or ``exec``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from typing import TypeAlias


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 20261028
DEFAULT_CASES = 150
MAX_CASES = 2000
MAX_DEPTH = 4
LEAF_MAGNITUDE = 9
TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class Literal:
    value: int | bool


@dataclass(frozen=True)
class Unary:
    operator: str
    operand: "Expression"


@dataclass(frozen=True)
class Binary:
    operator: str
    left: "Expression"
    right: "Expression"


Expression: TypeAlias = Literal | Unary | Binary

PRECEDENCE = {
    "or": 1,
    "and": 2,
    "==": 3,
    "!=": 3,
    "<": 3,
    "<=": 3,
    ">": 3,
    ">=": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
    "%": 5,
    "unary": 6,
}


@dataclass(frozen=True)
class PropertyCase:
    index: int
    name: str
    source: str
    expected_stdout: bytes


def _floor_quotient(left: int, right: int) -> int:
    """Compute floor(left/right) from signs and magnitudes, not Python //."""

    if right == 0:
        raise ZeroDivisionError("property generator produced a zero divisor")
    magnitude_quotient, magnitude_remainder = divmod(abs(left), abs(right))
    same_sign = (left < 0) == (right < 0)
    if same_sign or magnitude_remainder == 0:
        return magnitude_quotient if same_sign else -magnitude_quotient
    return -(magnitude_quotient + 1)


def oracle(expression: Expression) -> int | bool:
    """Evaluate the generated node structure using explicit semantic rules."""

    if isinstance(expression, Literal):
        return expression.value
    if isinstance(expression, Unary):
        value = oracle(expression.operand)
        if expression.operator == "-" and type(value) is int:
            return -value
        if expression.operator == "not" and type(value) is bool:
            return not value
        raise AssertionError(f"invalid generated unary expression: {expression!r}")

    left = oracle(expression.left)
    right = oracle(expression.right)
    operator = expression.operator
    if operator in {"+", "-", "*", "/", "%"}:
        if type(left) is not int or type(right) is not int:
            raise AssertionError(f"invalid generated arithmetic expression: {expression!r}")
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        quotient = _floor_quotient(left, right)
        if operator == "/":
            return quotient
        return left - quotient * right
    if operator in {"<", "<=", ">", ">=", "==", "!="}:
        if type(left) is not int or type(right) is not int:
            raise AssertionError(f"invalid generated comparison: {expression!r}")
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        if operator == "==":
            return left == right
        return left != right
    if operator == "and" and type(left) is bool and type(right) is bool:
        return left and right
    if operator == "or" and type(left) is bool and type(right) is bool:
        return left or right
    raise AssertionError(f"invalid generated binary expression: {expression!r}")


def render(expression: Expression, parent_precedence: int = 0, *, right_child: bool = False) -> str:
    """Render an expression while preserving the node tree and LWT precedence."""

    if isinstance(expression, Literal):
        if type(expression.value) is bool:
            rendered = "true" if expression.value else "false"
            precedence = PRECEDENCE["unary"]
        else:
            rendered = str(expression.value)
            precedence = PRECEDENCE["unary"]
    elif isinstance(expression, Unary):
        precedence = PRECEDENCE["unary"]
        operand = render(expression.operand, precedence, right_child=True)
        rendered = f"not {operand}" if expression.operator == "not" else f"-{operand}"
    else:
        precedence = PRECEDENCE[expression.operator]
        left = render(expression.left, precedence)
        right = render(expression.right, precedence, right_child=True)
        rendered = f"{left} {expression.operator} {right}"

    needs_parentheses = precedence < parent_precedence or (
        right_child and precedence == parent_precedence
    )
    return f"({rendered})" if needs_parentheses else rendered


def _fixed_expression_cases() -> list[Expression]:
    """Keep a few high-value operator boundaries present in every seed."""

    n = Literal
    b = Binary
    u = Unary
    return [
        b("+", n(1), b("*", n(2), n(3))),
        b("*", b("+", n(1), n(2)), n(3)),
        b("-", b("-", n(20), n(3)), n(2)),
        b("-", n(20), b("-", n(3), n(2))),
        b("/", u("-", n(7)), n(3)),
        b("%", u("-", n(7)), n(3)),
        b("/", n(7), u("-", n(3))),
        b("%", n(7), u("-", n(3))),
        b("or", b("and", b("<", n(1), n(2)), b(">", n(5), n(6))), n(True)),
        b("==", b("+", n(1), n(2)), n(3)),
    ]


def _integer_expression(rng: random.Random, depth: int) -> Expression:
    if depth <= 0 or rng.random() < 0.24:
        return Literal(rng.randint(-LEAF_MAGNITUDE, LEAF_MAGNITUDE))
    choice = rng.random()
    if choice < 0.12:
        return Unary("-", _integer_expression(rng, depth - 1))
    operator = rng.choice(("+", "-", "*", "/", "%"))
    left = _integer_expression(rng, depth - 1)
    right = _integer_expression(rng, depth - 1)
    if operator in {"/", "%"} and oracle(right) == 0:
        right = Literal(rng.choice((-LEAF_MAGNITUDE, -3, -1, 1, 3, LEAF_MAGNITUDE)))
    return Binary(operator, left, right)


def _boolean_expression(rng: random.Random, depth: int) -> Expression:
    if depth <= 0 or rng.random() < 0.30:
        operator = rng.choice(("<", "<=", ">", ">=", "==", "!="))
        return Binary(
            operator,
            _integer_expression(rng, 2),
            _integer_expression(rng, 2),
        )
    choice = rng.random()
    if choice < 0.16:
        return Unary("not", _boolean_expression(rng, depth - 1))
    operator = rng.choice(("and", "or"))
    return Binary(
        operator,
        _boolean_expression(rng, depth - 1),
        _boolean_expression(rng, depth - 1),
    )


def generate_expression_cases(seed: int, count: int) -> list[PropertyCase]:
    rng = random.Random(seed)
    expressions = _fixed_expression_cases()[:count]
    while len(expressions) < count:
        if rng.random() < 0.27:
            expressions.append(_boolean_expression(rng, MAX_DEPTH - 1))
        else:
            expressions.append(_integer_expression(rng, MAX_DEPTH))

    cases: list[PropertyCase] = []
    for index, expression in enumerate(expressions):
        value = oracle(expression)
        display = ("true" if value else "false") if type(value) is bool else str(value)
        cases.append(
            PropertyCase(
                index=index,
                name=f"expression-{index:04d}",
                source=f"emit {render(expression)};\n",
                expected_stdout=(display + "\n").encode("utf-8"),
            )
        )
    return cases


def generate_semantic_cases(seed: int, start_index: int) -> list[PropertyCase]:
    rng = random.Random(seed ^ 0x5A17_2026)
    values = [rng.randint(-20, 20) for _ in range(3)]
    while values[1] == 99:
        values[1] = rng.randint(-20, 20)
    text_alphabet = ("a", "界", "🙂", "e", "\u0301")
    text = "🙂e\u0301界" + "".join(rng.choice(text_alphabet) for _ in range(4))
    template_specs = [
        (
            "short-circuit-side-effects",
            'emit false and fail("and side must be skipped");\n'
            'emit true or fail("or side must be skipped");\n',
            b"false\ntrue\n",
        ),
        (
            "array-and-record-identity",
            "record Box {value};\n"
            "let a = [1]; let alias = a; let copy = [1];\n"
            "let r = Box{value: 1}; let r_alias = r; let r_copy = Box{value: 1};\n"
            "emit a == alias; emit a == copy; emit r == r_alias; emit r == r_copy;\n",
            b"true\nfalse\ntrue\nfalse\n",
        ),
        (
            "each-entry-snapshot",
            f"let items = [{values[0]}, {values[1]}, {values[2]}];\n"
            "let visited = [];\n"
            "each (item in items) { push(visited, item); items[1] = 99; }\n"
            "emit visited; emit items;\n",
            (
                f"[{values[0]}, {values[1]}, {values[2]}]\n"
                f"[{values[0]}, 99, {values[2]}]\n"
            ).encode("utf-8"),
        ),
        (
            "left-to-right-call-arguments",
            "let n = 0; let first = 0; let second = 0;\n"
            "fn mark(value) {\n"
            "  when (n == 0) { first = value; } otherwise { second = value; }\n"
            "  n = n + 1; return value;\n"
            "}\n"
            "fn pack(a, b) { return [a, b]; }\n"
            "emit pack(mark(11), mark(22)); emit [first, second];\n",
            b"[11, 22]\n[11, 22]\n",
        ),
        (
            "unicode-codepoint-length",
            f'emit len("{text}");\n',
            f"{sum(1 for _ in text)}\n".encode("ascii"),
        ),
        (
            "text-builtin-boundaries",
            r'emit split("a||b|", "|"); emit trim("\t x "); emit to_int("-00012");' + "\n",
            b'["a", "", "b", ""]\nx\n-12\n',
        ),
    ]
    return [
        PropertyCase(start_index + offset, name, source, expected)
        for offset, (name, source, expected) in enumerate(template_specs)
    ]


def _digest(cases: list[PropertyCase]) -> str:
    digest = hashlib.sha256()
    for case in cases:
        digest.update(str(case.index).encode("ascii"))
        digest.update(b"\0")
        digest.update(case.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(case.source.encode("utf-8"))
        digest.update(b"\0")
        digest.update(case.expected_stdout)
        digest.update(b"\0")
    return digest.hexdigest()


def _program_for_cases(cases: list[PropertyCase]) -> tuple[str, bytes]:
    return "".join(case.source for case in cases), b"".join(
        case.expected_stdout for case in cases
    )


def _run_lwt(source: str, expected_stdout: bytes) -> tuple[int | None, bytes, bytes, str | None]:
    try:
        with tempfile.TemporaryDirectory(prefix="lwt-semantic-property-") as temporary:
            source_path = Path(temporary) / "property_case.lwt"
            source_path.write_text(source, encoding="utf-8", newline="")
            command = [sys.executable, "-m", "lwt", str(source_path)]
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "utf-8"
            try:
                completed = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    input=b"",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=TIMEOUT_SECONDS,
                    check=False,
                    shell=False,
                    env=environment,
                )
            except subprocess.TimeoutExpired as error:
                stdout = error.stdout or b""
                stderr = error.stderr or b""
                return None, stdout, stderr, f"timeout after {TIMEOUT_SECONDS:g}s"
            except OSError as error:
                return None, b"", b"", f"process start failed: {error}"
            return completed.returncode, completed.stdout, completed.stderr, None
    except OSError as error:
        return None, b"", b"", f"temporary source setup failed: {error}"


def _first_mismatch(expected: bytes, actual: bytes) -> int:
    expected_lines = expected.split(b"\n")
    actual_lines = actual.split(b"\n")
    for index, (expected_line, actual_line) in enumerate(zip(expected_lines, actual_lines)):
        if expected_line != actual_line:
            return index
    return min(len(expected_lines), len(actual_lines)) - 1


def _report_failure(
    *,
    seed: int,
    count: int,
    case: PropertyCase,
    source: str,
    expected: bytes,
    return_code: int | None,
    actual_stdout: bytes,
    actual_stderr: bytes,
    launch_error: str | None,
) -> None:
    print("FAIL: deterministic LWT semantic property mismatch", file=sys.stderr)
    print(f"seed={seed} case_index={case.index} case={case.name}", file=sys.stderr)
    print(f"reproduce: python tools/run_semantic_properties.py --seed {seed} --cases {count} --case-index {case.index}", file=sys.stderr)
    if launch_error:
        print(f"process_error={launch_error}", file=sys.stderr)
    print("generated_source:", file=sys.stderr)
    print(source, file=sys.stderr, end="" if source.endswith("\n") else "\n")
    print(f"expected_exit_code=0 expected_stdout={expected!r} expected_stderr=b''", file=sys.stderr)
    print(f"actual_exit_code={return_code!r} actual_stdout={actual_stdout!r} actual_stderr={actual_stderr!r}", file=sys.stderr)


def run(seed: int, count: int, case_index: int | None = None) -> int:
    expression_cases = generate_expression_cases(seed, count)
    semantic_cases = generate_semantic_cases(seed, count)
    all_cases = expression_cases + semantic_cases

    if case_index is not None:
        if not 0 <= case_index < len(all_cases):
            raise ValueError(f"case index must be in 0..{len(all_cases) - 1}")
        case = all_cases[case_index]
        source, expected = case.source, case.expected_stdout
        programs = [(case, source, expected)]
    else:
        expression_source, expression_expected = _program_for_cases(expression_cases)
        programs = [(expression_cases[0], expression_source, expression_expected)]
        programs.extend((case, case.source, case.expected_stdout) for case in semantic_cases)

    run_scope = (
        f"programs={len(programs)} max_depth={MAX_DEPTH}"
        if case_index is None
        else f"programs=1 selected_case={case_index} suite_checks={len(all_cases)}"
    )
    print(
        "semantic-properties: "
        f"seed={seed} expression_checks={count} semantic_checks={len(semantic_cases)} "
        f"checks={len(all_cases)} {run_scope} "
        f"leaf_range=[-{LEAF_MAGNITUDE},{LEAF_MAGNITUDE}] timeout={TIMEOUT_SECONDS:g}s"
    )
    print(f"oracle_sha256={_digest(all_cases)}")

    failures = 0
    for batch_case, source, expected in programs:
        return_code, actual_stdout, actual_stderr, launch_error = _run_lwt(source, expected)
        if return_code == 0 and actual_stdout == expected and actual_stderr == b"":
            continue
        failures += 1
        selected = batch_case
        if case_index is None and batch_case.name.startswith("expression-"):
            mismatch_index = _first_mismatch(expected, actual_stdout)
            selected = expression_cases[max(0, min(mismatch_index, len(expression_cases) - 1))]
        _report_failure(
            seed=seed,
            count=count,
            case=selected,
            source=source,
            expected=expected,
            return_code=return_code,
            actual_stdout=actual_stdout,
            actual_stderr=actual_stderr,
            launch_error=launch_error,
        )
    if failures:
        print(f"semantic-properties: failed_programs={failures}/{len(programs)}", file=sys.stderr)
        return 1

    executed_checks = len(all_cases) if case_index is None else 1
    print(
        f"semantic-properties: PASS programs={len(programs)} "
        f"checks={executed_checks}"
        + (f" selected_case={case_index}" if case_index is not None else "")
    )
    return 0


def _bounded_int(value: str, *, minimum: int, maximum: int, label: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{label} must be a decimal integer") from error
    if not minimum <= parsed <= maximum:
        raise argparse.ArgumentTypeError(f"{label} must be in {minimum}..{maximum}")
    return parsed


def _seed(value: str) -> int:
    return _bounded_int(value, minimum=0, maximum=2**32 - 1, label="seed")


def _case_count(value: str) -> int:
    return _bounded_int(value, minimum=1, maximum=MAX_CASES, label="cases")


def _case_index(value: str) -> int:
    return _bounded_int(value, minimum=0, maximum=MAX_CASES + 5, label="case index")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=_seed, default=DEFAULT_SEED)
    parser.add_argument("--cases", type=_case_count, default=DEFAULT_CASES)
    parser.add_argument(
        "--case-index",
        type=_case_index,
        help="run one expression or semantic template by its zero-based index",
    )
    arguments = parser.parse_args(argv)
    try:
        return run(arguments.seed, arguments.cases, arguments.case_index)
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
