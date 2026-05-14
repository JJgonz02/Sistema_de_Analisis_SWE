# utils_ui.py
# Pequeñas funciones de utilidad para la interfaz gráfica.
# Se usan en GUI.py y en analysis_window.py por igual.

import numpy as np
from PySide6.QtWidgets import QFrame, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage

from estilos import BORDER


def crear_separador() -> QFrame:
    """Línea horizontal de un píxel para separar secciones en los paneles."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(
        f"color: {BORDER}; background: {BORDER}; border: none; max-height: 1px;"
    )
    return line


def mostrar_array_en_label(arr: np.ndarray, label: QLabel):
    """
    Dibuja un array numpy como imagen dentro de un QLabel.
    Acepta arrays 2D (escala de grises) o 3D (RGB).
    La imagen se escala para caber en el label manteniendo la proporción.
    """
    if arr is None:
        label.clear()
        return

    arr = np.ascontiguousarray(arr)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)

    h, w, ch = arr.shape
    qimg = QImage(arr.data, w, h, w * ch, QImage.Format_RGB888)
    pix  = QPixmap.fromImage(qimg)
    label.setPixmap(
        pix.scaled(label.width(), label.height(),
                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
    )
