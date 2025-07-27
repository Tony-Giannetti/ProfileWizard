# ui/process_list_widget.py
from typing import List

from PyQt5.QtCore    import Qt, QSize
from PyQt5.QtGui     import QFont
from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView, QSizePolicy
)


class ProcessListWidget(QListWidget):
    """List that supports drag‑reorder, delete‑key removal, and a pinned row."""

    def __init__(self, proc_mgr, *args, **kw):
        super().__init__(*args, **kw)
        self.proc_mgr = proc_mgr

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.InternalMove)

        self.setStyleSheet("QListWidget::item { height: 65px; }")

    # ---------- add helpers -------------------------------------------
    def add_process_item(self, text: str, payload):
        self._mk_item(self.count(), text, payload)

    def insert_process_item(self, row: int, text: str, payload):
        self._mk_item(row, text, payload, insert=True)

    def _mk_item(self, row: int, text: str, payload, insert=False):
        it = QListWidgetItem(text)
        it.setData(Qt.UserRole, payload)
        it.setSizeHint(QSize(it.sizeHint().width(), 65))
        font = it.font(); font.setBold(text.lower() == "dxf"); it.setFont(font)
        if insert:
            self.insertItem(row, it)
        else:
            self.addItem(it)

    # ---------- drag‑drop ---------------------------------------------
    def dropEvent(self, event):
        tgt_row = self.indexAt(event.pos()).row()
        if tgt_row == 0:          # keep DXF row pinned
            return
        src_row = self.currentRow()
        if src_row == 0:
            return
        super().dropEvent(event)
        self._sync()

    # ---------- delete‑key --------------------------------------------
    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
            if 0 in rows: rows.remove(0)     # don't delete DXF row
            for r in rows:
                self.takeItem(r)
                self.proc_mgr.remove(r)
            self.clearSelection()
        else:
            super().keyPressEvent(ev)

    # ---------- helpers -----------------------------------------------
    def _sync(self):
        for i in range(self.count()):
            self.proc_mgr.update(i, self.item(i).data(Qt.UserRole))
