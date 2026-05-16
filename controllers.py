"""
Modulo Controller (QThreads).

Gestisce tutti i task asincroni interfacciando i Models con la View (GUI)
in modo da non bloccare mai l'interfaccia utente principale.

Autore: Enrico Martini
Versione: 0.5.0
"""

from typing import Optional, List, Tuple, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from models import GitHubUpdateManager, TickerSearcher, FinancialDataFetcher, EtfDataFetcher


class UpdateCheckWorker(QThread):
    """
    Worker in background per la verifica degli aggiornamenti su GitHub.

    Args:
        current_version (str): Versione attuale memorizzata.
        repo (str): Percorso repository GitHub.
        parent (Optional[QObject]): Oggetto QObject genitore del thread.
    """
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)

    def __init__(self, current_version: str, repo: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.current_version: str = current_version
        self.repo: str = repo

    def run(self) -> None:
        """Esegue il polling asincrono su GitHub."""
        try:
            update_avail, new_ver, url = GitHubUpdateManager.check_for_updates(self.current_version, self.repo)
            self.finished.emit(update_avail, new_ver, url)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore fatale controllo aggiornamenti: {str(e)}")


class SearchWorker(QThread):
    """
    Worker in background per la ricerca testuale dei Ticker.

    Args:
        query (str): Testo da ricercare.
        parent (Optional[QObject]): Oggetto QObject genitore del thread.
    """
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, query: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.query: str = query

    def run(self) -> None:
        """Esegue la ricerca testuale di aziende ed ETF."""
        try:
            results: List[Tuple[str, str, str]] = TickerSearcher.search_by_name(self.query)
            self.finished.emit(results, self.query)
        except Exception as e:
            self.error.emit(str(e))


class FetchWorker(QThread):
    """
    Worker in background per il download dei dati finanziari aziendali.

    Args:
        fetcher (FinancialDataFetcher): Istanza del fetcher azionario con stato.
        ticker (str): Ticker da scaricare.
        parent (Optional[QObject]): Oggetto QObject genitore del thread.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, fetcher: FinancialDataFetcher, ticker: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.fetcher: FinancialDataFetcher = fetcher
        self.ticker: str = ticker

    def run(self) -> None:
        """Scarica i fondamentali contabili."""
        try:
            data: Dict[str, Any] = self.fetcher.fetch_data(self.ticker)
            self.finished.emit(data)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore imprevisto durante il download: {str(e)}")


class EtfFetchWorker(QThread):
    """
    Worker specifico in background per il download dei dati ETF.

    Args:
        fetcher (EtfDataFetcher): Istanza o classe per scaricare i fondi passivi.
        query (str): Ticker o ISIN dell'ETF.
        parent (Optional[QObject]): Oggetto QObject genitore del thread.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, fetcher: EtfDataFetcher, query: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.fetcher: EtfDataFetcher = fetcher
        self.query: str = query

    def run(self) -> None:
        """Scarica le metriche dell'ETF."""
        try:
            data: Dict[str, Any] = self.fetcher.fetch_data(self.query)
            self.finished.emit(data)
        except ValueError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Errore imprevisto ETF: {str(e)}")