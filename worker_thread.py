# worker_thread.py
# Hilo de carga del archivo DICOM. Corre en segundo plano para no
# bloquear la interfaz mientras se leen los fotogramas.
#
# Al terminar, emite un dict con:
#   frames_full  : todos los fotogramas completos (H, W, 3)
#   frames_roi   : recorte del ROI interno (región de medición)
#   frames_B     : recorte solo del área B-Mode
#   frames_SWE   : recorte solo del área SWE (elastograma)
#   roi_coords   : (x0, y0, x1, y1) del ROI interno, o None
#   has_roi      : True si el DICOM tiene metadatos de región

import numpy as np
import pydicom
from PySide6.QtCore import QThread, Signal

from DICOM_loader import load_dicom_file
from roi_utils import obtener_rois_grandes


class DicomLoaderThread(QThread):

    progress = Signal(int)   # 0 a 100
    finished = Signal(dict)  # resultado final

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        self.progress.emit(5)

        ds = pydicom.dcmread(self.file_path)
        self.progress.emit(10)

        # Buscar la región interna más pequeña (ROI de medición fino)
        roi_coords = None
        has_roi    = False

        if hasattr(ds, "SequenceOfUltrasoundRegions"):
            menor_area = float("inf")
            x0, y0, x1, y1 = 0, 0, 0, 0
            for reg in ds.SequenceOfUltrasoundRegions:
                area = ((reg.RegionLocationMaxX1 - reg.RegionLocationMinX0) *
                        (reg.RegionLocationMaxY1 - reg.RegionLocationMinY0))
                if area < menor_area:
                    menor_area = area
                    x0 = reg.RegionLocationMinX0
                    y0 = reg.RegionLocationMinY0
                    x1 = reg.RegionLocationMaxX1
                    y1 = reg.RegionLocationMaxY1
            roi_coords = (x0, y0, x1, y1)
            has_roi    = True

        self.progress.emit(15)

        # Relay de progreso: el loader reporta 0-100, aquí lo mapeamos a 15-90
        def _relay_progreso(v):
            self.progress.emit(15 + int(v * 0.75))

        frames_raw = load_dicom_file(self.file_path, progress_callback=_relay_progreso)
        self.progress.emit(90)

        # Detectar las dos regiones grandes (B y SWE) usando el primer frame
        roi_b, roi_e = None, None
        if hasattr(ds, "SequenceOfUltrasoundRegions") and len(frames_raw) > 0:
            roi_b, roi_e = obtener_rois_grandes(ds, frames_raw[0].shape)

        # Construir las listas de vistas
        frames_full = []
        frames_roi  = []
        frames_B    = []
        frames_SWE  = []

        for frame in frames_raw:
            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)

            frames_full.append(frame)

            if has_roi:
                x0, y0, x1, y1 = roi_coords
                frames_roi.append(frame[y0:y1, x0:x1])

            if roi_b is not None:
                frames_B.append(
                    frame[roi_b["y0"]:roi_b["y1"], roi_b["x0"]:roi_b["x1"]]
                )

            if roi_e is not None:
                frames_SWE.append(
                    frame[roi_e["y0"]:roi_e["y1"], roi_e["x0"]:roi_e["x1"]]
                )

        self.progress.emit(100)

        self.finished.emit({
            "frames_full": frames_full,
            "frames_roi" : frames_roi,
            "roi_coords" : roi_coords,
            "has_roi"    : has_roi,
            "frames_B"   : frames_B,
            "frames_SWE" : frames_SWE,
        })
