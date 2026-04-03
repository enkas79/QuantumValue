"""
Modulo Model (Logica di Business).

Contiene esclusivamente le regole matematiche, le valutazioni algoritmiche 
e l'estrazione dati dalle API (Yahoo Finance, FMP, justetf_scraping).
Nessuna dipendenza dalla GUI.

Autore: Enrico Martini
Versione: 0.3.4
"""

import sys
from typing import Dict, Union, Tuple, List, Any

# Gestione dipendenze esterne principali
try:
    import yfinance as yf
    import pandas as pd
    import requests
except ImportError as e:
    print(f"Errore: Librerie mancanti. Eseguire 'pip install yfinance pandas requests'.\nDettagli: {e}")
    sys.exit(1)

# Importazione justetf_scraping (Opzionale ma raccomandata)
try:
    import justetf_scraping as js
    JUSTETF_AVAILABLE = True
except ImportError:
    JUSTETF_AVAILABLE = False
    print("Avviso: 'justetf_scraping' non installato. Fallback Yahoo Finance per ETF attivo.")

from config import YAHOO_EXCHANGE_MAP


class GitHubUpdateManager:
    """Classe Model per la verifica degli aggiornamenti via API GitHub."""

    @staticmethod
    def check_for_updates(current_version: str, repo_path: str) -> Tuple[bool, str, str]:
        """Verifica la presenza di una nuova release su GitHub."""
        api_url: str = f"https://api.github.com/repos/{repo_path}/releases/latest"
        headers: Dict[str, str] = {'Accept': 'application/vnd.github.v3+json'}
        try:
            response = requests.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            data: dict = response.json()
            latest_tag: str = data.get('tag_name', '').replace('v', '')
            html_url: str = data.get('html_url', '')

            if not latest_tag:
                return False, current_version, ""

            update_available: bool = latest_tag > current_version.replace('v', '')
            return update_available, latest_tag, html_url
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Impossibile verificare gli aggiornamenti: {str(e)}")


class FinancialCalculator:
    """Classe Model per i calcoli delle metriche finanziarie base (Azioni)."""

    @staticmethod
    def calculate_metrics(data: Dict[str, float]) -> Dict[str, Union[float, str]]:
        """Esegue i calcoli finanziari di base partendo da un dizionario di input."""
        results: Dict[str, Union[float, str]] = {}
        try:
            ev_val: float = data.get('ev', 0.0)
            ebit_val: float = data.get('ebit', 0.0)
            results['ey'] = (ebit_val / ev_val) * 100 if ev_val != 0 else "Err(EV=0)"
        except (ZeroDivisionError, TypeError): results['ey'] = "Errore"

        try:
            inv_cap: float = data.get('invested_capital', 0.0)
            nopat_val: float = data.get('nopat', 0.0)
            results['roic'] = (nopat_val / inv_cap) * 100 if inv_cap != 0 else "Err(Cap=0)"
        except (ZeroDivisionError, TypeError): results['roic'] = "Errore"

        try:
            ebitda_val: float = data.get('ebitda', 0.0)
            results['ev_ebitda'] = ev_val / ebitda_val if ebitda_val != 0 else "Err(EBITDA=0)"
        except (ZeroDivisionError, TypeError): results['ev_ebitda'] = "Errore"

        return results


