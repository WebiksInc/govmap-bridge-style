from enum import Enum


# A less custom literal would be great, see: https://github.com/geostyler/geostyler-style/issues/548
class WellKnownText(str, Enum):
    NEW_LINE = '[newline]'
