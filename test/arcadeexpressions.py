# -*- coding: utf-8 -*-
import unittest

from bridgestyle.arcgis.expressions import (
    convertArcadeExpression,
    convertExpression,
    processRotationExpression,
)


class ArcadeExpressionTest(unittest.TestCase):
    """Covers the Arcade label expression handling. Arcade refers to fields as
    ``$feature.NAME`` (or ``$feature["NAME"]``) and quotes string literals with
    single quotes, so it has to be normalised to the inline ``[NAME]`` form the
    rest of the module understands."""

    # Same label, both engines, as exported by ArcGIS Pro.
    ARCADE = "$feature.CITY + '\\n' + 'Text: ' + $feature.SUMACCIDEN"
    VBSCRIPT = ' [CITY]  &Vbnewline& "Text: " & [SUMACCIDEN]'

    # tolowercase lowercases the literals too, as it already did for VBScript.
    EXPECTED = [
        "Concatenate",
        ["PropertyName", "city"],
        ["Concatenate", "[newline]text: ", ["PropertyName", "sumacciden"]],
    ]

    def test_field_references_are_normalised_to_brackets(self):
        self.assertEqual(
            convertArcadeExpression(self.ARCADE),
            "[CITY] + '\\n' + 'Text: ' + [SUMACCIDEN]",
        )

    def test_compound_label_is_converted(self):
        # The bug: every token became a literal, yielding the single string
        # "city'\n''Text: 'sumacciden" instead of a Concatenate of the fields.
        self.assertEqual(convertExpression(self.ARCADE, "Arcade", True), self.EXPECTED)

    def test_arcade_and_vbscript_convert_identically(self):
        self.assertEqual(
            convertExpression(self.ARCADE, "Arcade", True),
            convertExpression(self.VBSCRIPT, "VBScript", True),
        )

    def test_bracket_field_accessor(self):
        expr = '$feature["CITY"] + \'\\n\' + \'Text: \' + $feature[\'SUMACCIDEN\']'
        self.assertEqual(convertExpression(expr, "Arcade", True), self.EXPECTED)

    def test_textformatting_newline_constant(self):
        expr = "$feature.CITY + TextFormatting.NewLine + 'Text: ' + $feature.SUMACCIDEN"
        self.assertEqual(convertExpression(expr, "Arcade", True), self.EXPECTED)

    def test_escaped_newline_inside_a_literal(self):
        expr = "$feature.CITY + '\\nText: ' + $feature.SUMACCIDEN"
        self.assertEqual(convertExpression(expr, "Arcade", True), self.EXPECTED)

    def test_single_field(self):
        self.assertEqual(
            convertExpression("$feature.NAME", "Arcade", True), ["PropertyName", "name"]
        )

    def test_double_quoted_literals_still_work(self):
        expr = '$feature.CITY + "\\n" + "Text: " + $feature.SUMACCIDEN'
        self.assertEqual(convertExpression(expr, "Arcade", True), self.EXPECTED)

    def test_numeric_field_keeps_its_format_pattern(self):
        self.assertEqual(
            convertExpression("$feature.SUMACCIDEN", "Arcade", True, {"sumacciden": "#"}),
            ["numberFormat", "#", ["PropertyName", "sumacciden"]],
        )

    def test_rotation_expression_is_unaffected(self):
        # Guards the other caller of convertArcadeExpression: the normalisation
        # must not leak brackets into the property name.
        self.assertEqual(
            processRotationExpression("$feature.ANGLE", "Arithmetic", True),
            ["Mul", ["PropertyName", "angle"], -1],
        )
        self.assertEqual(
            processRotationExpression("[ANGLE]", "Geographic", True),
            ["Sub", ["PropertyName", "angle"], 90],
        )


if __name__ == "__main__":
    unittest.main()
