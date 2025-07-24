# osai_post.py  – 2025‑07‑21
# ---------------------------------------------------------------------------
#   OsaiPost
#     ▸ Generates roughing *and* smoothing G‑code for an Osai‑Open 5‑axis saw
#     ▸ Roughing  : one Y‑direction slice per (X,Z) point in `points`
#     ▸ Smoothing : serpentine X‑Z passes over `smoothing_pts`
#                   • first stripe plunges to depth
#                   • subsequent stripes move in Y only (no Z retract)
#     ▸ invert_xy : when True, swaps every X and Y so a “side” table view
#                   posts correctly without touching geometry generation
# ---------------------------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import Sequence, Tuple, List


class OsaiPost:
    # ------------------------------------------------------------------ #
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
        invert_xy: bool = False,           # ← NEW
    ):
        # coerce QPointF → tuple
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
        self.y_step = abs(y_step or blade_width)          # always positive
        self.z_clear, self.z_max = z_clear, z_max

        self.f_plunge = plunge_feed
        self.f_cut    = cut_feed
        self.f_xy     = cut_feed_xy or cut_feed

        self.invert   = invert_xy                         # ← flag saved

    # ---------- helpers -----------------------------------------------------
    def _xyz(self, x: float | None = None,
                   y: float | None = None,
                   z: float | None = None) -> str:
        """Return a 'X.. Y.. Z..' block with optional inversion."""
        if self.invert:
            x, y = y, x                                   # swap
        parts: list[str] = []
        if x is not None: parts.append(f"X{x:.2f}")
        if y is not None: parts.append(f"Y{y:.2f}")
        if z is not None: parts.append(f"Z{z:.2f}")
        return "  ".join(parts)

    # ------------------------------------------------------------------ #
    def generate(self) -> List[str]:
        ln: List[str] = [
            "; --------------------------------------------------------------",
            ";  SlabCAM – Osai roughing + smoothing",
            f";  Roughing cuts : {len(self.points)}",
            f";  Blade width   : {self.blade_w:.2f} mm",
            f";  Blade diameter: {self.blade_d:.2f} mm",
            f";  Invert X/Y    : {self.invert}",
            "; --------------------------------------------------------------",
            "(UAO,3)",
            "M18                ; Retract to max‑Z",
            "M30 S1500          ; Spindle ON",
            ";",
        ]
        
        c_code = "C0 A0" if self.invert else "C-90 A0"

        # ------------------- roughing ---------------------------------
        for idx, (x, z) in enumerate(self.points, start=1):
            ln += [
                f"; ---- Rough #{idx} ----------------------------------------",
                f"G0  {self._xyz(z=self.z_clear)}",
                f"G0  {self._xyz(x=x, y=self.y0)}  {c_code}",
                f"G1  {self._xyz(z=z)}  F{self.f_plunge:.0f}",
                f"G1  {self._xyz(y=self.y1)}  F{self.f_cut:.0f}",
            ]
        ln += ["M18                ; Retract to max‑Z"]
        
        # ------------------- smoothing --------------------------------
        if self.smooth:
            ln += [
                "; ==========================================================",
                ";  SMOOTHING PASSES",
                "; ==========================================================",
            ]

            y      = self.y0
            step   = -self.y_step if self.y0 > self.y1 else self.y_step
            dir_f  = True                # start left→right
            first  = True

            cond = (lambda yy: yy >= self.y1) if step < 0 else (lambda yy: yy <= self.y1)

            while cond(y):
                seq = self.smooth if dir_f else list(reversed(self.smooth))
                fx, fz = seq[0]

                ln.append(f"; ---- stripe Y={y:.2f}  dir={'fwd' if dir_f else 'rev'} ----")

                if first:
                    ln += [
                        f"G0  {self._xyz(z=self.z_clear)}",
                        f"G0  {self._xyz(x=fx, y=y)}  {c_code}",   # ← use same variable
                        f"G1  {self._xyz(z=fz)}  F{self.f_plunge:.0f}",
                    ]
                    first = False
                else:
                    ln += [f"G0  {self._xyz(x=fx, y=y)}"]
                ln += [f"G1  {self._xyz(y=y)}  F{self.f_cut:.0f}"]  

                for x, z in seq:
                    ln.append(f"G1  {self._xyz(x=x, z=z)}  F{self.f_xy:.0f}")

                # move in Y only (stay at depth) if another stripe remains
                y_next = y + step
                if cond(y_next):
                    ln.append(f"G1  {self._xyz(y=y_next)}  F{self.f_plunge:.0f}")

                y     = y_next
                dir_f = not dir_f

            ln += [
                "; ---- end smoothing ----",
                f"G0  {self._xyz(z=self.z_clear)}",
                "M18                ; Retract to max‑Z",
            ]

        # ------------------- program end ------------------------------
        ln += [
            "M31                ; Spindle OFF",
            "M32                ; End of program",
            ";",
            "",
        ]
        return ln

    # ------------------------------------------------------------------ #
    def save(self, path: str | Path) -> Path:
        """Write G‑code to *path* (.s10) and return the absolute Path."""
        path = Path(path).with_suffix(".s10")
        path.write_text("\n".join(self.generate()), encoding="utf-8")
        print(f"G‑code written to {path.resolve()}")
        return path


# ------------------ stand‑alone CLI test -------------------------------
if __name__ == "__main__":
    import json, sys
    if len(sys.argv) != 4:
        print("Usage:  python osai_post.py  points.json  output.s10  {front|side}")
        sys.exit(1)

    data     = json.loads(Path(sys.argv[1]).read_text())
    rough    = data["rough"]               # list[[x,z], ...]
    smooth   = data.get("smooth", [])      # optional
    sideview = sys.argv[3].lower() == "side"

    OsaiPost(
        rough,
        smoothing_pts=smooth,
        blade_width=3.5,
        y_start=1000, y_end=500,
        z_clear=50, z_max=100,
        invert_xy=sideview
    ).save(sys.argv[2])
