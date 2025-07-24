# dialogs.py
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox
)
from core.config import config

class MachineSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Machine Settings")
        form = QFormLayout(self)

        self.table_length = QDoubleSpinBox()
        self.table_length.setRange(0, 10000.0)
        self.table_length.setValue(config["machine_settings"]["table_length"])
        form.addRow("Table Length (mm):", self.table_length)

        self.table_width = QDoubleSpinBox()
        self.table_width.setRange(0, 10000.0)
        self.table_width.setValue(config["machine_settings"]["table_width"])
        form.addRow("Table Width (mm):", self.table_width)

        self.max_feed = QDoubleSpinBox()
        self.max_feed.setRange(0, 1e6)
        self.max_feed.setValue(config["machine_settings"]["max_feed_rate"])
        form.addRow("Max Feed Rate (mm/min):", self.max_feed)

        self.rapid = QDoubleSpinBox()
        self.rapid.setRange(0, 1e6)
        self.rapid.setValue(config["machine_settings"]["rapid_rate"])
        form.addRow("Rapid Rate (mm/min):", self.rapid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accepted)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accepted(self):
        config["machine_settings"]["max_feed_rate"] = self.max_feed.value()
        config["machine_settings"]["rapid_rate"]      = self.rapid.value()
        self.accept()


class ToolSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tool Settings")
        form = QFormLayout(self)

        self.dia = QDoubleSpinBox()
        self.dia.setRange(0, 3000.0)
        self.dia.setValue(config["tool_settings"]["blade_diameter"])
        form.addRow("Blade Diameter (mm):", self.dia)

        self.bladeWidth = QDoubleSpinBox()
        self.bladeWidth.setRange(0, 100.0)
        self.bladeWidth.setValue(config["tool_settings"]["blade_width"])
        form.addRow("Blade Width (mm):", self.bladeWidth)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accepted)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accepted(self):
        config["tool_settings"]["blade_diameter"] = self.dia.value()
        config["tool_settings"]["blade_width"] = self.bladeWidth.value()
        self.accept()


class ToolpathSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toolpath Settings")
        form = QFormLayout(self)

        self.start = QDoubleSpinBox()
        self.start.setRange(0, 10000.0)
        self.start.setValue(config["toolpath_settings"]["start"])
        form.addRow("Start Position (mm):", self.start)

        self.end = QDoubleSpinBox()
        self.end.setRange(0, 10000.0)
        self.end.setValue(config["toolpath_settings"]["end"])
        form.addRow("End Position (mm):", self.end)

        self.rough = QDoubleSpinBox()
        self.rough.setRange(0.0, 10.0)
        self.rough.setDecimals(3)
        self.rough.setValue(config["toolpath_settings"]["roughing_stepover"])
        form.addRow("Roughing Stepover (mm):", self.rough)

        self.smooth = QDoubleSpinBox()
        self.smooth.setRange(0.0, 10.0)
        self.smooth.setDecimals(3)
        self.smooth.setValue(config["toolpath_settings"]["smoothing_resolution"])
        form.addRow("Smoothing Resolution (mm):", self.smooth)

        self.smoothStep = QDoubleSpinBox()
        self.smoothStep.setRange(0.0, 100.0)
        self.smoothStep.setValue(config["toolpath_settings"]["smoothing_step"])
        form.addRow("Smoothing Step (mm):", self.smoothStep)

        self.feed = QDoubleSpinBox()
        self.feed.setRange(0, 1e6)
        self.feed.setValue(config["toolpath_settings"]["feed_rate"])
        form.addRow("Feed Rate (mm/min):", self.feed)

        self.stock = QDoubleSpinBox()
        self.stock.setRange(0, 100.0)
        self.stock.setValue(config["toolpath_settings"]["stock_allowance"])
        form.addRow("Stock Allowance (mm):", self.stock)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accepted)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accepted(self):
        config["toolpath_settings"]["roughing_stepover"]   = self.rough.value()
        config["toolpath_settings"]["smoothing_resolution"] = self.smooth.value()
        config["toolpath_settings"]["feed_rate"]          = self.feed.value()
        config["toolpath_settings"]["stock_allowance"]   = self.stock.value()
        self.accept()