class FinancialEvaluator:
    """Classe Model per l'assegnazione dei punteggi e la valutazione (Azioni)."""

    @staticmethod
    def evaluate_core(ey: float, roic: float, ev_ebitda: float) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
        """Valuta EY, ROIC e EV/EBITDA classici restituendo un voto globale di qualità."""
        col_exc, col_good, col_fair, col_weak, col_bad = "#27ae60", "#2ecc71", "#f39c12", "#d35400", "#c0392b"

        if ey >= 10: s_ey, t_ey, c_ey = 10, "Eccellente (>=10%)", col_exc
        elif ey >= 6: s_ey, t_ey, c_ey = 8, "Buono (>=6%)", col_good
        elif ey >= 3: s_ey, t_ey, c_ey = 5, "Sufficiente (>=3%)", col_fair
        elif ey > 0: s_ey, t_ey, c_ey = 3, "Debole (>0%)", col_weak
        else: s_ey, t_ey, c_ey = 1, "Negativo (Attenzione)", col_bad

        if roic >= 15: s_r, t_r, c_r = 10, "Eccellente (>=15%)", col_exc
        elif roic >= 10: s_r, t_r, c_r = 8, "Buono (>=10%)", col_good
        elif roic >= 5: s_r, t_r, c_r = 5, "Sufficiente (>=5%)", col_fair
        elif roic > 0: s_r, t_r, c_r = 3, "Debole (>0%)", col_weak
        else: s_r, t_r, c_r = 1, "Negativo (Distrugge Valore)", col_bad

        if ev_ebitda <= 0: s_ev, t_ev, c_ev = 1, "Negativo", col_bad
        elif ev_ebitda <= 5: s_ev, t_ev, c_ev = 10, "Molto a Sconto (<=5x)", col_exc
        elif ev_ebitda <= 10: s_ev, t_ev, c_ev = 8, "A Sconto (<=10x)", col_good
        elif ev_ebitda <= 15: s_ev, t_ev, c_ev = 5, "Equo (<=15x)", col_fair
        elif ev_ebitda <= 20: s_ev, t_ev, c_ev = 3, "Caro (<=20x)", col_weak
        else: s_ev, t_ev, c_ev = 1, "Molto Caro (>20x)", col_bad

        avg_score: float = round((s_ey + s_r + s_ev) / 3.0, 1)
        details: Dict[str, Dict[str, str]] = {
            'ey': {'text': f"{t_ey} (Voto {s_ey}/10)", 'color': c_ey},
            'roic': {'text': f"{t_r} (Voto {s_r}/10)", 'color': c_r},
            'ev_ebitda': {'text': f"{t_ev} (Voto {s_ev}/10)", 'color': c_ev}
        }

        if avg_score >= 7.5: return avg_score, "ACQUISTO (Strong Buy)", col_exc, details
        elif avg_score >= 6.0: return avg_score, "DA ATTENDERE (Hold)", col_weak, details
        else: return avg_score, "LASCIAR PERDERE (Avoid)", col_bad, details

    @staticmethod
    def evaluate_opportunity(pe: float, ps: float, peg: float, ev_ebitda: float) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
        """Valuta i 4 indicatori per le 'Occasioni in Borsa' fornendo un punteggio su 10 e un verdetto."""
        col_exc, col_fair, col_bad = "#27ae60", "#f39c12", "#c0392b"
        res: Dict[str, Dict[str, str]] = {}
        score: float = 0.0
        
        if 0 < pe < 20: s_pe, t_pe, c_pe = 2.5, "Ideale (< 20)", col_exc
        elif pe <= 0: s_pe, t_pe, c_pe = 0.0, "Negativo (Attenzione)", col_bad
        else: s_pe, t_pe, c_pe = 1.0, "Alto (>= 20)", col_fair
        res['pe'] = {'text': t_pe, 'color': c_pe}
        score += s_pe

        if 0 < ps < 2: s_ps, t_ps, c_ps = 2.5, "Ideale (< 2)", col_exc
        elif ps <= 0: s_ps, t_ps, c_ps = 0.0, "N.D. / Negativo", col_bad
        else: s_ps, t_ps, c_ps = 1.0, "Alto (>= 2)", col_fair
        res['ps'] = {'text': t_ps, 'color': c_ps}
        score += s_ps

        if 0 < peg < 1: s_peg, t_peg, c_peg = 2.5, "Ideale (< 1)", col_exc
        elif peg <= 0: s_peg, t_peg, c_peg = 0.0, "Negativo / N.D.", col_bad
        else: s_peg, t_peg, c_peg = 1.0, "Alto (>= 1)", col_fair
        res['peg'] = {'text': t_peg, 'color': c_peg}
        score += s_peg

        if 0 < ev_ebitda < 10: s_ev, t_ev, c_ev = 2.5, "Ideale (< 10)", col_exc
        elif ev_ebitda <= 0: s_ev, t_ev, c_ev = 0.0, "Negativo (Attenzione)", col_bad
        else: s_ev, t_ev, c_ev = 1.0, "Alto (>= 10)", col_fair
        res['ev_ebitda_occ'] = {'text': t_ev, 'color': c_ev}
        score += s_ev
        
        if score >= 7.5: verdict, v_color = "GRANDE OCCASIONE", col_exc
        elif score >= 5.0: verdict, v_color = "POSSIBILE OCCASIONE (Valutare)", col_fair
        else: verdict, v_color = "NESSUNA OCCASIONE EVIDENTE", col_bad

        return score, verdict, v_color, res


