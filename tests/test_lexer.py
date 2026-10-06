from __future__ import annotations

import unittest

from lwt.errors import LwtError
from lwt.lexer import TokenKind, scan


class LexerTests(unittest.TestCase):
    def test_empty_whitespace_and_comment_inputs_have_only_eof(self) -> None:
        for source in ("", " \t\f\v\n", "# comment", "# @ \ufeff"):
            with self.subTest(source=source):
                tokens = scan(source)
                self.assertEqual(len(tokens), 1)
                self.assertEqual(tokens[0].kind, TokenKind.EOF)
                self.assertEqual(tokens[0].line, source.count("\n") + 1)
                self.assertEqual(
                    tokens[0].column, len(source.rsplit("\n", 1)[-1]) + 1
                )

    def test_comment_without_final_newline_and_code_after_comment(self) -> None:
        tokens = scan("# @\nname # @\nnext # no final newline")
        self.assertEqual(
            [(token.kind, token.lexeme, token.line, token.column) for token in tokens],
            [
                (TokenKind.IDENT, "name", 2, 1),
                (TokenKind.IDENT, "next", 3, 1),
                (TokenKind.EOF, "", 3, 24),
            ],
        )

    def test_all_keywords_and_builtin_names(self) -> None:
        keywords = (
            "record fn let when otherwise while each in return emit true false "
            "null and or not break continue"
        ).split()
        builtin_names = "input args read_text len split trim to_int str fail push".split()
        tokens = scan(" ".join(keywords + builtin_names))[:-1]
        self.assertEqual([token.kind.value for token in tokens], keywords + ["IDENT"] * 10)
        self.assertEqual(tokens[keywords.index("true")].literal, True)
        self.assertEqual(tokens[keywords.index("false")].literal, False)

    def test_keywords_are_recognized_only_as_complete_ascii_identifiers(self) -> None:
        tokens = scan("trueValue andrew while_ _true false2")
        self.assertEqual([token.kind for token in tokens[:-1]], [TokenKind.IDENT] * 5)
        self.assertEqual(
            [token.lexeme for token in tokens[:-1]],
            ["trueValue", "andrew", "while_", "_true", "false2"],
        )

    def test_ascii_identifier_boundaries_and_non_ascii_rejection(self) -> None:
        tokens = scan("_ A a0 Z9 name_2")
        self.assertEqual([token.lexeme for token in tokens[:-1]], ["_", "A", "a0", "Z9", "name_2"])
        with self.assertRaises(LwtError) as caught:
            scan("变量")
        self.assertEqual(caught.exception.category, "LexError")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 1))

    def test_non_ascii_decimal_digit_is_not_an_integer_token(self) -> None:
        with self.assertRaises(LwtError) as caught:
            scan("١")
        self.assertEqual(caught.exception.category, "LexError")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 1))

    def test_integer_lexemes_are_unconverted_and_unbounded_in_s2(self) -> None:
        long_decimal = "9" * 6000
        tokens = scan("00012 " + long_decimal)
        self.assertEqual(tokens[0].kind, TokenKind.INT)
        self.assertEqual(tokens[0].lexeme, "00012")
        self.assertIsNone(tokens[0].literal)
        self.assertEqual(tokens[1].kind, TokenKind.INT)
        self.assertEqual(tokens[1].lexeme, long_decimal)
        self.assertIsNone(tokens[1].literal)

    def test_negative_sign_is_separate_from_integer(self) -> None:
        tokens = scan("-12")
        self.assertEqual(
            [(token.kind, token.lexeme) for token in tokens],
            [(TokenKind.MINUS, "-"), (TokenKind.INT, "12"), (TokenKind.EOF, "")],
        )

    def test_all_operators_and_delimiters(self) -> None:
        source = "+ - * / % == != < <= > >= = ( ) { } [ ] , : ; ."
        tokens = scan(source)[:-1]
        self.assertEqual(
            [token.kind for token in tokens],
            [
                TokenKind.PLUS,
                TokenKind.MINUS,
                TokenKind.STAR,
                TokenKind.SLASH,
                TokenKind.PERCENT,
                TokenKind.EQUAL_EQUAL,
                TokenKind.BANG_EQUAL,
                TokenKind.LESS,
                TokenKind.LESS_EQUAL,
                TokenKind.GREATER,
                TokenKind.GREATER_EQUAL,
                TokenKind.EQUAL,
                TokenKind.LEFT_PAREN,
                TokenKind.RIGHT_PAREN,
                TokenKind.LEFT_BRACE,
                TokenKind.RIGHT_BRACE,
                TokenKind.LEFT_BRACKET,
                TokenKind.RIGHT_BRACKET,
                TokenKind.COMMA,
                TokenKind.COLON,
                TokenKind.SEMICOLON,
                TokenKind.DOT,
            ],
        )
        self.assertEqual([token.lexeme for token in tokens], source.split())

    def test_longest_match_for_double_operators(self) -> None:
        tokens = scan("=== !== <<= >>=")[:-1]
        self.assertEqual(
            [(token.kind, token.lexeme) for token in tokens],
            [
                (TokenKind.EQUAL_EQUAL, "=="),
                (TokenKind.EQUAL, "="),
                (TokenKind.BANG_EQUAL, "!="),
                (TokenKind.EQUAL, "="),
                (TokenKind.LESS, "<"),
                (TokenKind.LESS_EQUAL, "<="),
                (TokenKind.GREATER, ">"),
                (TokenKind.GREATER_EQUAL, ">="),
            ],
        )

    def test_single_bang_is_a_lexical_error(self) -> None:
        with self.assertRaises(LwtError) as caught:
            scan("!")
        self.assertEqual(caught.exception.category, "LexError")
        self.assertEqual(caught.exception.exit_code, 2)

    def test_string_decodes_exactly_the_four_supported_escapes(self) -> None:
        token = scan(r'"\\\" \n \t"')[0]
        self.assertEqual(token.kind, TokenKind.STRING)
        self.assertEqual(token.lexeme, r'"\\\" \n \t"')
        self.assertEqual(token.literal, "\\\" \n \t")

    def test_empty_string_hash_and_bom_inside_string(self) -> None:
        tokens = scan('"" "a#b\ufeff"')
        self.assertEqual(tokens[0].literal, "")
        self.assertEqual(tokens[1].literal, "a#b\ufeff")

    def test_string_and_identifier_can_be_adjacent(self) -> None:
        tokens = scan('"text"name')
        self.assertEqual(
            [(token.kind, token.lexeme) for token in tokens],
            [(TokenKind.STRING, '"text"'), (TokenKind.IDENT, "name"), (TokenKind.EOF, "")],
        )

    def test_unknown_escape_points_to_backslash(self) -> None:
        with self.assertRaises(LwtError) as caught:
            scan(r'"bad\q"')
        self.assertEqual(caught.exception.message, "unknown string escape")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 5))

    def test_escape_at_eof_points_to_backslash(self) -> None:
        with self.assertRaises(LwtError) as caught:
            scan('"abc' + "\\")
        self.assertEqual(caught.exception.message, "incomplete string escape")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 5))

    def test_raw_newline_and_unterminated_strings_point_to_opening_quote(self) -> None:
        for source in ('"a\nb"', '"unclosed'):
            with self.subTest(source=source), self.assertRaises(LwtError) as caught:
                scan(source)
            self.assertEqual(caught.exception.location.column, 1)

    def test_unknown_character_and_first_error_only(self) -> None:
        with self.assertRaises(LwtError) as caught:
            scan("@ # later error: !")
        self.assertEqual(caught.exception.message, "unexpected character U+0040")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 1))

    def test_lf_crlf_and_cr_normalize_positions(self) -> None:
        tokens = scan("first\r\nsecond\rthird")
        self.assertEqual(
            [(token.lexeme, token.line, token.column) for token in tokens],
            [("first", 1, 1), ("second", 2, 1), ("third", 3, 1), ("", 3, 6)],
        )

    def test_tab_counts_as_one_column_and_supplementary_unicode_as_one_code_point(self) -> None:
        tokens = scan("\tname\n\"😀\" next")
        self.assertEqual((tokens[0].line, tokens[0].column), (1, 2))
        self.assertEqual((tokens[1].line, tokens[1].column), (2, 1))
        self.assertEqual((tokens[2].line, tokens[2].column), (2, 5))

    def test_one_leading_bom_is_removed_and_second_is_an_error(self) -> None:
        token = scan("\ufeffname")[0]
        self.assertEqual((token.kind, token.lexeme, token.column), (TokenKind.IDENT, "name", 1))
        with self.assertRaises(LwtError) as caught:
            scan("\ufeff\ufeffname")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 1))

    def test_bom_in_comment_is_ignored_and_noncomment_bom_is_an_error(self) -> None:
        tokens = scan("#\ufeff@\nname")
        self.assertEqual([token.lexeme for token in tokens], ["name", ""])
        with self.assertRaises(LwtError) as caught:
            scan("name\ufeff")
        self.assertEqual((caught.exception.location.line, caught.exception.location.column), (1, 5))

    def test_eof_position_is_exact(self) -> None:
        for source, expected in (("", (1, 1)), ("abc", (1, 4)), ("abc\n", (2, 1)), ("#x", (1, 3))):
            with self.subTest(source=source):
                eof = scan(source)[-1]
                self.assertEqual(eof.kind, TokenKind.EOF)
                self.assertEqual((eof.line, eof.column), expected)


if __name__ == "__main__":
    unittest.main()
