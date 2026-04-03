"""
Modulo di Configurazione.

Contiene le costanti globali, i metadati dell'applicazione
e le mappe di conversione fisse. Nessuna logica applicativa qui.

Autore: Enrico Martini
Versione: 0.3.4
"""

APP_NAME: str = "QuantumValue Analysis"
VERSION: str = "0.3.4"
AUTHOR: str = "Enrico Martini"
GITHUB_REPO: str = "enkas79/QuantumValueRepo"

# Mappatura delle borse valori usate da Yahoo Finance
YAHOO_EXCHANGE_MAP: dict[str, str] = {
    "NYQ": "NYSE", "NMS": "NASDAQ", "MIL": "MIB30", "PAR": "CAC40",
    "FRA": "DAX", "GER": "DAX", "LSE": "LSE", "MCE": "IBEX35",
    "AMS": "AEX", "HAN": "HAN", "EBS": "SWX"
}