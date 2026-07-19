"""
Test per dataclass, validazione input e selezione asset di release.

Autore: Enrico Martini
Versione: 0.7.14
"""

import os
import sys

import pandas as pd
import pytest

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import (
    StockData,
    EtfData,
    validate_input_data,
    pick_release_asset,
    _closest_price,
    _historical_series_from_statements,
)


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


# ---------------------------------------------------------------------------
# StockData: nuovi campi storici (campanelli d'allarme)
# ---------------------------------------------------------------------------

def test_stockdata_roundtrip_with_history_fields():
    data = StockData(
        company_name="Apple Inc.",
        pe=25.0,
        pe_history=[18.0, 20.0, 22.0],
        ebit_margin_history=[30.0, 28.0, 25.0],
        fcf=1000.0,
        fcf_history=[900.0, 950.0, 1000.0],
        price_change_hist_pct=15.5,
    )
    clone = StockData.from_dict(data.to_dict())
    assert clone == data


def test_stockdata_history_defaults_are_empty():
    data = StockData()
    assert data.pe_history == []
    assert data.ebit_margin_history == []
    assert data.fcf_history == []
    assert data.fcf == 0.0
    assert data.price_change_hist_pct == 0.0


# ---------------------------------------------------------------------------
# _closest_price / _historical_series_from_statements
# ---------------------------------------------------------------------------

def _make_hist(dates, closes):
    return pd.DataFrame({"Close": closes}, index=pd.DatetimeIndex(dates))


def test_closest_price_finds_nearest_date():
    hist = _make_hist(
        ["2021-01-04", "2022-01-03", "2023-01-02", "2024-01-02"],
        [100.0, 150.0, 200.0, 250.0],
    )
    assert _closest_price(hist, pd.Timestamp("2022-12-30")) == 200.0


def test_closest_price_handles_tz_aware_index():
    hist = _make_hist(
        ["2022-01-03", "2023-01-02"],
        [150.0, 200.0],
    )
    hist.index = hist.index.tz_localize("America/New_York")
    assert _closest_price(hist, pd.Timestamp("2023-01-01")) == 200.0


def test_closest_price_empty_history_returns_zero():
    assert _closest_price(pd.DataFrame(), pd.Timestamp("2023-01-01")) == 0.0


def test_historical_series_builds_pe_margin_fcf_and_price_change():
    # 3 esercizi annuali (dal piu' vecchio al piu' recente), come restituiti
    # da ticker.income_stmt / ticker.cashflow di yfinance.
    periods = [pd.Timestamp("2023-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")]
    inc_stmt = pd.DataFrame(
        {
            periods[0]: {"Total Revenue": 1000.0, "EBIT": 300.0, "Diluted EPS": 5.0},
            periods[1]: {"Total Revenue": 1100.0, "EBIT": 275.0, "Diluted EPS": 5.5},
            periods[2]: {"Total Revenue": 1200.0, "EBIT": 240.0, "Diluted EPS": 6.0},
        }
    )
    cashflow = pd.DataFrame(
        {
            periods[0]: {"Operating Cash Flow": 400.0, "Capital Expenditure": -100.0},
            periods[1]: {"Operating Cash Flow": 380.0, "Capital Expenditure": -120.0},
            periods[2]: {"Operating Cash Flow": 350.0, "Capital Expenditure": -150.0},
        }
    )
    hist = _make_hist(
        ["2023-12-30", "2024-12-30", "2025-12-30"],
        [100.0, 150.0, 180.0],
    )

    pe_hist, margin_hist, fcf_hist, price_change = _historical_series_from_statements(inc_stmt, cashflow, hist)

    assert pe_hist == pytest.approx([100.0 / 5.0, 150.0 / 5.5, 180.0 / 6.0])
    assert margin_hist == pytest.approx([30.0, 25.0, 20.0])
    assert fcf_hist == pytest.approx([300.0, 260.0, 200.0])
    assert price_change == pytest.approx(((180.0 / 100.0) - 1) * 100)


def test_historical_series_empty_income_statement_returns_empty():
    pe_hist, margin_hist, fcf_hist, price_change = _historical_series_from_statements(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    )
    assert pe_hist == []
    assert margin_hist == []
    assert fcf_hist == []
    assert price_change == 0.0
