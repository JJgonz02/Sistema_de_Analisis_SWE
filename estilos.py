# estilos.py
# Paleta de colores y hojas de estilo Qt usadas en toda la aplicación.
# Centralizar esto acá evita repetir los mismos strings en cada archivo.

# Colores base
DARK_BG    = "#0f1117"
PANEL_BG   = "#1a1f2e"
PANEL_DEEP = "#12151f"
BORDER     = "#2a2f45"
ACCENT     = "#378ADD"
TEXT_MAIN  = "#c8cfe8"
TEXT_DIM   = "#6a7290"
SUCCESS    = "#4caf50"
DANGER     = "#e05c5c"

MAX_HISTORY = 5  # cuántos análisis se guardan en el historial


# Paneles generales
PANEL_STYLE = f"""
    QWidget {{
        background-color: {PANEL_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
"""

# Etiquetas informativas
LABEL_TITLE_STYLE = f"""
    font-size: 11px;
    font-weight: bold;
    color: {ACCENT};
    letter-spacing: 1px;
    padding: 6px 10px 4px 10px;
    background: transparent;
    border: none;
"""

LABEL_KEY_STYLE = f"""
    font-size: 11px;
    color: {TEXT_DIM};
    background: transparent;
    border: none;
    padding: 1px 10px;
"""

LABEL_VAL_STYLE = f"""
    font-size: 11px;
    color: {TEXT_MAIN};
    background: transparent;
    border: none;
    padding: 1px 10px;
"""

# Botones de toggle (modos de visualización)
TOGGLE_BASE = f"""
    QPushButton {{
        background-color: {PANEL_BG};
        color: {TEXT_DIM};
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 5px 10px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        background-color: #252b40;
        color: {TEXT_MAIN};
    }}
    QPushButton:checked {{
        background-color: {ACCENT};
        color: white;
        border-color: {ACCENT};
        font-weight: bold;
    }}
"""

# Botón estándar
BTN_STYLE = f"""
    QPushButton {{
        background-color: {PANEL_BG};
        color: {TEXT_MAIN};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 12px;
    }}
    QPushButton:hover    {{ background-color: {ACCENT}; color: white; }}
    QPushButton:disabled {{ color: #555; border-color: #333; }}
"""

# Botón de análisis (con borde accent en estado normal)
ANALYZE_STYLE = f"""
    QPushButton {{
        background-color: {PANEL_BG};
        color: {TEXT_MAIN};
        border: 1px solid {ACCENT};
        border-radius: 4px;
        font-size: 12px;
    }}
    QPushButton:hover    {{ background-color: {ACCENT}; color: white; }}
    QPushButton:disabled {{ color: #555; border-color: #333; }}
"""

# Barra de progreso del análisis
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        background-color: #12151f;
        border: 1px solid {BORDER};
        border-radius: 4px;
        height: 8px;
        text-align: center;
        font-size: 9px;
        color: {TEXT_DIM};
    }}
    QProgressBar::chunk {{
        background-color: {ACCENT};
        border-radius: 3px;
    }}
"""

# Tarjetas del historial: normal vs activa
HISTORY_CARD_NORMAL = f"""
    QWidget#histCard {{
        background-color: #141928;
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
"""

HISTORY_CARD_ACTIVE = f"""
    QWidget#histCard {{
        background-color: #172035;
        border: 1px solid {ACCENT};
        border-radius: 6px;
    }}
"""

# Estilos de pestañas para la ventana de análisis
TAB_ACTIVE = f"""
    QPushButton {{
        background-color: {ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 6px;
        font-size: 11px;
        font-weight: bold;
        text-align: left;
    }}
"""

TAB_INACTIVE = f"""
    QPushButton {{
        background-color: {PANEL_DEEP};
        color: {TEXT_DIM};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 6px;
        font-size: 11px;
        text-align: left;
    }}
    QPushButton:hover {{
        background-color: #252b40;
        color: {TEXT_MAIN};
    }}
"""

NAV_BTN = f"""
    QPushButton {{
        background-color: #2a2f45; color: {TEXT_MAIN};
        border: 1px solid {BORDER}; border-radius: 4px;
        padding: 3px 8px;
    }}
    QPushButton:hover {{ background-color: {ACCENT}; color: white; }}
"""
