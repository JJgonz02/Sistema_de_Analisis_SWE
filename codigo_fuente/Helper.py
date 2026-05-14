# Helper.py
# Tour guiado interactivo para la ventana principal.
# Muestra un overlay oscuro con un "hueco" alrededor del widget destacado,
# y un tooltip con título, descripción y botones de navegación.
#
# Uso:
#   tour = HelperTour(ventana_principal, lista_de_pasos)
#   tour.start()
#
# Cada paso es un dict con:
#   widget   : el QWidget a resaltar
#   title    : título corto del tooltip
#   body     : descripción larga (puede tener saltos de línea)
#   position : "auto" | "top" | "bottom" | "left" | "right"

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtCore    import Qt, QRect, QPoint
from PySide6.QtGui     import QPainter, QColor, QPen, QBrush, QPainterPath

# Constantes visuales del tour
_OVERLAY_COLOR = QColor(10, 14, 25, 200)   # fondo semitransparente oscuro
_ACCENT        = QColor(55, 138, 221)      # azul para el borde del widget destacado
_BORDER_COLOR  = QColor(42, 47, 69)        # color del borde del tooltip

_MARGIN  = 10   # margen alrededor del widget resaltado
_TIP_W   = 310  # ancho fijo del tooltip
_TIP_PAD = 16   # padding interno del tooltip
_ARROW   = 10   # tamaño de la flecha indicadora


# ──────────────────────────────────────────────────────────────────────────────
# Overlay con "hueco" transparente
# ──────────────────────────────────────────────────────────────────────────────

