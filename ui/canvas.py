# canvas.py
from __future__ import annotations
from typing import Any, List
import ezdxf
from ezdxf.addons.drawing.qtviewer import CADGraphicsView, PyQtBackend
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.bbox import extents
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor, QPainterPath, QPolygonF
from PyQt5.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsItemGroup
from core.config import config
Point = tuple[float, float]

class Canvas(CADGraphicsView):
    
    def __init__(self, parent=None):
        super().__init__()
        if parent:
            self.setParent(parent)

        # Appearance
        self.setBackgroundBrush(QBrush(QColor("#2b2b2b")))
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().setCursor(Qt.ArrowCursor)

        self._dot_group = None 
        self._dot_items: list = []
        self._table_item = None          # <- remember table rect
        self._point_items: list = []     # <- active point dots
        self._pass_pen = QPen(QColor("#0400FF")); self._pass_pen.setCosmetic(True)
        self._dot_brush = QBrush(QColor("#FFFF00"))
        self._smoothing_poly_item = None
        self._smoothing_item = None 
        self.doc: ezdxf.document.Drawing | None = None

    def draw_table(self, length: float, width: float, *, orientation: str):
        if self._table_item:
            self.scene().removeItem(self._table_item)

        w   = length if orientation == "front" else width
        h   = 50

        pen   = QPen(QColor("#CDCDCDFF"), 1); pen.setCosmetic(True)
        brush = QBrush(QColor("#333333"))
        self._table_item = self.scene().addRect(0, 0, w, -h, pen, brush)
        self._table_item.setZValue(-100)

        self.setSceneRect(-600, -500, 4500, 1000)
        self.fitInView(0, 0, 4000, 500, Qt.KeepAspectRatio)

    def load_doc(self, doc: ezdxf.document.Drawing):
        self.doc = doc
        scene = self.scene()
        Frontend(RenderContext(doc), PyQtBackend(scene)).draw_layout(doc.modelspace())
        # self.fitInView(self.sceneRect(), mode=1)

    def show_points(self, pts: list[Point]) -> None:
        DOT_R = 0.2                       # radius in model‑space units
        PEN    = QPen(QColor("#FFFF00"))  # outline
        BRUSH  = QBrush(QColor("#FFFF00"))  # fill
        PEN.setCosmetic(True)             # stays 1‑px on screen
        for x, y in pts:
            self.scene().addEllipse(
                QRectF(x - DOT_R, y - DOT_R, 2 * DOT_R, 2 * DOT_R),
                PEN,
                BRUSH,
            )

    def display_path(self, pts):
        """Draw blade rectangle where (x, y) is bottom‑left corner."""
        for itm in self._dot_items:
            self.scene().removeItem(itm)
        self._dot_items.clear()

        blade_w = config["tool_settings"]["blade_width"]
        blade_h = config["tool_settings"]["blade_diameter"]  # height downward

        pen   = self._pass_pen
        brush = self._dot_brush

        for x_left, y in pts:
            rect = QRectF(x_left, y, blade_w, blade_h)      # bottom‑left anchor
            item = self.scene().addRect(rect, pen, brush)
            item.setZValue(10)
            self._dot_items.append(item)
