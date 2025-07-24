# ===============================
# file: main.py
# ===============================
import sys
from pathlib import Path
from PyQt5 import QtWidgets, QtCore
from viewer import GCodeSimDock

def main() -> None:
    app = QtWidgets.QApplication(sys.argv)

    # pick G-code file from CLI or fallback to example.nc
    gcode_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gcode.nc")
    if not gcode_path.exists():
        QtWidgets.QMessageBox.critical(None, "File not found",
                                       f"Cannot open {gcode_path}")
        sys.exit(1)

    win = QtWidgets.QMainWindow()
    win.setWindowTitle("G-code Blade Simulator")
    win.resize(1200, 800)

    dock = GCodeSimDock(str(gcode_path), parent=win)
    win.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
