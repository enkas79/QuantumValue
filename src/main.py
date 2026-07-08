"""
Entry Point (Punto di Avvio).

Inizializza la QApplication, attiva il logging e carica la finestra principale.
Questo è il file che dovrai puntare con PyInstaller per creare l'eseguibile:
comando: pyinstaller --onefile --windowed main.py

Autore: Enrico Martini
Versione: 0.7.7
"""
# comando Windows: pyinstaller --onefile --windowed --add-data "version.txt;." main.py
# comando macOS/Linux: pyinstaller --onefile --windowed --add-data "version.txt:." main.py

import sys
import os
import multiprocessing
from typing import Any

# Aggiungi la directory src al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class DummyStream:
    """Stream vuoto per prevenire crash su stampe o log di librerie terze."""
    def write(self, *args: Any, **kwargs: Any) -> None: pass
    def flush(self, *args: Any, **kwargs: Any) -> None: pass


if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

# Importazioni di PyQt6 strettamente necessarie per l'avvio
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPalette, QColor
except ImportError as e:
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)

# Importa i moduli dalla directory corrente (src/)
# Nota: usare import assoluti permette di eseguire questo file sia come script
# (python src/main.py / PyInstaller da src) sia tramite il wrapper root main.py.
import utils
import views


def _apply_light_theme(app: QApplication) -> None:
    """
    Forza palette e stylesheet chiari sull'intera applicazione.

    L'interfaccia è disegnata per il tema chiaro: senza questa forzatura,
    con il sistema operativo in modalità scura Qt applica la palette di
    sistema (testo chiaro) sopra gli sfondi bianchi imposti dagli
    stylesheet, rendendo il testo invisibile. Applicare palette e
    stylesheet a livello di QApplication garantisce coerenza anche in
    tutte le finestre di dialogo.
    """
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f2f5"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f2f5"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#95a5a6"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#e0e6ed"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#2980b9"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2e86de"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#95a5a6"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#95a5a6"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#95a5a6"))
    app.setPalette(palette)

    # Stylesheet globale: ogni regola che impone uno sfondo dichiara anche
    # il colore del testo, così il tema scuro dell'OS non può mai produrre
    # testo chiaro su sfondo chiaro.
    app.setStyleSheet("""
        QWidget { color: #2c3e50; }
        QMainWindow, QDialog { background-color: #f0f2f5; }
        QGroupBox { font-weight: bold; border: 1px solid #c8d6e5; border-radius: 6px; margin-top: 10px; background-color: white; }
        QLabel, QRadioButton { background: transparent; }
        QLineEdit { border: 1px solid #c8d6e5; border-radius: 4px; padding: 5px; background-color: white; color: #2c3e50; }
        QPushButton { font-weight: bold; border-radius: 4px; background-color: #e0e6ed; color: #2c3e50; border: 1px solid #c8d6e5; padding: 5px 10px; }
        QPushButton:hover { background-color: #d5dde6; }
        QPushButton:disabled { color: #95a5a6; }
        QTabWidget::pane { border: 1px solid #c8d6e5; background: white; border-radius: 6px; }
        QTabBar::tab { background: #e0e6ed; color: #2c3e50; padding: 10px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
        QTabBar::tab:selected { background: white; color: #2980b9; border-bottom: 2px solid white; }
        QTableWidget { background-color: white; color: #2c3e50; gridline-color: #e0e6ed; }
        QHeaderView::section { background-color: #e0e6ed; color: #2c3e50; font-weight: bold; border: none; padding: 4px; }
        QTextBrowser { background-color: white; color: #2c3e50; border: 1px solid #c8d6e5; }
        QMenuBar { background-color: #f0f2f5; color: #2c3e50; }
        QMenuBar::item:selected { background-color: #e0e6ed; }
        QMenu { background-color: white; color: #2c3e50; }
        QMenu::item:selected { background-color: #2e86de; color: white; }
        QStatusBar { background-color: #f0f2f5; color: #2c3e50; }
        QMessageBox { background-color: #f0f2f5; }
    """)


def main() -> None:
    """Funzione principale che esegue l'applicazione MVC."""

    # Inizializza immediatamente la diagnostica su file e gli hook di sistema
    utils.setup_logging()

    # Necessario per la corretta compilazione multi-thread di PyInstaller
    multiprocessing.freeze_support()
    
    # Crea e avvia l'applicazione PyQt6
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _apply_light_theme(app)

    # Istanzia la View (che a sua volta aggancia Models e Controllers)
    window = views.MainWindow()
    window.show()

    # Entra nel loop degli eventi
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
