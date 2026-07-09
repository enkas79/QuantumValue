"""
Modulo Tema (chiaro/scuro).

Centralizza palette, stylesheet e colori semantici dell'interfaccia.
Il tema viene applicato a livello di QApplication cosi' da coprire anche
tutte le finestre di dialogo, e non dipende mai dal tema dell'OS: senza
questa forzatura, con il sistema in modalita' scura Qt applicherebbe testo
chiaro sopra gli sfondi chiari imposti dagli stylesheet (o viceversa),
rendendo il testo illeggibile.

Autore: Enrico Martini
Versione: 0.7.13
"""

from string import Template
from typing import Dict

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

# Colori semantici per ciascun tema. Le viste devono leggere i colori da qui
# (via color()) invece di usare valori hardcoded, cosi' il cambio tema resta
# coerente in tutta l'app.
THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "window": "#f0f2f5",
        "card": "#ffffff",
        "border": "#c8d6e5",
        "text": "#2c3e50",
        "muted": "#7f8c8d",
        "placeholder": "#95a5a6",
        "input_bg": "#ffffff",
        "button_bg": "#e0e6ed",
        "button_hover": "#d5dde6",
        "tab_bg": "#e0e6ed",
        "value": "#222f3e",
        "accent": "#2980b9",
        "accent_etf": "#8e44ad",
        "highlight": "#2e86de",
    },
    "dark": {
        "window": "#1e2430",
        "card": "#2a3140",
        "border": "#3d4658",
        "text": "#e8ecf2",
        "muted": "#95a1b2",
        "placeholder": "#6c7a8e",
        "input_bg": "#232936",
        "button_bg": "#3d4658",
        "button_hover": "#4a5468",
        "tab_bg": "#242b39",
        "value": "#e8ecf2",
        "accent": "#5dade2",
        "accent_etf": "#bb8fce",
        "highlight": "#2e86de",
    },
}

# Stylesheet globale: ogni regola che impone uno sfondo dichiara anche il
# colore del testo, cosi' nessuna combinazione puo' produrre testo invisibile.
# Il QTextBrowser (guida) resta sempre chiaro perche' il suo HTML usa colori
# scuri fissi pensati per sfondo bianco.
_STYLESHEET = Template("""
    QWidget { color: $text; }
    QMainWindow, QDialog { background-color: $window; }
    QGroupBox { font-weight: bold; border: 1px solid $border; border-radius: 6px; margin-top: 10px; background-color: $card; }
    QLabel, QRadioButton { background: transparent; }
    QLineEdit { border: 1px solid $border; border-radius: 4px; padding: 5px; background-color: $input_bg; color: $text; }
    QPushButton { font-weight: bold; border-radius: 4px; background-color: $button_bg; color: $text; border: 1px solid $border; padding: 5px 10px; }
    QPushButton:hover { background-color: $button_hover; }
    QPushButton:disabled { color: $placeholder; }
    QTabWidget::pane { border: 1px solid $border; background: $card; border-radius: 6px; }
    QTabBar::tab { background: $tab_bg; color: $text; padding: 10px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
    QTabBar::tab:selected { background: $card; color: $accent; border-bottom: 2px solid $card; }
    QTableWidget { background-color: $card; color: $text; gridline-color: $border; }
    QHeaderView::section { background-color: $tab_bg; color: $text; font-weight: bold; border: none; padding: 4px; }
    QTextBrowser { background-color: #ffffff; color: #2c3e50; border: 1px solid $border; }
    QMenuBar { background-color: $window; color: $text; }
    QMenuBar::item:selected { background-color: $button_bg; }
    QMenu { background-color: $card; color: $text; }
    QMenu::item:selected { background-color: $highlight; color: white; }
    QStatusBar { background-color: $window; color: $text; }
    QMessageBox { background-color: $window; }
    QToolTip { background-color: $card; color: $text; border: 1px solid $border; }
""")

_current: str = "light"


def current_theme() -> str:
    """Restituisce il nome del tema attualmente applicato."""
    return _current


def color(key: str) -> str:
    """Restituisce il colore semantico richiesto per il tema attivo."""
    return THEMES[_current][key]


def apply_theme(app: QApplication, name: str = "light") -> None:
    """
    Applica palette e stylesheet del tema richiesto all'intera applicazione.

    Args:
        app (QApplication): L'applicazione a cui applicare il tema.
        name (str): "light" o "dark" (valori sconosciuti ricadono su "light").
    """
    global _current
    if name not in THEMES:
        name = "light"
    _current = name
    t = THEMES[name]

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["input_bg"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["window"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["card"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["placeholder"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["button_bg"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["highlight"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(t["placeholder"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(t["placeholder"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(t["placeholder"]))
    app.setPalette(palette)
    app.setStyleSheet(_STYLESHEET.substitute(t))
