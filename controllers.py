"""
Modulo Controller (QThreads).

Gestisce tutti i task asincroni interfacciando i Models con la View (GUI)
in modo da non bloccare mai l'interfaccia utente principale.

Autore: Enrico Martini
Versione: 0.4.4
"""

from typing import Optional, List, Tuple, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from models import GitHubUpdateManager, TickerSearcher, FinancialDataFetcher, EtfDataFetcher


class UpdateCheckWorker(QThread):
    """Worker in background per la verifica degli aggiornamenti su GitHub."""
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)

    def __init__(self, current_version: str, repo: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.current_version: str = current_version
        self.repo: str = repo

    def run(self) -> None:
        try:
            update_avail, new_ver, url = GitHubUpdateManager.check_for_updates(self.current_version, self.repo)
            self.finished.emit(update_avail, new_ver, url)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore fatale controllo aggiornamenti: {str(e)}")


class SearchWorker(QThread):
    """Worker in background per la ricerca testuale dei Ticker."""
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, query: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.query: str = query

    def run(self) -> None:
        try:
            results: List[Tuple[str, str, str]] = TickerSearcher.search_by_name(self.query)
            self.finished.emit(results, self.query)
        except Exception as e:
            self.error.emit(str(e))


class FetchWorker(QThread):
    """Worker in background per il download dei dati finanziari aziendali."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, fetcher: FinancialDataFetcher, ticker: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.fetcher: FinancialDataFetcher = fetcher
        self.ticker: str = ticker

    def run(self) -> None:
        try:
            data: Dict[str, Any] = self.fetcher.fetch_data(self.ticker)
            self.finished.emit(data)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore imprevisto durante il download: {str(e)}")


class EtfFetchWorker(QThread):
    """Worker specifico in background per il download dei dati ETF."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, fetcher: EtfDataFetcher, query: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.fetcher: EtfDataFetcher = fetcher
        self.query: str = query

    def run(self) -> None:
        try:
            data: Dict[str, Any] = self.fetcher.fetch_data(self.query)
            self.finished.emit(data)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore imprevisto ETF: {str(e)}")