class EtfEvaluator:
    """Classe Model per l'assegnazione dei punteggi e la valutazione degli ETF."""

    @staticmethod
    def evaluate(ter: float, aum: float, ret: float) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
        col_exc, col_good, col_fair, col_bad = "#27ae60", "#2ecc71", "#f39c12", "#c0392b"
        
        if 0 <= ter <= 0.20: s_ter, t_ter, c_ter = 10, "Eccellente (<= 0.20%)", col_exc
        elif ter <= 0.40: s_ter, t_ter, c_ter = 8, "Buono (<= 0.40%)", col_good
        elif ter <= 0.65: s_ter, t_ter, c_ter = 5, "Accettabile (<= 0.65%)", col_fair
        elif ter > 0.65: s_ter, t_ter, c_ter = 2, "Costoso (> 0.65%)", col_bad
        else: s_ter, t_ter, c_ter = 0, "Dati Errati", col_bad
        
        if aum >= 1000: s_aum, t_aum, c_aum = 10, "Eccellente (>= 1000M)", col_exc
        elif aum >= 500: s_aum, t_aum, c_aum = 8, "Buono (>= 500M)", col_good
        elif aum >= 100: s_aum, t_aum, c_aum = 5, "Accettabile (>= 100M)", col_fair
        elif aum > 0: s_aum, t_aum, c_aum = 2, "Rischioso (< 100M)", col_bad
        else: s_aum, t_aum, c_aum = 0, "Dati Errati", col_bad

        if ret >= 15: s_ret, t_ret, c_ret = 10, "Eccellente (>= 15%)", col_exc
        elif ret >= 8: s_ret, t_ret, c_ret = 8, "Buono (>= 8%)", col_good
        elif ret >= 0: s_ret, t_ret, c_ret = 5, "Positivo (>= 0%)", col_fair
        else: s_ret, t_ret, c_ret = 2, "Negativo (< 0%)", col_bad
        
        avg_score: float = round((s_ter + s_aum + s_ret) / 3.0, 1)
        details: Dict[str, Dict[str, str]] = {
            'ter': {'text': f"{t_ter} (Voto {s_ter}/10)", 'color': c_ter},
            'aum': {'text': f"{t_aum} (Voto {s_aum}/10)", 'color': c_aum},
            'ret_1y': {'text': f"{t_ret} (Voto {s_ret}/10)", 'color': c_ret}
        }

        if avg_score >= 7.5: return avg_score, "OTTIMO ETF (Efficiente e Liquido)", col_exc, details
        elif avg_score >= 6.0: return avg_score, "BUON ETF (Valido)", col_good, details
        else: return avg_score, "ETF DA EVITARE (Costoso/Illiquido)", col_bad, details


class TickerSearcher:
    """Classe Model per la ricerca di Ticker (Azioni)."""

    @staticmethod
    def search_by_name(query: str) -> List[Tuple[str, str, str]]:
        """Ricerca i ticker tramite Yahoo Finance."""
        url: str = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10"
        headers: Dict[str, str] = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data: dict = response.json()
            results: List[Tuple[str, str, str]] = []

            for quote in data.get('quotes', []):
                if quote.get('quoteType') in ['EQUITY', 'ETF']:
                    symbol: str = quote.get('symbol', '')
                    name: str = quote.get('shortname', quote.get('longname', 'Sconosciuto'))
                    raw_exchange: str = quote.get('exchange', 'N/A')
                    mapped_exchange: str = YAHOO_EXCHANGE_MAP.get(raw_exchange, raw_exchange)
                    if symbol:
                        results.append((symbol, name, mapped_exchange))
            return results
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete durante la ricerca: {str(e)}")


