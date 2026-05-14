# DICOM_loader.py
# Carga un archivo DICOM y devuelve sus fotogramas como lista de arrays numpy.
# El callback de progreso es opcional; si se pasa, se llama con valores de 0 a 100.

import pydicom


def load_dicom_file(file_path, progress_callback=None):
    """
    Lee un archivo DICOM y extrae todos sus fotogramas.

    Retorna una lista de arrays numpy (uno por fotograma).
    Si hay algún error de lectura, imprime el mensaje y retorna lista vacía.
    """
    try:
        if progress_callback:
            progress_callback(10)

        ds = pydicom.dcmread(file_path)
        ds.decompress()

        if progress_callback:
            progress_callback(40)

        raw = ds.pixel_array
        frames = []

        if len(raw.shape) == 4:
            # Archivo multifotograma
            total = len(raw)
            for i, frame in enumerate(raw):
                frames.append(frame)
                if progress_callback:
                    progress_callback(40 + int((i / total) * 60))
        else:
            # Solo un fotograma
            frames.append(raw)
            if progress_callback:
                progress_callback(100)

        return frames

    except Exception as e:
        print("Error cargando archivo:", e)
        return []