class _Overlay(QWidget):
    """
    Dibuja 4 bandas oscuras alrededor del widget resaltado,
    dejando esa zona completamente visible.
    Evita CompositionMode_Clear porque no funciona bien con ventanas padre.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(parent.rect())
        self._hole = QRect()

    def set_hole(self, rect: QRect):
        self._hole = rect
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        H = self.height()
        h = self._hole

        if h.isNull():
            p.fillRect(0, 0, W, H, _OVERLAY_COLOR)
        else:
            # Dibujamos las 4 bandas por separado, dejando el hueco libre
            if h.top() > 0:
                p.fillRect(0, 0, W, h.top(), _OVERLAY_COLOR)
            if h.bottom() < H:
                p.fillRect(0, h.bottom(), W, H - h.bottom(), _OVERLAY_COLOR)
            if h.left() > 0:
                p.fillRect(0, h.top(), h.left(), h.height(), _OVERLAY_COLOR)
            if h.right() < W:
                p.fillRect(h.right(), h.top(), W - h.right(), h.height(), _OVERLAY_COLOR)

            # Borde azul alrededor del widget destacado
            p.setPen(QPen(_ACCENT, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(h, 7, 7)

        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# Tooltip del tour
# ──────────────────────────────────────────────────────────────────────────────

class _TourTooltip(QWidget):

    def __init__(self, parent: QWidget, on_prev, on_next, on_close):
        super().__init__(parent)
        self.setFixedWidth(_TIP_W)
        self._arrow_side   = "bottom"
        self._arrow_offset = _TIP_W // 2
        self._construir_ui(on_prev, on_next, on_close)

    def _construir_ui(self, on_prev, on_next, on_close):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._card = QWidget(self)
        self._card.setStyleSheet("""
            QWidget {
                background-color: #161c2e;
                border: 1px solid #2a2f45;
                border-radius: 10px;
            }
        """)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(_TIP_PAD, _TIP_PAD, _TIP_PAD, _TIP_PAD)
        card_lay.setSpacing(8)

        # Fila de encabezado: título + botón de cerrar
        head_row = QHBoxLayout()
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #c8cfe8; "
            "background: transparent; border: none;"
        )
        self._title_lbl.setWordWrap(True)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #6a7290; border: none; font-size: 13px; }
            QPushButton:hover { color: #e05c5c; }
        """)
        close_btn.clicked.connect(on_close)

        head_row.addWidget(self._title_lbl, stretch=1)
        head_row.addWidget(close_btn, alignment=Qt.AlignTop)
        card_lay.addLayout(head_row)

        # Texto del cuerpo
        self._body_lbl = QLabel()
        self._body_lbl.setStyleSheet(
            "font-size: 11px; color: #9098b0; background: transparent; border: none;"
        )
        self._body_lbl.setWordWrap(True)
        card_lay.addWidget(self._body_lbl)

        # Separador
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2a2f45; border: none; border-radius: 0;")
        card_lay.addWidget(sep)

        # Navegación: contador + botones prev/next
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        nav_row.setContentsMargins(0, 4, 0, 0)

        self._step_lbl = QLabel()
        self._step_lbl.setStyleSheet(
            "font-size: 10px; color: #6a7290; background: transparent; border: none;"
        )

        self._prev_btn = QPushButton("← Anterior")
        self._prev_btn.setStyleSheet("""
            QPushButton { background:#1e2538; color:#9098b0; border:1px solid #2a2f45;
                          border-radius:5px; padding:4px 14px; font-size:11px; }
            QPushButton:hover { background:#252d45; color:#c8cfe8; }
            QPushButton:disabled { color:#3a4060; border-color:#1e2538; }
        """)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.clicked.connect(on_prev)

        self._next_btn = QPushButton("Siguiente →")
        self._next_btn.setStyleSheet("""
            QPushButton { background:#378ADD; color:white; border:1px solid #185FA5;
                          border-radius:5px; padding:4px 18px; font-size:11px; font-weight:bold; }
            QPushButton:hover { background:#185FA5; }
        """)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.clicked.connect(on_next)

        nav_row.addWidget(self._step_lbl)
        nav_row.addStretch()
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._next_btn)
        card_lay.addLayout(nav_row)

        outer.addWidget(self._card)
        self.adjustSize()

    def set_content(self, title: str, body: str, step: int, total: int):
        self._title_lbl.setText(title)
        self._body_lbl.setText(body)
        self._step_lbl.setText(f"{step} / {total}")
        self._prev_btn.setEnabled(step > 1)
        self._next_btn.setText("Finalizar" if step == total else "Siguiente →")
        self.adjustSize()

    def set_arrow(self, side: str, offset: int):
        self._arrow_side   = side
        self._arrow_offset = offset
        self.update()

    def paintEvent(self, _event):
        # Dibuja una pequeña flecha triangular apuntando al widget resaltado
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        a    = _ARROW
        s    = self._arrow_side
        r    = self._card.geometry()
        path = QPainterPath()

        if s == "bottom":
            ox = max(a * 2, min(self._arrow_offset, r.width() - a * 2))
            bx = r.left() + ox
            path.moveTo(bx - a, r.bottom())
            path.lineTo(bx,     r.bottom() + a)
            path.lineTo(bx + a, r.bottom())
        elif s == "top":
            ox = max(a * 2, min(self._arrow_offset, r.width() - a * 2))
            bx = r.left() + ox
            path.moveTo(bx - a, r.top())
            path.lineTo(bx,     r.top() - a)
            path.lineTo(bx + a, r.top())
        elif s == "right":
            oy = max(a * 2, min(self._arrow_offset, r.height() - a * 2))
            by = r.top() + oy
            path.moveTo(r.right(),     by - a)
            path.lineTo(r.right() + a, by)
            path.lineTo(r.right(),     by + a)
        elif s == "left":
            oy = max(a * 2, min(self._arrow_offset, r.height() - a * 2))
            by = r.top() + oy
            path.moveTo(r.left(),     by - a)
            path.lineTo(r.left() - a, by)
            path.lineTo(r.left(),     by + a)

        if not path.isEmpty():
            p.setPen(QPen(_BORDER_COLOR, 1))
            p.setBrush(QBrush(QColor("#161c2e")))
            p.drawPath(path)
        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# Controlador del tour
# ──────────────────────────────────────────────────────────────────────────────

