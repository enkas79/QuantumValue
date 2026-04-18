"""
Modulo di Configurazione.

Contiene le costanti globali, i metadati dell'applicazione
e le mappe di conversione fisse. Nessuna logica applicativa qui.
In questa versione, il software legge dinamicamente la propria
versione dal file esterno 'version.txt' per l'integrazione CI/CD.

Autore: Enrico Martini
Versione: Dinamica (via version.txt)
"""

import os
import sys

def _get_base_path() -> str:
    """
    Restituisce il percorso base dell'applicazione.
    Gestisce in automatico la compatibilità con l'eseguibile PyInstaller (sys._MEIPASS).

    Returns:
        str: Il percorso assoluto in cui cercare i file di asset.
    """
    try:
        # Percorso temporaneo in cui PyInstaller estrae i file
        return sys._MEIPASS
    except AttributeError:
        # Percorso classico quando eseguito in locale come script Python
        return os.path.abspath(".")

def _load_version() -> str:
    """
    Legge la versione dal file 'version.txt' iniettato nel pacchetto.

    Returns:
        str: La versione letta, oppure '0.0.0' in caso di errore (Fail-Safe).
    """
    version_file: str = os.path.join(_get_base_path(), "version.txt")
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


APP_NAME: str = "QuantumValue Analysis"
VERSION: str = _load_version()
AUTHOR: str = "Enrico Martini"
GITHUB_REPO: str = "enkas79/QuantumValue"

# Mappatura delle borse valori usate da Yahoo Finance
YAHOO_EXCHANGE_MAP: dict[str, str] = {
    "NYQ": "NYSE", "NMS": "NASDAQ", "MIL": "MIB30", "PAR": "CAC40",
    "FRA": "DAX", "GER": "DAX", "LSE": "LSE", "MCE": "IBEX35",
    "AMS": "AEX", "HAN": "HAN", "EBS": "SWX"
}