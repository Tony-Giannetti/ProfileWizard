# core/probe.py

from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass

from core.dxf_probe import VerticalProbe

# ------------------------------------------------------------------------- types
Point = Tuple[float, float]  # (x, y)


@dataclass
class Path:
    """A sampled tool‑path (just points + a label)."""
    points: List[Point]
    label: str = "roughing"   # or "smoothing", etc.


def sample_outline(
    mspace,
    xmin: float,
    xmax: float,
    *,
    blade_width: float,
    x_step: float,
    offsets: int = 3,
) -> List[Point]:
    probe   = VerticalProbe(mspace)
    offs    = [blade_width * i / (offsets - 1) for i in range(offsets)]

    pts: List[Point] = []
    x = xmin
    while x <= xmax:
        best_y = None
        best_x = None
        for dx in offs:
            y = probe.highest_y(x + dx)
            if y is not None and (best_y is None or y > best_y):
                best_y = y
                best_x = x + dx
        if best_y is not None:
            pts.append((x, best_y))   # <─ store true column of max Y
        x += x_step
    return pts