# roi_utils.py
# Funciones para extraer y manipular las regiones de interés (ROI)
# a partir de los metadatos DICOM (SequenceOfUltrasoundRegions).
#
# En estos archivos DICOM de elastografía hay varias regiones definidas:
#   - Una región B-Mode: la imagen de ultrasonido clásica
#   - Una región SWE: el mapa de color de rigidez
#   - Una región interna más pequeña: el área de medición fina dentro del SWE
#
# Si los tipos de datos no permiten identificarlas, se usa la posición vertical:
# la región más alta en pantalla es la SWE, la más baja es el B-Mode.

import numpy as np
import cv2


def obtener_rois_grandes(ds, shape: tuple) -> tuple[dict, dict]:
    """
    Devuelve (roi_b, roi_e) como diccionarios con claves x0, y0, x1, y1.

    Primero intenta identificarlas por RegionDataType (dt=1 → B-Mode, dt=2/6 → SWE).
    Si no es posible, las ordena por posición vertical y asume que
    la más alta es la SWE y la más baja el B-Mode.
    """
    H, W = shape[:2]
    area_minima = H * W * 0.01  # ignoramos regiones muy pequeñas (menos del 1%)

    rois = []
    for reg in ds.SequenceOfUltrasoundRegions:
        x0 = int(reg.RegionLocationMinX0)
        y0 = int(reg.RegionLocationMinY0)
        x1 = int(reg.RegionLocationMaxX1)
        y1 = int(reg.RegionLocationMaxY1)
        area = (x1 - x0) * (y1 - y0)
        dt   = int(getattr(reg, "RegionDataType", -1))

        if area > area_minima:
            rois.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, dt=dt))

    roi_b, roi_e = None, None
    for r in rois:
        if r["dt"] == 1      and roi_b is None: roi_b = r
        if r["dt"] in (2, 6) and roi_e is None: roi_e = r

    # Fallback: si no hay tipos, usamos posición vertical
    if roi_b is None or roi_e is None:
        rois_por_y = sorted(rois, key=lambda r: r["y0"])
        roi_e = rois_por_y[0]   # la más alta en pantalla → SWE
        roi_b = rois_por_y[-1]  # la más baja → B-Mode

    return roi_b, roi_e


def obtener_roi_interno(ds) -> tuple[int, int, int, int]:
    """
    Busca la región de menor área en SequenceOfUltrasoundRegions.
    Esta suele ser el recuadro de medición fino dentro del SWE.
    Retorna las coordenadas globales (x0, y0, x1, y1).
    """
    menor_area = float("inf")
    mejor = None

    for reg in ds.SequenceOfUltrasoundRegions:
        x0, y0 = int(reg.RegionLocationMinX0), int(reg.RegionLocationMinY0)
        x1, y1 = int(reg.RegionLocationMaxX1), int(reg.RegionLocationMaxY1)
        area = (x1 - x0) * (y1 - y0)
        if area < menor_area:
            menor_area = area
            mejor = (x0, y0, x1, y1)

    return mejor


def a_coordenadas_relativas(rect_global: tuple, roi_base: dict) -> tuple:
    """
    Convierte un rectángulo en coordenadas globales a coordenadas
    relativas dentro de roi_base.
    """
    return (
        rect_global[0] - roi_base["x0"],
        rect_global[1] - roi_base["y0"],
        rect_global[2] - roi_base["x0"],
        rect_global[3] - roi_base["y0"],
    )


def extraer_roi(img: np.ndarray, rect: tuple) -> np.ndarray:
    """Recorta la región definida por rect (x0, y0, x1, y1) de una imagen."""
    return img[rect[1]:rect[3], rect[0]:rect[2]]


# ──────────────────────────────────────────────────────────────────────────────
# Detección y recorte del borde naranja (artefacto del transductor)
# ──────────────────────────────────────────────────────────────────────────────

def _mascara_naranja(hsv: np.ndarray) -> np.ndarray:
    """
    Genera una máscara booleana con los píxeles de color naranja.
    Usamos tres rangos en el espacio HSV para capturar el tono naranja
    del borde del transductor, que puede variar un poco según el equipo.
    """
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    rango1 = (H >=  0) & (H <=  8) & (S >= 80) & (V >= 80)
    rango2 = (H >=  5) & (H <= 25) & (S >= 80) & (V >= 80)
    rango3 = (H >= 22) & (H <= 32) & (S >= 60) & (V >= 80)
    return rango1 | rango2 | rango3


def _grosor_desde_borde(mask: np.ndarray, direccion: str,
                         invertir: bool, umbral_frac: float = 0.30) -> int:
    """
    Cuenta cuántas filas (o columnas) desde un borde tienen al menos
    umbral_frac de píxeles naranja. Eso nos da el grosor del borde.
    """
    if direccion == "columnas":
        mask = mask.T
    lineas = mask[::-1] if invertir else mask
    N      = lineas.shape[1]
    grosor = 0
    for linea in lineas:
        if np.sum(linea) / N >= umbral_frac:
            grosor += 1
        else:
            break
    return grosor


def detectar_grosor_borde(roi_b_rgb: np.ndarray, margen_extra: int = 1) -> dict:
    """
    Analiza el ROI B-Mode del frame 0 y devuelve cuántos píxeles hay que
    recortar por cada lado para eliminar el borde naranja del transductor.
    """
    hsv  = cv2.cvtColor(roi_b_rgb, cv2.COLOR_RGB2HSV).astype(np.int32)
    mask = _mascara_naranja(hsv)
    H, W = mask.shape

    top    = _grosor_desde_borde(mask, "filas",    False)
    bottom = _grosor_desde_borde(mask, "filas",    True)
    left   = _grosor_desde_borde(mask, "columnas", False)
    right  = _grosor_desde_borde(mask, "columnas", True)

    return {
        "top"   : min(top    + margen_extra, H // 4),
        "bottom": min(bottom + margen_extra, H // 4),
        "left"  : min(left   + margen_extra, W // 4),
        "right" : min(right  + margen_extra, W // 4),
    }


def recortar_borde(img_rgb: np.ndarray, grosor: dict) -> np.ndarray:
    """
    Aplica el recorte de borde calculado por detectar_grosor_borde.
    Funciona con cualquier imagen del mismo tamaño que el ROI de referencia.
    Retorna una copia de la imagen sin los bordes naranja.
    """
    t, b = grosor["top"],  grosor["bottom"]
    l, r = grosor["left"], grosor["right"]
    H, W = img_rgb.shape[:2]

    y0, y1 = t, H - b if b > 0 else H
    x0, x1 = l, W - r if r > 0 else W

    if y1 <= y0 or x1 <= x0:
        return img_rgb.copy()

    return img_rgb[y0:y1, x0:x1].copy()
