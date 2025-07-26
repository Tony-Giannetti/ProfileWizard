from __future__ import annotations
from pathlib import Path
from typing import Sequence

from .osai_post import OsaiPost


class BretonPost(OsaiPost):
    """Simple Breton controller post based on :class:`OsaiPost`."""

    def save(self, path: str | Path) -> Path:
        """Write Breton G-code to *path* (.nc) and return the absolute Path."""
        path = Path(path).with_suffix(".nc")
        path.write_text("\n".join(self.generate()), encoding="utf-8")
        print(f"G-code written to {path.resolve()}")
        return path
