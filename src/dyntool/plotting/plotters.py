"""plotter-first 正式绘图器。"""

from __future__ import annotations

from ._plotters_box import BoxPlotter
from ._plotters_frame import FramePlotter
from ._plotters_octave import OneThirdOctavePlotter
from ._plotters_story_value import StoryValuePlotter

for _export in (
    FramePlotter,
    BoxPlotter,
    OneThirdOctavePlotter,
    StoryValuePlotter,
):
    _export.__module__ = __name__

del _export

__all__ = [
    "BoxPlotter",
    "FramePlotter",
    "OneThirdOctavePlotter",
    "StoryValuePlotter",
]
