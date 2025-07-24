# dxf/dxf.py
from pathlib import Path
import ezdxf
from ezdxf.bbox import extents as _bbox_extents

class Dxf:
    """Thin wrapper around ezdxf.Drawing (no geometry code here)."""

    def __init__(self, path: Path, doc: ezdxf.document.Drawing) -> None:
        self.path = path
        self.doc  = doc
        self.msp  = doc.modelspace()

    # ----- factory ---------------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> "Dxf":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        return cls(path, ezdxf.readfile(str(path)))

    # ----- convenience -----------------------------------------------------
    @property
    def extents(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) in model‑space units."""
        mn, mx = _bbox_extents(self.msp)
        return mn.x, mn.y, mx.x, mx.y