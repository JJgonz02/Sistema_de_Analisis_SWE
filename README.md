# Sistema de Análisis SWE
### Herramienta computacional para el análisis cuantitativo de elastografía por ondas de corte (SWE) en músculo esquelético
 
Proyecto de grado — Ingeniería Biomédica · Pontificia Universidad Javeriana Cali  
Autor: Juan José González Carvajal
 
---
 
## ¿Qué es?
 
Aplicación de escritorio para el procesamiento automático de estudios DICOM de elastografía por ondas de corte (SWE). A partir de un archivo DICOM multifotograma, el sistema detecta la región elastográfica, convierte los colores del mapa SWE a kilopascales mediante una LUT de calibración y calcula métricas cuantitativas de rigidez tisular frame a frame y de forma global.
 
Fue desarrollada como herramienta de apoyo para investigación académica en el contexto de caracterización muscular en osteoartritis de rodilla. **No está orientada al diagnóstico clínico.**
 
---
 
## Funcionalidades principales
 
- Carga y visualización de estudios DICOM multifotograma
- Detección automática de la región SWE y el ROI de medición a partir de los metadatos DICOM
- Conversión píxel a kPa mediante LUT de calibración por color
- Análisis frame a frame: histograma de distribución y estadísticas por fotograma
- Análisis global: mapa de rigidez media, mapa de variabilidad temporal, histograma global, evolución temporal y cobertura
- Historial de análisis dentro de la sesión
- Exportación de resultados:
  - `reporte_swe.pdf` — métricas globales y gráficas
  - `metricas_frames.xlsx` — estadísticas por fotograma
---
 
## Estructura del repositorio
 
```
Sistema_de_Analisis_SWE/
├── codigo_fuente/
│   ├── main.py               # Punto de entrada
│   ├── GUI.py                # Ventana principal
│   ├── analysis_window.py    # Ventana de resultados
│   ├── analysis_worker.py    # Hilo de análisis (QThread)
│   ├── worker_thread.py      # Hilo de carga DICOM
│   ├── DICOM_loader.py       # Lectura de archivos DICOM
│   ├── roi_utils.py          # Extracción y manipulación de ROIs
│   ├── export_results.py     # Generación de PDF y Excel
│   ├── utils_ui.py           # Utilidades de interfaz
│   ├── estilos.py            # Paleta y hojas de estilo Qt
│   └── Helper.py             # Tour guiado interactivo
└── ejecutable/
    ├── main.exe              # Ejecutable de Windows
    └── _internal/            # Dependencias empaquetadas
```
 
---
 
## Ejecución
 
### Opción A — Ejecutable (recomendado)
 
1. Descarga este repositorio como ZIP desde el botón **Code → Download ZIP**
2. Descomprime y navega a la carpeta `ejecutable/`
3. Ejecuta `main.exe`
No requiere instalar Python ni dependencias adicionales.
 
### Opción B — Desde el código fuente
 
Requiere Python 3.10+ y las siguientes dependencias:
 
```bash
pip install PySide6 pydicom numpy opencv-python scipy matplotlib reportlab openpyxl
```
 
Luego:
 
```bash
cd codigo_fuente
python main.py
```
 
---
 
## Datos DICOM — importante
 
> **Este repositorio no contiene archivos DICOM.**
 
Los estudios elastográficos utilizados para el desarrollo, validación y pruebas experimentales del proyecto son de acceso abierto y se encuentran disponibles en Zenodo:
 
**[https://zenodo.org/records/15025467](https://zenodo.org/records/15025467)**
 
Estos archivos no son de autoría propia y se distribuyen bajo la licencia **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Se recomienda utilizarlos para probar la aplicación, ya que corresponden exactamente al tipo de estudio para el que fue diseñado el sistema.
 
---
 
## Consideraciones de uso
 
- La aplicación fue diseñada y evaluada con estudios SWE de un equipo y protocolo específicos. Su rendimiento puede variar con imágenes de otros equipos o configuraciones de captura.
- Los resultados generados son de carácter experimental y no constituyen herramientas diagnósticas clínicamente validadas.
- El sistema es una prueba de concepto académica.
---
 
## Licencia
Los datos DICOM de ejemplo (Zenodo) se distribuyen bajo **CC BY 4.0** y no forman parte de este repositorio.
