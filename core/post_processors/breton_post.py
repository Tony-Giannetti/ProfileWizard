from __future__ import annotations
from pathlib import Path
from typing import Sequence

from .osai_post import OsaiPost


class BretonPost(OsaiPost):
    """Simple Breton controller post based on :class:`OsaiPost`."""

    def save(self, path: str | Path) -> Path:
        """Write Breton G-code to *path* (.nc) and return the absolute Path."""
=======
from typing import Sequence, Tuple, List


class BretonPost:
    """Generate Breton-style G-code from point data."""

    def __init__(
        self,
        points: Sequence,
        smoothing_pts: Sequence | None = None,
        *,
        blade_width: float = 3.5,
        blade_diameter: float | None = None,
        y_start: float,
        y_end: float,
        y_step: float | None = None,
        z_clear: float,
        z_max: float,
        plunge_feed: float = 500.0,
        cut_feed: float = 2000.0,
        cut_feed_xy: float | None = None,
        invert_xy: bool = False,
        orientation: str = "0.0000,0.0000,,,,0,0",
        work_plane: str = "0,0,0,0,0,0",
        line_numbers: bool = False,
    ):
        self.points: List[Tuple[float, float]] = [
            (p.x(), p.y()) if hasattr(p, "x") else (p[0], p[1]) for p in points
        ]
        self.smooth: List[Tuple[float, float]] = [
            (p.x(), p.y()) if hasattr(p, "x") else (p[0], p[1])
            for p in (smoothing_pts or [])
        ]

        self.blade_w = blade_width
        self.blade_d = blade_diameter
        self.y0, self.y1 = y_start, y_end
        self.y_step = abs(y_step or blade_width)
        self.z_clear, self.z_max = z_clear, z_max

        self.f_plunge = plunge_feed
        self.f_cut = cut_feed
        self.f_xy = cut_feed_xy or cut_feed

        self.invert = invert_xy
        self.orientation = orientation
        self.work_plane = work_plane
        self.number_lines = line_numbers
        self._counter = 1

    # ------------------------------------------------------------------ #
    def _xyz(self, x: float | None = None, y: float | None = None, z: float | None = None) -> str:
        if self.invert:
            x, y = y, x
        parts: list[str] = []
        if x is not None:
            parts.append(f"X{x:.2f}")
        if y is not None:
            parts.append(f"Y{y:.2f}")
        if z is not None:
            parts.append(f"Z{z:.2f}")
        return "  ".join(parts)

    def _line(self, text: str) -> str:
        if self.number_lines:
            prefix = f"N{self._counter} "
            self._counter += 1
            return prefix + text
        return text

    # ------------------------------------------------------------------ #
    def generate(self) -> List[str]:
        add = lambda s: ln.append(self._line(s))
        ln: List[str] = []

        # ------------------- header -----------------------------------
        add("; Breton G-code")
        add("BRETON_INIT(0)")
        add("G518")
        add("BRETON_WAREA(\"MILL\")")
        add("BRETON_PRE_TOOL")
        add("BRETON_CHGTOOL")
        add("BRETON_POST_TOOL(5,0)")
        add(f"BRETON_ORIENTATION({self.orientation})")
        add(f"BRETON_SETWPLANE({self.work_plane})")
        add("MS1")
        add("M4S1600")
        add("M07")

        c_code = "C0 A0" if self.invert else "C-90 A0"

        # ------------------- roughing ---------------------------------
        for idx, (x, z) in enumerate(self.points, start=1):
            add(f"; ---- Rough #{idx} ----")
            add(f"G0  {self._xyz(z=self.z_clear)}")
            add(f"G0  {self._xyz(x=x, y=self.y0)}  {c_code}")
            add(f"G1  {self._xyz(z=z)}  F{self.f_plunge:.0f}")
            add(f"G1  {self._xyz(y=self.y1)}  F{self.f_cut:.0f}")
        add("M18")

        # ------------------- smoothing --------------------------------
        if self.smooth:
            y = self.y0
            step = -self.y_step if self.y0 > self.y1 else self.y_step
            dir_f = True
            first = True
            cond = (lambda yy: yy >= self.y1) if step < 0 else (lambda yy: yy <= self.y1)

            while cond(y):
                seq = self.smooth if dir_f else list(reversed(self.smooth))
                fx, fz = seq[0]

                add(f"; ---- stripe Y={y:.2f} ----")

                if first:
                    add(f"G0  {self._xyz(z=self.z_clear)}")
                    add(f"G0  {self._xyz(x=fx, y=y)}  {c_code}")
                    add(f"G1  {self._xyz(z=fz)}  F{self.f_plunge:.0f}")
                    first = False
                else:
                    add(f"G0  {self._xyz(x=fx, y=y)}")
                add(f"G1  {self._xyz(y=y)}  F{self.f_cut:.0f}")

                for x, z in seq:
                    add(f"G1  {self._xyz(x=x, z=z)}  F{self.f_xy:.0f}")

                y_next = y + step
                if cond(y_next):
                    add(f"G1  {self._xyz(y=y_next)}  F{self.f_plunge:.0f}")

                y = y_next
                dir_f = not dir_f

            add("; ---- end smoothing ----")
            add(f"G0  {self._xyz(z=self.z_clear)}")
            add("M18")

        # ------------------- footer -----------------------------------
        add("BRETON_ENDPRG")
        add("M30")
        return ln

    # ------------------------------------------------------------------ #
    def save(self, path: str | Path) -> Path:
        path = Path(path).with_suffix(".nc")
        path.write_text("\n".join(self.generate()), encoding="utf-8")
        print(f"G-code written to {path.resolve()}")
        return path
