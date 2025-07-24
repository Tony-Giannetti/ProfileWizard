# ===============================
# file: viewer.py  (rev 2025‑07‑21b)
# Chunk‑&‑freeze rendering + restored camera, pan & rotate behaviour
# ===============================
from PyQt5 import QtCore, QtWidgets, QtGui
import numpy as np
from pyqtgraph.opengl import (
    GLViewWidget, GLLinePlotItem, GLMeshItem, MeshData
)

from .parser     import pose_stream
from .machine    import make_blade
from .kinematics import Blade4X, SCALE_MM


# ────────────────────────────────────────────────────────────────────
# Geometry helper – draw a translucent stock slab (double‑sided)
# ────────────────────────────────────────────────────────────────────
def make_double_sided_box(size: np.ndarray,
                          rgba=(0.2, 0.6, 1.0, 0.25)) -> GLMeshItem:
    """Return a cube mesh whose faces are duplicated back‑to‑front."""
    x, y, z = size / 2.0
    v = np.array([
        [-x, -y,  z], [ x, -y,  z], [ x,  y,  z], [-x,  y,  z],
        [-x, -y, -z], [ x, -y, -z], [ x,  y, -z], [-x,  y, -z],
    ])
    quads = [
        [0, 1, 2, 3], [1, 5, 6, 2], [5, 4, 7, 6],
        [4, 0, 3, 7], [3, 2, 6, 7], [4, 5, 1, 0],
    ]
    faces = []
    for q in quads:                               # front
        faces += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        faces += [[q[2], q[1], q[0]], [q[3], q[2], q[0]]]  # back
    md = MeshData(vertexes=v.astype(float),
                  faces=np.asarray(faces, int))
    return GLMeshItem(meshdata=md, smooth=False,
                      drawFaces=True, drawEdges=False,
                      color=rgba, glOptions='translucent')


# ────────────────────────────────────────────────────────────────────
# View widget – original orbit (LMB) + screen‑plane pan (MMB/RMB)
# ────────────────────────────────────────────────────────────────────
class SmoothGLView(GLViewWidget):
    """Exactly the feel of the pre‑refactor viewer:  
       • LMB   – orbit • MMB / RMB – pan in view plane."""
    ROT_SENS = 0.1          # ° per pixel
    PAN_SENS = 0.001        # world units per pixel
    Y_INV    = 1            # drag‑up ⇒ look‑up; set −1 to invert

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._last_orbit = None
        self._last_pan   = None

    # ---------- mouse -------------------------------------------------
    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            self._last_orbit = ev.pos(); ev.accept()
        elif ev.button() in (QtCore.Qt.MouseButton.MiddleButton,
                             QtCore.Qt.MouseButton.RightButton):
            self._last_pan = ev.pos(); ev.accept()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & QtCore.Qt.MouseButton.LeftButton and self._last_orbit is not None:
            d = ev.pos() - self._last_orbit
            self.orbit(-d.x()*self.ROT_SENS,
                       self.Y_INV*d.y()*self.ROT_SENS)
            self._last_orbit = ev.pos(); ev.accept()
        elif (ev.buttons() & (QtCore.Qt.MouseButton.MiddleButton |
                              QtCore.Qt.MouseButton.RightButton)
              and self._last_pan is not None):
            d = ev.pos() - self._last_pan
            self._pan_screen(d.x(), d.y())
            self._last_pan = ev.pos(); ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            self._last_orbit = None
        elif ev.button() in (QtCore.Qt.MouseButton.MiddleButton,
                             QtCore.Qt.MouseButton.RightButton):
            self._last_pan = None
        super().mouseReleaseEvent(ev)

    # ---------- helper ------------------------------------------------
    def _pan_screen(self, dx_px: float, dy_px: float):
        az = np.deg2rad(self.opts['azimuth'])
        el = np.deg2rad(self.opts['elevation'])
        fwd = np.array([-np.cos(el)*np.cos(az),
                        -np.cos(el)*np.sin(az),
                        -np.sin(el)])
        right = np.cross([0, 0, 1], fwd); right /= np.linalg.norm(right)
        upvec = np.cross(fwd, right);     upvec /= np.linalg.norm(upvec)
        move  = (dx_px*right + dy_px*upvec) * self.opts['distance'] * self.PAN_SENS
        self.opts['center'] += QtGui.QVector3D(*move)
        self.update()

