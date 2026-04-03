"""
Modulo Utils (Utility).

Contiene classi e funzioni di supporto indipendenti dal dominio,
come la formattazione dei dati e la gestione globale delle eccezioni.

Autore: Enrico Martini
Versione: 0.3.4
"""

import traceback
from typing import Any

# Importazione Qt6 per la finestra di errore globale
try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError as e:
    import sys
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)


def global_exception_handler(exc_type: type, exc_value: BaseException, exc_tb: Any) -> None:
    """
    Cattura crash imprevisti nel thread principale ed evita la chiusura silenziosa.
    
    Args:
        exc_type (type): Tipo dell'eccezione sollevata.
        exc_value (BaseException): Valore o messaggio dell'eccezione.
        exc_tb (Any): Traceback dell'errore.
    """
    error_msg: str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Errore Fatale di Sistema")
    msg.setText("Il programma ha riscontrato un errore critico.")
    msg.setInformativeText(str(exc_value))
    msg.setDetailedText(error_msg)
    msg.exec()


class DataFormatter:
    """Classe di supporto per la formattazione e sanitizzazione dei dati numerici."""

    @staticmethod
    def parse_to_float(value_str: str) -> float:
        """
        Converte una stringa formattata (es. '1.5M', '3,2B', '5%') in un float.
        
        Args:
            value_str (str): Valore stringa da parsare.
            
        Returns:
            float: Il valore numerico estratto.
        """
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

    @staticmethod
    def format_to_string(value: float) -> str:
        """
        Formatta un float in una stringa leggibile per la UI.
        
        Args:
            value (float): Valore da formattare.
            
        Returns:
            str: Valore stringa formattato.
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