#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimal Qt 3D viewer (PyQt5)
• STL (or OBJ/PLY) loaded with QMesh
• XY grid built from thin cylinders
• Orbit/zoom camera via QOrbitCameraController
"""
import os, sys
from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5.Qt3DCore    import QEntity, QTransform
from PyQt5.Qt3DRender  import QMesh, QCamera
from PyQt5.Qt3DExtras  import (
    Qt3DWindow, QOrbitCameraController,
    QPhongMaterial, QCylinderMesh
)

from PyQt5.QtCore      import QUrl
from PyQt5.QtGui       import QVector3D

STL_PATH = os.path.abspath("head.stl")

# ----------------------------------------------------------------------
def build_grid(size_x=3500, size_y=2000, step=100, parent=None):
    """Return an entity drawing an XY grid centred at the origin."""
    grid_root = QEntity(parent)

    # reusable cylinder mesh (thin line)
    cyl_x = QCylinderMesh()
    cyl_x.setRadius(1.0)
    cyl_x.setLength(size_x)
    cyl_x.setRings(4)
    cyl_x.setSlices(8)

    cyl_y = QCylinderMesh()
    cyl_y.setRadius(1.0)
    cyl_y.setLength(size_y)
    cyl_y.setRings(4)
    cyl_y.setSlices(8)

    mat = QPhongMaterial(parent)
    mat.setDiffuse(QtGui.QColor(140, 140, 140))

    # parallel to Y-axis (lines along X)
    for y in range(-size_y // 2, size_y // 2 + 1, step):
        ent  = QEntity(grid_root)
        ent.addComponent(cyl_x)
        xf   = QTransform()
        xf.setTranslation(QVector3D(0, y, 0))
        xf.setRotation(QtGui.QQuaternion.fromEulerAngles(90, 0, 0))
        ent.addComponent(xf)
        ent.addComponent(mat)

    # parallel to X-axis (lines along Y)
    for x in range(-size_x // 2, size_x // 2 + 1, step):
        ent  = QEntity(grid_root)
        ent.addComponent(cyl_y)
        xf   = QTransform()
        xf.setTranslation(QVector3D(x, 0, 0))
        ent.addComponent(xf)
        ent.addComponent(mat)

    return grid_root
# ----------------------------------------------------------------------


class Viewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt 3D G-code Preview")
        self.resize(1200, 800)

        # — Qt 3D framebuffer/GL window wrapped in a QWidget —
        self.view     = Qt3DWindow()
        container     = QtWidgets.QWidget.createWindowContainer(self.view, parent=self)
        self.setCentralWidget(container)

        # — Scene root —
        self.root      = QEntity()

        # — Camera & orbit controller —
        cam = self.view.camera()
        cam.lens().setPerspectiveProjection(60, 16/9, 0.1, 10000)
        cam.setPosition(QVector3D(0, -4500, 2000))
        cam.setViewCenter(QVector3D(0, 0, 0))

        cam_ctrl = QOrbitCameraController(self.root)
        cam_ctrl.setLinearSpeed(250)
        cam_ctrl.setLookSpeed(180)
        cam_ctrl.setCamera(cam)

        # — XY grid —
        build_grid(parent=self.root)

        # — Machine mesh —
        saw_ent  = QEntity(self.root)

        mesh     = QMesh()
        mesh.setSource(QUrl.fromLocalFile(STL_PATH))
        saw_ent.addComponent(mesh)

        mat      = QPhongMaterial(self.root)
        mat.setDiffuse(QtGui.QColor("lightsteelblue"))
        saw_ent.addComponent(mat)

        # optional orientation fix if STL is Y-up
        # xf = QTransform()
        # xf.setRotation(QtGui.QQuaternion.fromEulerAngles(-90, 0, 0))
        # saw_ent.addComponent(xf)

        self.view.setRootEntity(self.root)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = Viewer()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
