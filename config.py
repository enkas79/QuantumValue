"""
Modulo di Configurazione.

Contiene le costanti globali, i metadati dell'applicazione,
i parametri centralizzati delle chiamate HTTP e le mappe di conversione fisse.

Autore: Enrico Martini
Versione: 0.6.0
"""

import os
import sys


def _get_base_path() -> str:
    """Restituisce il percorso base dell'applicazione gestendo PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return str(sys._MEIPASS)
    return os.path.abspath(".")


def _load_version() -> str:
    """Legge la versione dal file esterno version.txt."""
    version_file = os.path.join(_get_base_path(), "version.txt")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except IOError:
            return "0.6.0"
    return "0.6.0"


# Metadati dell'Applicazione
APP_NAME: str = "QuantumValue Analysis"
VERSION: str = _load_version()
AUTHOR: str = "Enrico Martini"
GITHUB_REPO: str = "enkas79/quantumvalue"

# Impostazioni di Rete Centralizzate
HTTP_TIMEOUT: int = 7
HTTP_HEADERS: dict[str, str] = {
    'User-Agent': f'QuantumValue-Analysis/{VERSION} (Desktop App; Python/PyQt6)'
}

# Mappatura dei codici di mercato di Yahoo Finance in etichette leggibili
YAHOO_EXCHANGE_MAP: dict[str, str] = {
    'NMS': 'NASDAQ (USA)',
    'NYQ': 'NYSE (USA)',
    'ASE': 'AMEX (USA)',
    'MIL': 'Borsa Italiana (Milano)',
    'GER': 'XETRA (Germania)',
    'FRA': 'Borsa di Francoforte',
    'PAR': 'Euronext Parigi',
    'AMS': 'Euronext Amsterdam',
    'BRU': 'Euronext Bruxelles',
    'LIS': 'Euronext Lisbona',
    'LSE': 'Borsa di Londra (UK)',
    'TOE': 'Borsa di Tokyo (Giappone)',
    'TSX': 'Borsa di Toronto (Canada)',
    'HKG': 'Borsa di Hong Kong',
    'ASX': 'Borsa di Sydney (Australia)',
    'EBS': 'Borsa Svizzera (SIX)'
}