"""
Entry Point (Punto di Avvio) - WRAPPER

Questo file è un wrapper che esegue il vero entry point in src/main.py
per mantenere la compatibilità con le vecchie installazioni.

Autore: Enrico Martini
Versione: 0.6.5
"""

import sys
import os

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Esegui il vero main
from src.main import main

if __name__ == "__main__":
    main()
