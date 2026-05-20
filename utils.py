"""
Modulo Utils (Utility).

Contiene funzioni pure di supporto, gestione globale delle eccezioni
e inizializzazione del sistema di logging accoppiato su file.

Autore: Enrico Martini
Versione: 0.6.3
"""

import traceback
import sys
import logging
import threading
from typing import Any

try:
    from PyQt6.QtWidgets import QMessageBox, QApplication
    from PyQt6.QtCore import QThread
except ImportError as e:
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)

# Logger globale di riferimento per l'intera applicazione
logger = logging.getLogger("QuantumValue")


def setup_logging() -> None:
    """
    Inizializza il file log di debug locale con flushing immediato
    e aggancia i gestori di eccezione nativi di Python.
    """
    logging.basicConfig(
        filename="quantumvalue_debug.log",
        filemode="w",  # Sovrascrive il file ad ogni avvio per pulizia sequenziale
        format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
        level=logging.DEBUG
    )

    # Aggancia il gestore per il thread principale della GUI
    sys.excepthook = global_exception_handler

    # Aggancia il gestore per i thread di background (es. yfinance o QThreads)
    threading.excepthook = threading_exception_handler

    logger.info("Sistema di tracciamento e logging inizializzato. Versione applicazione: 0.6.3")


def global_exception_handler(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
    """Cattura crash imprevisti nel thread principale ed evita la chiusura silenziosa."""
    error_msg: str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"Eccezione non gestita intercettata nel Main Thread:\n{error_msg}")

    app = QApplication.instance()
    if app and app.thread() != QThread.currentThread():
        return

    try:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Errore Fatale di Sistema")
        msg.setText("Il programma ha riscontrato un errore critico.")
        msg.setInformativeText(str(exc_value))
        msg.setDetailedText(error_msg)
        msg.exec()
    except Exception as e:
        logger.error(f"Impossibile mostrare la QMessageBox grafica di errore: {str(e)}")


def threading_exception_handler(args: Any) -> None:
    """Cattura crash imprevisti nei thread di background asincroni."""
    error_msg: str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    logger.critical(f"Eccezione non gestita nel Thread secondario [{args.thread.name}]:\n{error_msg}")


def parse_to_float(value_str: str) -> float:
    """
    Converte una stringa formattata (inclusi suffissi finanziari e simboli valutari) in un float.

    Args:
        value_str (str): Valore stringa da parsare.

    Returns:
        float: Il valore numerico economico estratto e sanificato.
    """
    for symbol in ('$', '€', '£', ' '):
        value_str = value_str.replace(symbol, '')

    clean_str: str = value_str.strip().upper().replace(',', '.').replace('%', '')
    if not clean_str:
        raise ValueError("Campo vuoto o non valido.")

    multiplier: float = 1.0
    if clean_str.endswith('K'):
        multiplier = 1_000.0
        clean_str = clean_str[:-1]
    elif clean_str.endswith('M'):
        multiplier = 1_000_000.0
        clean_str = clean_str[:-1]
    elif clean_str.endswith('B'):
        multiplier = 1_000_000_000.0
        clean_str = clean_str[:-1]

    try:
        return float(clean_str) * multiplier
    except (ValueError, TypeError):
        raise ValueError(f"Formato numerico non valido: '{value_str}'.")


def format_to_string(value: float) -> str:
    """
    Formatta un float in una stringa leggibile standard per l'interfaccia utente.

    Args:
        value (float): Valore numerico da formattare.

    Returns:
        str: Valore stringa convertito e localizzato con separatori.
    """
    try:
        abs_value: float = abs(value)
        if abs_value >= 1_000_000_000:
            formatted: str = f"{value / 1_000_000_000:.2f}B"
        elif abs_value >= 1_000_000:
            formatted = f"{value / 1_000_000:.2f}M"
        elif abs_value >= 1_000:
            formatted = f"{value / 1_000:.2f}K"
        else:
            formatted = f"{value:.2f}"
        return formatted.replace('.', ',')
    except (TypeError, ValueError):
        return "0,00"