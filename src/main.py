"""
Entry Point (Punto di Avvio).

Inizializza la QApplication, attiva il logging e carica la finestra principale.
Questo è il file che dovrai puntare con PyInstaller per creare l'eseguibile:
comando: pyinstaller --onefile --windowed main.py

Autore: Enrico Martini
Versione: 0.7.13
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
    from PyQt6.QtCore import QSettings
except ImportError as e:
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)

# Importa i moduli dalla directory corrente (src/)
# Nota: usare import assoluti permette di eseguire questo file sia come script
# (python src/main.py / PyInstaller da src) sia tramite il wrapper root main.py.
import config
import theme
import utils
import views


def main() -> None:
    """Funzione principale che esegue l'applicazione MVC."""

    # Inizializza immediatamente la diagnostica su file e gli hook di sistema
    utils.setup_logging()

    # Necessario per la corretta compilazione multi-thread di PyInstaller
    multiprocessing.freeze_support()
    
    # Crea e avvia l'applicazione PyQt6
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Applica il tema salvato nelle preferenze (default: chiaro). Vedi theme.py
    # per il motivo per cui il tema va sempre forzato a livello di applicazione.
    settings = QSettings(config.AUTHOR.replace(" ", ""), config.APP_NAME.replace(" ", ""))
    theme.apply_theme(app, str(settings.value("theme", "light")))

    # Istanzia la View (che a sua volta aggancia Models e Controllers)
    window = views.MainWindow()
    window.showMaximized()

    # Entra nel loop degli eventi
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
