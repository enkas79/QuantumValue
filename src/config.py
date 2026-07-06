"""
Modulo di Configurazione.

Contiene le costanti globali, i metadati dell'applicazione,
i parametri centralizzati delle chiamate HTTP e le mappe di conversione fisse.

Autore: Enrico Martini
Versione: 0.7.0
"""

import os
import sys
import tempfile

# Aggiungi la directory corrente al path per importare i moduli locali
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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

# Costanti per i colori dell'interfaccia
COLORS = {
    "excellent": "#27ae60",
    "good": "#2ecc71",
    "fair": "#f39c12",
    "weak": "#d35400",
    "bad": "#c0392b",
    "neutral": "#7f8c8d"
}

def _get_cache_dir() -> str:
    """
    Restituisce una cartella stabile e scrivibile per la cache persistente.

    A differenza di _get_base_path(), non punta mai a _MEIPASS: con PyInstaller
    quella cartella viene ricreata ed eliminata ad ogni avvio, quindi una cache
    persistente lì dentro non sopravvivrebbe mai al riavvio dell'eseguibile.
    """
    user_home: str = os.path.expanduser("~")
    cache_dir: str = os.path.join(user_home, ".quantumvalue", "cache")
    try:
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    except OSError:
        return tempfile.gettempdir()


# Impostazioni di caching
CACHE_EXPIRY_HOURS: int = 1
CACHE_DB_PATH: str = os.path.join(_get_cache_dir(), "quantumvalue_cache.db")

# Dati statici di fallback per ticker comuni (usati se tutti i provider falliscono)
STATIC_FALLBACK = {
    "AAPL": {
        "company_name": "Apple Inc.",
        "currency": "USD",
        "prices": {"current": 180.0, "1d": 178.0, "1w": 175.0, "1m": 170.0, "1y": 150.0},
        "ebit": 100000000000,
        "ev": 2000000000000,
        "nopat": 80000000000,
        "invested_capital": 500000000000,
        "ebitda": 120000000000,
        "pe": 25.0,
        "ps": 6.0,
        "peg": 1.5
    },
    "MSFT": {
        "company_name": "Microsoft Corporation",
        "currency": "USD",
        "prices": {"current": 400.0, "1d": 398.0, "1w": 390.0, "1m": 380.0, "1y": 350.0},
        "ebit": 80000000000,
        "ev": 2500000000000,
        "nopat": 60000000000,
        "invested_capital": 400000000000,
        "ebitda": 100000000000,
        "pe": 30.0,
        "ps": 10.0,
        "peg": 1.8
    },
    "GOOGL": {
        "company_name": "Alphabet Inc. (Google)",
        "currency": "USD",
        "prices": {"current": 150.0, "1d": 148.0, "1w": 145.0, "1m": 140.0, "1y": 130.0},
        "ebit": 70000000000,
        "ev": 1800000000000,
        "nopat": 55000000000,
        "invested_capital": 300000000000,
        "ebitda": 85000000000,
        "pe": 22.0,
        "ps": 5.5,
        "peg": 1.2
    },
    "AMZN": {
        "company_name": "Amazon.com Inc.",
        "currency": "USD",
        "prices": {"current": 160.0, "1d": 158.0, "1w": 155.0, "1m": 150.0, "1y": 140.0},
        "ebit": 30000000000,
        "ev": 1500000000000,
        "nopat": 20000000000,
        "invested_capital": 250000000000,
        "ebitda": 50000000000,
        "pe": 60.0,
        "ps": 3.0,
        "peg": 2.0
    },
    "TSLA": {
        "company_name": "Tesla Inc.",
        "currency": "USD",
        "prices": {"current": 180.0, "1d": 178.0, "1w": 175.0, "1m": 170.0, "1y": 200.0},
        "ebit": 15000000000,
        "ev": 600000000000,
        "nopat": 10000000000,
        "invested_capital": 100000000000,
        "ebitda": 20000000000,
        "pe": 80.0,
        "ps": 8.0,
        "peg": 3.0
    }
}

# Margine predefinito per approssimare EBIT da EBITDA
DEFAULT_EBIT_MARGIN_PROX: float = 0.85