class EtfDataFetcher:
    """Classe Model dedicata per il recupero dati degli ETF (justetf_scraping o YF fallback)."""
    
    @staticmethod
    def fetch_data(query: str) -> Dict[str, Any]:
        """Scarica i dati analitici dell'ETF indicato."""
        if not query: raise ValueError("Inserire un ISIN, Ticker o Nome ETF valido.")
        
        if JUSTETF_AVAILABLE:
            try:
                df = js.load_overview()
                match = df[df['Ticker'].str.contains(query, case=False, na=False) |
                           df['ISIN'].str.contains(query, case=False, na=False) |
                           df['Name'].str.contains(query, case=False, na=False)]
                
                if not match.empty:
                    row = match.iloc[0]
                    def parse_perc(val: Any) -> float:
                        if pd.isna(val): return 0.0
                        return float(str(val).replace('%', '').strip()) if isinstance(val, str) else float(val)

                    return {
                        'company_name': f"{row.get('Name', 'ETF Sconosciuto')} ({row.get('ISIN', '')})",
                        'currency': 'EUR',
                        'ter': parse_perc(row.get('TER', 0)),
                        'aum': float(row.get('Fund size in m EUR', 0)),
                        'ret_1y': parse_perc(row.get('1 year return', 0)),
                        'ret_3y': parse_perc(row.get('3 year return', 0)),
                        'replication': str(row.get('Replication', 'N/A'))
                    }
            except Exception as e:
                print(f"Fallback justetf fallito: {e}. Passaggio a Yahoo Finance.")

        try:
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            if not info or 'shortName' not in info:
                raise ValueError(f"ETF '{query}' non trovato.")
                
            total_assets = float(info.get('totalAssets', 0.0) or 0.0)
            ytd_ret = float(info.get('ytdReturn', 0.0) or 0.0) * 100 
            ter_yf = float(info.get('annualReportExpenseRatio', 0.0) or info.get('yield', 0.0) or 0.0) * 100

            return {
                'company_name': info.get('longName', query),
                'currency': info.get('currency', 'USD'),
                'ter': ter_yf,
                'aum': total_assets / 1_000_000, 
                'ret_1y': ytd_ret,
                'ret_3y': float(info.get('threeYearAverageReturn', 0.0) or 0.0) * 100,
                'replication': "Fisica/Sintetica (Dato YF non dispo.)"
            }
        except Exception as e:
            raise ValueError(f"Impossibile trovare i dati dell'ETF tramite i provider: {e}")


