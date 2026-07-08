"""
Test per il modulo models.

Autore: Enrico Martini
Versione: 0.7.6
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
