"""
Entry Point (Punto di Avvio).

Inizializza la QApplication e carica la finestra principale.
Questo è il file che dovrai puntare con PyInstaller per creare l'eseguibile:
comando: pyinstaller --onefile --windowed main.py

Autore: Enrico Martini
"""
# comando Windows: pyinstaller --onefile --windowed --add-data "version.txt;." main.py
# comando macOS/Linux: pyinstaller --onefile --windowed --add-data "version.txt:." main.py

import sys
import multiprocessing
from typing import Any

# Importazioni di PyQt6 strettamente necessarie per l'avvio
try:
    from PyQt6.QtWidgets import QApplication
except ImportError as e:
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)

from utils import global_exception_handler
from views import MainWindow


def main() -> None:
    """Funzione principale che esegue l'applicazione MVC."""
    
    # Necessario per la corretta compilazione multi-thread di PyInstaller
    multiprocessing.freeze_support()
    
    # Inizializza l'handler globale per evitare la chiusura silenziosa
    sys.excepthook = global_exception_handler
    
    # Crea e avvia l'applicazione PyQt6
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Istanzia la View (che a sua volta aggancia Models e Controllers)
    window = MainWindow()
    window.show()

    # Entra nel loop degli eventi
    sys.exit(app.exec())


if __name__ == "__main__":
    main()