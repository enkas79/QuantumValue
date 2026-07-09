"""
Modulo Utils (Utility).

Contiene funzioni pure di supporto, gestione globale delle eccezioni
e inizializzazione del sistema di logging accoppiato su file in area sicura.

Autore: Enrico Martini
Versione: 0.7.10
"""

import os
import sys
import traceback
import logging
import threading
import tempfile
from typing import Any, Union
from logging.handlers import RotatingFileHandler

# Aggiungi la directory corrente al path per importare i moduli locali
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PyQt6.QtWidgets import QMessageBox, QApplication
    from PyQt6.QtCore import QThread
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# Logger globale di riferimento per l'intera applicazione
logger = logging.getLogger("QuantumValue")


def setup_logging() -> None:
    """
    Inizializza il file log di debug locale in una directory con permessi garantiti
    (Home dell'utente) e aggancia i gestori di eccezione nativi di Python.
    """
    # Determina un percorso sicuro dove l'utente ha i permessi di scrittura
    user_home: str = os.path.expanduser("~")
    log_dir: str = os.path.join(user_home, ".quantumvalue")

    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path: str = os.path.join(log_dir, "quantumvalue_debug.log")
    except Exception:
        # Fallback assoluto: usa la cartella dei file temporanei di sistema
        log_path = os.path.join(tempfile.gettempdir(), "quantumvalue_debug.log")

    # Configura RotatingFileHandler per evitare file di log troppo grandi
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,  # Mantiene 3 file di backup
        encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(threadName)s: %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Aggancia il gestore per il thread principale della GUI
    sys.excepthook = global_exception_handler

    # Aggancia il gestore per i thread di background (es. yfinance o QThreads)
    threading.excepthook = threading_exception_handler

    logger.info(f"Sistema di logging inizializzato in: {log_path}")
    try:
        from config import VERSION
        logger.info(f"Versione applicazione: {VERSION}")
    except Exception:
        logger.info("Versione applicazione: sconosciuta")


def global_exception_handler(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
    """Cattura crash imprevisti nel thread principale ed evita la chiusura silenziosa."""
    error_msg: str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"Eccezione non gestita intercettata nel Main Thread:\n{error_msg}")

    if PYQT_AVAILABLE:
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
    if not value_str or not isinstance(value_str, str):
        raise ValueError("Campo vuoto o non valido.")

    for symbol in ('$', '€', '£', ' ', '%'):
        value_str = value_str.replace(symbol, '')

    clean_str: str = value_str.strip().upper().replace(',', '.')
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


def encrypt_api_key(api_key: str) -> str:
    """
    Offusca una API key con Fernet prima di salvarla su disco.

    NOTA: la chiave di cifratura e' derivata da valori statici presenti nel
    sorgente (pubblico) di questo repository, quindi questa funzione protegge
    solo dalla lettura casuale del file di configurazione, non da un attaccante
    che ha accesso al codice. Non usare per segreti che richiedono una vera
    protezione crittografica.

    Args:
        api_key (str): La chiave API da offuscare.

    Returns:
        str: La chiave offuscata in formato base64.
    """
    try:
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        from config import AUTHOR

        salt = b"quantumvalue_salt_123"
        key = hashlib.sha256((AUTHOR + str(salt)).encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.encrypt(api_key.encode()).decode()
    except ImportError:
        # Fallback: ritorna la chiave in plaintext se cryptography non è disponibile
        return api_key


def decrypt_api_key(encrypted: str) -> str:
    """
    Decripta una API key criptata.
    
    Args:
        encrypted (str): La chiave criptata in formato base64.
    
    Returns:
        str: La chiave decriptata.
    """
    try:
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        from config import AUTHOR

        salt = b"quantumvalue_salt_123"
        key = hashlib.sha256((AUTHOR + str(salt)).encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        # Fallback: ritorna la chiave in plaintext se non può essere decriptata
        return encrypted


# Identificativi usati nel portachiavi di sistema per la API key FMP
_KEYRING_SERVICE = "QuantumValue"
_KEYRING_USER = "fmp_api_key"


def save_api_key(settings: Any, api_key: str) -> None:
    """
    Salva la API key FMP nel portachiavi di sistema (libreria keyring).

    Se il portachiavi non e' disponibile (libreria assente o backend di
    sistema mancante), ricade sul vecchio schema: chiave offuscata con
    Fernet dentro QSettings.

    Args:
        settings: QSettings dell'applicazione (usato solo per il fallback).
        api_key (str): La chiave API da salvare.
    """
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, api_key)
        # Rimuove l'eventuale copia offuscata legacy da QSettings
        settings.remove("fmp_api_key")
        return
    except Exception:
        logger.warning("Portachiavi di sistema non disponibile: salvo la API key offuscata in QSettings.")
    settings.setValue("fmp_api_key", encrypt_api_key(api_key))


def load_api_key(settings: Any) -> str:
    """
    Carica la API key FMP dal portachiavi di sistema, con fallback su QSettings.

    Se trova una chiave legacy in QSettings e il portachiavi e' disponibile,
    la migra automaticamente al portachiavi e rimuove la copia offuscata.

    Args:
        settings: QSettings dell'applicazione.

    Returns:
        str: La API key, o stringa vuota se non configurata.
    """
    try:
        import keyring
        stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        if stored:
            return stored
    except Exception:
        pass

    encrypted = str(settings.value("fmp_api_key", "") or "")
    if not encrypted:
        return ""
    api_key = decrypt_api_key(encrypted)

    # Migrazione trasparente della chiave legacy al portachiavi
    if api_key:
        try:
            import keyring
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, api_key)
            settings.remove("fmp_api_key")
        except Exception:
            pass
    return api_key


def delete_api_key(settings: Any) -> None:
    """
    Elimina la API key FMP sia dal portachiavi di sistema sia da QSettings.

    Args:
        settings: QSettings dell'applicazione.
    """
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
    except Exception:
        pass
    settings.remove("fmp_api_key")
