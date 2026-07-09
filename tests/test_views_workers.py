"""
Test di regressione per la gestione dei riferimenti ai worker QThread in
MainWindow.

Riproduce il crash segnalato in produzione:
    RuntimeError: wrapped C/C++ object of type SearchWorker has been deleted
Il worker veniva schedulato per la distruzione con deleteLater(), ma il
riferimento Python (self.search_worker) non veniva mai azzerato: una
richiesta di ricerca successiva a distruzione avvenuta toccava un oggetto
Qt gia' eliminato tramite la guardia "self.search_worker.isRunning()".

Nota implementativa: qui si usa qtbot.waitUntil() (polling sullo stato
finale) invece di qtbot.waitSignal(). A differenza dei test in
test_controllers.py - dove worker.start() e' dentro il blocco "with
qtbot.waitSignal(...)" e quindi la connessione precede l'avvio - qui il
worker viene avviato internamente da _on_search_requested() prima che il
test possa collegarsi al segnale. Con provider mockati (istantanei) il
thread puo' emettere "finished" prima che qtbot.waitSignal si connetta:
le connessioni queued di Qt si valutano al momento dell'emit, quindi una
connessione tardiva perderebbe l'evento e il test si bloccherebbe fino al
timeout. waitUntil, basato su polling dello stato, non ha questa race.

Autore: Enrico Martini
Versione: 0.7.12
"""

import os
import sys

import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Salta l'intero modulo se PyQt6 o pytest-qt non sono disponibili
pytest.importorskip("PyQt6.QtCore")
pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QDialog, QMessageBox

import models
import views


@pytest.fixture
def main_window(qtbot, monkeypatch):
    """MainWindow pronta per i test, senza dialoghi modali ne' rete reale."""
    # MainWindow.__init__ schedula un controllo aggiornamenti reale via rete
    # (QTimer.singleShot a 1s): mockato per non dipendere dalla rete del
    # sandbox e non far scattare un secondo UpdateCheckWorker durante i test.
    monkeypatch.setattr(models, "check_for_updates", lambda v, repo: (False, v, ""))

    # I QMessageBox statici e TickerSearchDialog.exec() sono modali: in un
    # ambiente headless nessuno li chiude e bloccherebbero l'event loop per
    # sempre. Mockati per isolare il comportamento sotto test: la sola
    # gestione dei riferimenti ai worker.
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(views.TickerSearchDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    window = views.MainWindow()
    qtbot.addWidget(window)
    # Evita anche il dialogo modale di setup FMP al primo avvio
    window.settings.setValue("fmp_asked_once", True)
    yield window
    window.close()


def test_search_worker_ref_cleared_after_success(qtbot, main_window, monkeypatch):
    # Nessun match esatto: apre (il TickerSearchDialog mockato) senza bloccare
    monkeypatch.setattr(models, "search_by_name",
                        lambda q, quote_types=('EQUITY', 'ETF'): [("NOMATCH", "Nessuna Corrispondenza", "NASDAQ (USA)")])

    main_window.input_ticker.setText("QUERY")
    main_window._on_search_requested()
    assert main_window.search_worker is not None

    qtbot.waitUntil(lambda: main_window.search_worker is None, timeout=5000)

    # Riproduzione esatta della guardia che andava in crash: prima del fix,
    # l'attributo restava valorizzato con un oggetto C++ gia' distrutto e
    # isRunning() sollevava RuntimeError.
    result = (main_window.search_worker and main_window.search_worker.isRunning()) or \
             (main_window.etf_worker and main_window.etf_worker.isRunning())
    assert not result


def test_search_worker_ref_cleared_after_error(qtbot, main_window, monkeypatch):
    def boom(query, quote_types=('EQUITY', 'ETF')):
        raise RuntimeError("rete non disponibile")

    monkeypatch.setattr(models, "search_by_name", boom)

    main_window.input_ticker.setText("QUERY")
    main_window._on_search_requested()
    assert main_window.search_worker is not None

    qtbot.waitUntil(lambda: main_window.search_worker is None, timeout=5000)
    # Non deve sollevare RuntimeError
    assert not (main_window.search_worker and main_window.search_worker.isRunning())


def test_second_search_after_completion_does_not_crash(qtbot, main_window, monkeypatch):
    """Scenario esatto del bug: due ricerche in sequenza, la seconda dopo il completamento della prima."""
    monkeypatch.setattr(models, "search_by_name",
                        lambda q, quote_types=('EQUITY', 'ETF'): [("NOMATCH", "Nessuna Corrispondenza", "NASDAQ (USA)")])

    main_window.input_ticker.setText("PRIMA")
    main_window._on_search_requested()
    assert main_window.search_worker is not None
    qtbot.waitUntil(lambda: main_window.search_worker is None, timeout=5000)

    # Prima del fix, questa seconda chiamata sollevava:
    # RuntimeError: wrapped C/C++ object of type SearchWorker has been deleted
    main_window.input_ticker.setText("SECONDA")
    main_window._on_search_requested()
    assert main_window.search_worker is not None
    qtbot.waitUntil(lambda: main_window.search_worker is None, timeout=5000)


def test_etf_worker_ref_cleared_after_success(qtbot, main_window, monkeypatch):
    etf = models.EtfData(company_name="iShares Core MSCI World", ter=0.20, aum=5000.0)
    monkeypatch.setattr(models, "fetch_etf_data", lambda q: etf)

    main_window.rb_etf.setChecked(True)
    main_window.input_ticker.setText("SWDA")
    main_window._on_search_requested()
    assert main_window.etf_worker is not None

    qtbot.waitUntil(lambda: main_window.etf_worker is None, timeout=5000)
    assert not (main_window.etf_worker and main_window.etf_worker.isRunning())


def test_etf_name_search_fallback_on_direct_fetch_failure(qtbot, main_window, monkeypatch):
    """Se il Ticker/ISIN diretto non trova l'ETF, deve scattare automaticamente
    la ricerca per nome (stesso comportamento gia' presente per le Azioni)."""
    def boom(query):
        raise ValueError(f"ETF '{query}' non trovato.")
    monkeypatch.setattr(models, "fetch_etf_data", boom)

    search_calls = []

    def fake_search(query, quote_types=('EQUITY', 'ETF')):
        search_calls.append((query, quote_types))
        return [("SWDA.MI", "iShares Core MSCI World", "Borsa Italiana (Milano)")]

    monkeypatch.setattr(models, "search_by_name", fake_search)

    main_window.rb_etf.setChecked(True)
    main_window.input_ticker.setText("iShares Core MSCI World")
    main_window._on_search_requested()
    assert main_window.etf_worker is not None

    # Il fallimento del fetch diretto innesca il SearchWorker per nome (solo ETF)
    qtbot.waitUntil(lambda: main_window.etf_worker is None, timeout=5000)
    qtbot.waitUntil(lambda: main_window.search_worker is None, timeout=5000)

    # Il campo di input forza il maiuscolo (comportamento gia' esistente)
    assert search_calls == [("ISHARES CORE MSCI WORLD", ('ETF',))]


def test_fetch_worker_ref_cleared_after_success(qtbot, main_window):
    main_window.fetcher.fetch_data = lambda ticker: models.StockData(company_name="Fake Corp", ev=1.0)

    main_window._start_data_fetch("FAKE")
    assert main_window.fetch_worker is not None

    qtbot.waitUntil(lambda: main_window.fetch_worker is None, timeout=5000)
    assert not (main_window.fetch_worker and main_window.fetch_worker.isRunning())
