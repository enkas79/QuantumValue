"""
Modulo Model (Logica di Business).

Contiene le regole matematiche di calcolo finanziario, gli algoritmi di screening
el caching dei dati e l'estrazione dati dai provider (Yahoo Finance, FMP).

Autore: Enrico Martini
Versione: 0.6.5
"""

import sys
import os
import json
from typing import Dict, Union, Tuple, List, Any, Optional

# Aggiungi la directory corrente al path per importare i moduli locali
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import yfinance as yf
    import pandas as pd
    import requests
    YFINANCE_AVAILABLE = True
except ImportError as e:
    YFINANCE_AVAILABLE = False
    print(f"Errore: yfinance non trovato. Eseguire 'pip install yfinance'.\nDettagli: {e}")

try:
    import httpx
    from tenacity import retry, stop_after_attempt, wait_exponential
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

import config
from cache import get_cached, set_cached

# Margine predefinito per approssimare EBIT da EBITDA
DEFAULT_EBIT_MARGIN_PROX = config.DEFAULT_EBIT_MARGIN_PROX


# Decorator per retry con tenacity (fallback a requests se httpx non disponibile)
def _retry_request(func):
    """Decorator per aggiungere retry alle chiamate HTTP."""
    if HTTPX_AVAILABLE:
        return retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))(func)
    else:
        return func


def check_for_updates(current_version: str, repo_path: str) -> Tuple[bool, str, str]:
    """
    Verifica la presenza di una nuova release su GitHub via API pubblica.

    Args:
        current_version (str): Versione attuale dell'applicazione.
        repo_path (str): Path del repository GitHub (es. 'utente/repo').

    Returns:
        Tuple[bool, str, str]: (aggiornamento_disponibile, tag_versione, url_html)
    """
    api_url: str = f"https://api.github.com/repos/{repo_path}/releases/latest"
    try:
        response = requests.get(
            api_url, 
            headers=config.HTTP_HEADERS, 
            timeout=config.HTTP_TIMEOUT
        )
        if response.status_code == 404:
            return False, current_version, ""
        response.raise_for_status()
        data: dict = response.json()
        latest_tag: str = data.get('tag_name', '').replace('v', '')
        html_url: str = data.get('html_url', '')

        if not latest_tag:
            return False, current_version, ""

        def parse_version(v: str) -> Tuple[int, ...]:
            try:
                return tuple(map(int, v.split('.')))
            except ValueError:
                return (0, 0, 0)

        curr_v_clean: str = current_version.replace('v', '')
        update_available: bool = parse_version(latest_tag) > parse_version(curr_v_clean)
        return update_available, latest_tag, html_url
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Impossibile verificare gli aggiornamenti: {str(e)}")


def calculate_metrics(data: Dict[str, float]) -> Dict[str, Union[float, str]]:
    """
    Esegue i calcoli finanziari di base partendo da un dizionario di input.

    Args:
        data (Dict[str, float]): Dizionario contenente le voci contabili grezze.

    Returns:
        Dict[str, Union[float, str]]: Metriche calcolate o messaggi di errore strutturati.
    """
    results: Dict[str, Union[float, str]] = {}

    ev_val: float = data.get('ev', 0.0)
    ebit_val: float = data.get('ebit', 0.0)
    results['ey'] = (ebit_val / ev_val) * 100 if ev_val != 0.0 else "Err(EV=0)"

    inv_cap: float = data.get('invested_capital', 0.0)
    nopat_val: float = data.get('nopat', 0.0)
    results['roic'] = (nopat_val / inv_cap) * 100 if inv_cap != 0.0 else "Err(Cap=0)"

    ebitda_val: float = data.get('ebitda', 0.0)
    results['ev_ebitda'] = ev_val / ebitda_val if ebitda_val != 0.0 else "Err(EBITDA=0)"

    return results


