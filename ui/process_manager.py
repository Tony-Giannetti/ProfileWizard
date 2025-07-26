# ui/process_manager.py
from typing import List
from core.probe import Path
from dataclasses import dataclass

@dataclass
class DxfInfo:
    path: Path
    xmin: float 

class ProcessManager:
    
    def __init__(self) -> None:
        self._passes: List[object] = []      # Path or DxfInfo

    # ---------- storage -------------------------------------------------
    def add(self, obj) -> None:
        self._passes.append(obj)

    def insert(self, index: int, obj) -> None:        # ← ADD THIS
        """Insert *obj* at *index* (used for the pinned DXF row)."""
        self._passes.insert(index, obj)

    def update(self, index: int, obj) -> None:
        """Replace the object at ``index`` with ``obj``."""
        self._passes[index] = obj

    def __getitem__(self, idx: int):
        return self._passes[idx]

    # ---------- helpers -------------------------------------------------
    def count_by_label(self, label: str) -> int:
        from core.probe import Path
        return sum(1 for p in self._passes if isinstance(p, Path) and p.label == label)

    @property
    def passes(self) -> List[object]:
        return self._passes
    