import unittest

from bridgestyle.arcgis.expressions import (
    convertExpression,
    convertVBScriptExpression,
)


class VBScriptExpressionTest(unittest.TestCase):
    """Covers the VBScript label expression handling: inline expressions (added
    in the previous PR) and multi-line ``Function ... End Function`` blocks."""

    FUNCTION_BLOCK = (
        'Function FindLabel ( [CITY], [SUMACCIDEN] )\r\n\r\n'
        '  FindLabel = [CITY] & vbNewLine & "Text: " & CStr([SUMACCIDEN])\r\n\r\n'
        'End Function'
    )
    INLINE = '[CITY] & vbNewLine & "Text: " & [SUMACCIDEN]'

    def test_function_block_is_unwrapped_to_inline_expression(self):
        self.assertEqual(
            convertVBScriptExpression(self.FUNCTION_BLOCK),
            '[CITY] & vbNewLine & "Text: " & [SUMACCIDEN]',
        )

    def test_function_block_and_inline_convert_identically(self):
        # The whole point: both formats produce the same GeoStyler expression.
        self.assertEqual(
            convertExpression(self.FUNCTION_BLOCK, "VBScript", True),
            convertExpression(self.INLINE, "VBScript", True),
        )

    def test_inline_expression_still_works(self):
        # Backward compatibility with the previous PR's inline support.
        self.assertEqual(
            convertExpression('[City] &Vbnewline& "text" & [SUMACCIDEN]', "VBScript", True),
            [
                "Concatenate",
                ["PropertyName", "city"],
                ["Concatenate", "[newline]text", ["PropertyName", "sumacciden"]],
            ],
        )

    def test_keywords_are_case_insensitive(self):
        expr = (
            'FUNCTION findlabel([A])\n'
            '  findlabel = [A] & VBCRLF & [B]\n'
            'END FUNCTION'
        )
        self.assertEqual(convertVBScriptExpression(expr), '[A] & VBCRLF & [B]')

    def test_nested_casts_and_line_continuation_are_stripped(self):
        expr = (
            'Function FindLabel([A])\n'
            '  FindLabel = cStr([A]) & vbNewLine & _\n'
            '    CInt(CStr([B]))\n'
            'End Function'
        )
        # Casts gone and the line continuation collapsed; the residual whitespace
        # is insignificant (stripped when tokens are split), so assert on the
        # converted GeoStyler expression rather than the intermediate spacing.
        self.assertEqual(
            convertExpression(expr, "VBScript", True),
            [
                "Concatenate",
                ["PropertyName", "a"],
                ["Concatenate", "[newline]", ["PropertyName", "b"]],
            ],
        )

    def test_single_field_function(self):
        expr = 'Function FindLabel([NAME])\n  FindLabel = [NAME]\nEnd Function'
        self.assertEqual(convertExpression(expr, "VBScript", True), ["PropertyName", "name"])


if __name__ == "__main__":
    unittest.main()
