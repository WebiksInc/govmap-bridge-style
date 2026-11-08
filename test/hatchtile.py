import math
import unittest
from io import BytesIO

from bridgestyle.arcgis import togeostyler
from bridgestyle.arcgis.togeostyler import _drawHatchTile, _hatchTileGeometry


def _hatch(rotation, separation=22.68, offsetX=0, dashed=False):
    stroke = {
        "type": "CIMSolidStroke",
        "enable": True,
        "width": 1.5,
        "color": {"type": "CIMRGBColor", "values": [104, 104, 104, 100]},
    }
    if dashed:
        stroke["effects"] = [{"type": "CIMGeometricEffectDashes", "dashTemplate": [6, 3]}]
    return {
        "type": "CIMHatchFill",
        "enable": True,
        "rotation": rotation,
        "separation": separation,
        "offsetX": offsetX,
        "lineSymbol": {"type": "CIMLineSymbol", "symbolLayers": [stroke]},
    }


def _fill(layer):
    return togeostyler.processSymbolLayer(layer, "CIMPolygonSymbol", {})


class HatchTileTest(unittest.TestCase):

    def test_tile_keeps_the_angle_and_spacing(self):
        for rotation in (30, 5, 95, 330, 355):
            width, height, a, b, _, scale = _hatchTileGeometry(rotation, 30.0, 0)
            # The normal (a, b) of the drawn lines, back to a counterclockwise line angle.
            angle = math.degrees(math.atan2(a, b)) % 180
            self.assertAlmostEqual(angle, rotation % 180, delta=0.5, msg=rotation)
            self.assertAlmostEqual(1 / math.hypot(a, b) / scale, 30.0, delta=0.3, msg=rotation)
            self.assertGreaterEqual(min(width, height), 64)

    def test_tile_is_seamless(self):
        from PIL import Image

        width, height, a, b, phase, scale = _hatchTileGeometry(30, 30.0, 0)
        tile = Image.open(BytesIO(_drawHatchTile(width, height, a, b, phase, 2 * scale, (0, 0, 0, 255))))
        alpha = tile.getchannel("A")
        # Tiled side by side, the last column and the first are neighbours, so a line leaving through
        # the right edge must continue at the left one.
        right = [alpha.getpixel((width - 1, y)) for y in range(height)]
        left = [alpha.getpixel((0, y)) for y in range(height)]
        self.assertLess(sum(abs(r - l) for r, l in zip(right, left)) / height, 40)

    def test_offset_moves_the_line(self):
        width, height, a, b, phase, scale = _hatchTileGeometry(30, 30.0, 10.0)
        self.assertAlmostEqual(phase, 10.0 / 30.0, delta=0.02)

    def test_odd_angle_or_offset_becomes_an_image(self):
        fill = _fill(_hatch(30))
        self.assertEqual(fill["graphicFill"][0]["kind"], "Icon")
        self.assertIn("hatch-", fill["graphicFill"][0]["image"])
        self.assertEqual(_fill(_hatch(45, offsetX=2))["graphicFill"][0]["kind"], "Icon")

    def test_mark_kept_for_45_degree_steps_and_dashes(self):
        self.assertEqual(_fill(_hatch(45))["graphicFill"][0]["kind"], "Mark")
        self.assertEqual(_fill(_hatch(90))["graphicFill"][0]["kind"], "Mark")
        self.assertEqual(_fill(_hatch(30, dashed=True))["graphicFill"][0]["kind"], "Mark")


if __name__ == "__main__":
    unittest.main()
