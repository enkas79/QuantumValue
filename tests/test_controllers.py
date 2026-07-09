"""
Test per i worker QThread del Controller (con pytest-qt e provider mockati).

Autore: Enrico Martini
Versione: 0.7.14
"""

import os
import sys

import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Salta l'intero modulo se PyQt6 o pytest-qt non sono disponibili
pytest.importorskip("PyQt6.QtCore")
pytest.importorskip("pytestqt")

import models
import controllers


def test_search_worker_success(qtbot, monkeypatch):
    results = [("AAPL", "Apple Inc.", "NASDAQ (USA)")]
    monkeypatch.setattr(models, "search_by_name", lambda q, quote_types=('EQUITY', 'ETF'): results)

    worker = controllers.SearchWorker("apple")
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()
    assert blocker.args == [results, "apple"]
    worker.wait()


def test_search_worker_error(qtbot, monkeypatch):
    def boom(query, quote_types=('EQUITY', 'ETF')):
        raise RuntimeError("rete non disponibile")

    monkeypatch.setattr(models, "search_by_name", boom)

    worker = controllers.SearchWorker("apple")
    with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
        worker.start()
    assert "rete non disponibile" in blocker.args[0]
    worker.wait()


def test_fetch_worker_emits_stockdata(qtbot):
    class FakeFetcher:
        def fetch_data(self, ticker):
            return models.StockData(company_name="Fake Corp", ev=10.0)

    worker = controllers.FetchWorker(FakeFetcher(), "FAKE")
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()
    data = blocker.args[0]
    assert isinstance(data, models.StockData)
    assert data.company_name == "Fake Corp"
    worker.wait()


def test_fetch_worker_valueerror_becomes_error_signal(qtbot):
    class FailingFetcher:
        def fetch_data(self, ticker):
            raise ValueError("Ticker inesistente")

    worker = controllers.FetchWorker(FailingFetcher(), "XXX")
    with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
        worker.start()
    assert "Ticker inesistente" in blocker.args[0]
    worker.wait()


def test_etf_worker_success(qtbot, monkeypatch):
    etf = models.EtfData(company_name="iShares Core MSCI World", ter=0.20, aum=5000.0)
    monkeypatch.setattr(models, "fetch_etf_data", lambda q: etf)

    worker = controllers.EtfFetchWorker("SWDA")
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()
    assert blocker.args[0] == etf
    worker.wait()


def test_etf_worker_error(qtbot, monkeypatch):
    def boom(query):
        raise ValueError("ETF non trovato")

    monkeypatch.setattr(models, "fetch_etf_data", boom)

    worker = controllers.EtfFetchWorker("XYZ")
    with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
        worker.start()
    assert "ETF non trovato" in blocker.args[0]
    worker.wait()


def test_update_worker_success(qtbot, monkeypatch):
    monkeypatch.setattr(models, "check_for_updates",
                        lambda v, repo: (True, "9.9.9", "https://example.com/setup.exe"))

    worker = controllers.UpdateCheckWorker("0.1.0", "owner/repo")
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()
    assert blocker.args == [True, "9.9.9", "https://example.com/setup.exe"]
    worker.wait()