class HelperTour:
    """
    Controla el flujo completo del tour: crea overlay y tooltip,
    gestiona la navegación entre pasos, y limpia todo al cerrar.
    """

    def __init__(self, window, steps: list[dict]):
        self._win    = window
        self._steps  = steps
        self._idx    = 0
        self._active = False
        self._overlay: _Overlay | None      = None
        self._tooltip: _TourTooltip | None  = None

    def start(self):
        if self._active:
            return
        self._active = True
        self._idx    = 0

        self._overlay = _Overlay(self._win)
        self._overlay.resize(self._win.size())
        self._overlay.show()
        self._overlay.raise_()

        self._tooltip = _TourTooltip(
            self._win,
            on_prev  = self._anterior,
            on_next  = self._siguiente,
            on_close = self.stop,
        )
        self._tooltip.raise_()
        self._tooltip.show()

        self._ir_a(0)

    def stop(self):
        if not self._active:
            return
        self._active = False
        for w in (self._overlay, self._tooltip):
            if w:
                w.hide()
                w.deleteLater()
        self._overlay = None
        self._tooltip = None

    def _anterior(self):
        if self._idx > 0:
            self._ir_a(self._idx - 1)

    def _siguiente(self):
        if self._idx < len(self._steps) - 1:
            self._ir_a(self._idx + 1)
        else:
            self.stop()

    def _ir_a(self, idx: int):
        self._idx = idx
        paso = self._steps[idx]

        self._overlay.resize(self._win.size())
        hueco = self._rect_widget_en_ventana(paso["widget"])
        self._overlay.set_hole(hueco)

        self._tooltip.set_content(
            paso["title"], paso["body"],
            idx + 1, len(self._steps),
        )
        self._posicionar_tooltip(hueco, paso.get("position", "auto"))

    def _rect_widget_en_ventana(self, widget: QWidget) -> QRect:
        """Obtiene el rectángulo del widget en coordenadas de la ventana principal."""
        tl = widget.mapTo(self._win, QPoint(0, 0))
        return QRect(
            tl.x() - _MARGIN,
            tl.y() - _MARGIN,
            widget.width()  + _MARGIN * 2,
            widget.height() + _MARGIN * 2,
        )

    def _posicionar_tooltip(self, hueco: QRect, posicion: str):
        """
        Coloca el tooltip en el mejor lado disponible alrededor del widget resaltado.
        Si posicion es "auto", elige el lado con más espacio libre.
        """
        win_w = self._win.width()
        win_h = self._win.height()
        tip_w = self._tooltip.width()
        tip_h = self._tooltip.height() + _ARROW

        if posicion == "auto":
            espacio = {
                "bottom": win_h - hueco.bottom(),
                "top"   : hueco.top(),
                "right" : win_w - hueco.right(),
                "left"  : hueco.left(),
            }
            posicion = max(espacio, key=espacio.get)

        gap = 14

        if posicion == "bottom":
            x, y = hueco.center().x() - tip_w // 2, hueco.bottom() + gap
            arrow_side, arrow_offset = "top",    tip_w // 2
        elif posicion == "top":
            x, y = hueco.center().x() - tip_w // 2, hueco.top() - tip_h - gap
            arrow_side, arrow_offset = "bottom", tip_w // 2
        elif posicion == "right":
            x, y = hueco.right() + gap, hueco.center().y() - tip_h // 2
            arrow_side, arrow_offset = "left",   tip_h // 2
        else:
            x, y = hueco.left() - tip_w - gap, hueco.center().y() - tip_h // 2
            arrow_side, arrow_offset = "right",  tip_h // 2

        # Asegurarse de que no se salga de la ventana
        x = max(8, min(x, win_w - tip_w - 8))
        y = max(8, min(y, win_h - tip_h - 8))

        if posicion in ("bottom", "top"):
            arrow_offset = hueco.center().x() - x
        else:
            arrow_offset = hueco.center().y() - y

        self._tooltip.set_arrow(arrow_side, arrow_offset)
        self._tooltip.move(x, y)
        self._tooltip.raise_()
