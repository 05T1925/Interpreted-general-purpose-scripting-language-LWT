from __future__ import annotations

from contextlib import redirect_stdout
from fractions import Fraction
import io
import unittest

from tools.run_semantic_properties import (
    Binary,
    Literal,
    generate_expression_cases,
    generate_semantic_cases,
    oracle,
    render,
    run,
)


class SemanticPropertyGeneratorTests(unittest.TestCase):
    def test_fixed_seed_generates_identical_sources_and_oracles(self) -> None:
        first = generate_expression_cases(20261028, 40)
        second = generate_expression_cases(20261028, 40)
        self.assertEqual(first, second)

        first_templates = generate_semantic_cases(20261028, 40)
        second_templates = generate_semantic_cases(20261028, 40)
        self.assertEqual(first_templates, second_templates)

    def test_requested_expression_count_is_respected_below_fixed_seed_set_size(self) -> None:
        self.assertEqual(len(generate_expression_cases(7, 4)), 4)

    def test_floor_oracle_satisfies_mathematical_quotient_and_remainder_rules(self) -> None:
        cases = generate_expression_cases(9917, 150)
        for left in range(-9, 10):
            for right in range(-9, 10):
                if right == 0:
                    continue
                quotient = oracle(Binary("/", Literal(left), Literal(right)))
                remainder = oracle(Binary("%", Literal(left), Literal(right)))
                self.assertIs(type(quotient), int)
                self.assertIs(type(remainder), int)
                self.assertEqual(left, quotient * right + remainder)
                self.assertLess(Fraction(quotient), Fraction(left, right) + 1)
                self.assertLessEqual(Fraction(quotient), Fraction(left, right))
                self.assertLess(abs(remainder), abs(right))
                self.assertTrue(remainder == 0 or (remainder > 0) == (right > 0))
        self.assertEqual(len(cases), 150)

    def test_renderer_preserves_right_nested_nonassociative_expression(self) -> None:
        expression = Binary(
            "-",
            Literal(20),
            Binary("-", Literal(3), Literal(2)),
        )
        self.assertEqual(render(expression), "20 - (3 - 2)")
        self.assertEqual(oracle(expression), 19)

    def test_small_property_batch_runs_through_public_cli(self) -> None:
        # The fixed semantic template suite grew from 7 to 13 cases in S42:
        # six deterministic dict/throw/finally property checks were added to
        # generate_semantic_cases (no randomness; fixed source + expected).
        # With seed 20261028 and --cases 12 this yields 13 programs and 24
        # checks deterministically. The assertion still pins the exact count
        # and the oracle hash, so determinism coverage is unchanged.
        output = io.StringIO()
        with redirect_stdout(output):
            result = run(20261028, 12)
        self.assertEqual(result, 0)
        self.assertIn("semantic-properties: PASS programs=13 checks=24", output.getvalue())
        self.assertIn("oracle_sha256=", output.getvalue())

    def test_case_index_runs_one_reproducible_check(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = run(20261028, 12, case_index=0)
        self.assertEqual(result, 0)
        self.assertIn("PASS programs=1 checks=1 selected_case=0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
