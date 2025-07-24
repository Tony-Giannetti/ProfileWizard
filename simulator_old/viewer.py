# ===============================
# file: viewer.py
# ===============================
from PyQt5 import QtCore, QtWidgets, QtGui
import numpy as np
from pyqtgraph.opengl import (
    GLViewWidget, GLLinePlotItem, GLMeshItem, MeshData
)

from .parser     import pose_stream
from .machine    import make_blade
from .kinematics import Blade4X, SCALE_MM

RUNTIME_STEP_MM  = 1.0   # blade moves this far each internal step
STORE_EVERY_N    = 5     # keep only every 5th vertex in the poly‑line
DISPLAY_STEP_MM   = 5.0   # store every 5 mm of travel
ANGLE_THRESH_DEG  = 8.0

# ────────────────────────────────────────────────────────────────────
# Geometry helper ─ stock slab drawn double-sided
# ────────────────────────────────────────────────────────────────────
def make_double_sided_box(size: np.ndarray,
                          rgba=(0.2, 0.6, 1.0, 0.25)) -> GLMeshItem:
    """Return a cube mesh whose faces are duplicated back-to-front."""
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
    for q in quads:
        faces += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]   # front
        faces += [[q[2], q[1], q[0]], [q[3], q[2], q[0]]]   # back
    md = MeshData(vertexes=v.astype(float),
                  faces=np.asarray(faces, int))
    return GLMeshItem(meshdata=md, smooth=False,
                      drawFaces=True, drawEdges=False,
                      color=rgba, glOptions='translucent')


# ────────────────────────────────────────────────────────────────────
# View widget with gentle orbit + screen-plane pan
# ────────────────────────────────────────────────────────────────────
class SmoothGLView(GLViewWidget):
    ROT_SENS = 0.1          # °/px
    PAN_SENS = 0.001        # world-units/px
    Y_INV    = 1            # 1 = drag-up ⇒ look-up; −1 inverts

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._last_orbit = None
        self._last_pan   = None

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            self._last_orbit = ev.pos(); ev.accept()
        elif ev.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._last_pan = ev.pos(); ev.accept()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & QtCore.Qt.LeftButton and self._last_orbit is not None:
            d = ev.pos() - self._last_orbit
            self.orbit(-d.x()*self.ROT_SENS,
                        self.Y_INV*d.y()*self.ROT_SENS)
            self._last_orbit = ev.pos(); ev.accept()
        elif (ev.buttons() & (QtCore.Qt.MiddleButton | QtCore.Qt.RightButton)
              and self._last_pan is not None):
            d = ev.pos() - self._last_pan
            self._pan_screen(d.x(), d.y())
            self._last_pan = ev.pos(); ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            self._last_orbit = None
        elif ev.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._last_pan = None
        super().mouseReleaseEvent(ev)

    def _pan_screen(self, dx_px: float, dy_px: float):
        az  = np.deg2rad(self.opts['azimuth'])
        el  = np.deg2rad(self.opts['elevation'])
        fwd = np.array([-np.cos(el)*np.cos(az),
                        -np.cos(el)*np.sin(az),
                        -np.sin(el)])
        right = np.cross([0, 0, 1], fwd); right /= np.linalg.norm(right)
        upvec = np.cross(fwd, right);     upvec /= np.linalg.norm(upvec)
        move = (dx_px*right + dy_px*upvec) * self.opts['distance'] * self.PAN_SENS
        self.opts['center'] += QtGui.QVector3D(*move)
        self.update()


