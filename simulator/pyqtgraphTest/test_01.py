#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyQtGraph 3-D viewer bootstrap:
• PyQt5 window
• GLViewWidget as the central widget
• Grid + axis helpers
• Loads one STL mesh and drops it at the origin
"""

import sys
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import MeshData
import math, pyqtgraph as pg

# ----------------------------------------------------------------------
# Optional: enable 4× multisampling for smoother lines/edges
fmt = QtGui.QSurfaceFormat()
fmt.setSamples(4)
QtGui.QSurfaceFormat.setDefaultFormat(fmt)
# ----------------------------------------------------------------------

try:
    # pip install numpy-stl
    from stl import mesh as stlmesh
except ImportError:
    stlmesh = None
    print("numpy-stl is not installed; STL loading will be skipped.")

class GCodeViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("G-code 3-D Preview (PyQtGraph)")
        self.resize(1200, 800)

        # ---------- 3-D view -------------------------------------------------
        self.view = gl.GLViewWidget()
        self.view.opts['distance'] = 800          # initial zoom-out
        self.view.setBackgroundColor('k')         # dark theme
        self.setCentralWidget(self.view)          # or dock later

        # ---------- helpers --------------------------------------------------
        self.grid = gl.GLGridItem()
        self.grid.setSize(x=3500, y=2000, z=0)
        self.grid.setSpacing(x=100, y=100, z=10)
        # self.grid.rotate(90, 1, 0, 0)
        self.view.addItem(self.grid)

        self.fit_to_grid()

        axes = gl.GLAxisItem()
        axes.setSize(200, 200, 200)
        self.view.addItem(axes)

        # ---------- machine mesh --------------------------------------------
        self.add_machine_mesh("head.stl")   # <-- change path here
        self.add_origin_sphere()

    # ------------------------------------------------------------------
    def add_machine_mesh(self, path: str):
        """
        Load an STL and drop it into the scene.
        Split your real model into X-bridge / Y-carriage / Z-head…
        for independent motion; here we just add one static body.
        """
        if stlmesh is None:
            return

        try:
            raw = stlmesh.Mesh.from_file(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self, "Mesh load error",
                f"Could not load {path}\n{exc}")
            return

        verts  = raw.vectors.reshape(-1, 3)
        faces  = np.arange(len(verts)).reshape(-1, 3)
        body   = gl.GLMeshItem(vertexes=verts,
                               faces=faces,
                               smooth=False,
                               drawEdges=True,
                               shader='shaded')
        # If your model is Y-up, rotate so Z is up in pyqtgraph:
        body.rotate(90, 1, 0, 0)

        self.view.addItem(body)

    def fit_to_grid(self, margin: float = 1.15):
        size = self.grid.size()

        # unpack QSize / QSizeF / tuple
        if isinstance(size, QtCore.QSize):
            sx, sy, sz = size.width(), size.height(), 0
        else:                                # tuple or sequence
            sx, sy, *rest = size
            sz = rest[0] if rest else 0

        diag = math.hypot(sx, sy) * 0.5
        fov  = self.view.opts['fov']          # usually 60°
        dist = diag / math.tan(math.radians(fov / 2)) * margin

        # 1️⃣ first tell the camera how far back and at what angles
        self.view.setCameraPosition(
            distance=dist,
            elevation=30,     # iso view
            azimuth=45
        )

        # 2️⃣ then set the scene centre explicitly
        self.view.opts['center'] = pg.Vector(0, 0, 0)
        # self.view.opts['center'] = pg.Vector(sx, sy, 0)  # center at origin

    def add_origin_sphere(self, radius=50):
        """Add a yellow sphere at the grid’s front-left corner (-X, -Y)."""
        # 1.  Look up the grid extents ------------------------------
        size = self.grid.size()                     # QSizeF or tuple
        if isinstance(size, QtCore.QSize):
            sx, sy = size.width(), size.height()
        else:
            sx, sy = size[:2]                       # ignore z

        # 2.  Corner coordinates (grid is centred at 0,0,0) ---------
        corner_x = -sx / 2.0        # left edge
        corner_y = -sy / 2.0        # front edge (toward camera)

        # 3.  Build + position the sphere ---------------------------
        meshdata = gl.MeshData.sphere(rows=20, cols=20, radius=radius)
        sphere   = gl.GLMeshItem(meshdata=meshdata,
                                 smooth=True,
                                 color=(1, 1, 0, 1),   # yellow
                                 drawEdges=False,
                                 shader='shaded')
        sphere.translate(corner_x, corner_y, 0)      # drop at corner
        self.view.addItem(sphere)

        
def main():
    app = QtWidgets.QApplication(sys.argv)
    win = GCodeViewer()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