class FinancialDataFetcher:
    """Classe Model per l'estrazione dei dati azionari dai provider (Yahoo/FMP)."""

    def __init__(self, fmp_api_key: str = "") -> None:
        self.fmp_api_key: str = fmp_api_key

    def fetch_data(self, ticker_symbol: str) -> Dict[str, Any]:
        """Recupera i dati fondamentali dell'azione dal miglior provider disponibile."""
        if not ticker_symbol: raise ValueError("Inserire un Ticker valido.")
        try: return self._fetch_from_yahoo(ticker_symbol)
        except Exception as yf_error:
            if self.fmp_api_key:
                try: return self._fetch_from_fmp(ticker_symbol)
                except Exception as fmp_error: raise ValueError(f"Fallimento totale provider.\nYahoo: {yf_error}\nFMP: {fmp_error}")
            else:
                raise ValueError(f"Errore Yahoo Finance (Nessuna API di backup): {str(yf_error)}")

    def _fetch_from_yahoo(self, ticker_symbol: str) -> Dict[str, Any]:
        ticker = yf.Ticker(ticker_symbol.upper())
        info: dict = ticker.info

        if not info or 'shortName' not in info:
            raise ValueError(f"Ticker '{ticker_symbol}' non trovato su Yahoo.")

        ev: float = float(info.get('enterpriseValue', 0.0) or 0.0)
        ebitda: float = float(info.get('ebitda', 0.0) or 0.0)

        hist = ticker.history(period="1y")
        prices: Dict[str, float] = {'current': 0.0, '1d': 0.0, '1w': 0.0, '1m': 0.0, '1y': 0.0}

        if not hist.empty:
            closes = hist['Close']
            prices['current'] = float(closes.iloc[-1])
            prices['1d'] = float(closes.iloc[-2]) if len(closes) >= 2 else prices['current']
            prices['1w'] = float(closes.iloc[-6]) if len(closes) >= 6 else prices['current'] 
            prices['1m'] = float(closes.iloc[-22]) if len(closes) >= 22 else prices['current'] 
            prices['1y'] = float(closes.iloc[0]) if len(closes) > 0 else prices['current'] 

        pe: float = float(info.get('trailingPE', 0.0) or 0.0)
        ps: float = float(info.get('priceToSalesTrailing12Months', 0.0) or 0.0)
        peg: float = float(info.get('pegRatio', 0.0) or 0.0)

        inc_stmt = ticker.income_stmt
        bal_sheet = ticker.balance_sheet

        ebit: float = ebitda * 0.85
        if not inc_stmt.empty and 'EBIT' in inc_stmt.index:
            try: ebit = float(inc_stmt.loc['EBIT'].iloc[0])
            except (TypeError, ValueError): pass

        tax_prov, pretax = 0.0, 1.0
        if not inc_stmt.empty and 'Tax Provision' in inc_stmt.index:
            try: tax_prov = float(inc_stmt.loc['Tax Provision'].iloc[0])
            except (TypeError, ValueError): pass
        if not inc_stmt.empty and 'Pretax Income' in inc_stmt.index:
            try: pretax = float(inc_stmt.loc['Pretax Income'].iloc[0])
            except (TypeError, ValueError): pass

        tax_rate: float = min(tax_prov / pretax, 0.35) if pretax > 0 and tax_prov > 0 else 0.21
        nopat: float = ebit * (1 - tax_rate)

        total_debt: float = float(info.get('totalDebt', 0.0) or 0.0)
        equity: float = float(info.get('bookValue', 0.0) or 0.0) * float(info.get('sharesOutstanding', 0.0) or 0.0)

        if not bal_sheet.empty and 'Stockholders Equity' in bal_sheet.index:
            try: equity = float(bal_sheet.loc['Stockholders Equity'].iloc[0])
            except (TypeError, ValueError): pass

        return {
            'company_name': info.get('longName', ticker_symbol),
            'currency': info.get('currency', 'USD'),
            'prices': prices, 'ebit': ebit, 'ev': ev, 'nopat': nopat,
            'invested_capital': total_debt + equity, 'ebitda': ebitda,
            'pe': pe, 'ps': ps, 'peg': peg
        }

    def _fetch_from_fmp(self, ticker_symbol: str) -> Dict[str, Any]:
        base_url: str = "https://financialmodelingprep.com/api/v3"
        try:
            prof_resp = requests.get(f"{base_url}/profile/{ticker_symbol}?apikey={self.fmp_api_key}", timeout=10).json()
            if not prof_resp: raise ValueError("Azienda non trovata nel database FMP.")
            profile: dict = prof_resp[0]

            km_resp = requests.get(f"{base_url}/key-metrics-ttm/{ticker_symbol}?apikey={self.fmp_api_key}", timeout=10).json()
            km: dict = km_resp[0] if km_resp else {}
            
            ratios_resp = requests.get(f"{base_url}/ratios-ttm/{ticker_symbol}?apikey={self.fmp_api_key}", timeout=10).json()
            ratios: dict = ratios_resp[0] if ratios_resp else {}

            inc_resp = requests.get(f"{base_url}/income-statement/{ticker_symbol}?limit=1&apikey={self.fmp_api_key}", timeout=10).json()
            inc: dict = inc_resp[0] if inc_resp else {}

            ev: float = float(km.get('enterpriseValueTTM', 0.0) or 0.0)
            ebitda: float = float(inc.get('ebitda', 0.0) or 0.0)
            ebit: float = float(inc.get('operatingIncome', ebitda * 0.85) or ebitda * 0.85)
            
            pe: float = float(ratios.get('peRatioTTM', 0.0) or 0.0)
            ps: float = float(ratios.get('priceToSalesRatioTTM', 0.0) or 0.0)
            peg: float = float(ratios.get('pegRatioTTM', 0.0) or 0.0)

            tax_rate: float = 0.21
            inc_before_tax: float = float(inc.get('incomeBeforeTax', 0) or 0)
            inc_tax_exp: float = float(inc.get('incomeTaxExpense', 0) or 0)

            if inc_before_tax > 0: tax_rate = inc_tax_exp / inc_before_tax

            nopat: float = ebit * (1 - min(max(tax_rate, 0.15), 0.35))
            invested_capital: float = float(km.get('investedCapitalTTM', ev * 0.8) or ev * 0.8)

            curr_price = float(profile.get('price', 0.0))
            prices = {'current': curr_price, '1d': curr_price, '1w': curr_price, '1m': curr_price, '1y': curr_price}

            return {
                'company_name': profile.get('companyName', ticker_symbol),
                'currency': profile.get('currency', 'USD'),
                'prices': prices, 'ebit': ebit, 'ev': ev, 'nopat': nopat,
                'invested_capital': invested_capital, 'ebitda': ebitda,
                'pe': pe, 'ps': ps, 'peg': peg
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete FMP: {str(e)}")