def evaluate_core(
    ey: Union[float, str],
    roic: Union[float, str],
    ev_ebitda: Union[float, str]
) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
    """
    Valuta EY, ROIC e EV/EBITDA classici restituendo un voto globale di qualità.

    Args:
        ey (Union[float, str]): Valore o errore dell'Earnings Yield.
        roic (Union[float, str]): Valore o errore del Return on Invested Capital.
        ev_ebitda (Union[float, str]): Valore o errore del multiplo EV/EBITDA.

    Returns:
        Tuple[float, str, str, Dict[str, Dict[str, str]]]: (punteggio, verdetto, colore, dettagli)
    """
    col_exc = config.COLORS["excellent"]
    col_good = config.COLORS["good"]
    col_fair = config.COLORS["fair"]
    col_weak = config.COLORS["weak"]
    col_bad = config.COLORS["bad"]

    f_ey: float = float(ey) if isinstance(ey, (int, float)) else -999.0
    f_roic: float = float(roic) if isinstance(roic, (int, float)) else -999.0
    f_ev: float = float(ev_ebitda) if isinstance(ev_ebitda, (int, float)) else 999.0

    if f_ey >= 10: s_ey, t_ey, c_ey = 10, "Eccellente (>=10%)", col_exc
    elif f_ey >= 6: s_ey, t_ey, c_ey = 8, "Buono (>=6%)", col_good
    elif f_ey >= 3: s_ey, t_ey, c_ey = 5, "Sufficiente (>=3%)", col_fair
    elif f_ey > 0: s_ey, t_ey, c_ey = 3, "Debole (>0%)", col_weak
    else: s_ey, t_ey, c_ey = 1, "Negativo (Attenzione)", col_bad

    if f_roic >= 15: s_r, t_r, c_r = 10, "Eccellente (>=15%)", col_exc
    elif f_roic >= 10: s_r, t_r, c_r = 8, "Buono (>=10%)", col_good
    elif f_roic >= 5: s_r, t_r, c_r = 5, "Sufficiente (>=5%)", col_fair
    elif f_roic > 0: s_r, t_r, c_r = 3, "Debole (>0%)", col_weak
    else: s_r, t_r, c_r = 1, "Negativo (Distrugge Valore)", col_bad

    if f_ev <= 0: s_ev, t_ev, c_ev = 1, "Negativo", col_bad
    elif f_ev <= 5: s_ev, t_ev, c_ev = 10, "Molto a Sconto (<=5x)", col_exc
    elif f_ev <= 10: s_ev, t_ev, c_ev = 8, "A Sconto (<=10x)", col_good
    elif f_ev <= 15: s_ev, t_ev, c_ev = 5, "Equo (<=15x)", col_fair
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


def evaluate_opportunity(
    pe: Union[float, str],
    ps: Union[float, str],
    peg: Union[float, str],
    ev_ebitda: Union[float, str]
) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
    """Valuta i 4 indicatori rapidi di mercato stabilendo il punteggio di convenienza."""
    col_exc = config.COLORS["excellent"]
    col_fair = config.COLORS["fair"]
    col_bad = config.COLORS["bad"]
    res: Dict[str, Dict[str, str]] = {}
    score: float = 0.0

    f_pe: float = float(pe) if isinstance(pe, (int, float)) else -1.0
    f_ps: float = float(ps) if isinstance(ps, (int, float)) else -1.0
    f_peg: float = float(peg) if isinstance(peg, (int, float)) else -1.0
    f_ev: float = float(ev_ebitda) if isinstance(ev_ebitda, (int, float)) else -1.0

    if 0 < f_pe < 20: s_pe, t_pe, c_pe = 2.5, "Ideale (< 20)", col_exc
    elif f_pe <= 0: s_pe, t_pe, c_pe = 0.0, "Negativo (Attenzione)", col_bad
    else: s_pe, t_pe, c_pe = 1.0, "Alto (>= 20)", col_fair
    res['pe'] = {'text': t_pe, 'color': c_pe}
    score += s_pe

    if 0 < f_ps < 2: s_ps, t_ps, c_ps = 2.5, "Ideale (< 2)", col_exc
    elif f_ps <= 0: s_ps, t_ps, c_ps = 0.0, "N.D. / Negativo", col_bad
    else: s_ps, t_ps, c_ps = 1.0, "Alto (>= 2)", col_fair
    res['ps'] = {'text': t_ps, 'color': c_ps}
    score += s_ps

    if 0 < f_peg < 1: s_peg, t_peg, c_peg = 2.5, "Ideale (< 1)", col_exc
    elif f_peg <= 0: s_peg, t_peg, c_peg = 0.0, "Negativo / N.D.", col_bad
    else: s_peg, t_peg, c_peg = 1.0, "Alto (>= 1)", col_fair
    res['peg'] = {'text': t_peg, 'color': c_peg}
    score += s_peg

    if 0 < f_ev < 10: s_ev, t_ev, c_ev = 2.5, "Ideale (< 10)", col_exc
    elif f_ev <= 0: s_ev, t_ev, c_ev = 0.0, "Negativo (Attenzione)", col_bad
    else: s_ev, t_ev, c_ev = 1.0, "Alto (>= 10)", col_fair
    res['ev_ebitda_occ'] = {'text': t_ev, 'color': c_ev}
    score += s_ev

    if score >= 7.5: verdict, v_color = "GRANDE OCCASIONE", col_exc
    elif score >= 5.0: verdict, v_color = "POSSIBILE OCCASIONE (Valutare)", col_fair
    else: verdict, v_color = "NESSUNA OCCASIONE EVIDENTE", col_bad

    return score, verdict, v_color, res


