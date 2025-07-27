from __future__ import annotations
from pathlib import Path
from typing import Sequence

from . import planner, probe
from .post_processors.osai_post import OsaiPost
from .post_processors.breton_post import BretonPost


def generate_path(dxf_wrapper, cfg, label: str) -> probe.Path:
    """Build a :class:`probe.Path` of type *label* using *dxf_wrapper*."""
    if label == "roughing":
        path = planner.build_roughing_path(dxf_wrapper, cfg)
    elif label == "smoothing":
        path = planner.build_smoothing_path(dxf_wrapper, cfg)
    else:
        raise ValueError(f"Unknown path label: {label}")

    if not path.points:
        raise ValueError("No points found")
    if label == "smoothing" and len(path.points) < 2:
        raise ValueError("Not enough points for smoothing")
    return path


def export_gcode(passes: Sequence[object], cfg, out_file: str | Path) -> Path:
    """Gather paths in *passes* and write a G-code file to *out_file*."""
    mach = cfg["machine_settings"]
    tool = cfg["tool_settings"]
    tp   = cfg["toolpath_settings"]

    controller = mach.get("controller", "Osai")
    PostClass  = BretonPost if controller == "Breton" else OsaiPost

    rough_pts, smooth_pts = [], None
    for p in passes:
        if isinstance(p, probe.Path):
            if p.label == "roughing":
                rough_pts.extend(p.points)
            elif p.label == "smoothing" and smooth_pts is None:
                smooth_pts = list(p.points)

    if not rough_pts:
        raise ValueError("Need at least one roughing path")

    post = PostClass(
        rough_pts,
        smoothing_pts=smooth_pts,
        blade_width=tool["blade_width"],
        blade_diameter=tool["blade_diameter"],
        y_start=tp.get("start", 1000.0),
        y_end=tp.get("end", 500.0),
        y_step=tp.get("smoothing_step", tool["blade_width"]),
        z_clear=mach.get("z_clearance", 50.0),
        z_max=mach.get("z_max", 100.0),
        plunge_feed=tp.get("plunge_feed", 500.0),
        cut_feed=tp.get("roughing_feedrate", 2000.0),
        cut_feed_xy=tp.get("smoothing_feedrate", 800.0),
        invert_xy=(mach.get("table_orientation") == "side"),
    )

    out_path = Path(out_file)
    return post.save(out_path)
