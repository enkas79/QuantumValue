"""
Test per il modulo cache (SQLite locale).

Autore: Enrico Martini
Versione: 0.7.13
"""

import os
import sys

import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cache


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Cache isolata su un database temporaneo, richiusa a fine test."""
    monkeypatch.setattr(cache, "CACHE_DB_PATH", str(tmp_path / "test_cache.db"))
    monkeypatch.setattr(cache, "_conn", None)
    yield cache
    if cache._conn is not None:
        cache._conn.close()
        cache._conn = None


def test_set_and_get_roundtrip(temp_cache):
    payload = {"ticker": "AAPL", "ev": 2_000_000_000.0, "prices": {"current": 180.0}}
    assert temp_cache.set_cached("stock_AAPL", payload) is True
    assert temp_cache.get_cached("stock_AAPL") == payload


def test_get_missing_key_returns_none(temp_cache):
    assert temp_cache.get_cached("chiave_inesistente") is None


def test_expired_entry_returns_none_and_is_removed(temp_cache, monkeypatch):
    temp_cache.set_cached("stock_MSFT", {"ev": 1.0})
    # Con scadenza a 0 ore ogni record risulta immediatamente scaduto
    monkeypatch.setattr(temp_cache, "CACHE_EXPIRY_HOURS", 0)
    assert temp_cache.get_cached("stock_MSFT") is None
    # Il record scaduto viene rimosso fisicamente dal database
    monkeypatch.setattr(temp_cache, "CACHE_EXPIRY_HOURS", 1)
    assert temp_cache.get_cached("stock_MSFT") is None


def test_overwrite_same_key(temp_cache):
    temp_cache.set_cached("k", {"v": 1})
    temp_cache.set_cached("k", {"v": 2})
    assert temp_cache.get_cached("k") == {"v": 2}


def test_clear_cache(temp_cache):
    temp_cache.set_cached("a", {"v": 1})
    temp_cache.set_cached("b", {"v": 2})
    assert temp_cache.clear_cache() is True
    assert temp_cache.get_cached("a") is None
    assert temp_cache.get_cached("b") is None


def test_cache_stats(temp_cache):
    temp_cache.set_cached("a", {"v": 1})
    temp_cache.set_cached("b", {"v": 2})
    stats = temp_cache.get_cache_stats()
    assert stats["total"] == 2
    assert stats["valid"] + stats["expired"] == 2
