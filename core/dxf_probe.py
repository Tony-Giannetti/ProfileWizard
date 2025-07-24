# core/dxf_probe.py

import math
from typing import Iterable, Optional, Sequence

import ezdxf
from ezdxf.entities import Line, Circle, Arc, LWPolyline


def _angle_deg(dx: float, dy: float) -> float:

    return math.degrees(math.atan2(dy, dx)) % 360.0

def _on_arc_ccw(a: float, start: float, end: float) -> bool:
    a, start, end = a % 360, start % 360, end % 360
    return start <= a <= end if start <= end else (a >= start or a <= end)

def _on_arc(a: float, start: float, end: float, ccw: bool) -> bool:
    return _on_arc_ccw(a, start, end) if ccw else _on_arc_ccw(a, end, start)

class VerticalProbe:

    def __init__(
        self,
        entity_source: Iterable,
        types: Sequence[str] = ("ARC", "CIRCLE", "LWPOLYLINE", "LINE"),
    ):
        self._types = types
        self.rebuild(entity_source)

    def rebuild(self, source: Iterable):
        self._arcs, self._circs, self._polys, self._lines = [], [], [], []
        for e in source:
            t = e.dxftype()
            if t == "ARC":
                self._arcs.append(e)
            elif t == "CIRCLE":
                self._circs.append(e)
            elif t == "LWPOLYLINE":
                self._polys.append(e)
            elif t == "LINE":
                self._lines.append(e)

    # ---------- public ------------------------------------------------
    def highest_y(self, x: float) -> Optional[float]:
        for bucket in (
            self._arcs,
            self._circs,
            self._polys,
            self._lines,
        ):
            best = None
            for e in bucket:
                y = self._y_at_x(e, x)
                if y is not None:
                    best = y if best is None else max(best, y)
            if best is not None:
                return best
        return None  # nothing intersects

    # ---------- dispatch ---------------------------------------------
    def _y_at_x(self, e, x):
        if isinstance(e, Arc):
            return self._y_arc(e, x)
        if isinstance(e, Circle):
            return self._y_circle(e, x)
        if isinstance(e, LWPolyline):
            return self._y_poly(e, x)
        if isinstance(e, Line):
            return self._y_line(e, x)
        return None

    # ---------- per-entity solvers (same maths you had) ---------------
    @staticmethod
    def _y_circle(c: Circle, x):
        cx, cy, _ = c.dxf.center
        r, dx = c.dxf.radius, x - cx
        if abs(dx) > r:
            return None
        return cy + math.sqrt(r * r - dx * dx)

    @staticmethod
    def _y_line(l: Line, x):
        x1, y1, _ = l.dxf.start
        x2, y2, _ = l.dxf.end
        if math.isclose(x1, x2):
            return max(y1, y2) if math.isclose(x, x1) else None

        if x < min(x1, x2) or x > max(x1, x2):
            return None

        t = (x - x1) / (x2 - x1)
        return y1 + t * (y2 - y1)

    def _y_poly(self, p: LWPolyline, x):
        best = None
        for seg in p.virtual_entities():
            y = self._y_at_x(seg, x)
            if y is not None:
                best = y if best is None else max(best, y)
        return best

    def _y_arc(self, a: Arc, x):
        cx, cy, _ = a.dxf.center
        r, dx = a.dxf.radius, x - cx

        if abs(dx) > r:
            return None

        dy = math.sqrt(r * r - dx * dx)
        hits = [(x, cy + dy), (x, cy - dy)]

        start, end = a.dxf.start_angle, a.dxf.end_angle
        ccw = (a.dxf.extrusion[2] if hasattr(a.dxf, "extrusion") else 1.0) >= 0
        ys = [
            py
            for px, py in hits
            if _on_arc(_angle_deg(px - cx, py - cy), start, end, ccw)
        ]
        return max(ys) if ys else None