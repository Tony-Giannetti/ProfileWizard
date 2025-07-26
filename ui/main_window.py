# main_window.py
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui  import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction,
    QFileDialog, QMessageBox, QToolBar,
    QListWidgetItem, QDockWidget, QWidget,
    QFormLayout, QDoubleSpinBox, QStackedWidget,
    QVBoxLayout, QFileDialog
)

from core import probe
from core import planner
from core.config import config, save_config
from ui.dialogs import MachineSettingsDialog, ToolSettingsDialog, ToolpathSettingsDialog
from ui.canvas import Canvas
from ui.process_manager import ProcessManager, DxfInfo
from ui.process_list_widget import ProcessListWidget
from dxf.dxf import Dxf
from core.post_processors.osai_post import OsaiPost
from core.post_processors.breton_post import BretonPost
from simulator.viewer import GCodeSimDock

# ===================================================================== MainWindow
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Profile Wizard")
        self.resize(1600, 1000)

        # ---------- back‑end holders ---------------------------------
        self.proc_mgr     = ProcessManager()
        self.process_list = ProcessListWidget(self.proc_mgr)

        # ---------- UI scaffolding -----------------------------------
        self._side_view = config["machine_settings"].get("table_orientation") == "side"
        self.orientation = config["machine_settings"]["table_orientation"]
        self._dxf_info: DxfInfo | None = None
        self._create_menus()
        self._create_side_panel()      # needs self.process_list
        self._create_top_toolbar()

        # ---------- central canvas -----------------------------------
        self.view = Canvas(self)
        self.setCentralWidget(self.view)

        # list‑widget signals that need canvas:
        self.process_list.itemClicked.connect(self._on_process_clicked)

        self.sim_dock = None 

    # ---------------------------------------------------------------- menus
    def _create_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(QAction("Open DXF…", self, shortcut="Ctrl+O"))

        settings = self.menuBar().addMenu("&Settings")
        ms = QAction("Machine Settings…", self); ms.triggered.connect(self.open_machine_settings)
        ts = QAction("Tool Settings…",   self); ts.triggered.connect(self.open_tool_settings)
        ps = QAction("Tool-path Settings…", self); ps.triggered.connect(self.open_toolpath_settings)
        settings.addActions([ms, ts, ps])

    # ---------------------------------------------------------------- toolbar
    def _create_top_toolbar(self):
        tb = QToolBar("Tools", self); tb.setIconSize(QSize(50, 50))
        self.addToolBar(Qt.TopToolBarArea, tb)

        self._icon_front = QIcon("ui/icons/front.png")
        self._icon_side  = QIcon("ui/icons/side.png")
        side_view = config["machine_settings"].get("table_orientation") == "side"

        def act(icon, text, slot=None, sc=None, tip=None):
            a = QAction(QIcon(icon), text, self)
            if sc:  a.setShortcut(sc)
            if tip: a.setToolTip(tip)
            if slot: a.triggered.connect(slot)
            return a

        tb.addActions([
            act("ui/icons/new.png",
                "New",
                lambda: self.view.draw_table(
                    config["machine_settings"]["table_length"],
                    config["machine_settings"]["table_width"],
                    orientation=config["machine_settings"]["table_orientation"]),
                "Ctrl+N"),

            act("ui/icons/open.png",      "Open Project",       sc="Ctrl+O"),
            act("ui/icons/save.png",      "Save Project",       sc="Ctrl+S"),
        ])

        tb.addSeparator()
        spacer = QWidget(self)
        spacer.setFixedWidth(65)
        tb.addWidget(spacer)
        tb.addSeparator()

        self.orient_act = QAction(self)                # NOT checkable
        self._set_orient_icon(self._side_view)
        self.orient_act.triggered.connect(self._toggle_table_orientation)
        tb.addAction(self.orient_act)

        tb.addActions([
            act("ui/icons/importDXF.png", "Import DXF",   self.open_dxf, "Ctrl+I"),
            act("ui/icons/roughing.png",  "Generate Roughing",  self.generate_roughing),
            act("ui/icons/smoothing.png", "Generate Smoothing", self.generate_smoothing),
            act("ui/icons/exportGcode.png", "Export G‑code", self.export_gcode),
            act("ui/icons/simulate.png", "Simulate", self.simulate),
        ])

    # ---------------------------------------------------------------- side panel
    def _create_side_panel(self):
        # ---------- container widget inside dock -----------------------
        panel = QWidget()
        vbox  = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ---------- 1) process list ------------------------------------
        self.process_list = ProcessListWidget(self.proc_mgr)
        vbox.addWidget(self.process_list, 1)  # stretch = 1

        # ---------- 2) stacked settings palette ------------------------
        self._palette = QStackedWidget()
        vbox.addWidget(self._palette, 0)      # stretch = 0

        # --- empty page (index 0) --------------------------------------
        self._palette.addWidget(QWidget())

        # --- roughing page (index 1) -----------------------------------
        roughing_w = QWidget()
        flr = QFormLayout(roughing_w); flr.setContentsMargins(6, 6, 6, 6)

        r_step = config["toolpath_settings"]["roughing_stepover"]
        r_stock = config["toolpath_settings"]["stock_allowance"]
        r_feed = config["toolpath_settings"].get("roughing_feedrate", 1000.0)

        flr.addRow("Step (mm)",
                self._mk_spin("roughing_stepover", r_step))
        flr.addRow("Stock (mm)",
                self._mk_spin("stock_allowance", r_stock))
        flr.addRow("Feed‑rate (mm/min)",
                self._mk_spin("roughing_feedrate", r_feed, geom_affects=False))

        self._palette.addWidget(roughing_w)

        # --- smoothing page (index 2) ----------------------------------
        smoothing_w = QWidget()
        fls = QFormLayout(smoothing_w); fls.setContentsMargins(6, 6, 6, 6)

        s_res = config["toolpath_settings"]["smoothing_resolution"]
        s_step = config["toolpath_settings"]["smoothing_step"]
        s_feed = config["toolpath_settings"].get("smoothing_feedrate", 800.0)

        fls.addRow("Resolution (mm)",
                self._mk_spin("smoothing_resolution", s_res))
        fls.addRow("Step (mm)",
                self._mk_spin("smoothing_step", s_step))
        fls.addRow("Feed‑rate (mm/min)",
                self._mk_spin("smoothing_feedrate", s_feed, geom_affects=False))

        self._palette.addWidget(smoothing_w)

        # --- dxf page (index 3) --------------------------------------------
        dxf_w = QWidget()
        fld   = QFormLayout(dxf_w); fld.setContentsMargins(6, 6, 6, 6)

        # ❶ Min‑X (shifts drawing)
        self._xmin_spin = QDoubleSpinBox()
        self._xmin_spin.setRange(-20000, 20000)
        self._xmin_spin.valueChanged.connect(self._on_xmin_changed)
        fld.addRow("Min X (mm)", self._xmin_spin)

        # ❷ Start / End Y (affect posting only)
        start_y = config["toolpath_settings"].get("start", 1000.0)
        end_y   = config["toolpath_settings"].get("end",   500.0)

        fld.addRow("Start Y (mm)",
            self._mk_spin("start", start_y, geom_affects=False))
        fld.addRow("End Y (mm)",
            self._mk_spin("end",   end_y,   geom_affects=False))

        self._palette.addWidget(dxf_w)   # index 3

        self._palette.setCurrentIndex(0)  # start hidden

        # ---------- dock ------------------------------------------------
        dock = QDockWidget("Process List", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # ---------- selection change -> palette switch -----------------
        self.process_list.currentItemChanged.connect(self._palette_on_row_change)

    def _palette_on_row_change(self, current, previous):
        proc = current.data(Qt.UserRole)
        if isinstance(proc, probe.Path) and proc.label == "roughing":
            self._palette.setCurrentIndex(1)
        elif isinstance(proc, probe.Path) and proc.label == "smoothing":
            self._palette.setCurrentIndex(2)
        elif isinstance(proc, DxfInfo):
            self._xmin_spin.blockSignals(True)
            self._xmin_spin.setValue(proc.xmin)
            self._xmin_spin.blockSignals(False)
            self._palette.setCurrentIndex(3)
        else:
            self._palette.setCurrentIndex(0)
            
    # ---------------------------------------------------------------- settings dialogs
    def open_machine_settings(self):
        if MachineSettingsDialog(self).exec_():
            save_config()

    def open_tool_settings(self):
        if ToolSettingsDialog(self).exec_(): save_config()

    def open_toolpath_settings(self):
        if ToolpathSettingsDialog(self).exec_(): save_config()

    def _mk_spin(self, key, initial, geom_affects=True,
                minimum=0, maximum=1e6, step=0.1):
        """
        Creates a QDoubleSpinBox bound to toolpath_settings[key].
        If geom_affects is True and the selected path matches the key’s
        process type, the geometry is regenerated live.
        """
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(3)
        box.setSingleStep(step)
        box.setValue(initial)

        def _on_change(v):
            config["toolpath_settings"][key] = float(v)
            if geom_affects:
                self._regen_current_process()
        box.valueChanged.connect(_on_change)
        return box

    def _update_tp(self, key, value):
        config["toolpath_settings"][key] = float(value)

    # ---------------------------------------------------------------- DXF load
    def open_dxf(self):
        if not self.view.scene().items():
            QMessageBox.warning(self, "Warning", "Create a new project first.")
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Open DXF", "", "DXF Files (*.dxf)")
        if not fn:
            return
        try:
            self.dxfWrapper = Dxf.from_file(fn)
        except Exception as e:
            QMessageBox.critical(self, "DXF Error", str(e)); return
        self.view.load_doc(self.dxfWrapper.doc)

        # ---------- add / refresh pinned DXF row ------------------------
        xmin, _, _, _ = self.dxfWrapper.extents
        info = DxfInfo(Path(fn).resolve(), xmin=xmin)

        # if a previous DXF row exists, replace it
        if self.process_list.count() and isinstance(self.proc_mgr.passes[0], DxfInfo):
            self.proc_mgr.passes[0] = info
            it = self.process_list.item(0); it.setData(Qt.UserRole, info)
        else:
            self.proc_mgr.insert(0, info)
            self.process_list.insert_process_item(0, "DXF", info)

        self._dxf_info = info
        self.process_list.setCurrentRow(0)
        self.statusBar().showMessage(f"Loaded {Path(fn).name}", 4000)


    # ================================================================= Roughing
    def generate_roughing(self):
        if not getattr(self, "dxfWrapper", None) or self.view.doc is None:
            QMessageBox.warning(self, "No DXF", "Load a DXF first."); return

        path = planner.build_roughing_path(self.dxfWrapper, config)
        if not path.points:
            QMessageBox.warning(self, "Sampler", "No points found.")
            return

        self.proc_mgr.add(path)

        idx   = self.proc_mgr.count_by_label("roughing")
        self.process_list.add_process_item(f"Roughing {idx}", path)

        self.view.display_path(path.points)
        self.statusBar().showMessage("Roughing path generated", 3000)

    # ================================================================= Smoothing
    def generate_smoothing(self) -> None:
        if not getattr(self, "dxfWrapper", None) or self.view.doc is None:
            QMessageBox.warning(self, "No DXF", "Load a DXF first.")
            return

        path = planner.build_smoothing_path(self.dxfWrapper, config)
        if not path.points:
            QMessageBox.warning(self, "Sampler", "No points found.")
            return

        if len(path.points) < 2:
            QMessageBox.information(self, "Smoothing", "Not enough points for smoothing.")
            return

        self.proc_mgr.add(path)

        idx   = self.proc_mgr.count_by_label("smoothing")
        self.process_list.add_process_item(f"Smoothing {idx}", path)

        self.view.display_path(path.points)      # same cyan polyline you had
        self.statusBar().showMessage("Smoothing path generated", 3000)


    def _regen_current_process(self):
        item = self.process_list.currentItem()
        if not item or not getattr(self, "dxfWrapper", None):
            return
        row   = self.process_list.currentRow()
        label = item.text().lower()

        new_path = None
        if label.startswith("roughing"):
            new_path = planner.build_roughing_path(self.dxfWrapper, config)
        elif label.startswith("smoothing"):
            new_path = planner.build_smoothing_path(self.dxfWrapper, config)

        if new_path:
            self.proc_mgr.update(row, new_path)
            item.setData(Qt.UserRole, new_path)
            self.view.display_path(new_path.points)


    # ---------------------------------------------------------------- click handler
    def _on_process_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if isinstance(path, probe.Path):
            self.view.display_path(path.points)

    def export_gcode(self, checked: bool = False):
        # 1) choose save location
        mach       = config["machine_settings"]
        controller = mach.get("controller", "Osai")
        ext        = ".nc" if controller == "Breton" else ".s10"

        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Save G‑code",
            f"gcode{ext}",
            f"G‑code (*{ext});;All Files (*)",
        )
        if not fn:
            return  # user cancelled

        # 2) guard clauses
        if not getattr(self, "dxfWrapper", None):
            QMessageBox.warning(self, "No DXF", "No geometry loaded.")
            return
        if not self.proc_mgr.passes:
            QMessageBox.warning(self, "No processes", "Generate some paths first.")
            return

        # 3) gather paths in current list order
        rough_pts, smooth_pts = [], None
        for p in self.proc_mgr.passes:
            if isinstance(p, probe.Path):
                if p.label == "roughing":
                    rough_pts.extend(p.points)
                elif p.label == "smoothing" and smooth_pts is None:
                    smooth_pts = list(p.points)

        if not rough_pts:
            QMessageBox.warning(self, "No roughing", "Need at least one roughing path.")
            return

        # 4) build & save
        tool  = config["tool_settings"]
        tp    = config["toolpath_settings"]
        ori   = (mach["table_orientation"] == "side")

        PostClass = BretonPost if controller == "Breton" else OsaiPost
        post = PostClass(
            rough_pts,
            smoothing_pts=smooth_pts,
            blade_width   = tool["blade_width"],
            blade_diameter= tool["blade_diameter"],
            y_start       = tp.get("start", 1000.0),
            y_end         = tp.get("end",   500.0),
            y_step        = tp.get("smoothing_step", tool["blade_width"]),
            z_clear       = mach.get("z_clearance", 50.0),
            z_max         = mach.get("z_max",       100.0),
            plunge_feed   = tp.get("plunge_feed",        500.0),
            cut_feed      = tp.get("roughing_feedrate", 2000.0),
            cut_feed_xy   = tp.get("smoothing_feedrate", 800.0),
            invert_xy     = ori,
        )

        out_path = post.save(fn)
        self.statusBar().showMessage(f"G‑code saved → {out_path.name}", 4000)

    def simulate(self):
        # 1) ask for a .s10 if none is supplied
        fn, _ = QFileDialog.getOpenFileName(self, "Open G-code")
        if not fn:
            return

        # 2) close any previous simulator dock
        if self.sim_dock is not None:
            self.sim_dock.close()
            self.removeDockWidget(self.sim_dock)

        # 3) create & dock the new one
        self.sim_dock = GCodeSimDock(fn, parent=self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.sim_dock)
        self.sim_dock.show()

    def _toggle_table_orientation(self):
        # check first if there is a table
        if not self.view.scene().items():
            QMessageBox.warning(self, "Warning", "Create a new project first.")
            return
        # flip internal state
        self._side_view = not self._side_view

        # persist
        cfg = config["machine_settings"]
        cfg["table_orientation"] = "side" if self._side_view else "front"
        save_config()

        # update UI icon / tip
        self._set_orient_icon(self._side_view)

        # redraw table
        length = cfg["table_length"]
        width  = cfg["table_width"]
        self.view.draw_table(length, width,
                            orientation=cfg["table_orientation"])

    def _set_orient_icon(self, side_view: bool):
        if side_view:
            self.orient_act.setIcon(self._icon_side)
            self.orient_act.setToolTip("Table: side view")
        else:
            self.orient_act.setIcon(self._icon_front)
            self.orient_act.setToolTip("Table: front view")

    def _on_xmin_changed(self, new_val):
        if self._dxf_info is None:
            return

        dx = new_val - self._dxf_info.xmin
        if abs(dx) < 1e-6:
            return

        # ---- translate entities ---------------------------------------
        for e in self.dxfWrapper.msp:
            try:
                e.translate(dx, 0, 0)
            except AttributeError:
                if hasattr(e.dxf, "start"):
                    e.dxf.start.x += dx; e.dxf.end.x += dx

        self._dxf_info.xmin = new_val

        # ---- redraw WITHOUT losing the table --------------------------
        cfg      = config["machine_settings"]
        length   = cfg["table_length"]
        width    = cfg["table_width"]
        orient   = cfg["table_orientation"]

        self.view._table_item = None          # avoid dangling pointer
        self.view._dot_items.clear()
        self.view.scene().clear()

        # first redraw the table, then the DXF
        self.view.draw_table(length, width, orientation=orient)
        self.view.load_doc(self.dxfWrapper.doc)


# ===================================================================== run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
