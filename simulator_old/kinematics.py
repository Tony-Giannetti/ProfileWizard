# ===============================
# file: kinematics.py
# ===============================
from typing import Dict
from pyqtgraph.opengl import GLMeshItem

SCALE_MM   = 0.1            # 1 viewer unit = 10 mm
BLADE_R_MM = 200.0          # keep in sync with machine.make_blade

class Blade4X:
    """Disc follows X, Y, Z, C.  Bottom edge traces the programmed path."""

    def __init__(self, parts: Dict[str, GLMeshItem]):
        self.blade = parts["blade"]

    def apply(self, x_mm: float, y_mm: float, z_mm: float, c_deg: float):
        cx = x_mm * SCALE_MM
        cy = y_mm * SCALE_MM
        cz = (z_mm + BLADE_R_MM) * SCALE_MM

        self.blade.resetTransform()

        # ① stand the disc upright (XY → XZ plane)   …world-axis rotation
        self.blade.rotate(90, 1, 0, 0, local=False)

        # ② swivel around the world Z-axis by C degrees
        self.blade.rotate(c_deg, 0, 0, 1, local=False)

        # ③ move the centre so the bottom tip hits the programmed XYZ
        self.blade.translate(cx, cy, cz)