# ────────────────────────────────────────────────────────────────────
# Simulator dock widget
# ────────────────────────────────────────────────────────────────────
class GCodeSimDock(QtWidgets.QDockWidget):
    CHUNK_SIZE            = 1000          # verts per frozen segment
    SPEED_MIN, SPEED_MAX  = 1, 300

    def __init__(self, gcode_file: str, parent=None):
        super().__init__("G‑code Simulator", parent)
        self.setFeatures(self.NoDockWidgetFeatures)

        # 1 — GL scene ------------------------------------------------
        self.view = SmoothGLView()
        self.view.setBackgroundColor(QtGui.QColor("#202030"))

        # blade model
        self.parts = make_blade()
        self.view.addItem(self.parts["blade"])

        # translucent slab
        self.box_sz = np.array([3500, 2000, 50], float) * SCALE_MM
        slab = make_double_sided_box(self.box_sz)
        slab.translate(*(self.box_sz/2 * [1, 1, -1]))
        self.view.addItem(slab)

        # 2 — path containers ----------------------------------------
        self.verts_g0, self.verts_g1 = [], []  # entire history
        self.tail_g0,  self.tail_g1  = [], []  # only the “live” tail
        self._frozen_items           = []      # static chunks

        # tail line items (updated every frame)
        self.path_g0 = GLLinePlotItem(width=1.5, antialias=True,
                                      color=(0.3, 0.3, 0.3, 0.6))
        self.path_g1 = GLLinePlotItem(width=2.0, antialias=True,
                                      color=(1.0, 1.0, 0.0, 1.0))
        self.view.addItem(self.path_g0)
        self.view.addItem(self.path_g1)

        # 3 — data helpers -------------------------------------------
        self._kin        = Blade4X(self.parts)
        self._poses_all  = list(pose_stream(gcode_file))
        self._cursor     = 0
        self._prev_g     = None

        # 4 — UI controls --------------------------------------------
        self._build_controls()

        # layout
        wrap = QtWidgets.QWidget()
        lay  = QtWidgets.QVBoxLayout(wrap); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view, 1); lay.addWidget(self.ctrls)
        self.setWidget(wrap)

        # 5 — timer ---------------------------------------------------
        self._timer   = QtCore.QTimer(self); self._timer.timeout.connect(self._tick)
        self._running = False

        # 6 — camera + clean scene -----------------------------------
        QtCore.QTimer.singleShot(0, self._set_start_camera)
        self._reset_scene()  # empties everything & zeroes blade

    # ----------------------------------------------------------------
    # Camera helper
    # ----------------------------------------------------------------
    def _set_start_camera(self):
        dist = np.linalg.norm(self.box_sz) * 1.2
        ctr  = QtGui.QVector3D(self.box_sz[0]/2,
                               self.box_sz[1]/2,
                              -self.box_sz[2]/4)
        self.view.setCameraPosition(pos=ctr, distance=float(dist),
                                    elevation=15, azimuth=-55)

    # ----------------------------------------------------------------
    # Control bar
    # ----------------------------------------------------------------
    def _build_controls(self):
        self.ctrls = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(self.ctrls); h.setContentsMargins(6, 3, 6, 3)

        self.play_btn    = QtWidgets.QPushButton("▶︎", minimumWidth=40,
                                                 clicked=self._toggle_play)
        self.restart_btn = QtWidgets.QPushButton("↺", minimumWidth=30,
                                                 clicked=self._restart)

        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(self.SPEED_MIN, self.SPEED_MAX)
        self.speed_slider.setSingleStep(1); self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(100)

        self.prog = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.prog.setRange(0, len(self._poses_all)); self.prog.setValue(0)
        self.prog.sliderPressed.connect(self._pause_for_seek)
        self.prog.sliderReleased.connect(self._seek_here)

        h.addWidget(self.play_btn)
        h.addWidget(QtWidgets.QLabel("speed")); h.addWidget(self.speed_slider)
        h.addStretch()
        h.addWidget(self.restart_btn)
        h.addWidget(self.prog, 1)

        # handy shortcuts
        QtWidgets.QShortcut("Space", self, activated=self._toggle_play)
        QtWidgets.QShortcut("R",     self, activated=self._restart)
        QtWidgets.QShortcut("PgUp",  self,
            activated=lambda: self.speed_slider.setValue(
                min(self.SPEED_MAX, self.speed_slider.value()+1)))
        QtWidgets.QShortcut("PgDown", self,
            activated=lambda: self.speed_slider.setValue(
                max(self.SPEED_MIN, self.speed_slider.value()-1)))

    # ----------------------------------------------------------------
    # Scene‑state helpers
    # ----------------------------------------------------------------
    def _reset_scene(self):
        # remove frozen chunks
        for item in self._frozen_items:
            self.view.removeItem(item)
        self._frozen_items.clear()

        # clear tails + visuals
        self.tail_g0.clear(); self.tail_g1.clear()
        self.path_g0.setData(pos=np.empty((0, 3)))
        self.path_g1.setData(pos=np.empty((0, 3)))

        # clear full history refs
        self.verts_g0.clear(); self.verts_g1.clear()
        self._cursor = 0; self._prev_g = None

        # blade to home; UI reset
        self._kin.apply(0, 0, 0, 0)
        self.prog.blockSignals(True); self.prog.setValue(0); self.prog.blockSignals(False)

    def _rebuild_to_cursor(self):
        tgt = self._cursor
        self._reset_scene()
        self._cursor = 0
        for i in range(tgt):
            self._process_pose(self._poses_all[i], record=True, autoupdate=False)
            self._cursor += 1
        self._update_paths()
        self.prog.blockSignals(True); self.prog.setValue(tgt); self.prog.blockSignals(False)

    # ----------------------------------------------------------------
    # Playback controls
    # ----------------------------------------------------------------
    def _toggle_play(self):
        if self._running:
            self._timer.stop(); self.play_btn.setText("▶︎"); self._running = False
        else:
            self._timer.start(16); self.play_btn.setText("❚❚"); self._running = True

    def _restart(self):
        was = self._running
        if was: self._toggle_play()
        self._reset_scene()
        if was: self._toggle_play()

    # progress‑slider events
    def _pause_for_seek(self):
        self._was_running = self._running
        if self._running: self._toggle_play()

    def _seek_here(self):
        self._cursor = self.prog.value()
        self._rebuild_to_cursor()
        if getattr(self, "_was_running", False):
            self._toggle_play()

    # ----------------------------------------------------------------
    # Timer tick
    # ----------------------------------------------------------------
    def _tick(self):
        step = max(1, self.speed_slider.value() // 3)
        for _ in range(step):
            if self._cursor >= len(self._poses_all):
                self._toggle_play(); return
            pose = self._poses_all[self._cursor]; self._cursor += 1
            self._process_pose(pose, record=True)
        self._update_paths()
        self.prog.blockSignals(True); self.prog.setValue(self._cursor); self.prog.blockSignals(False)

    # ----------------------------------------------------------------
    #  Path‑building helpers
    # ----------------------------------------------------------------
    def _freeze_tail(self, g_code):
        if g_code == 0 and self.tail_g0:
            item = GLLinePlotItem(pos=np.asarray(self.tail_g0, float),
                                  width=1.5, antialias=True,
                                  color=(0.3, 0.3, 0.3, 0.6))
            self.view.addItem(item); self._frozen_items.append(item)
            self.tail_g0.clear(); self.path_g0.setData(pos=np.empty((0, 3)))
        elif g_code == 1 and self.tail_g1:
            item = GLLinePlotItem(pos=np.asarray(self.tail_g1, float),
                                  width=2.0, antialias=True,
                                  color=(1.0, 1.0, 0.0, 1.0))
            self.view.addItem(item); self._frozen_items.append(item)
            self.tail_g1.clear(); self.path_g1.setData(pos=np.empty((0, 3)))

    def _process_pose(self, a, record=False, autoupdate=True):
        # move blade
        self._kin.apply(a["X"], a["Y"], a["Z"], a["C"])

        # record path points
        if record:
            v = [a["X"]*SCALE_MM, a["Y"]*SCALE_MM, a["Z"]*SCALE_MM]
            if a["G"] == 0:
                if self._prev_g == 1:
                    self.tail_g1.append([np.nan]*3); self.verts_g1.append([np.nan]*3)
                self.tail_g0.append(v); self.verts_g0.append(v)
                if len(self.tail_g0) >= self.CHUNK_SIZE: self._freeze_tail(0)
            else:  # cutting move
                if self._prev_g == 0:
                    self.tail_g0.append([np.nan]*3); self.verts_g0.append([np.nan]*3)
                self.tail_g1.append(v); self.verts_g1.append(v)
                if len(self.tail_g1) >= self.CHUNK_SIZE: self._freeze_tail(1)
            self._prev_g = a["G"]

        if autoupdate:
            self._update_paths()

    def _update_paths(self):
        if self.tail_g0:
            self.path_g0.setData(pos=np.asarray(self.tail_g0))
        if self.tail_g1:
            self.path_g1.setData(pos=np.asarray(self.tail_g1))
