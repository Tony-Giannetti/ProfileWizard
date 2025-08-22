from PyQt5.QtWidgets import QMainWindow, QLabel


class MainWindow(QMainWindow):
    """Minimal main window for the new application prototype."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Profile Wizard Prototype")
        self.setCentralWidget(QLabel("Hello, Profile Wizard!"))
