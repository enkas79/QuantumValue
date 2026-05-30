"""
Modulo Cache.

Gestisce il caching locale dei dati finanziari per ridurre le chiamate HTTP
ai provider esterni (Yahoo Finance, FMP).

Autore: Enrico Martini
Versione: 0.6.5
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from config import CACHE_DB_PATH, CACHE_EXPIRY_HOURS

logger = logging.getLogger("QuantumValue")


def _init_cache_db() -> sqlite3.Connection:
    """
    Inizializza il database SQLite per il caching.
    
    Returns:
        sqlite3.Connection: Connessione al database.
    """
    # Assicurati che la directory esista
    cache_dir = os.path.dirname(CACHE_DB_PATH)
    if cache_dir and not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    conn = sqlite3.connect(CACHE_DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_cached(key: str) -> Optional[Dict[str, Any]]:
    """
    Recupera un valore dalla cache se non è scaduto.
    
    Args:
        key (str): Chiave univoca per il dato cacheato.
    
    Returns:
        Optional[Dict[str, Any]]: Dati cacheati o None se scaduti/inesistenti.
    """
    try:
        conn = _init_cache_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value, timestamp FROM cache WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            value_json, timestamp_str = result
            timestamp = datetime.fromisoformat(timestamp_str)
            expiry_time = timedelta(hours=CACHE_EXPIRY_HOURS)
            
            if datetime.now() - timestamp < expiry_time:
                logger.debug(f"Cache hit per chiave: {key}")
                return json.loads(value_json)
            else:
                logger.debug(f"Cache scaduto per chiave: {key}")
                # Rimuovi il record scaduto
                _remove_cached(key)
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero dalla cache per {key}: {str(e)}")
        return None


def set_cached(key: str, value: Dict[str, Any]) -> bool:
    """
    Salva un valore nella cache.
    
    Args:
        key (str): Chiave univoca per il dato.
        value (Dict[str, Any]): Dati da cacheare.
    
    Returns:
        bool: True se il salvataggio è riuscito, False altrimenti.
    """
    try:
        conn = _init_cache_db()
        value_json = json.dumps(value)
        timestamp = datetime.now().isoformat()
        
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
            (key, value_json, timestamp)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Cache salvato per chiave: {key}")
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio nella cache per {key}: {str(e)}")
        return False


def _remove_cached(key: str) -> bool:
    """
    Rimuove un valore dalla cache.
    
    Args:
        key (str): Chiave del dato da rimuovere.
    
    Returns:
        bool: True se la rimozione è riuscita, False altrimenti.
    """
    try:
        conn = _init_cache_db()
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Errore nella rimozione dalla cache per {key}: {str(e)}")
        return False


def clear_cache() -> bool:
    """
    Svuota completamente la cache.
    
    Returns:
        bool: True se la pulizia è riuscita, False altrimenti.
    """
    try:
        conn = _init_cache_db()
        conn.execute("DELETE FROM cache")
        conn.commit()
        conn.close()
        logger.info("Cache svuotata completamente")
        return True
    except Exception as e:
        logger.error(f"Errore nello svuotamento della cache: {str(e)}")
        return False


def get_cache_stats() -> Dict[str, int]:
    """
    Restituisce statistiche sulla cache.
    
    Returns:
        Dict[str, int]: Dizionario con conteggi (totale, scaduti, validi).
    """
    try:
        conn = _init_cache_db()
        cursor = conn.cursor()
        
        # Totale record
        cursor.execute("SELECT COUNT(*) FROM cache")
        total = cursor.fetchone()[0]
        
        # Record scaduti
        expiry_time = timedelta(hours=CACHE_EXPIRY_HOURS)
        current_time = datetime.now().isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM cache WHERE timestamp < datetime(?, '-' || ? || ' hours')",
            (current_time, CACHE_EXPIRY_HOURS)
        )
        expired = cursor.fetchone()[0]
        
        conn.close()
        return {
            "total": total,
            "expired": expired,
            "valid": total - expired
        }
    except Exception as e:
        logger.error(f"Errore nel recupero statistiche cache: {str(e)}")
        return {"total": 0, "expired": 0, "valid": 0}
