"""
Test per il modulo models.

Autore: Enrico Martini
Versione: 0.7.14
"""

import pytest
import sys
import os

# Aggiungi la directory src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import (
    calculate_metrics, 
    evaluate_core, 
    evaluate_opportunity, 
    evaluate_etf,
    search_by_name
)


class TestCalculateMetrics:
    """Test per la funzione calculate_metrics."""
    
    def test_calculate_metrics_basic(self):
        """Test con dati validi."""
        data = {
            "ev": 1000.0,
            "ebit": 100.0,
            "invested_capital": 500.0,
            "nopat": 80.0,
            "ebitda": 150.0
        }
        results = calculate_metrics(data)
        assert results["ey"] == 10.0  # (100 / 1000) * 100
        assert results["roic"] == 16.0  # (80 / 500) * 100
        assert abs(results["ev_ebitda"] - 6.666) < 0.01  # 1000 / 150
    
    def test_calculate_metrics_zero_ev(self):
        """Test con EV = 0."""
        data = {
            "ev": 0.0,
            "ebit": 100.0,
            "invested_capital": 500.0,
            "nopat": 80.0,
            "ebitda": 150.0
        }
        results = calculate_metrics(data)
        assert results["ey"] == "Err(EV=0)"
        assert results["roic"] == 16.0
    
    def test_calculate_metrics_zero_invested_capital(self):
        """Test con Capitale Investito = 0."""
        data = {
            "ev": 1000.0,
            "ebit": 100.0,
            "invested_capital": 0.0,
            "nopat": 80.0,
            "ebitda": 150.0
        }
        results = calculate_metrics(data)
        assert results["ey"] == 10.0
        assert results["roic"] == "Err(Cap=0)"
    
    def test_calculate_metrics_zero_ebitda(self):
        """Test con EBITDA = 0."""
        data = {
            "ev": 1000.0,
            "ebit": 100.0,
            "invested_capital": 500.0,
            "nopat": 80.0,
            "ebitda": 0.0
        }
        results = calculate_metrics(data)
        assert results["ey"] == 10.0
        assert results["roic"] == 16.0
        assert results["ev_ebitda"] == "Err(EBITDA=0)"


class TestEvaluateCore:
    """Test per la funzione evaluate_core."""
    
    def test_evaluate_core_excellent(self):
        """Test con valori eccellenti."""
        score, verdict, color, details = evaluate_core(10.0, 15.0, 5.0)
        assert score == 10.0
        assert verdict == "ACQUISTO (Strong Buy)"
        assert color == "#27ae60"  # excellent
        assert "ey" in details
        assert "roic" in details
        assert "ev_ebitda" in details
    
    def test_evaluate_core_good(self):
        """Test con valori buoni."""
        score, verdict, color, details = evaluate_core(8.0, 12.0, 8.0)
        assert score >= 7.0
        assert verdict == "ACQUISTO (Strong Buy)"
    
    def test_evaluate_core_bad(self):
        """Test con valori scadenti."""
        score, verdict, color, details = evaluate_core(2.0, 3.0, 20.0)
        assert score < 6.0
        assert verdict == "LASCIAR PERDERE (Avoid)"
        assert color == "#c0392b"  # bad


class TestEvaluateOpportunity:
    """Test per la funzione evaluate_opportunity."""
    
    def test_evaluate_opportunity_ideal(self):
        """Test con valori ideali."""
        score, verdict, color, details = evaluate_opportunity(15.0, 1.5, 0.8, 8.0)
        assert score == 10.0
        assert verdict == "GRANDE OCCASIONE"
        assert color == "#27ae60"  # excellent
    
    def test_evaluate_opportunity_possible(self):
        """Test con valori accettabili (PE e PS ideali, PEG ed EV/EBITDA no)."""
        score, verdict, color, details = evaluate_opportunity(15.0, 1.5, 1.2, 12.0)
        assert 5.0 <= score < 7.5
        assert verdict == "POSSIBILE OCCASIONE (Valutare)"
    
    def test_evaluate_opportunity_none(self):
        """Test con valori non ideali."""
        score, verdict, color, details = evaluate_opportunity(30.0, 3.0, 2.0, 15.0)
        assert score < 5.0
        assert verdict == "NESSUNA OCCASIONE EVIDENTE"


class TestEvaluateETF:
    """Test per la funzione evaluate_etf."""
    
    def test_evaluate_etf_excellent(self):
        """Test con ETF eccellente."""
        score, verdict, color, details = evaluate_etf(0.15, 1500.0, 20.0, 18.0)
        assert score >= 7.5
        assert verdict == "OTTIMO ETF (Efficiente e Liquido)"
        assert color == "#27ae60"  # excellent
    
    def test_evaluate_etf_good(self):
        """Test con ETF buono (TER accettabile, AUM e rendimento buoni)."""
        score, verdict, color, details = evaluate_etf(0.55, 800.0, 10.0, 8.0)
        assert 6.0 <= score < 7.5
        assert verdict == "BUON ETF (Valido)"
        assert color == "#2ecc71"  # good
    
    def test_evaluate_etf_bad(self):
        """Test con ETF scadente."""
        score, verdict, color, details = evaluate_etf(0.80, 50.0, -5.0, -3.0)
        assert score < 6.0
        assert verdict == "ETF DA EVITARE (Costoso/Illiquido)"
        assert color == "#c0392b"  # bad