def evaluate_etf(
    ter: Union[float, str], 
    aum: Union[float, str], 
    ret_1y: Union[float, str],
    ret_3y: Union[float, str] = 0.0
) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
    """
    Assegna i punteggi e la valutazione complessiva di efficienza per gli ETF.
    
    Args:
        ter: Total Expense Ratio (%)
        aum: Assets Under Management (in milioni)
        ret_1y: Rendimento 1 anno (%)
        ret_3y: Rendimento 3 anni (%) - opzionale
    
    Returns:
        Tuple[float, str, str, Dict[str, Dict[str, str]]]: (punteggio, verdetto, colore, dettagli)
    """
    col_exc = config.COLORS["excellent"]
    col_good = config.COLORS["good"]
    col_fair = config.COLORS["fair"]
    col_bad = config.COLORS["bad"]

    f_ter: float = float(ter) if isinstance(ter, (int, float)) else -1.0
    f_aum: float = float(aum) if isinstance(aum, (int, float)) else -1.0
    f_ret_1y: float = float(ret_1y) if isinstance(ret_1y, (int, float)) else -999.0
    f_ret_3y: float = float(ret_3y) if isinstance(ret_3y, (int, float)) else -999.0
    
    # Media ponderata dei rendimenti (70% 1Y, 30% 3Y)
    avg_ret: float = 0.7 * f_ret_1y + 0.3 * f_ret_3y if f_ret_3y != -999.0 else f_ret_1y

    if 0 <= f_ter <= 0.20: s_ter, t_ter, c_ter = 10, "Eccellente (<= 0.20%)", col_exc
    elif f_ter <= 0.40: s_ter, t_ter, c_ter = 8, "Buono (<= 0.40%)", col_good
    elif f_ter <= 0.65: s_ter, t_ter, c_ter = 5, "Accettabile (<= 0.65%)", col_fair
    else: s_ter, t_ter, c_ter = 2, "Costoso (> 0.65%)", col_bad

    if f_aum >= 1000: s_aum, t_aum, c_aum = 10, "Eccellente (>= 1000M)", col_exc
    elif f_aum >= 500: s_aum, t_aum, c_aum = 8, "Buono (>= 500M)", col_good
    elif f_aum >= 100: s_aum, t_aum, c_aum = 5, "Accettabile (>= 100M)", col_fair
    else: s_aum, t_aum, c_aum = 2, "Rischioso (< 100M)", col_bad

    if avg_ret >= 15: s_ret, t_ret, c_ret = 10, "Eccellente (>= 15%)", col_exc
    elif avg_ret >= 8: s_ret, t_ret, c_ret = 8, "Buono (>= 8%)", col_good
    elif avg_ret >= 0: s_ret, t_ret, c_ret = 5, "Positivo (>= 0%)", col_fair
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


