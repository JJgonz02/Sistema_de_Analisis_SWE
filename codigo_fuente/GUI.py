# GUI.py
# Ventana principal del visor de elastografía SWE.
#
# Tiene tres secciones en el panel izquierdo:
#   - Carga y análisis del archivo DICOM
#   - Información del archivo (metadatos)
#   - Modo de visualización (frame completo / elastograma / B-Mode)
#   - Historial de hasta MAX_HISTORY análisis en memoria
#
# En el panel derecho: visor de fotogramas + controles de reproducción.

import os
import time
import numpy as np
import pydicom
import sys


from PySide6.QtWidgets import (
    QMainWindow, QWidget,
    QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QSlider,
    QLineEdit, QProgressDialog, QProgressBar,
    QMessageBox, QButtonGroup,
    QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage

from worker_thread    import DicomLoaderThread
from analysis_worker  import AnalysisWorker
from analysis_window  import AnalysisWindow
from Helper           import HelperTour
from estilos import (
    DARK_BG, PANEL_BG, BORDER, ACCENT, TEXT_MAIN, TEXT_DIM, SUCCESS, DANGER,
    MAX_HISTORY,
    PANEL_STYLE, LABEL_TITLE_STYLE, LABEL_KEY_STYLE, LABEL_VAL_STYLE,
    TOGGLE_BASE, BTN_STYLE, ANALYZE_STYLE, PROGRESS_BAR_STYLE,
    HISTORY_CARD_NORMAL, HISTORY_CARD_ACTIVE,
)
from utils_ui import crear_separador, mostrar_array_en_label

# Constantes de modo de visualización
VIEW_FULL        = 0
VIEW_WITH_ELASTO = 1
VIEW_ELASTO_ONLY = 2
VIEW_MODO_B      = 3

# Utilidad para acceder a archivos incluidos en PyInstaller
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


# ──────────────────────────────────────────────────────────────────────────────
# Tarjeta del historial de análisis
# ──────────────────────────────────────────────────────────────────────────────
class HistoryCard(QWidget):
    """
    Muestra un análisis guardado de forma compacta.
    Doble clic → abre la ventana de resultados.
    Botón × → elimina la entrada del historial.
    """

    def __init__(self, index: int, meta: dict, on_open, on_delete, parent=None):
        super().__init__(parent)
        self.setObjectName("histCard")
        self.index      = index
        self._on_open   = on_open
        self._on_delete = on_delete
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(HISTORY_CARD_NORMAL)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(6)

        num_lbl = QLabel(f"#{index + 1}")
        num_lbl.setFixedWidth(22)
        num_lbl.setAlignment(Qt.AlignCenter)
        num_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {ACCENT}; "
            f"background: transparent; border: none;"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(meta["nombre"])
        name_lbl.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MAIN}; background: transparent; border: none;"
        )
        name_lbl.setWordWrap(False)

        detail_lbl = QLabel(
            f"{meta['hora']}  ·  {meta['n_frames']} frames  ·  "
            f"μ {meta['media']:.1f} kPa"
        )
        detail_lbl.setStyleSheet(
            f"font-size: 9px; color: {TEXT_DIM}; background: transparent; border: none;"
        )

        text_col.addWidget(name_lbl)
        text_col.addWidget(detail_lbl)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(18, 18)
        del_btn.setCursor(Qt.ArrowCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                border: none; font-size: 14px; padding: 0;
            }}
            QPushButton:hover {{ color: {DANGER}; }}
        """)
        del_btn.clicked.connect(lambda: self._on_delete(self.index))

        lay.addWidget(num_lbl)
        lay.addLayout(text_col, stretch=1)
        lay.addWidget(del_btn, alignment=Qt.AlignTop)

    def mouseDoubleClickEvent(self, event):
        self._on_open(self.index)
        super().mouseDoubleClickEvent(event)

    def set_active(self, active: bool):
        self.setStyleSheet(HISTORY_CARD_ACTIVE if active else HISTORY_CARD_NORMAL)
    



# ──────────────────────────────────────────────────────────────────────────────
# Ventana principal
# ──────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizador DICOM — Elastografía SWE")
        self.setStyleSheet(f"background-color: {DARK_BG}; color: {TEXT_MAIN};")

        # Estado del visor
        self.frames_full   = []
        self.frames_roi    = []
        self.frames_b      = []
        self.frames_e      = []
        self.roi_coords    = None
        self.has_roi       = False
        self.current_index = 0
        self.ds            = None
        self.current_view  = VIEW_FULL

        # Historial: lista de dicts con "resultado" y "meta"
        self._history: list[dict] = []
        self._active_card_idx: int | None = None
        self._analysis_windows: dict[int, AnalysisWindow] = {}

        # Reproducción
        self.timer = QTimer()
        self.timer.timeout.connect(self._avanzar_frame)
        self.is_playing   = False
        self.loop_enabled = False

        self._tour: HelperTour | None = None

        self._construir_ui()

    # ──────────────────────────────────────────────────────────────────
    # Construcción de la UI
    # ──────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        left_col.setContentsMargins(0, 0, 0, 0)

        # Panel de botones principales
        btn_panel = QWidget()
        btn_panel.setFixedWidth(230)
        btn_panel.setStyleSheet(PANEL_STYLE)
        btn_layout = QVBoxLayout(btn_panel)
        btn_layout.setContentsMargins(10, 10, 10, 10)
        btn_layout.setSpacing(8)

        self.load_button = QPushButton("📂  Cargar archivo DICOM")
        self.load_button.setFixedHeight(36)
        self.load_button.setStyleSheet(BTN_STYLE)
        self.load_button.clicked.connect(self._cargar_archivo)

        self.analyze_button = QPushButton("Analizar")
        self.analyze_button.setFixedHeight(36)
        self.analyze_button.setEnabled(False)
        self.analyze_button.setStyleSheet(ANALYZE_STYLE)
        self.analyze_button.clicked.connect(self._ejecutar_analisis)

        self.analysis_progress_bar = QProgressBar()
        self.analysis_progress_bar.setRange(0, 100)
        self.analysis_progress_bar.setValue(0)
        self.analysis_progress_bar.setFixedHeight(8)
        self.analysis_progress_bar.setTextVisible(False)
        self.analysis_progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        self.analysis_progress_bar.hide()

        self.analysis_status = QLabel("")
        self.analysis_status.setAlignment(Qt.AlignCenter)
        self.analysis_status.setStyleSheet(
            f"font-size: 11px; color: {SUCCESS}; background: transparent; border: none;"
        )

        btn_layout.addWidget(self.load_button)
        btn_layout.addWidget(self.analyze_button)
        btn_layout.addWidget(self.analysis_progress_bar)
        btn_layout.addWidget(self.analysis_status)
        btn_layout.addWidget(crear_separador())

        self.help_button = QPushButton("Ayuda")
        self.help_button.setFixedHeight(30)
        self.help_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #252b40;
                color: {ACCENT};
                border-color: {ACCENT};
            }}
        """)
        self.help_button.clicked.connect(self._iniciar_tour)
        btn_layout.addWidget(self.help_button)

        left_col.addWidget(btn_panel)

        # Panel de información del archivo
        info_panel = QWidget()
        info_panel.setFixedWidth(230)
        info_panel.setStyleSheet(PANEL_STYLE)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(0, 4, 0, 10)
        info_layout.setSpacing(0)

        info_title = QLabel("INFORMACIÓN DEL ARCHIVO")
        info_title.setStyleSheet(LABEL_TITLE_STYLE)
        info_layout.addWidget(info_title)
        info_layout.addWidget(crear_separador())

        self._info_fields = {}
        for key, label_text in [
            ("nombre",     "Nombre"),
            ("fabricante", "Fabricante"),
            ("filas",      "Filas"),
            ("columnas",   "Columnas"),
            ("fotogramas", "Fotogramas"),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)
            lbl_key = QLabel(f"{label_text}:")
            lbl_key.setStyleSheet(LABEL_KEY_STYLE)
            lbl_key.setFixedWidth(90)
            lbl_val = QLabel("—")
            lbl_val.setStyleSheet(LABEL_VAL_STYLE)
            lbl_val.setWordWrap(True)
            row.addWidget(lbl_key)
            row.addWidget(lbl_val, stretch=1)
            info_layout.addLayout(row)
            self._info_fields[key] = lbl_val

        left_col.addWidget(info_panel)

        # Panel de modo de visualización
        view_panel = QWidget()
        view_panel.setFixedWidth(230)
        view_panel.setStyleSheet(PANEL_STYLE)
        view_layout = QVBoxLayout(view_panel)
        view_layout.setContentsMargins(0, 4, 0, 10)
        view_layout.setSpacing(6)

        view_title = QLabel("MODO DE VISUALIZACIÓN")
        view_title.setStyleSheet(LABEL_TITLE_STYLE)
        view_layout.addWidget(view_title)
        view_layout.addWidget(crear_separador())

        view_inner = QVBoxLayout()
        view_inner.setContentsMargins(10, 6, 10, 0)
        view_inner.setSpacing(5)

        self._view_buttons = QButtonGroup(self)
        self._view_buttons.setExclusive(True)

        for view_id, label in [
            (VIEW_FULL,        "Frame completo"),
            (VIEW_WITH_ELASTO, "Con elastograma"),
            (VIEW_ELASTO_ONLY, "Solo elastograma"),
            (VIEW_MODO_B,      "Solo modo B"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(TOGGLE_BASE)
            btn.setFixedHeight(32)
            if view_id == VIEW_FULL:
                btn.setChecked(True)
            self._view_buttons.addButton(btn, view_id)
            view_inner.addWidget(btn)

        self._view_buttons.idClicked.connect(self._al_cambiar_vista)

        self._roi_note = QLabel("ℹ Sin ROI detectado")
        self._roi_note.setStyleSheet(
            f"font-size: 10px; color: {TEXT_DIM}; background: transparent; "
            f"border: none; padding: 4px 10px 0 10px;"
        )
        self._roi_note.setWordWrap(True)

        view_layout.addLayout(view_inner)
        view_layout.addWidget(self._roi_note)
        left_col.addWidget(view_panel)

        # Panel de historial de análisis
        history_panel = QWidget()
        history_panel.setFixedWidth(230)
        history_panel.setStyleSheet(PANEL_STYLE)
        hist_outer = QVBoxLayout(history_panel)
        hist_outer.setContentsMargins(0, 4, 0, 8)
        hist_outer.setSpacing(0)

        hist_head = QHBoxLayout()
        hist_head.setContentsMargins(10, 0, 8, 0)
        hist_head.setSpacing(4)
        hist_head_lbl = QLabel("HISTORIAL DE ANÁLISIS")
        hist_head_lbl.setStyleSheet(LABEL_TITLE_STYLE)
        self._hist_count_lbl = QLabel(f"0 / {MAX_HISTORY}")
        self._hist_count_lbl.setStyleSheet(
            f"font-size: 9px; color: {TEXT_DIM}; background: transparent; border: none;"
        )
        hist_head.addWidget(hist_head_lbl)
        hist_head.addStretch()
        hist_head.addWidget(self._hist_count_lbl)
        hist_outer.addLayout(hist_head)
        hist_outer.addWidget(crear_separador())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #12151f; width: 5px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #2a2f45; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent; border: none;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(6, 6, 6, 0)
        self._cards_layout.setSpacing(5)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_container)
        scroll.setFixedHeight(210)
        hist_outer.addWidget(scroll)

        hint = QLabel("Doble clic para abrir · × para eliminar")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            f"font-size: 9px; color: {TEXT_DIM}; background: transparent; "
            f"border: none; padding: 4px 0 0 0;"
        )
        hist_outer.addWidget(hint)

        left_col.addWidget(history_panel)
        left_col.addStretch()

        left_container = QWidget()
        left_container.setFixedWidth(230)
        left_container.setLayout(left_col)
        root.addWidget(left_container, alignment=Qt.AlignTop)

        # Columna derecha: visor + controles de reproducción
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self.file_name_label = QLabel("Ningún archivo cargado")
        self.file_name_label.setAlignment(Qt.AlignCenter)
        self.file_name_label.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {TEXT_MAIN}; "
            f"padding: 4px; background: transparent;"
        )
        right_col.addWidget(self.file_name_label)

        self.image_label = QLabel()
        self.image_label.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
        )
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(900, 650)
        right_col.addWidget(self.image_label, stretch=1)

        # Controles de reproducción
        ctrl_widget = QWidget()
        ctrl_widget.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; padding: 2px;"
        )
        ctrl_layout = QHBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(8, 4, 8, 4)
        ctrl_layout.setSpacing(6)

        nav_btn_style = f"""
            QPushButton {{
                background-color: #2a2f45; color: {TEXT_MAIN};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 3px 8px; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {ACCENT}; color: white; }}
            QPushButton:checked {{ background-color: {ACCENT}; color: white; }}
        """

        self.play_button = QPushButton("▶")
        self.play_button.setFixedWidth(36)
        self.play_button.setStyleSheet(nav_btn_style)
        self.play_button.clicked.connect(self._alternar_reproduccion)

        self.loop_button = QPushButton("↳↰")
        self.loop_button.setCheckable(True)
        self.loop_button.setFixedWidth(36)
        self.loop_button.setStyleSheet(nav_btn_style)
        self.loop_button.clicked.connect(self._alternar_loop)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.valueChanged.connect(self._al_mover_slider)

        self.prev_button = QPushButton("◀")
        self.prev_button.setFixedWidth(36)
        self.prev_button.setStyleSheet(nav_btn_style)
        self.prev_button.clicked.connect(self._frame_anterior)

        self.frame_input = QLineEdit()
        self.frame_input.setFixedWidth(55)
        self.frame_input.setAlignment(Qt.AlignCenter)
        self.frame_input.setStyleSheet(
            f"background: #2a2f45; color: {TEXT_MAIN}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 2px;"
        )
        self.frame_input.returnPressed.connect(self._saltar_a_frame)

        self.next_button = QPushButton("▶")
        self.next_button.setFixedWidth(36)
        self.next_button.setStyleSheet(nav_btn_style)
        self.next_button.clicked.connect(self._frame_siguiente)

        self.frame_label = QLabel("Fotograma: 0 / 0")
        self.frame_label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_DIM}; background: transparent; border: none;"
        )

        ctrl_layout.addWidget(self.play_button)
        ctrl_layout.addWidget(self.loop_button)
        ctrl_layout.addWidget(self.slider, stretch=1)
        ctrl_layout.addWidget(self.prev_button)
        ctrl_layout.addWidget(self.frame_input)
        ctrl_layout.addWidget(self.next_button)
        ctrl_layout.addWidget(self.frame_label)

        right_col.addWidget(ctrl_widget)
        root.addLayout(right_col, stretch=1)

    # ──────────────────────────────────────────────────────────────────
    # Carga del archivo
    # ──────────────────────────────────────────────────────────────────

    def _cargar_archivo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo DICOM", "", "All Files (*)"
        )
        if not file_path:
            return

        self.ds        = pydicom.dcmread(file_path)
        self.file_path = file_path

        # Limpiar estado anterior
        self.frames_full  = []
        self.frames_roi   = []
        self.roi_coords   = None
        self.has_roi      = False
        self.analysis_status.setText("")
        self.analysis_progress_bar.setValue(0)
        self.analysis_progress_bar.hide()
        self.analyze_button.setEnabled(False)

        self._actualizar_panel_info(file_path)

        self.progress_dialog = QProgressDialog(
            "Cargando DICOM y extrayendo ROIs...", None, 0, 100, self
        )
        self.progress_dialog.setWindowTitle("Procesando")
        self.progress_dialog.setModal(True)
        self.progress_dialog.show()

        self.loader_thread = DicomLoaderThread(file_path)
        self.loader_thread.progress.connect(self.progress_dialog.setValue)
        self.loader_thread.finished.connect(self._carga_terminada)
        self.loader_thread.start()

        self.file_name_label.setText(os.path.basename(file_path))

    def _actualizar_panel_info(self, file_path: str):
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        self._info_fields["nombre"].setText(os.path.basename(file_path))
        self._info_fields["fabricante"].setText(str(ds.get("Manufacturer", "—")))
        self._info_fields["filas"].setText(str(ds.get("Rows", "—")))
        self._info_fields["columnas"].setText(str(ds.get("Columns", "—")))
        self._info_fields["fotogramas"].setText(str(ds.get("NumberOfFrames", "1")))

    def _carga_terminada(self, data: dict):
        self.progress_dialog.close()

        self.frames_full = data["frames_full"]
        self.frames_roi  = data["frames_roi"]
        self.roi_coords  = data["roi_coords"]
        self.has_roi     = data["has_roi"]
        self.frames_b    = data["frames_B"]
        self.frames_e    = data["frames_SWE"]

        if not self.frames_full:
            return

        total = len(self.frames_full)
        self.slider.setMaximum(total - 1)
        self.slider.setValue(0)
        self.current_index = 0

        if self.has_roi:
            x0, y0, x1, y1 = self.roi_coords
            self._roi_note.setText(f"✓ ROI detectado\n({x1-x0}×{y1-y0} px)")
            self._roi_note.setStyleSheet(
                f"font-size: 10px; color: {SUCCESS}; background: transparent; "
                f"border: none; padding: 4px 10px 0 10px;"
            )
        else:
            self._roi_note.setText("⚠ Sin ROI en metadatos.\nModos 2 y 3 no disponibles.")
            self._view_buttons.button(VIEW_WITH_ELASTO).setEnabled(False)
            self._view_buttons.button(VIEW_ELASTO_ONLY).setEnabled(False)
            self._view_buttons.button(VIEW_FULL).setChecked(True)
            self.current_view = VIEW_FULL

        self._mostrar_frame_actual()
        self._actualizar_info_frame()
        self.analyze_button.setEnabled(True)

    # ──────────────────────────────────────────────────────────────────
    # Visualización
    # ──────────────────────────────────────────────────────────────────

    def _obtener_frame_para_mostrar(self, idx: int):
        if not self.frames_full:
            return None
        frame = self.frames_full[idx]
        if   self.current_view == VIEW_FULL:
            return frame
        elif self.current_view == VIEW_WITH_ELASTO:
            return self.frames_e[idx] if self.has_roi else frame
        elif self.current_view == VIEW_ELASTO_ONLY:
            return self.frames_roi[idx] if (self.has_roi and self.frames_roi) else frame
        elif self.current_view == VIEW_MODO_B:
            return self.frames_b[idx]
        return frame

    def _mostrar_frame_actual(self):
        arr = self._obtener_frame_para_mostrar(self.current_index)
        if arr is not None:
            mostrar_array_en_label(arr, self.image_label)

    def _al_cambiar_vista(self, view_id: int):
        self.current_view = view_id
        self._mostrar_frame_actual()

    # ──────────────────────────────────────────────────────────────────
    # Análisis
    # ──────────────────────────────────────────────────────────────────

    def _ejecutar_analisis(self):
        if self.ds is None:
            return

        lut_path = resource_path("lut.npy")

        if not hasattr(self.ds, "SequenceOfUltrasoundRegions"):
            QMessageBox.critical(
                self, "Error",
                "El archivo DICOM no contiene SequenceOfUltrasoundRegions.\n"
                "No es posible detectar el ROI automáticamente."
            )
            return

        if len(self._history) >= MAX_HISTORY:
            resp = QMessageBox.question(
                self, "Historial lleno",
                f"El historial ya tiene {MAX_HISTORY} análisis guardados.\n"
                "Se eliminará el más antiguo para guardar el nuevo.\n¿Continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if resp != QMessageBox.Yes:
                return

        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("Analizando…")
        self.analysis_status.setText("")
        self.analysis_progress_bar.setValue(0)
        self.analysis_progress_bar.show()

        self._current_analysis_file = os.path.basename(
            getattr(self, "file_path", "desconocido")
        )

        self.analysis_worker = AnalysisWorker(self.ds, lut_path)
        self.analysis_worker.progress.connect(self._al_progreso_analisis)
        self.analysis_worker.finished.connect(self._analisis_terminado)
        self.analysis_worker.start()

    def _al_progreso_analisis(self, value: int):
        self.analysis_progress_bar.setValue(value)
        self.analysis_status.setText(f"{value}%")
        self.analysis_status.setStyleSheet(
            f"font-size: 11px; color: {TEXT_DIM}; background: transparent; border: none;"
        )

    def _analisis_terminado(self, resultado: dict):
        self.analysis_progress_bar.hide()
        self.analyze_button.setText("Analizar")
        self.analyze_button.setEnabled(True)

        hora = time.strftime("%H:%M")
        self.analysis_status.setText(f"✓  Análisis: {hora}")
        self.analysis_status.setStyleSheet(
            f"font-size: 11px; color: {SUCCESS}; background: transparent; border: none;"
        )

        sg   = resultado["stats_globales"]
        meta = {
            "nombre"  : self._current_analysis_file,
            "hora"    : hora,
            "n_frames": resultado["n_frames"],
            "media"   : sg["media"],
        }

        if len(self._history) >= MAX_HISTORY:
            self._eliminar_entrada_historial(0)

        nuevo_idx = len(self._history)
        self._history.append({"resultado": resultado, "meta": meta})
        self._insertar_tarjeta_historial(nuevo_idx, meta)
        self._actualizar_contador_historial()
        self._abrir_ventana_analisis(nuevo_idx)

    # ──────────────────────────────────────────────────────────────────
    # Gestión del historial
    # ──────────────────────────────────────────────────────────────────

    def _insertar_tarjeta_historial(self, idx: int, meta: dict):
        card = HistoryCard(
            index=idx, meta=meta,
            on_open=self._abrir_ventana_analisis,
            on_delete=self._eliminar_entrada_historial,
        )
        pos = self._cards_layout.count() - 1  # antes del stretch final
        self._cards_layout.insertWidget(pos, card)

    def _reconstruir_tarjetas_historial(self):
        """Elimina y recrea todas las tarjetas. Se llama después de borrar una entrada."""
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, entry in enumerate(self._history):
            self._insertar_tarjeta_historial(i, entry["meta"])

        self._actualizar_contador_historial()

    def _abrir_ventana_analisis(self, idx: int):
        """
        Abre la ventana de resultados para el índice indicado.
        Si ya estaba abierta, simplemente la trae al frente.
        """
        if idx < 0 or idx >= len(self._history):
            return

        self._marcar_tarjeta_activa(idx)

        win = self._analysis_windows.get(idx)
        if win is not None and win.isVisible():
            win.raise_()
            win.activateWindow()
            return

        resultado = self._history[idx]["resultado"]
        meta      = self._history[idx]["meta"]

        win = AnalysisWindow(resultado)
        win.setWindowTitle(
            f"Análisis #{idx + 1} — {meta['nombre']}  ({meta['hora']})"
        )
        self._analysis_windows[idx] = win
        win.show()

    def _eliminar_entrada_historial(self, idx: int):
        if idx < 0 or idx >= len(self._history):
            return

        win = self._analysis_windows.pop(idx, None)
        if win is not None:
            win.close()

        # Re-indexar el dict de ventanas (los índices mayores bajan 1)
        actualizado = {}
        for k, v in self._analysis_windows.items():
            actualizado[k - 1 if k > idx else k] = v
        self._analysis_windows = actualizado

        self._history.pop(idx)

        if self._active_card_idx is not None:
            if self._active_card_idx == idx:
                self._active_card_idx = None
            elif self._active_card_idx > idx:
                self._active_card_idx -= 1

        self._reconstruir_tarjetas_historial()

        if self._active_card_idx is not None:
            self._marcar_tarjeta_activa(self._active_card_idx)

    def _marcar_tarjeta_activa(self, idx: int):
        self._active_card_idx = idx
        for i in range(self._cards_layout.count()):
            item = self._cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), HistoryCard):
                card = item.widget()
                card.set_active(card.index == idx)

    def _actualizar_contador_historial(self):
        self._hist_count_lbl.setText(f"{len(self._history)} / {MAX_HISTORY}")

    # ──────────────────────────────────────────────────────────────────
    # Controles de reproducción
    # ──────────────────────────────────────────────────────────────────

    def _al_mover_slider(self, value: int):
        if not self.frames_full:
            return
        self.current_index = value
        self._mostrar_frame_actual()
        self._actualizar_info_frame()

    def _actualizar_info_frame(self):
        total = len(self.frames_full)
        self.frame_label.setText(f"Frame: {self.current_index + 1} / {total}")
        self.frame_input.setText(str(self.current_index + 1))

    def _saltar_a_frame(self):
        try:
            value = int(self.frame_input.text()) - 1
            if 0 <= value < len(self.frames_full):
                self.slider.setValue(value)
        except ValueError:
            pass

    def _alternar_reproduccion(self):
        if not self.frames_full:
            return
        if self.is_playing:
            self.timer.stop()
            self.play_button.setText("▶")
            self.is_playing = False
        else:
            if self.current_index == len(self.frames_full) - 1 and not self.loop_enabled:
                self.current_index = 0
                self.slider.setValue(0)
            self.timer.start(1000 // 24)
            self.play_button.setText("■")
            self.is_playing = True

    def _avanzar_frame(self):
        if not self.frames_full:
            return
        if self.current_index < len(self.frames_full) - 1:
            self.slider.setValue(self.current_index + 1)
        else:
            if self.loop_enabled:
                self.slider.setValue(0)
            else:
                self.timer.stop()
                self.play_button.setText("▶")
                self.is_playing = False

    def _alternar_loop(self):
        self.loop_enabled = self.loop_button.isChecked()

    def _frame_anterior(self):
        if self.current_index > 0:
            self.slider.setValue(self.current_index - 1)

    def _frame_siguiente(self):
        if self.current_index < len(self.frames_full) - 1:
            self.slider.setValue(self.current_index + 1)

    # ──────────────────────────────────────────────────────────────────
    # Tour guiado
    # ──────────────────────────────────────────────────────────────────

    def _pasos_tour(self) -> list[dict]:
        return [
            {
                "widget"  : self.load_button,
                "title"   : "Cargar archivo DICOM",
                "body"    : (
                    "Haz clic aquí para abrir el explorador de archivos "
                    "y seleccionar un archivo DICOM de elastografía SWE. "
                    "El visor extraerá automáticamente los fotogramas y el ROI."
                ),
                "position": "right",
            },
            {
                "widget"  : self.analyze_button,
                "title"   : "Información del archivo",
                "body"    : (
                    "Tras cargar el DICOM, aquí aparecen los metadatos clave: "
                    "nombre del archivo, fabricante del equipo, dimensiones "
                    "de los fotogramas y número total de fotogramas."
                ),
                "position": "right",
            },
            {
                "widget"  : self._view_buttons.button(0),
                "title"   : "Modos de visualización",
                "body"    : (
                    "Cambia entre cuatro vistas:\n"
                    "· Frame completo — imagen original del ecógrafo.\n"
                    "· Con elastograma — imagen con la región SWE.\n"
                    "· Solo elastograma — únicamente el mapa de color SWE.\n"
                    "· Solo modo B — ultrasonido en escala de grises."
                ),
                "position": "right",
            },
            {
                "widget"  : self.image_label,
                "title"   : "Visor de fotogramas",
                "body"    : (
                    "Aquí se muestra el fotograma actual según el modo "
                    "de visualización seleccionado. La imagen se escala "
                    "automáticamente manteniendo la proporción original."
                ),
                "position": "left",
            },
            {
                "widget"  : self.slider,
                "title"   : "Control de navegación",
                "body"    : (
                    "Arrastra el slider para moverte entre fotogramas. "
                    "Usa ◀ / ▶ para ir de uno en uno, o escribe el número "
                    "de fotograma directamente en el campo central."
                ),
                "position": "top",
            },
            {
                "widget"  : self.analyze_button,
                "title"   : "Analizar el video",
                "body"    : (
                    "Lanza el análisis completo en segundo plano. "
                    "Extrae el ROI SWE frame a frame y convierte cada píxel a kPa "
                    "mediante la LUT de calibración. La barra de progreso "
                    "indica el avance en tiempo real."
                ),
                "position": "right",
            },
            {
                "widget"  : self._cards_container,
                "title"   : "Historial de análisis",
                "body"    : (
                    f"Cada análisis completado se guarda aquí (máximo {MAX_HISTORY}). "
                    "Doble clic en una tarjeta para abrir sus resultados. "
                    "El botón × elimina la entrada del historial."
                ),
                "position": "right",
            },
        ]

    def _iniciar_tour(self):
        if self._tour is not None:
            self._tour.stop()

        steps = self._pasos_tour()

        # Intentamos apuntar al panel de información completo subiendo
        # desde el campo "nombre" hasta encontrar un widget suficientemente ancho
        nombre_lbl = self._info_fields["nombre"]
        info_panel = nombre_lbl
        for _ in range(5):
            p = info_panel.parentWidget()
            if p is None:
                break
            info_panel = p
            if info_panel.width() > 150:
                break
        steps[1]["widget"] = info_panel

        self._tour = HelperTour(self, steps)
        self._tour.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._tour is not None and self._tour._active:
            self._tour._overlay.resize(self.size())
            self._tour._ir_a(self._tour._idx)
