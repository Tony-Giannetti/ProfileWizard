"""Helper functions for building tool paths from DXF data."""

from __future__ import annotations

from . import probe


def _colinear(p0: probe.Point, p1: probe.Point, p2: probe.Point, *, tol: float = 1e-3) -> bool:
    """Return ``True`` if the three points are approximately colinear."""
    (x0, y0), (x1, y1), (x2, y2) = p0, p1, p2
    area = abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))
    return area <= tol


def build_roughing_path(dxf_wrapper, cfg) -> probe.Path:
    """Generate a :class:`probe.Path` for roughing from ``dxf_wrapper``."""

    blade_w = cfg["tool_settings"]["blade_width"]
    x_step = cfg["toolpath_settings"]["roughing_stepover"]
    stock = cfg["toolpath_settings"].get("stock_allowance", 0.0)

    xmin, _, xmax, _ = dxf_wrapper.extents

    pts = probe.sample_outline(
        dxf_wrapper.msp,
        xmin=xmin - blade_w,
        xmax=xmax + blade_w,
        blade_width=blade_w,
        x_step=x_step,
    )

    if stock:
        pts = [(x, y + stock) for x, y in pts]

    return probe.Path(points=pts, label="roughing")


def build_smoothing_path(dxf_wrapper, cfg) -> probe.Path:
    """Generate a :class:`probe.Path` for smoothing from ``dxf_wrapper``."""

    blade_w = cfg["tool_settings"]["blade_width"]
    x_step = cfg["toolpath_settings"]["smoothing_resolution"]
    # optional stock allowance for smoothing paths
    stock = cfg["toolpath_settings"].get("smoothing_stock", 0.0)

    xmin, _, xmax, _ = dxf_wrapper.extents
    start_x = xmin - blade_w

    pts = probe.sample_outline(
        dxf_wrapper.msp,
        xmin=start_x,
        xmax=xmax,
        blade_width=blade_w,
        x_step=x_step,
    )

    if stock:
        pts = [(x, y + stock) for x, y in pts]

    if len(pts) >= 3:
        keep = [pts[0]]
        for i in range(1, len(pts) - 1):
            if not _colinear(keep[-1], pts[i], pts[i + 1]):
                keep.append(pts[i])
        keep.append(pts[-1])
        pts = keep

    return probe.Path(points=pts, label="smoothing")