def search_by_name(query: str) -> List[Tuple[str, str, str]]:
    """
    Ricerca i ticker azionari ed ETF tramite endpoint pubblico di Yahoo Finance.
    
    Args:
        query (str): Testo da cercare (ticker, nome azienda, ISIN).
    
    Returns:
        List[Tuple[str, str, str]]: Lista di (simbolo, nome, borsa).
    """
    # Gestisce spazi e formattazione
    query = query.strip().replace(" ", "+")
    url: str = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10"
    
    try:
        response = requests.get(
            url, 
            headers=config.HTTP_HEADERS, 
            timeout=config.HTTP_TIMEOUT
        )
        response.raise_for_status()
        data: dict = response.json()
        results: List[Tuple[str, str, str]] = []

        for quote in data.get('quotes', []):
            if quote.get('quoteType') in ['EQUITY', 'ETF']:
                symbol: str = quote.get('symbol', '').replace(" ", "")  # Rimuove spazi
                name: str = quote.get('shortname', quote.get('longname', 'Sconosciuto'))
                raw_exchange: str = quote.get('exchange', 'N/A')
                mapped_exchange: str = config.YAHOO_EXCHANGE_MAP.get(raw_exchange, raw_exchange)
                if symbol:
                    results.append((symbol, name, mapped_exchange))
        return results
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Errore di rete durante la ricerca: {str(e)}")