class TestSearchByName:
    """Test per la funzione search_by_name."""
    
    @pytest.mark.skip(reason="Richiede connessione internet e Yahoo Finance")
    def test_search_by_name_aapl(self):
        """Test ricerca AAPL."""
        results = search_by_name("AAPL")
        assert len(results) > 0
        assert any("AAPL" in r[0] for r in results)
    
    @pytest.mark.skip(reason="Richiede connessione internet e Yahoo Finance")
    def test_search_by_name_microsoft(self):
        """Test ricerca Microsoft."""
        results = search_by_name("Microsoft")
        assert len(results) > 0
        assert any("MSFT" in r[0] for r in results)


class _FakeHttpResponse:
    """Risposta HTTP fittizia con solo il metodo .json() usato dai provider."""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestTwelveDataProvider:
    """Test per il provider di riserva Twelve Data."""

    def test_fetch_maps_fields_correctly(self, monkeypatch):
        import models

        stats_payload = {
            "meta": {"name": "Example Corp", "currency": "USD"},
            "statistics": {
                "valuations_metrics": {
                    "enterprise_value": 100.0,
                    "trailing_pe": 15.0,
                    "price_to_sales_ttm": 3.0,
                    "peg_ratio": 1.2
                },
                "financials": {
                    "income_statement": {"ebitda": 20.0},
                    "balance_sheet": {
                        "total_debt_mrq": 10.0,
                        "book_value_per_share_mrq": 5.0
                    }
                },
                "stock_statistics": {"shares_outstanding": 4.0}
            }
        }
        quote_payload = {"close": "42.5"}
        responses = [_FakeHttpResponse(stats_payload), _FakeHttpResponse(quote_payload)]

        def fake_get(self, url, params=None, timeout=None):
            return responses.pop(0)

        monkeypatch.setattr(models.requests.Session, "get", fake_get)

        provider = models.TwelveDataProvider(api_key="td-key")
        data = provider.fetch("EXMPL")

        assert data.company_name == "Example Corp"
        assert data.currency == "USD"
        assert data.ev == 100.0
        assert data.ebitda == 20.0
        assert data.pe == 15.0
        assert data.ps == 3.0
        assert data.peg == 1.2
        assert data.invested_capital == 10.0 + 5.0 * 4.0
        assert data.prices["current"] == 42.5

    def test_fetch_without_api_key_raises(self, monkeypatch):
        import models
        # fetch() e' decorato con @_retry_request (tenacity): anche un errore
        # "atteso" come la chiave mancante viene ritentato 3 volte con backoff
        # esponenziale reale. Si azzera l'attesa per non rallentare la suite.
        monkeypatch.setattr("time.sleep", lambda _seconds: None)
        provider = models.TwelveDataProvider(api_key="")
        with pytest.raises(Exception):
            provider.fetch("AAPL")

    def test_fetch_symbol_not_found_raises(self, monkeypatch):
        import models

        monkeypatch.setattr("time.sleep", lambda _seconds: None)

        def fake_get(self, url, params=None, timeout=None):
            return _FakeHttpResponse({"status": "error", "message": "symbol not found"})

        monkeypatch.setattr(models.requests.Session, "get", fake_get)

        provider = models.TwelveDataProvider(api_key="td-key")
        with pytest.raises(Exception):
            provider.fetch("ZZZZZZ")


