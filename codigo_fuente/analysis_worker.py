# analysis_worker.py
# Hilo de análisis principal. Procesa todos los fotogramas del volumen DICOM,
# convierte cada píxel de color SWE a kilopascales usando una LUT de calibración,
# y calcula estadísticas por frame y globales.
#
# Se ejecuta en segundo plano (QThread) para no congelar la interfaz.
# Emite progreso de 0 a 100 y al final un dict completo con resultados.

import numpy as np
import cv2
from scipy.spatial import KDTree
from PySide6.QtCore import QThread, Signal

from roi_utils import (
    obtener_rois_grandes,
    obtener_roi_interno,
    a_coordenadas_relativas,
    extraer_roi,
    detectar_grosor_borde,
    recortar_borde,
)


class AnalysisWorker(QThread):

    progress = Signal(int)     # 0 a 100
    finished = Signal(object)  # dict con todos los resultados

    def __init__(self, ds, lut_path: str, margen_extra: int = 1):
        super().__init__()
        self.ds           = ds
        self.lut_path     = lut_path
        self.margen_extra = margen_extra

    def run(self):
        ds  = self.ds
        lut = np.load(self.lut_path)

        # La LUT tiene forma (N, 4): columna 0 → kPa, columnas 1-3 → RGB
        lut_kpa = lut[:, 0]
        tree    = KDTree(lut[:, 1:])

        # Preparar el frame 0 para detectar geometría y bordes
        frame0_full = ds.pixel_array[0] if ds.pixel_array.ndim == 4 else ds.pixel_array

        if frame0_full.ndim == 2:
            frame0_full = cv2.cvtColor(frame0_full, cv2.COLOR_GRAY2RGB)
        elif frame0_full.shape[2] == 4:
            frame0_full = cv2.cvtColor(frame0_full, cv2.COLOR_RGBA2RGB)

        # Identificar las dos regiones principales (B-Mode y SWE)
        roi_b_meta, roi_e_meta = obtener_rois_grandes(ds, frame0_full.shape)

        # El ROI interno (medición fina) está en coordenadas globales;
        # lo convertimos a coordenadas relativas dentro del SWE
        rect_global = obtener_roi_interno(ds)
        rect_rel    = a_coordenadas_relativas(rect_global, roi_e_meta)

        # Recortar los ROIs del frame 0 para detectar el borde naranja
        img_b0 = frame0_full[roi_b_meta["y0"]:roi_b_meta["y1"],
                              roi_b_meta["x0"]:roi_b_meta["x1"]]
        img_e0 = frame0_full[roi_e_meta["y0"]:roi_e_meta["y1"],
                              roi_e_meta["x0"]:roi_e_meta["x1"]]

        roi_b0_f = extraer_roi(img_b0, rect_rel)
        roi_e0_f = extraer_roi(img_e0, rect_rel)

        # Calcular grosor del borde naranja una sola vez (en el frame 0)
        grosor = detectar_grosor_borde(roi_b0_f, margen_extra=self.margen_extra)

        # Las dimensiones del ROI limpio definen el tamaño de los volúmenes
        roi_e0_clean = recortar_borde(roi_e0_f, grosor)
        roi_h, roi_w = roi_e0_clean.shape[:2]

        n_frames = ds.pixel_array.shape[0]

        # Volúmenes de resultados
        volumen_kpa  = np.full((n_frames, roi_h, roi_w), np.nan, dtype=np.float32)
        volumen_roi  = np.zeros((n_frames, roi_h, roi_w, 3), dtype=np.uint8)
        volumen_mask = np.zeros((n_frames, roi_h, roi_w), dtype=bool)

        # Procesar cada fotograma
        for i in range(n_frames):
            frame = ds.pixel_array[i]

            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            elif frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)

            img_b = frame[roi_b_meta["y0"]:roi_b_meta["y1"],
                          roi_b_meta["x0"]:roi_b_meta["x1"]]
            img_e = frame[roi_e_meta["y0"]:roi_e_meta["y1"],
                          roi_e_meta["x0"]:roi_e_meta["x1"]]

            roi_b_f = extraer_roi(img_b, rect_rel)
            roi_e_f = extraer_roi(img_e, rect_rel)

            # Quitar el borde naranja del SWE (mismo grosor que en frame 0)
            roi_e_clean = recortar_borde(roi_e_f, grosor)

            # Máscara: píxeles con color real (no fondo negro o gris neutro)
            hsv     = cv2.cvtColor(roi_e_clean, cv2.COLOR_RGB2HSV)
            mascara = (hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 40)

            # Convertir colores a kPa usando la LUT de calibración
            _, idxs  = tree.query(roi_e_clean.reshape(-1, 3).astype(np.float32))
            kpa_flat = lut_kpa[idxs].reshape(roi_h, roi_w)

            volumen_kpa[i]  = np.where(mascara, kpa_flat, np.nan)
            volumen_roi[i]  = roi_e_clean
            volumen_mask[i] = mascara

            self.progress.emit(int((i + 1) / n_frames * 100))

        # Calcular estadísticas globales sobre todos los píxeles válidos
        todos      = volumen_kpa[~np.isnan(volumen_kpa)]
        mapa_medio = np.nanmean(volumen_kpa, axis=0)
        mapa_std   = np.nanstd(volumen_kpa,  axis=0)

        media_por_frame  = np.nanmean(volumen_kpa, axis=(1, 2))
        std_por_frame    = np.nanstd(volumen_kpa,  axis=(1, 2))
        cobertura_frames = np.array([
            100 * np.sum(~np.isnan(volumen_kpa[i])) / (roi_h * roi_w)
            for i in range(n_frames)
        ])

        stats_globales = {
            "media"          : float(np.mean(todos)),
            "mediana"        : float(np.median(todos)),
            "std"            : float(np.std(todos)),
            "p25"            : float(np.percentile(todos, 25)),
            "p75"            : float(np.percentile(todos, 75)),
            "p90"            : float(np.percentile(todos, 90)),
            "minimo"         : float(np.min(todos)),
            "maximo"         : float(np.max(todos)),
            "cv"             : float(np.std(todos) / np.mean(todos) * 100),
            "cobertura_media": float(np.mean(cobertura_frames)),
            "n_total"        : int(len(todos)),
        }

        resultado = {
            "volumen_kpa"     : volumen_kpa,
            "volumen_roi"     : volumen_roi,
            "volumen_mask"    : volumen_mask,
            "mapa_medio"      : mapa_medio,
            "mapa_std"        : mapa_std,
            "media_por_frame" : media_por_frame,
            "std_por_frame"   : std_por_frame,
            "cobertura_frames": cobertura_frames,
            "stats_globales"  : stats_globales,
            # Metadatos de geometría (útiles para depuración)
            "roi_e_meta"      : roi_e_meta,
            "roi_b_meta"      : roi_b_meta,
            "rect_rel"        : rect_rel,
            "grosor_borde"    : grosor,
            "n_frames"        : n_frames,
        }

        self.finished.emit(resultado)