# ────────────────────────────────────────────────────────────────────
#  Dock widget simulator
# ────────────────────────────────────────────────────────────────────
class GCodeSimDock(QtWidgets.QDockWidget):
    SPEED_MIN, SPEED_MAX = 1, 60      # raw slider detents

    def __init__(self, nc_path: str, parent=None):
        super().__init__("G-code Simulator", parent)
        self.nc_path = nc_path
        self._store_skip = 0

        # preload program for progress slider
        self._poses_all = list(pose_stream(nc_path))
        self._cursor    = 0

        # ---------- GL scene -----------------------------------------
        self.view = SmoothGLView()
        self.view.setBackgroundColor(QtGui.QColor("#202030"))
        self.parts = make_blade();           self.view.addItem(self.parts["blade"])

        self.box_sz = np.array([3500, 2000, 50], float) * SCALE_MM
        slab = make_double_sided_box(self.box_sz)
        slab.translate(*(self.box_sz/2 * [1,1,-1]))
        self.view.addItem(slab)

        self.verts_g0, self.verts_g1 = [], []
        self.path_g0 = GLLinePlotItem(width=1.5, antialias=True,
                                      color=(0.3,0.3,0.3,0.6))
        self.path_g1 = GLLinePlotItem(width=2.0, antialias=True,
                                      color=(1.0,1.0,0.0,1.0))
        self.view.addItem(self.path_g0); self.view.addItem(self.path_g1)

        # ---------- controls bar -------------------------------------
        self._build_controls()

        # wrap view + controls in dock widget contents
        wrap = QtWidgets.QWidget()
        lay  = QtWidgets.QVBoxLayout(wrap); lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.view, 1); lay.addWidget(self.ctrls)
        self.setWidget(wrap)

        # data helpers & timer
        self._kin      = Blade4X(self.parts)
        self._prev_g   = None
        self._accum_dist = 0.0          # mm since last stored vertex
        self._last_dir   = None         # previous segment direction (unit vector)
        self._timer    = QtCore.QTimer(self); self._timer.timeout.connect(self._tick)
        self._running  = False

        QtCore.QTimer.singleShot(0, self._set_start_camera)
        self._reset_scene()

        # shortcuts
        QtWidgets.QShortcut("Space", self, activated=self._toggle_play)
        QtWidgets.QShortcut("R",     self, activated=self._restart)
        QtWidgets.QShortcut("PgUp",  self,
            activated=lambda: self.speed_slider.setValue(
                min(self.SPEED_MAX, self.speed_slider.value()+1)))
        QtWidgets.QShortcut("PgDown", self,
            activated=lambda: self.speed_slider.setValue(
                max(self.SPEED_MIN, self.speed_slider.value()-1)))

    # ----------------------------------------------------------------
    # Build control bar
    # ----------------------------------------------------------------
    def _build_controls(self):
        self.ctrls = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(self.ctrls); h.setContentsMargins(6,4,6,4)

        # ▶︎
        self.play_btn = QtWidgets.QPushButton("▶︎")
        self.play_btn.setFixedSize(56, 40)
        self.play_btn.setStyleSheet("font-size:24px;")
        self.play_btn.clicked.connect(self._toggle_play)
        h.addWidget(self.play_btn)

        # ↻
        rst = QtWidgets.QPushButton("↻")
        rst.setFixedSize(56, 40)
        rst.setStyleSheet("font-size:24px;")
        rst.clicked.connect(self._restart)
        h.addWidget(rst)

        # speed slider
        h.addSpacing(12); h.addWidget(QtWidgets.QLabel("Speed"))
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(self.SPEED_MIN, self.SPEED_MAX)
        self.speed_slider.setValue(15)
        self.speed_slider.setTracking(True)
        h.addWidget(self.speed_slider, 1)

        # progress slider
        h.addSpacing(12); h.addWidget(QtWidgets.QLabel("Progress"))
        self.prog = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        rng_max   = max(1, len(self._poses_all)-1)
        self.prog.setRange(0, rng_max)
        self.prog.setTracking(True)
        self.prog.setStyleSheet("""
            QSlider::groove:horizontal { height:4px; background:#888; }
            QSlider::handle:horizontal { background:#d0d0d0; width:14px;
                                         margin:-6px 0; border-radius:3px; }
        """)
        self.prog.sliderPressed.connect(self._pause_for_seek)
        self.prog.sliderReleased.connect(self._seek_here)
        h.addWidget(self.prog, 2)

    # ----------------------------------------------------------------
    # Camera helpers
    # ----------------------------------------------------------------
    def _set_start_camera(self):
        dist = np.linalg.norm(self.box_sz) * 1.2
        ctr  = QtGui.QVector3D(self.box_sz[0]/2,
                               self.box_sz[1]/2,
                              -self.box_sz[2]/4)
        self.view.setCameraPosition(pos=ctr, distance=float(dist),
                                    elevation=15, azimuth=-55)

    # ----------------------------------------------------------------
    # Scene reset / rebuild
    # ----------------------------------------------------------------
    def _reset_scene(self):
        self._cursor  = 0
        self._prev_g  = None
        self.verts_g0.clear(); self.verts_g1.clear()
        self.path_g0.setData(pos=np.empty((0,3)))
        self.path_g1.setData(pos=np.empty((0,3)))
        self._kin.apply(0,0,0,0)
        self.prog.blockSignals(True); self.prog.setValue(0); self.prog.blockSignals(False)
        self._accum_dist = 0.0
        self._last_dir   = None
        self._last_xyz_mm = np.array([0.0, 0.0, 0.0])

    def _rebuild_to_cursor(self):
        """Rebuild blade pose & polylines so they match self._cursor."""
        target = self._cursor              # ❶ remember where the user wants to go
        self._reset_scene()                # this now resets graphics only
        self._cursor = 0                   # start replay from the beginning

        for i in range(target):            # ❷ fast-forward to target
            self._process_pose(self._poses_all[i],
                            record=True, autoupdate=False)
            self._cursor += 1

        self._update_polylines()               # ❸ draw
        self.prog.blockSignals(True)       # keep slider silent
        self.prog.setValue(target)         # show new position
        self.prog.blockSignals(False)


    # ----------------------------------------------------------------
    # Playback controls
    # ----------------------------------------------------------------
    def _toggle_play(self):
        if self._running:
            self._timer.stop(); self.play_btn.setText("▶︎"); self._running=False
        else:
            self._timer.start(16); self.play_btn.setText("❚❚"); self._running=True

    def _restart(self):
        was = self._running
        if was: self._toggle_play()
        self._reset_scene()
        if was: self._toggle_play()

    # progress slider events
    def _pause_for_seek(self):
        self._was_running = self._running
        if self._running: self._toggle_play()

    def _seek_here(self):
        self._cursor = self.prog.value()
        self._rebuild_to_cursor()
        if getattr(self, "_was_running", False): self._toggle_play()

    # ----------------------------------------------------------------
    # Timer tick
    # ----------------------------------------------------------------
    def _tick(self):
        speed_eff = max(1, self.speed_slider.value() // 3)
        for _ in range(speed_eff):
            if self._cursor >= len(self._poses_all):
                self._toggle_play(); return
            pose = self._poses_all[self._cursor]; self._cursor += 1
            self._process_pose(pose, record=True)

        self._update_polylines()
        self.prog.blockSignals(True); self.prog.setValue(self._cursor); self.prog.blockSignals(False)

    # ----------------------------------------------------------------
    # Helper: process one pose
    # ----------------------------------------------------------------
    def _process_pose(self, a, record=False, autoupdate=True):
        # 1) always move the blade
        self._kin.apply(a["X"], a["Y"], a["Z"], a["C"])
        if not record:
            return

        # 2) compute segment information
        v = np.array([a["X"], a["Y"], a["Z"]], float)
        if not self.verts_g0 and not self.verts_g1:
            need_store = True                     # first point always
            seg_dir    = None
            seg_len    = 0.0
        else:
            prev = np.array(self._last_xyz_mm, float)
            delta = v - prev
            seg_len = np.linalg.norm(delta)
            seg_dir = delta / seg_len if seg_len else None

            # criteria: direction change or 5 mm travelled
            turn = 0 if self._last_dir is None else np.degrees(
                    np.arccos(np.clip(np.dot(seg_dir, self._last_dir), -1, 1)))
            need_store = (self._accum_dist + seg_len >= DISPLAY_STEP_MM) or (
                        turn > ANGLE_THRESH_DEG)

        # 3) update accumulators
        self._accum_dist += seg_len
        if need_store:
            self._accum_dist = 0.0
            self._store_vertex(v, a["G"])
        self._last_xyz_mm = v
        self._last_dir    = seg_dir
        if autoupdate and need_store:
            self._update_polylines()

    def _store_vertex(self, v_mm, gcode):
        v_scene = [v_mm[0]*SCALE_MM, v_mm[1]*SCALE_MM, v_mm[2]*SCALE_MM]
        if gcode == 0:
            if self._prev_g == 1:
                self.verts_g1.append([np.nan]*3)
            self.verts_g0.append(v_scene)
        else:
            if self._prev_g == 0:
                self.verts_g0.append([np.nan]*3)
            self.verts_g1.append(v_scene)
        self._prev_g = gcode

    def _update_polylines(self):
        if self.verts_g0:
            self.path_g0.setData(pos=np.asarray(self.verts_g0))
        if self.verts_g1:
            self.path_g1.setData(pos=np.asarray(self.verts_g1))