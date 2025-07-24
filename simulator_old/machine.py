# ===============================
# file: machine.py
# ===============================
from math import sin, cos, pi
import numpy as np
from PyQt5 import QtGui
from pyqtgraph.opengl import GLMeshItem, MeshData

# use the same scene-unit scale as kinematics.py
from .kinematics import SCALE_MM


def _disc_mesh(radius: float, half_t: float, sectors: int = 64) -> MeshData:
    """
    Build a thin solid disc whose centre is at (0,0,0) and whose axis is +Z.

    radius  – disc radius   (scene units)
    half_t  – half thickness (scene units, i.e. t / 2)
    """
    # ------- vertices --------------------------------------------------
    theta = np.linspace(0, 2 * pi, sectors, endpoint=False)
    # ring on +Z face
    top_ring = np.stack((radius * np.cos(theta),
                         radius * np.sin(theta),
                         np.full(sectors,  half_t)), axis=1)
    # ring on −Z face
    bot_ring = np.stack((radius * np.cos(theta),
                         radius * np.sin(theta),
                         np.full(sectors, -half_t)), axis=1)
    # centres
    v_top = np.array([[0, 0,  half_t]])
    v_bot = np.array([[0, 0, -half_t]])

    vertices = np.vstack((v_top, v_bot, top_ring, bot_ring))

    # index helpers
    i_top_center = 0
    i_bot_center = 1
    i_top_ring   = 2
    i_bot_ring   = 2 + sectors

    # ------- faces -----------------------------------------------------
    faces = []

    # top cap fan
    for i in range(sectors):
        faces.append([i_top_center,
                      i_top_ring + i,
                      i_top_ring + (i + 1) % sectors])

    # bottom cap fan
    for i in range(sectors):
        faces.append([i_bot_center,
                      i_bot_ring + (i + 1) % sectors,
                      i_bot_ring + i])

    # rim (two tris per sector)
    for i in range(sectors):
        a = i_top_ring + i
        b = i_top_ring + (i + 1) % sectors
        c = i_bot_ring + i
        d = i_bot_ring + (i + 1) % sectors
        faces.extend([[a, b, d], [a, d, c]])

    faces = np.array(faces, dtype=int)
    return MeshData(vertexes=vertices, faces=faces)


def make_blade(radius_mm: float = 200.0,
               thickness_mm: float = 6.0,
               sectors: int = 64):
    """
    Return a dict  {"blade": GLMeshItem}

    ▸ Disc plane initially lies in the XY plane (axis +Z).  
    ▸ Mesh origin = disc centre.  
    ▸ Size is already multiplied by SCALE_MM so it matches the tool-path units.
    """
    r_scene = radius_mm * SCALE_MM
    half_t  = 0.5 * thickness_mm * SCALE_MM

    md = _disc_mesh(r_scene, half_t, sectors)
    blade = GLMeshItem(meshdata=md, smooth=False, drawFaces=True, drawEdges=False)

    # a neutral metallic grey looks more "saw-blade-ish"
    blade.setColor(QtGui.QColor("#bbbbbb"))

    return {"blade": blade}