def _parse_perc(val: Any) -> float:
    """
    Parsa un valore percentuale da stringa o numero.
    
    Args:
        val: Valore da parsare (può essere str, float, int, None, NaN).
    
    Returns:
        float: Valore numerico (0.0 se non valido).
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    val_str = str(val).upper().replace('%', '').strip()
    if val_str in ("N/A", "NA", "", "NONE"):
        return 0.0
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def fetch_etf_data(query: str) -> Dict[str, Any]:
    """
    Scarica i dati analitici dell'ETF indicato interrogando Yahoo Finance.
    
    Args:
        query (str): Ticker, ISIN o nome ETF.
    
    Returns:
        Dict[str, Any]: Dati dell'ETF.
    
    Raises:
        ValueError: Se l'ETF non viene trovato.
    """
    if not query:
        raise ValueError("Inserire un ISIN, Ticker o Nome ETF valido.")
    
    # Prova prima con la cache
    cache_key = f"etf_{query.upper()}"
    cached_data = get_cached(cache_key)
    if cached_data:
        return cached_data

    try:
        ticker = yf.Ticker(query.upper())
        info = ticker.info
        if not info or 'shortName' not in info:
            raise ValueError(f"ETF '{query}' non trovato.")

        total_assets = float(info.get('totalAssets', 0.0) or 0.0)
        ytd_ret = float(info.get('ytdReturn', 0.0) or 0.0) * 100
        ter_yf = float(info.get('annualReportExpenseRatio', 0.0) or info.get('yield', 0.0) or 0.0) * 100

        result = {
            'company_name': info.get('longName', query),
            'currency': info.get('currency', 'USD'),
            'ter': ter_yf,
            'aum': total_assets / 1_000_000,  # Converti in milioni
            'ret_1y': ytd_ret,
            'ret_3y': float(info.get('threeYearAverageReturn', 0.0) or 0.0) * 100,
            'replication': "Fisica/Sintetica (Dato YF non disponibile)"
        }
        
        # Salva in cache
        set_cached(cache_key, result)
        return result
        
    except Exception as e:
        raise ValueError(f"Impossibile trovare i dati dell'ETF tramite Yahoo Finance: {e}")


class FinancialDataFetcher:
    """
    Classe Model con stato per l'estrazione dei dati azionari dai provider (Yahoo/FMP).
    
    Include:
    - Caching locale dei dati
    - Fallback multi-livello (Yahoo -> FMP -> Static)
    - Gestione errori robusta
    """

    def __init__(self, fmp_api_key: str = "") -> None:
        self.fmp_api_key: str = fmp_api_key

    def fetch_data(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Recupera i dati fondamentali dell'azione dal miglior provider disponibile.
        
        Args:
            ticker_symbol (str): Simbolo del ticker (es. "AAPL").
        
        Returns:
            Dict[str, Any]: Dati finanziari completi.
        
        Raises:
            ValueError: Se tutti i provider falliscono.
        """
        if not ticker_symbol:
            raise ValueError("Inserire un Ticker valido.")
        
        ticker_upper = ticker_symbol.upper()
        cache_key = f"stock_{ticker_upper}"
        
        # 1. Prova con la cache
        cached_data = get_cached(cache_key)
        if cached_data:
            return cached_data
        
        # 2. Prova con Yahoo Finance
        try:
            data = self._fetch_from_yahoo(ticker_upper)
            set_cached(cache_key, data)
            return data
        except Exception as yf_error:
            logger = logging.getLogger("QuantumValue")
            logger.warning(f"Yahoo Finance fallito per {ticker_upper}: {str(yf_error)}")
            
            # 3. Prova con FMP (se chiave configurata)
            if self.fmp_api_key:
                try:
                    data = self._fetch_from_fmp(ticker_upper)
                    set_cached(cache_key, data)
                    return data
                except Exception as fmp_error:
                    logger.error(f"FMP fallito per {ticker_upper}: {str(fmp_error)}")
                    
                    # 4. Fallback a dati statici
                    if ticker_upper in config.STATIC_FALLBACK:
                        logger.warning(f"Utilizzo dati statici per {ticker_upper}")
                        return config.STATIC_FALLBACK[ticker_upper]
                    else:
                        raise ValueError(
                            f"Fallimento totale provider per {ticker_upper}.\n"
                            f"Yahoo: {str(yf_error)}\n"
                            f"FMP: {str(fmp_error)}\n"
                            f"Nessun dato statico disponibile."
                        )
            else:
                # 4. Fallback a dati statici (senza FMP)
                if ticker_upper in config.STATIC_FALLBACK:
                    logger.warning(f"Utilizzo dati statici per {ticker_upper}")
                    return config.STATIC_FALLBACK[ticker_upper]
                else:
                    raise ValueError(
                        f"Errore Yahoo Finance (Nessuna API di backup configurata): {str(yf_error)}\n"
                        f"Nessun dato statico disponibile per {ticker_upper}."
                    )

    def _fetch_from_yahoo(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Recupera i dati da Yahoo Finance.
        
        Args:
            ticker_symbol (str): Simbolo del ticker.
        
        Returns:
            Dict[str, Any]: Dati finanziari.
        """
        ticker = yf.Ticker(ticker_symbol)
        info: dict = ticker.info

        if not info or 'shortName' not in info:
            raise ValueError(f"Ticker '{ticker_symbol}' non trovato su Yahoo.")

        ev: float = float(info.get('enterpriseValue', 0.0) or 0.0)
        ebitda: float = float(info.get('ebitda', 0.0) or 0.0)

        # Recupera lo storico dei prezzi
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

        # Recupera i dati dal bilancio
        inc_stmt = ticker.income_stmt
        bal_sheet = ticker.balance_sheet

        # Calcola EBIT
        ebit: float = ebitda * DEFAULT_EBIT_MARGIN_PROX
        if not inc_stmt.empty and 'EBIT' in inc_stmt.index:
            try:
                ebit = float(inc_stmt.loc['EBIT'].iloc[0])
            except (TypeError, ValueError):
                pass
        elif not inc_stmt.empty and 'Operating Income' in inc_stmt.index:
            try:
                ebit = float(inc_stmt.loc['Operating Income'].iloc[0])
            except (TypeError, ValueError):
                pass

        # Calcola tax rate
        tax_prov, pretax = 0.0, 1.0
        if not inc_stmt.empty and 'Tax Provision' in inc_stmt.index:
            try:
                tax_prov = float(inc_stmt.loc['Tax Provision'].iloc[0])
            except (TypeError, ValueError):
                pass
        if not inc_stmt.empty and 'Pretax Income' in inc_stmt.index:
            try:
                pretax = float(inc_stmt.loc['Pretax Income'].iloc[0])
            except (TypeError, ValueError):
                pass

        tax_rate: float = min(tax_prov / pretax, 0.35) if pretax > 0 and tax_prov > 0 else 0.21
        nopat: float = ebit * (1 - tax_rate)

        # Calcola Invested Capital
        total_debt: float = float(info.get('totalDebt', 0.0) or 0.0)
        equity: float = float(info.get('bookValue', 0.0) or 0.0) * float(info.get('sharesOutstanding', 0.0) or 0.0)

        if not bal_sheet.empty and 'Stockholders Equity' in bal_sheet.index:
            try:
                equity = float(bal_sheet.loc['Stockholders Equity'].iloc[0])
            except (TypeError, ValueError):
                pass

        invested_capital: float = total_debt + equity

        return {
            'company_name': info.get('longName', ticker_symbol),
            'currency': info.get('currency', 'USD'),
            'prices': prices, 
            'ebit': ebit, 
            'ev': ev, 
            'nopat': nopat,
            'invested_capital': invested_capital, 
            'ebitda': ebitda,
            'pe': pe, 
            'ps': ps, 
            'peg': peg
        }

    def _fetch_from_fmp(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Recupera i dati da Financial Modeling Prep (FMP).
        
        Args:
            ticker_symbol (str): Simbolo del ticker.
        
        Returns:
            Dict[str, Any]: Dati finanziari.
        """
        if not self.fmp_api_key:
            raise ValueError("Nessuna API Key FMP configurata.")
        
        base_url: str = "https://financialmodelingprep.com/api/v3"
        
        try:
            # Recupera il profilo aziendale
            prof_resp = requests.get(
                f"{base_url}/profile/{ticker_symbol}?apikey={self.fmp_api_key}",
                timeout=config.HTTP_TIMEOUT
            ).json()
            if not prof_resp:
                raise ValueError("Azienda non trovata nel database FMP.")
            profile: dict = prof_resp[0]

            # Recupera le metriche chiave
            km_resp = requests.get(
                f"{base_url}/key-metrics-ttm/{ticker_symbol}?apikey={self.fmp_api_key}",
                timeout=config.HTTP_TIMEOUT
            ).json()
            km: dict = km_resp[0] if km_resp else {}

            # Recupera i ratios
            ratios_resp = requests.get(
                f"{base_url}/ratios-ttm/{ticker_symbol}?apikey={self.fmp_api_key}",
                timeout=config.HTTP_TIMEOUT
            ).json()
            ratios: dict = ratios_resp[0] if ratios_resp else {}

            # Recupera il bilancio
            inc_resp = requests.get(
                f"{base_url}/income-statement/{ticker_symbol}?limit=1&apikey={self.fmp_api_key}",
                timeout=config.HTTP_TIMEOUT
            ).json()
            inc: dict = inc_resp[0] if inc_resp else {}

            ev: float = float(km.get('enterpriseValueTTM', 0.0) or 0.0)
            ebitda: float = float(inc.get('ebitda', 0.0) or 0.0)
            ebit: float = float(inc.get('operatingIncome', ebitda * DEFAULT_EBIT_MARGIN_PROX) or ebitda * DEFAULT_EBIT_MARGIN_PROX)

            pe: float = float(ratios.get('peRatioTTM', 0.0) or 0.0)
            ps: float = float(ratios.get('priceToSalesRatioTTM', 0.0) or 0.0)
            peg: float = float(ratios.get('pegRatioTTM', 0.0) or 0.0)

            # Calcola tax rate
            tax_rate: float = 0.21
            inc_before_tax: float = float(inc.get('incomeBeforeTax', 0) or 0)
            inc_tax_exp: float = float(inc.get('incomeTaxExpense', 0) or 0)

            if inc_before_tax > 0:
                tax_rate = inc_tax_exp / inc_before_tax

            nopat: float = ebit * (1 - min(max(tax_rate, 0.15), 0.35))
            invested_capital: float = float(km.get('investedCapitalTTM', ev * 0.8) or ev * 0.8)

            curr_price = float(profile.get('price', 0.0))
            prices = {
                'current': curr_price, 
                '1d': curr_price, 
                '1w': curr_price, 
                '1m': curr_price, 
                '1y': curr_price
            }

            return {
                'company_name': profile.get('companyName', ticker_symbol),
                'currency': profile.get('currency', 'USD'),
                'prices': prices, 
                'ebit': ebit, 
                'ev': ev, 
                'nopat': nopat,
                'invested_capital': invested_capital, 
                'ebitda': ebitda,
                'pe': pe, 
                'ps': ps, 
                'peg': peg
            }
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete FMP: {str(e)}")
