# analysis_window.py
# Ventana de resultados que se abre al completar un análisis.
# Tiene dos pestañas en el panel izquierdo:
#   - "Por fotograma": ROI, máscara, histograma y tabla de stats del frame actual
#   - "Análisis global": mapa medio, mapa std, histograma global,
#                        evolución temporal y cobertura por frame

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton,
    QLineEdit, QSizePolicy, QStackedWidget,
    QButtonGroup,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage

from estilos import (
    DARK_BG, PANEL_BG, PANEL_DEEP, BORDER, ACCENT, TEXT_MAIN, TEXT_DIM,
    TAB_ACTIVE, TAB_INACTIVE, NAV_BTN,
)
from utils_ui import crear_separador


TAB_FRAME  = 0
TAB_GLOBAL = 1


class AnalysisWindow(QWidget):

    def __init__(self, resultado: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis de elastografía")
        self.setMinimumSize(1300, 820)
        self.setStyleSheet(f"background-color: {DARK_BG}; color: {TEXT_MAIN};")

        self.resultado  = resultado
        self.n_frames   = resultado["n_frames"]
        self.is_playing = False

        self.timer = QTimer()
        self.timer.timeout.connect(self._siguiente_frame)

        self._construir_ui()
        self._actualizar_frame(0)

    # ──────────────────────────────────────────────────────────────────
    # Construcción de la UI
    # ──────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Panel izquierdo: pestañas + metadatos rápidos
        panel_izq = QWidget()
        panel_izq.setFixedWidth(155)
        panel_izq.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
        )
        lay_izq = QVBoxLayout(panel_izq)
        lay_izq.setContentsMargins(8, 10, 8, 10)
        lay_izq.setSpacing(6)

        # Botones de pestaña
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_btns  = {}

        for tab_id, titulo, subtitulo in [
            (TAB_FRAME,  "Por fotograma",   "frame a frame"),
            (TAB_GLOBAL, "Análisis global", "video completo"),
        ]:
            btn = QPushButton(f"{titulo}\n{subtitulo}")
            btn.setCheckable(True)
            btn.setFixedHeight(48)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._tab_group.addButton(btn, tab_id)
            lay_izq.addWidget(btn)
            self._tab_btns[tab_id] = btn

        self._tab_btns[TAB_FRAME].setChecked(True)
        self._aplicar_estilos_pestanas()
        self._tab_group.idClicked.connect(self._al_cambiar_pestana)

        lay_izq.addWidget(crear_separador())

        # Datos rápidos globales en el panel lateral
        sg = self.resultado["stats_globales"]
        for etiqueta, valor in [
            ("FRAMES",        str(self.n_frames)),
            ("MEDIA GLOBAL",  f"{sg['media']:.1f} kPa"),
            ("MEDIANA",       f"{sg['mediana']:.1f} kPa"),
            ("COBERTURA MED.",f"{sg['cobertura_media']:.1f}%"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(1)
            k = QLabel(etiqueta)
            k.setStyleSheet(
                f"font-size: 9px; color: {TEXT_DIM}; background: transparent; border: none;"
            )
            k.setAlignment(Qt.AlignCenter)
            v = QLabel(valor)
            v.setStyleSheet(
                f"font-size: 10px; color: {TEXT_MAIN}; background: transparent; border: none;"
            )
            v.setAlignment(Qt.AlignCenter)
            v.setWordWrap(True)
            col.addWidget(k)
            col.addWidget(v)
            lay_izq.addLayout(col)

        lay_izq.addStretch()
        root.addWidget(panel_izq, alignment=Qt.AlignTop)

        # Panel derecho: contenido de la pestaña activa
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
        )
        self._stack.addWidget(self._construir_pestana_frame())   # índice 0
        self._stack.addWidget(self._construir_pestana_global())  # índice 1
        root.addWidget(self._stack, stretch=1)

    # ──────────────────────────────────────────────────────────────────
    # Pestaña "Por fotograma"
    # ──────────────────────────────────────────────────────────────────

    def _construir_pestana_frame(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # Fila de imágenes: ROI original y máscara de píxeles válidos
        fila_imgs = QHBoxLayout()
        fila_imgs.setSpacing(8)

        def _col_imagen(titulo: str):
            col = QVBoxLayout()
            col.setSpacing(3)
            ttl = QLabel(titulo)
            ttl.setAlignment(Qt.AlignCenter)
            ttl.setStyleSheet(
                f"font-size: 11px; color: {TEXT_DIM}; background: transparent; border: none;"
            )
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"background-color: {PANEL_DEEP}; border-radius: 6px;")
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            col.addWidget(ttl)
            col.addWidget(lbl)
            return col, lbl

        col_roi,  self.roi_label  = _col_imagen("ROI original (SWE)")
        col_mask, self.mask_label = _col_imagen("Máscara — píxeles válidos")
        fila_imgs.addLayout(col_roi,  stretch=1)
        fila_imgs.addLayout(col_mask, stretch=1)
        lay.addLayout(fila_imgs, stretch=3)

        # Controles de navegación
        fila_nav = QHBoxLayout()
        fila_nav.setSpacing(6)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(36)
        self.play_btn.setStyleSheet(NAV_BTN)
        self.play_btn.clicked.connect(self._alternar_reproduccion)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.n_frames - 1)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._al_mover_slider)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedWidth(36)
        self.prev_btn.setStyleSheet(NAV_BTN)
        self.prev_btn.clicked.connect(self._frame_anterior)

        self.frame_input = QLineEdit("1")
        self.frame_input.setFixedWidth(55)
        self.frame_input.setAlignment(Qt.AlignCenter)
        self.frame_input.setStyleSheet(
            f"background: #2a2f45; color: {TEXT_MAIN}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self.frame_input.returnPressed.connect(self._saltar_a_frame)

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedWidth(36)
        self.next_btn.setStyleSheet(NAV_BTN)
        self.next_btn.clicked.connect(self._siguiente_frame)

        self.frame_lbl = QLabel(f"/ {self.n_frames}")
        self.frame_lbl.setStyleSheet(
            f"font-size: 11px; color: {TEXT_DIM}; background: transparent; border: none;"
        )

        fila_nav.addWidget(self.play_btn)
        fila_nav.addWidget(self.slider, stretch=1)
        fila_nav.addWidget(self.prev_btn)
        fila_nav.addWidget(self.frame_input)
        fila_nav.addWidget(self.next_btn)
        fila_nav.addWidget(self.frame_lbl)
        lay.addLayout(fila_nav)

        # Fila inferior: histograma + tabla de estadísticas del frame
        fila_inf = QHBoxLayout()
        fila_inf.setSpacing(8)
        self._frame_stats_container = QVBoxLayout()
        fila_inf.addLayout(self._frame_stats_container, stretch=1)
        lay.addLayout(fila_inf, stretch=2)

        self._frame_stats_canvas = None
        return w

    # ──────────────────────────────────────────────────────────────────
    # Pestaña "Análisis global"
    # ──────────────────────────────────────────────────────────────────

    def _construir_pestana_global(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(0)
        lay.addWidget(self._construir_figura_global())
        return w

    def _construir_figura_global(self) -> FigureCanvas:
        r  = self.resultado
        sg = r["stats_globales"]

        fig = plt.figure(figsize=(14, 8), facecolor="#0f1117")
        gs  = fig.add_gridspec(2, 4, left=0.06, right=0.97,
                               top=0.91, bottom=0.09,
                               hspace=0.42, wspace=0.35)

        ax_medio = fig.add_subplot(gs[0, 0])
        ax_std   = fig.add_subplot(gs[0, 1])
        ax_hist  = fig.add_subplot(gs[0, 2:])
        ax_temp  = fig.add_subplot(gs[1, :2])
        ax_cob   = fig.add_subplot(gs[1, 2:])

        txt = dict(color=TEXT_MAIN, fontsize=9)

        # Mapa de rigidez media (promedio temporal de todos los frames)
        im1 = ax_medio.imshow(r["mapa_medio"], cmap="jet", vmin=0, vmax=300, aspect="auto")
        cb1 = plt.colorbar(im1, ax=ax_medio, shrink=0.85)
        cb1.set_label("kPa", color=TEXT_MAIN, fontsize=8)
        plt.setp(cb1.ax.yaxis.get_ticklabels(), color=TEXT_MAIN, fontsize=7)
        ax_medio.set_title("Rigidez media espacial", color=TEXT_MAIN, fontsize=10)
        ax_medio.axis("off")

        # Mapa de variabilidad temporal (std entre frames)
        im2 = ax_std.imshow(r["mapa_std"], cmap="hot", aspect="auto")
        cb2 = plt.colorbar(im2, ax=ax_std, shrink=0.85)
        cb2.set_label("kPa", color=TEXT_MAIN, fontsize=8)
        plt.setp(cb2.ax.yaxis.get_ticklabels(), color=TEXT_MAIN, fontsize=7)
        ax_std.set_title("Variabilidad temporal (std)", color=TEXT_MAIN, fontsize=10)
        ax_std.axis("off")

        # Histograma global de todos los kPa válidos
        todos = r["volumen_kpa"][~np.isnan(r["volumen_kpa"])]
        bins  = np.linspace(0, 300, 60)
        ax_hist.hist(todos, bins=bins, color=ACCENT, edgecolor="none", alpha=0.85)
        ax_hist.axvline(sg["media"],   color="#FFB800", lw=1.5,
                        label=f"Media: {sg['media']:.1f} kPa")
        ax_hist.axvline(sg["mediana"], color="#ff4f7b", lw=1.5, ls="--",
                        label=f"Mediana: {sg['mediana']:.1f} kPa")
        ax_hist.axvspan(sg["p25"], sg["p75"], alpha=0.15, color="#FFB800",
                        label=f"IQR: {sg['p25']:.1f}–{sg['p75']:.1f} kPa")
        ax_hist.axvline(sg["p90"], color="#00e5ff", lw=1.2, ls=":",
                        label=f"P90: {sg['p90']:.1f} kPa")
        ax_hist.set_xlabel("Rigidez (kPa)", **txt)
        ax_hist.set_ylabel("Frecuencia",    **txt)
        ax_hist.set_title(
            f"Distribución global — {r['n_frames']} fotogramas",
            color=TEXT_MAIN, fontsize=10
        )
        ax_hist.set_facecolor(PANEL_DEEP)
        ax_hist.tick_params(colors=TEXT_DIM, labelsize=8)
        ax_hist.legend(fontsize=8, facecolor=PANEL_DEEP, edgecolor=BORDER, labelcolor=TEXT_MAIN)
        ax_hist.set_xlim(0, 300)
        for sp in ax_hist.spines.values(): sp.set_edgecolor(BORDER)

        # Evolución temporal: media ± std por frame
        nf  = r["n_frames"]
        eje = np.arange(nf)
        mpf = r["media_por_frame"]
        spf = r["std_por_frame"]
        ax_temp.plot(eje, mpf, color=ACCENT, lw=1.2, label="Media")
        ax_temp.fill_between(eje, mpf - spf, mpf + spf,
                             alpha=0.2, color=ACCENT, label="±1 std")
        ax_temp.axhline(sg["media"], color="#FFB800", lw=1, ls="--",
                        label=f"Media global: {sg['media']:.1f} kPa")
        ax_temp.set_xlabel("Fotograma", **txt)
        ax_temp.set_ylabel("kPa",       **txt)
        ax_temp.set_title("Evolución temporal", color=TEXT_MAIN, fontsize=10)
        ax_temp.set_facecolor(PANEL_DEEP)
        ax_temp.tick_params(colors=TEXT_DIM, labelsize=8)
        ax_temp.legend(fontsize=8, facecolor=PANEL_DEEP, edgecolor=BORDER, labelcolor=TEXT_MAIN)
        ax_temp.set_xlim(0, nf - 1)
        for sp in ax_temp.spines.values(): sp.set_edgecolor(BORDER)

        # Cobertura por frame: porcentaje de píxeles válidos
        ax_cob.plot(eje, r["cobertura_frames"], color="#00e5ff", lw=1.2)
        ax_cob.axhline(sg["cobertura_media"], color="#FFB800", lw=1, ls="--",
                       label=f"Media: {sg['cobertura_media']:.1f}%")
        ax_cob.set_xlabel("Fotograma",     **txt)
        ax_cob.set_ylabel("Cobertura (%)", **txt)
        ax_cob.set_title("Cobertura válida por fotograma", color=TEXT_MAIN, fontsize=10)
        ax_cob.set_facecolor(PANEL_DEEP)
        ax_cob.tick_params(colors=TEXT_DIM, labelsize=8)
        ax_cob.legend(fontsize=8, facecolor=PANEL_DEEP, edgecolor=BORDER, labelcolor=TEXT_MAIN)
        ax_cob.set_xlim(0, nf - 1)
        ax_cob.set_ylim(0, 100)
        for sp in ax_cob.spines.values(): sp.set_edgecolor(BORDER)

        fig.suptitle("Análisis completo — Elastografía SWE", color="#e0e4f0", fontsize=13)

        canvas = FigureCanvas(fig)
        plt.close(fig)
        return canvas

    # ──────────────────────────────────────────────────────────────────
    # Actualización del frame actual
    # ──────────────────────────────────────────────────────────────────

    def _actualizar_frame(self, idx: int):
        r = self.resultado

        self._dibujar_en_label(self.roi_label, r["volumen_roi"][idx])

        mask = r["volumen_mask"][idx].astype(np.uint8) * 255
        self._dibujar_en_label(self.mask_label, np.stack([mask, mask, mask], axis=-1))

        self.frame_input.setText(str(idx + 1))

        kpa     = r["volumen_kpa"][idx]
        validos = kpa[~np.isnan(kpa)]
        stats   = {}
        if len(validos) > 0:
            stats = {
                "media"    : float(np.nanmean(kpa)),
                "mediana"  : float(np.nanmedian(kpa)),
                "std"      : float(np.nanstd(kpa)),
                "p25"      : float(np.nanpercentile(kpa, 25)),
                "p75"      : float(np.nanpercentile(kpa, 75)),
                "cobertura": float(100 * len(validos) / kpa.size),
            }
        self._redibujar_stats_frame(kpa, stats)

    def _redibujar_stats_frame(self, kpa: np.ndarray, stats: dict):
        """Regenera el panel de histograma + tabla para el frame actual."""
        if self._frame_stats_canvas is not None:
            self._frame_stats_container.removeWidget(self._frame_stats_canvas)
            self._frame_stats_canvas.deleteLater()
            self._frame_stats_canvas = None

        fig, axes = plt.subplots(1, 2, figsize=(9, 2.8), facecolor=DARK_BG)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.85, bottom=0.18, wspace=0.35)
        txt = dict(color=TEXT_MAIN, fontsize=8)

        ax_h = axes[0]
        validos = kpa[~np.isnan(kpa)]
        if len(validos) > 0:
            ax_h.hist(validos, bins=np.linspace(0, 300, 40),
                      color=ACCENT, edgecolor="none", alpha=0.85)
            ax_h.axvline(stats["media"],   color="#FFB800", lw=1.3,
                         label=f"μ = {stats['media']:.1f} kPa")
            ax_h.axvline(stats["mediana"], color="#ff4f7b", lw=1.3, ls="--",
                         label=f"med = {stats['mediana']:.1f} kPa")
            ax_h.axvspan(stats["p25"], stats["p75"],
                         alpha=0.15, color="#FFB800",
                         label=f"IQR {stats['p25']:.1f}–{stats['p75']:.1f}")
        ax_h.set_xlabel("kPa", **txt)
        ax_h.set_ylabel("px",  **txt)
        ax_h.set_title("Distribución — frame actual", color=TEXT_MAIN, fontsize=9)
        ax_h.set_facecolor(PANEL_DEEP)
        ax_h.tick_params(colors=TEXT_DIM, labelsize=7)
        ax_h.set_xlim(0, 300)
        if len(validos) > 0:
            ax_h.legend(fontsize=7, facecolor=PANEL_DEEP, edgecolor=BORDER, labelcolor=TEXT_MAIN)
        for sp in ax_h.spines.values(): sp.set_edgecolor(BORDER)

        # Tabla de estadísticas numéricas
        ax_t = axes[1]
        ax_t.axis("off")
        ax_t.set_facecolor(PANEL_DEEP)
        if stats:
            filas = [
                ["Métrica",   "Valor"],
                ["Media",     f"{stats['media']:.1f} kPa"],
                ["Mediana",   f"{stats['mediana']:.1f} kPa"],
                ["Std",       f"{stats['std']:.1f} kPa"],
                ["P25",       f"{stats['p25']:.1f} kPa"],
                ["P75",       f"{stats['p75']:.1f} kPa"],
                ["Cobertura", f"{stats['cobertura']:.1f}%"],
            ]
            tabla = ax_t.table(cellText=filas[1:], colLabels=filas[0],
                               loc="center", cellLoc="center")
            tabla.auto_set_font_size(False)
            tabla.set_fontsize(8)
            for (row, col), cell in tabla.get_celld().items():
                cell.set_facecolor(PANEL_DEEP if row > 0 else BORDER)
                cell.set_text_props(color=TEXT_MAIN)
                cell.set_edgecolor(BORDER)
        ax_t.set_title("Estadísticas del frame", color=TEXT_MAIN, fontsize=9)

        canvas = FigureCanvas(fig)
        plt.close(fig)
        self._frame_stats_container.addWidget(canvas)
        self._frame_stats_canvas = canvas

    # ──────────────────────────────────────────────────────────────────
    # Controles de navegación
    # ──────────────────────────────────────────────────────────────────

    def _al_mover_slider(self, value: int):
        self._actualizar_frame(value)

    def _frame_anterior(self):
        v = self.slider.value()
        if v > 0:
            self.slider.setValue(v - 1)

    def _siguiente_frame(self):
        v = self.slider.value()
        if v < self.n_frames - 1:
            self.slider.setValue(v + 1)
        elif self.is_playing:
            self._detener_reproduccion()

    def _saltar_a_frame(self):
        try:
            idx = int(self.frame_input.text()) - 1
            if 0 <= idx < self.n_frames:
                self.slider.setValue(idx)
        except ValueError:
            pass

    def _alternar_reproduccion(self):
        if self.is_playing:
            self._detener_reproduccion()
        else:
            if self.slider.value() == self.n_frames - 1:
                self.slider.setValue(0)
            self.timer.start(1000 // 11)
            self.play_btn.setText("■")
            self.is_playing = True

    def _detener_reproduccion(self):
        self.timer.stop()
        self.play_btn.setText("▶")
        self.is_playing = False

    # ──────────────────────────────────────────────────────────────────
    # Gestión de pestañas
    # ──────────────────────────────────────────────────────────────────

    def _al_cambiar_pestana(self, tab_id: int):
        self._stack.setCurrentIndex(tab_id)
        self._aplicar_estilos_pestanas()

    def _aplicar_estilos_pestanas(self):
        activa = self._tab_group.checkedId()
        for tab_id, btn in self._tab_btns.items():
            btn.setStyleSheet(TAB_ACTIVE if tab_id == activa else TAB_INACTIVE)

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _dibujar_en_label(label: QLabel, arr: np.ndarray):
        """Dibuja un array numpy dentro de un QLabel, escalado para encajar."""
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