class TestEodhdProvider:
    """Test per il provider di riserva EODHD."""

    def test_symbol_suffix_defaults_to_us(self):
        import models
        assert models.EodhdProvider._to_eodhd_symbol("AAPL") == "AAPL.US"
        assert models.EodhdProvider._to_eodhd_symbol("ENI.MI") == "ENI.MI"

    def test_fetch_maps_fields_correctly(self, monkeypatch):
        import models

        fund_payload = {
            "General": {"Name": "Example Corp", "CurrencyCode": "USD"},
            "Highlights": {"EBITDA": 20.0, "PERatio": 15.0, "PEGRatio": 1.2},
            "Valuation": {"EnterpriseValue": 100.0, "PriceSalesTTM": 3.0},
            "Financials": {
                "Income_Statement": {
                    "yearly": {
                        "2022-12-31": {"ebit": 12.0},
                        "2023-12-31": {
                            "ebit": 15.0,
                            "incomeBeforeTax": 25.0,
                            "incomeTaxExpense": 5.0
                        }
                    }
                },
                "Balance_Sheet": {
                    "yearly": {
                        "2023-12-31": {
                            "shortLongTermDebtTotal": 10.0,
                            "totalStockholderEquity": 30.0
                        }
                    }
                }
            }
        }
        quote_payload = {"close": "42.5"}
        responses = [_FakeHttpResponse(fund_payload), _FakeHttpResponse(quote_payload)]

        def fake_get(self, url, params=None, timeout=None):
            return responses.pop(0)

        monkeypatch.setattr(models.requests.Session, "get", fake_get)

        provider = models.EodhdProvider(api_key="eodhd-key")
        data = provider.fetch("EXMPL")

        assert data.company_name == "Example Corp"
        assert data.currency == "USD"
        assert data.ev == 100.0
        assert data.ebitda == 20.0
        assert data.ebit == 15.0  # dal periodo annuale piu' recente (2023, non 2022)
        assert data.pe == 15.0
        assert data.ps == 3.0
        assert data.peg == 1.2
        assert data.invested_capital == 10.0 + 30.0
        assert data.prices["current"] == 42.5

    def test_fetch_without_api_key_raises(self, monkeypatch):
        import models
        monkeypatch.setattr("time.sleep", lambda _seconds: None)
        provider = models.EodhdProvider(api_key="")
        with pytest.raises(Exception):
            provider.fetch("AAPL")

    def test_fetch_symbol_not_found_raises(self, monkeypatch):
        import models

        monkeypatch.setattr("time.sleep", lambda _seconds: None)

        def fake_get(self, url, params=None, timeout=None):
            return _FakeHttpResponse({})

        monkeypatch.setattr(models.requests.Session, "get", fake_get)

        provider = models.EodhdProvider(api_key="eodhd-key")
        with pytest.raises(Exception):
            provider.fetch("ZZZZZZ")


class TestFinancialDataFetcherChain:
    """Test per la catena di provider e i fallback di FinancialDataFetcher."""

    def test_providers_chain_yahoo_only_by_default(self):
        import models
        fetcher = models.FinancialDataFetcher()
        assert [p.name for p in fetcher._providers()] == ["Yahoo Finance"]

    def test_providers_chain_includes_all_configured(self):
        import models
        fetcher = models.FinancialDataFetcher(
            fmp_api_key="fmp-key", twelvedata_api_key="td-key", eodhd_api_key="eodhd-key"
        )
        assert [p.name for p in fetcher._providers()] == ["Yahoo Finance", "FMP", "Twelve Data", "EODHD"]

    def test_fetch_data_falls_back_to_extra_backup_provider(self, monkeypatch):
        import models

        monkeypatch.setattr(models, "get_cached", lambda key: None)
        monkeypatch.setattr(models, "set_cached", lambda key, value: True)

        def boom(self, ticker):
            raise ValueError("provider fallito")

        expected = models.StockData(company_name="Fallback Corp", ev=42.0)

        monkeypatch.setattr(models.YahooProvider, "fetch", boom)
        monkeypatch.setattr(models.FmpProvider, "fetch", boom)
        monkeypatch.setattr(models.TwelveDataProvider, "fetch", lambda self, ticker: expected)

        fetcher = models.FinancialDataFetcher(fmp_api_key="fmp-key", twelvedata_api_key="td-key")
        result = fetcher.fetch_data("ZZZZ")
        assert result == expected

    def test_fetch_data_falls_back_through_all_extra_backups(self, monkeypatch):
        import models

        monkeypatch.setattr(models, "get_cached", lambda key: None)
        monkeypatch.setattr(models, "set_cached", lambda key, value: True)

        def boom(self, ticker):
            raise ValueError("provider fallito")

        expected = models.StockData(company_name="EODHD Corp", ev=7.0)

        monkeypatch.setattr(models.YahooProvider, "fetch", boom)
        monkeypatch.setattr(models.FmpProvider, "fetch", boom)
        monkeypatch.setattr(models.TwelveDataProvider, "fetch", boom)
        monkeypatch.setattr(models.EodhdProvider, "fetch", lambda self, ticker: expected)

        fetcher = models.FinancialDataFetcher(
            fmp_api_key="fmp-key", twelvedata_api_key="td-key", eodhd_api_key="eodhd-key"
        )
        result = fetcher.fetch_data("YYYY")
        assert result == expected

    def test_fetch_data_all_providers_fail_raises(self, monkeypatch):
        import models

        monkeypatch.setattr(models, "get_cached", lambda key: None)

        def boom(self, ticker):
            raise ValueError("provider fallito")

        monkeypatch.setattr(models.YahooProvider, "fetch", boom)
        monkeypatch.setattr(models.FmpProvider, "fetch", boom)
        monkeypatch.setattr(models.TwelveDataProvider, "fetch", boom)
        monkeypatch.setattr(models.EodhdProvider, "fetch", boom)

        fetcher = models.FinancialDataFetcher(
            fmp_api_key="fmp-key", twelvedata_api_key="td-key", eodhd_api_key="eodhd-key"
        )
        with pytest.raises(ValueError):
            fetcher.fetch_data("NONEXISTENTTICKERXYZ")
