"""
Test per dataclass, validazione input e selezione asset di release.

Autore: Enrico Martini
Versione: 0.7.12
"""

import os
import sys

import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import StockData, EtfData, validate_input_data, pick_release_asset


# ---------------------------------------------------------------------------
# StockData / EtfData
# ---------------------------------------------------------------------------

def test_stockdata_roundtrip():
    data = StockData(company_name="Apple Inc.", ev=2e12, sparkline=[1.0, 2.0])
    clone = StockData.from_dict(data.to_dict())
    assert clone == data


def test_stockdata_from_dict_ignores_unknown_keys():
    data = StockData.from_dict({"company_name": "X", "campo_ignoto": 42})
    assert data.company_name == "X"
    assert not hasattr(data, "campo_ignoto")


def test_stockdata_defaults_for_missing_keys():
    data = StockData.from_dict({"ev": 10.0})
    assert data.ev == 10.0
    assert data.company_name == "N/A"
    assert data.sparkline == []
    assert data.prices == {}


def test_etfdata_roundtrip():
    data = EtfData(company_name="iShares Core", ter=0.20, aum=5000.0)
    clone = EtfData.from_dict(data.to_dict())
    assert clone == data


def test_etfdata_from_dict_ignores_unknown_keys():
    data = EtfData.from_dict({"ter": 0.1, "sconosciuto": True})
    assert data.ter == 0.1


# ---------------------------------------------------------------------------
# validate_input_data
# ---------------------------------------------------------------------------

def _valid_data():
    return {
        'ebit': 100e9, 'ev': 2000e9, 'nopat': 80e9, 'invested_capital': 500e9,
        'ebitda': 120e9, 'pe': 25.0, 'ps': 6.0, 'peg': 1.5,
    }


def test_validate_ok():
    assert validate_input_data(_valid_data()) == {}


def test_validate_ev_non_positive():
    data = _valid_data()
    data['ev'] = 0.0
    assert 'ev' in validate_input_data(data)


def test_validate_invested_capital_non_positive():
    data = _valid_data()
    data['invested_capital'] = -1.0
    assert 'invested_capital' in validate_input_data(data)


def test_validate_ebit_greater_than_ev():
    data = _valid_data()
    data['ebit'] = data['ev'] * 2
    assert 'ebit' in validate_input_data(data)


def test_validate_roic_above_100():
    data = _valid_data()
    data['nopat'] = data['invested_capital'] * 2
    assert 'nopat' in validate_input_data(data)


def test_validate_extreme_multiples():
    data = _valid_data()
    data['pe'] = 500.0
    data['ps'] = 80.0
    data['peg'] = -1.0
    warnings = validate_input_data(data)
    assert {'pe', 'ps', 'peg'} <= set(warnings)


# ---------------------------------------------------------------------------
# pick_release_asset
# ---------------------------------------------------------------------------

ASSETS = [
    {"name": "QuantumValue_Analysis_Setup_v0.7.9.exe",
     "browser_download_url": "https://example.com/setup.exe"},
    {"name": "QuantumValue_Analysis_v0.7.9_amd64.deb",
     "browser_download_url": "https://example.com/pacchetto.deb"},
    {"name": "QuantumValue_Analysis_v0.7.9_macOS.zip",
     "browser_download_url": "https://example.com/bundle.zip"},
]


@pytest.mark.parametrize("platform, expected", [
    ("win32", "https://example.com/setup.exe"),
    ("linux", "https://example.com/pacchetto.deb"),
    ("darwin", "https://example.com/bundle.zip"),
])
def test_pick_release_asset_per_platform(platform, expected):
    assert pick_release_asset(ASSETS, platform=platform) == expected


def test_pick_release_asset_no_match():
    assert pick_release_asset([{"name": "note.txt", "browser_download_url": "x"}],
                              platform="win32") == ""


def test_pick_release_asset_empty_list():
    assert pick_release_asset([], platform="linux") == ""
