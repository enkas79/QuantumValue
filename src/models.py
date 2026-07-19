"""
Modulo Model (Logica di Business).

Contiene le regole matematiche di calcolo finanziario, gli algoritmi di screening
el caching dei dati e l'estrazione dati dai provider (Yahoo Finance, FMP).

Autore: Enrico Martini
Versione: 0.7.14
"""

import sys
import os
import json
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, asdict, fields
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

# Secondi di attesa sul provider primario prima di avviare in parallelo il
# provider di riserva (pattern "hedged request"): limita la latenza quando
# Yahoo e' lento senza sprecare quota FMP quando Yahoo risponde subito.
HEDGE_DELAY_SECONDS: float = 6.0


@dataclass
class StockData:
    """Dati fondamentali di un titolo azionario, tipizzati ai bordi del Model."""
    company_name: str = "N/A"
    currency: str = "USD"
    prices: Dict[str, float] = field(default_factory=dict)
    sparkline: List[float] = field(default_factory=list)
    ebit: float = 0.0
    ev: float = 0.0
    nopat: float = 0.0
    invested_capital: float = 0.0
    ebitda: float = 0.0
    pe: float = 0.0
    ps: float = 0.0
    peg: float = 0.0
    fcf: float = 0.0
    # Serie storiche (dal periodo piu' vecchio al piu' recente disponibile,
    # tipicamente fino a 4-5 esercizi annuali) usate dai 4 "campanelli
    # d'allarme" di evaluate_red_flags. Liste vuote quando il provider non le
    # fornisce: la valutazione le tratta come N/D, non come regola violata.
    pe_history: List[float] = field(default_factory=list)
    ebit_margin_history: List[float] = field(default_factory=list)
    fcf_history: List[float] = field(default_factory=list)
    price_change_hist_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializza in dizionario JSON-compatibile (per cache e fallback)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StockData":
        """Costruisce l'oggetto da un dizionario, ignorando chiavi sconosciute."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class EtfData:
    """Profilo analitico di un ETF, tipizzato ai bordi del Model."""
    company_name: str = "N/A"
    currency: str = "EUR"
    replication: str = "N/A"
    ter: float = 0.0
    aum: float = 0.0
    ret_1y: float = 0.0
    ret_3y: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializza in dizionario JSON-compatibile (per cache)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EtfData":
        """Costruisce l'oggetto da un dizionario, ignorando chiavi sconosciute."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def validate_input_data(data: Dict[str, float]) -> Dict[str, str]:
    """
    Verifica la plausibilita' dei dati finanziari inseriti.

    Non blocca il calcolo: restituisce avvisi per campo da mostrare come
    warning visivo, cosi' l'utente si accorge di valori fuori scala (es.
    errori di unita' K/M/B) prima di fidarsi del verdetto.

    Args:
        data (Dict[str, float]): Voci contabili grezze gia' parse-ate.

    Returns:
        Dict[str, str]: Mappa campo -> messaggio di avviso (vuota se tutto ok).
    """
    warnings: Dict[str, str] = {}
    ev = data.get('ev', 0.0)
    ebit = data.get('ebit', 0.0)
    ebitda = data.get('ebitda', 0.0)
    nopat = data.get('nopat', 0.0)
    inv_cap = data.get('invested_capital', 0.0)
    pe = data.get('pe', 0.0)
    ps = data.get('ps', 0.0)
    peg = data.get('peg', 0.0)

    if ev <= 0:
        warnings['ev'] = "EV non positivo: Earnings Yield e EV/EBITDA non sono calcolabili."
    if inv_cap <= 0:
        warnings['invested_capital'] = "Capitale Investito non positivo: ROIC non calcolabile."
    if ev > 0 and ebit > ev:
        warnings['ebit'] = "EBIT maggiore dell'EV: probabile errore di scala (K/M/B)."
    if ebitda != 0 and abs(ebit) > abs(ebitda) * 1.5:
        warnings['ebit'] = "EBIT molto superiore all'EBITDA: verifica le unita' di misura."
    if inv_cap > 0 and nopat / inv_cap > 1.0:
        warnings['nopat'] = "ROIC oltre il 100%: valore sospetto, verifica NOPAT e Capitale Investito."
    if pe > 200:
        warnings['pe'] = "P/E oltre 200: valore anomalo o utili prossimi allo zero."
    if ps > 50:
        warnings['ps'] = "P/S oltre 50: valore fuori scala per la maggior parte dei settori."
    if peg > 10 or peg < 0:
        warnings['peg'] = "PEG fuori dall'intervallo tipico (0-10): dato poco affidabile."
    return warnings


def pick_release_asset(assets: List[Dict[str, Any]], platform: str = sys.platform) -> str:
    """
    Sceglie dall'elenco degli asset di una GitHub Release quello adatto
    alla piattaforma corrente.

    Args:
        assets: Lista di asset della release (API GitHub).
        platform: Identificatore piattaforma (sys.platform).

    Returns:
        str: URL di download diretto, o stringa vuota se nessun asset combacia.
    """
    if platform.startswith("win"):
        suffix = ".exe"
    elif platform == "darwin":
        suffix = "_macos.zip"
    else:
        suffix = ".deb"

    for asset in assets:
        name = str(asset.get('name', '')).lower()
        if name.endswith(suffix):
            return str(asset.get('browser_download_url', ''))
    return ""


# Decorator per retry con tenacity (fallback a requests se httpx non disponibile)
def _retry_request(func):
    """Decorator per aggiungere retry alle chiamate HTTP."""
    if HTTPX_AVAILABLE:
        return retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))(func)
    else:
        return func


@_retry_request
def check_for_updates(current_version: str, repo_path: str) -> Tuple[bool, str, str]:
    """
    Verifica la presenza di una nuova release su GitHub via API pubblica.

    Args:
        current_version (str): Versione attuale dell'applicazione.
        repo_path (str): Path del repository GitHub (es. 'utente/repo').

    Returns:
        Tuple[bool, str, str]: (aggiornamento_disponibile, tag_versione, url_download).
        L'URL punta all'asset della release adatto alla piattaforma corrente
        (installer .exe, pacchetto .deb o bundle macOS), con fallback alla
        pagina HTML della release se nessun asset combacia.
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
        html_url: str = pick_release_asset(data.get('assets', [])) or data.get('html_url', '')

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


def evaluate_red_flags(
    pe: Union[float, str],
    pe_history: List[float],
    ps: Union[float, str],
    ebit_margin_history: List[float],
    price_change_hist_pct: Union[float, str],
    fcf_history: List[float]
) -> Tuple[int, str, str, Dict[str, Dict[str, str]]]:
    """
    Verifica i 4 "campanelli d'allarme" da valutazione (quality/value trap):

    1. P/E molto oltre la propria media storica (non una soglia assoluta).
    2. P/S oltre i limiti tipici di un'azienda matura (>= 15-20x fatturato).
    3. Margine EBIT in contrazione mentre il prezzo del titolo sale.
    4. Free Cash Flow negativo su piu' periodi consecutivi.

    Ogni regola richiede uno storico minimo: se il provider non lo fornisce
    (es. TwelveData/EODHD, o inserimento manuale dei soli valori correnti),
    la voce risulta "N/D" e non conta come campanello attivo, per evitare
    falsi allarmi su dati assenti.

    Args:
        pe: P/E corrente.
        pe_history: Storico del P/E (dal periodo piu' vecchio al piu' recente).
        ps: P/S corrente.
        ebit_margin_history: Storico del margine EBIT in % (vecchio -> recente).
        price_change_hist_pct: Variazione % del prezzo sull'arco temporale
            coperto da ebit_margin_history (stesso periodo, per confrontare
            margini e prezzo in modo coerente).
        fcf_history: Storico del Free Cash Flow (vecchio -> recente).

    Returns:
        Tuple[int, str, str, Dict[str, Dict[str, str]]]:
        (campanelli attivi, verdetto sintetico, colore, dettagli per regola).
    """
    col_exc = config.COLORS["excellent"]
    col_fair = config.COLORS["fair"]
    col_bad = config.COLORS["bad"]
    col_neutral = config.COLORS["neutral"]

    details: Dict[str, Dict[str, str]] = {}
    triggered = 0

    # 1. P/E molto oltre la media storica
    f_pe: float = float(pe) if isinstance(pe, (int, float)) else 0.0
    valid_pe_hist = [float(v) for v in pe_history if isinstance(v, (int, float)) and v > 0]
    if f_pe > 0 and len(valid_pe_hist) >= 2:
        avg_hist_pe = sum(valid_pe_hist) / len(valid_pe_hist)
        ratio = f_pe / avg_hist_pe if avg_hist_pe > 0 else 0.0
        if ratio >= 1.8:
            triggered += 1
            details['pe_vs_history'] = {
                'text': f"P/E {f_pe:.1f} vs media storica {avg_hist_pe:.1f} ({ratio:.1f}x): "
                        f"ben oltre la norma storica del titolo.",
                'color': col_bad
            }
        elif ratio >= 1.3:
            details['pe_vs_history'] = {
                'text': f"P/E {f_pe:.1f} vs media storica {avg_hist_pe:.1f} ({ratio:.1f}x): "
                        f"sopra la media, da monitorare.",
                'color': col_fair
            }
        else:
            details['pe_vs_history'] = {
                'text': f"P/E {f_pe:.1f} in linea con la media storica ({avg_hist_pe:.1f}).",
                'color': col_exc
            }
    else:
        details['pe_vs_history'] = {'text': "N/D: storico P/E insufficiente per il confronto.", 'color': col_neutral}

    # 2. P/S oltre i limiti tipici per un'azienda matura (non una startup pre-ricavi)
    f_ps: float = float(ps) if isinstance(ps, (int, float)) else 0.0
    if f_ps > 0:
        if f_ps >= 20:
            triggered += 1
            details['ps_extreme'] = {
                'text': f"P/S {f_ps:.1f}x: oltre 20 volte il fatturato. Il mercato pretende margini "
                        f"futuri quasi perfetti (non applicabile a startup pre-ricavi).",
                'color': col_bad
            }
        elif f_ps >= 15:
            triggered += 1
            details['ps_extreme'] = {
                'text': f"P/S {f_ps:.1f}x: oltre 15 volte il fatturato, valutazione tirata per un'azienda matura.",
                'color': col_fair
            }
        else:
            details['ps_extreme'] = {'text': f"P/S {f_ps:.1f}x entro i limiti tipici (< 15x).", 'color': col_exc}
    else:
        details['ps_extreme'] = {'text': "N/D: P/S non disponibile.", 'color': col_neutral}

    # 3. Margine EBIT in contrazione mentre il prezzo sale
    valid_margins = [float(v) for v in ebit_margin_history if isinstance(v, (int, float))]
    f_price_chg: float = float(price_change_hist_pct) if isinstance(price_change_hist_pct, (int, float)) else 0.0
    if len(valid_margins) >= 2:
        margin_declining = valid_margins[-1] < valid_margins[0]
        if margin_declining and f_price_chg > 0:
            triggered += 1
            details['margin_contraction'] = {
                'text': f"Margine EBIT sceso da {valid_margins[0]:.1f}% a {valid_margins[-1]:.1f}% "
                        f"mentre il prezzo e' salito del {f_price_chg:.1f}%: il mercato potrebbe "
                        f"comprare una narrativa, non i bilanci.",
                'color': col_bad
            }
        elif margin_declining:
            details['margin_contraction'] = {
                'text': f"Margine EBIT in calo ({valid_margins[0]:.1f}% -> {valid_margins[-1]:.1f}%), "
                        f"ma il prezzo non e' salito in parallelo.",
                'color': col_fair
            }
        else:
            details['margin_contraction'] = {
                'text': f"Margine EBIT stabile o in crescita ({valid_margins[0]:.1f}% -> {valid_margins[-1]:.1f}%).",
                'color': col_exc
            }
    else:
        details['margin_contraction'] = {'text': "N/D: storico margini insufficiente.", 'color': col_neutral}

    # 4. FCF negativo su piu' periodi consecutivi
    valid_fcf = [float(v) for v in fcf_history if isinstance(v, (int, float))]
    if valid_fcf:
        negative_periods = sum(1 for v in valid_fcf if v < 0)
        if negative_periods >= 2 and negative_periods >= len(valid_fcf) - 1:
            triggered += 1
            details['fcf_negative'] = {
                'text': f"FCF negativo in {negative_periods}/{len(valid_fcf)} degli ultimi periodi: "
                        f"verifica se giustificato da investimenti di crescita (es. capex elevati), "
                        f"altrimenti rischio di bruciare cassa.",
                'color': col_bad
            }
        elif valid_fcf[-1] < 0:
            details['fcf_negative'] = {
                'text': f"FCF piu' recente negativo ({valid_fcf[-1]:,.0f}), ma non ancora un pattern persistente.",
                'color': col_fair
            }
        else:
            details['fcf_negative'] = {
                'text': f"FCF positivo nel periodo piu' recente ({valid_fcf[-1]:,.0f}).",
                'color': col_exc
            }
    else:
        details['fcf_negative'] = {'text': "N/D: Free Cash Flow non disponibile.", 'color': col_neutral}

    if triggered >= 3:
        verdict, v_color = "PIU' CAMPANELLI D'ALLARME ATTIVI (valutare con cautela)", col_bad
    elif triggered >= 1:
        verdict, v_color = f"{triggered} CAMPANELLO D'ALLARME ATTIVO", col_fair
    else:
        verdict, v_color = "NESSUN CAMPANELLO D'ALLARME (sui dati disponibili)", col_exc

    return triggered, verdict, v_color, details


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


@_retry_request
def search_by_name(query: str, quote_types: Tuple[str, ...] = ('EQUITY', 'ETF')) -> List[Tuple[str, str, str]]:
    """
    Ricerca i ticker azionari ed ETF tramite endpoint pubblico di Yahoo Finance.

    Args:
        query (str): Testo da cercare (ticker, nome azienda, ISIN).
        quote_types (Tuple[str, ...]): Tipi di strumento da includere nei risultati
            (es. solo 'ETF' per restringere la ricerca ai soli fondi).

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
            if quote.get('quoteType') in quote_types:
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


def _closest_price(hist_df: Any, target_date: Any) -> float:
    """
    Trova il prezzo di chiusura piu' vicino a una data target in uno storico
    yfinance (`ticker.history`), usato per abbinare un prezzo alle date di
    fine esercizio dei bilanci annuali (colonne di `income_stmt`/`cashflow`).

    Gestisce la differenza di timezone tra l'indice dei prezzi (spesso
    tz-aware, fuso della borsa) e le date dei bilanci (tz-naive).

    Args:
        hist_df: DataFrame storico prezzi con colonna 'Close' e indice datetime.
        target_date: Data target (Timestamp o compatibile).

    Returns:
        float: Prezzo di chiusura piu' vicino, 0.0 se non determinabile.
    """
    if hist_df is None or hist_df.empty:
        return 0.0
    try:
        target = pd.Timestamp(target_date)
        if target.tzinfo is not None:
            target = target.tz_localize(None)
        idx = hist_df.index
        idx_naive = idx.tz_localize(None) if getattr(idx, 'tz', None) is not None else idx
        pos = int(abs(idx_naive - target).argmin())
        return float(hist_df['Close'].iloc[pos])
    except (TypeError, ValueError, KeyError):
        return 0.0


def _historical_series_from_statements(
    inc_stmt: Any,
    cashflow: Any,
    hist_df: Any
) -> Tuple[List[float], List[float], List[float], float]:
    """
    Costruisce le serie storiche (P/E, margine EBIT, FCF) e la variazione %
    del prezzo sullo stesso arco temporale, a partire dai bilanci annuali
    (`income_stmt`, `cashflow`) e dallo storico prezzi di un Ticker yfinance.

    Le serie sono ordinate dal periodo piu' vecchio al piu' recente. Un
    periodo contribuisce a una serie solo se i dati necessari sono presenti
    e plausibili (es. EPS > 0 per il P/E): eventuali buchi non generano
    valori fittizi, riducono solo la lunghezza della serie.

    Args:
        inc_stmt: `ticker.income_stmt` (colonne = date di fine esercizio).
        cashflow: `ticker.cashflow` (stesse colonne, voci di cassa).
        hist_df: `ticker.history(...)` con storico prezzi di pari periodo.

    Returns:
        Tuple[List[float], List[float], List[float], float]:
        (pe_history, ebit_margin_history, fcf_history, price_change_hist_pct).
    """
    pe_history: List[float] = []
    ebit_margin_history: List[float] = []
    fcf_history: List[float] = []
    price_change_hist_pct: float = 0.0

    if inc_stmt is None or inc_stmt.empty:
        return pe_history, ebit_margin_history, fcf_history, price_change_hist_pct

    periods_sorted = sorted(inc_stmt.columns)

    for period in periods_sorted:
        col = inc_stmt[period]
        revenue = col.get('Total Revenue', None)
        ebit_p = col.get('EBIT', col.get('Operating Income', None))
        eps_p = col.get('Diluted EPS', col.get('Basic EPS', None))

        if revenue is not None and pd.notna(revenue) and revenue != 0 and ebit_p is not None and pd.notna(ebit_p):
            ebit_margin_history.append((float(ebit_p) / float(revenue)) * 100)

        if eps_p is not None and pd.notna(eps_p) and float(eps_p) > 0:
            price_at_period = _closest_price(hist_df, period)
            if price_at_period > 0:
                pe_history.append(price_at_period / float(eps_p))

    if cashflow is not None and not cashflow.empty:
        cf_periods_sorted = sorted(cashflow.columns)
        for period in cf_periods_sorted:
            col = cashflow[period]
            fcf_p = col.get('Free Cash Flow', None)
            if fcf_p is None or pd.isna(fcf_p):
                ocf = col.get('Operating Cash Flow', col.get('Total Cash From Operating Activities', None))
                capex = col.get('Capital Expenditure', col.get('Capital Expenditures', None))
                if ocf is not None and pd.notna(ocf) and capex is not None and pd.notna(capex):
                    fcf_p = float(ocf) + float(capex)
            if fcf_p is not None and pd.notna(fcf_p):
                fcf_history.append(float(fcf_p))

    if len(periods_sorted) >= 2 and hist_df is not None and not hist_df.empty:
        price_start = _closest_price(hist_df, periods_sorted[0])
        price_end = float(hist_df['Close'].iloc[-1])
        if price_start > 0:
            price_change_hist_pct = ((price_end / price_start) - 1) * 100

    return pe_history, ebit_margin_history, fcf_history, price_change_hist_pct


def fetch_etf_data(query: str) -> "EtfData":
    """
    Scarica i dati analitici dell'ETF indicato interrogando Yahoo Finance.

    Args:
        query (str): Ticker, ISIN o nome ETF.

    Returns:
        EtfData: Dati dell'ETF.

    Raises:
        ValueError: Se l'ETF non viene trovato.
    """
    if not query:
        raise ValueError("Inserire un ISIN, Ticker o Nome ETF valido.")

    # Prova prima con la cache
    cache_key = f"etf_{query.upper()}"
    cached_data = get_cached(cache_key)
    if cached_data:
        return EtfData.from_dict(cached_data)

    try:
        ticker = yf.Ticker(query.upper())
        info = ticker.info
        if not info or 'shortName' not in info:
            raise ValueError(f"ETF '{query}' non trovato.")

        total_assets = float(info.get('totalAssets', 0.0) or 0.0)
        ytd_ret = float(info.get('ytdReturn', 0.0) or 0.0) * 100
        ter_yf = float(info.get('annualReportExpenseRatio', 0.0) or info.get('yield', 0.0) or 0.0) * 100

        result = EtfData(
            company_name=info.get('longName', query),
            currency=info.get('currency', 'USD'),
            ter=ter_yf,
            aum=total_assets / 1_000_000,  # Converti in milioni
            ret_1y=ytd_ret,
            ret_3y=float(info.get('threeYearAverageReturn', 0.0) or 0.0) * 100,
            replication="Fisica/Sintetica (Dato YF non disponibile)"
        )

        # Salva in cache
        set_cached(cache_key, result.to_dict())
        return result

    except Exception as e:
        raise ValueError(f"Impossibile trovare i dati dell'ETF tramite Yahoo Finance: {e}")


class DataProvider(ABC):
    """
    Interfaccia dei provider di dati fondamentali azionari.

    Aggiungere un nuovo provider (es. Alpha Vantage) significa implementare
    questa classe e inserirla nella catena di FinancialDataFetcher, senza
    toccare la logica di orchestrazione.
    """

    name: str = "base"

    @abstractmethod
    def fetch(self, ticker_symbol: str) -> StockData:
        """Recupera i fondamentali del titolo; solleva eccezione in caso di errore."""


class YahooProvider(DataProvider):
    """Provider primario: Yahoo Finance via yfinance."""

    name = "Yahoo Finance"

    @_retry_request
    def fetch(self, ticker_symbol: str) -> StockData:
        """
        Recupera i dati da Yahoo Finance.

        Args:
            ticker_symbol (str): Simbolo del ticker.

        Returns:
            StockData: Dati finanziari.
        """
        ticker = yf.Ticker(ticker_symbol)
        info: dict = ticker.info

        if not info or 'shortName' not in info:
            raise ValueError(f"Ticker '{ticker_symbol}' non trovato su Yahoo.")

        ev: float = float(info.get('enterpriseValue', 0.0) or 0.0)
        ebitda: float = float(info.get('ebitda', 0.0) or 0.0)

        # Recupera lo storico dei prezzi. Si scarica una finestra di 5 anni
        # (invece dell'anno usato in precedenza) perche' serve anche per
        # abbinare un prezzo alle date di fine esercizio dei bilanci annuali
        # (fino a ~4-5 anni indietro) nel calcolo dei campanelli d'allarme.
        hist_5y = ticker.history(period="5y")
        # L'anno piu' recente (per prezzo corrente, variazioni e sparkline)
        # resta una finestra sugli ultimi ~252 giorni di borsa, coerente con
        # il comportamento precedente basato su period="1y".
        hist = hist_5y.tail(260) if not hist_5y.empty else hist_5y
        prices: Dict[str, float] = {'current': 0.0, '1d': 0.0, '1w': 0.0, '1m': 0.0, '1y': 0.0}
        sparkline: List[float] = []

        if not hist.empty:
            closes = hist['Close']
            prices['current'] = float(closes.iloc[-1])
            prices['1d'] = float(closes.iloc[-2]) if len(closes) >= 2 else prices['current']
            prices['1w'] = float(closes.iloc[-6]) if len(closes) >= 6 else prices['current']
            prices['1m'] = float(closes.iloc[-22]) if len(closes) >= 22 else prices['current']
            prices['1y'] = float(closes.iloc[0]) if len(closes) > 0 else prices['current']

            # Serie ridotta (max ~60 punti) per il mini-grafico dell'ultimo anno.
            # Lista di float puri: serializzabile in cache JSON senza pandas.
            values = [float(v) for v in closes.tolist() if v == v]
            step = max(1, len(values) // 60)
            sparkline = values[::step]
            if values and (not sparkline or sparkline[-1] != values[-1]):
                sparkline.append(values[-1])

        pe: float = float(info.get('trailingPE', 0.0) or 0.0)
        ps: float = float(info.get('priceToSalesTrailing12Months', 0.0) or 0.0)
        peg: float = float(info.get('pegRatio', 0.0) or 0.0)

        # Recupera i dati dal bilancio
        inc_stmt = ticker.income_stmt
        bal_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        pe_history, ebit_margin_history, fcf_history, price_change_hist_pct = (
            _historical_series_from_statements(inc_stmt, cashflow, hist_5y)
        )
        fcf: float = fcf_history[-1] if fcf_history else 0.0

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

        return StockData(
            company_name=info.get('longName', ticker_symbol),
            currency=info.get('currency', 'USD'),
            prices=prices,
            sparkline=sparkline,
            ebit=ebit,
            ev=ev,
            nopat=nopat,
            invested_capital=invested_capital,
            ebitda=ebitda,
            pe=pe,
            ps=ps,
            peg=peg,
            fcf=fcf,
            pe_history=pe_history,
            ebit_margin_history=ebit_margin_history,
            fcf_history=fcf_history,
            price_change_hist_pct=price_change_hist_pct
        )


class FmpProvider(DataProvider):
    """Provider di riserva: Financial Modeling Prep (richiede API key)."""

    name = "FMP"

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = api_key

    @_retry_request
    def fetch(self, ticker_symbol: str) -> StockData:
        """
        Recupera i dati da Financial Modeling Prep (FMP).

        Args:
            ticker_symbol (str): Simbolo del ticker.

        Returns:
            StockData: Dati finanziari.
        """
        if not self.api_key:
            raise ValueError("Nessuna API Key FMP configurata.")

        base_url: str = "https://financialmodelingprep.com/api/v3"

        try:
            # Riutilizza la stessa connessione (keep-alive) per le 4 chiamate FMP,
            # riducendo la latenza aggiuntiva proprio nel path di fallback (dove Yahoo
            # e' gia' lento o ha fallito).
            with requests.Session() as session:
                # Recupera il profilo aziendale
                prof_resp = session.get(
                    f"{base_url}/profile/{ticker_symbol}?apikey={self.api_key}",
                    timeout=config.HTTP_TIMEOUT
                ).json()
                if not prof_resp:
                    raise ValueError("Azienda non trovata nel database FMP.")
                profile: dict = prof_resp[0]

                # Recupera le metriche chiave
                km_resp = session.get(
                    f"{base_url}/key-metrics-ttm/{ticker_symbol}?apikey={self.api_key}",
                    timeout=config.HTTP_TIMEOUT
                ).json()
                km: dict = km_resp[0] if km_resp else {}

                # Recupera i ratios
                ratios_resp = session.get(
                    f"{base_url}/ratios-ttm/{ticker_symbol}?apikey={self.api_key}",
                    timeout=config.HTTP_TIMEOUT
                ).json()
                ratios: dict = ratios_resp[0] if ratios_resp else {}

                # Recupera il bilancio
                inc_resp = session.get(
                    f"{base_url}/income-statement/{ticker_symbol}?limit=1&apikey={self.api_key}",
                    timeout=config.HTTP_TIMEOUT
                ).json()
                inc: dict = inc_resp[0] if inc_resp else {}

                # Free Cash Flow piu' recente (per il campanello d'allarme FCF).
                # Nota: a differenza di Yahoo, qui non si recupera uno storico
                # pluriennale ne' i prezzi storici, quindi le regole P/E-vs-media
                # e margine-vs-prezzo restano N/D su questo provider di riserva.
                cf_resp = session.get(
                    f"{base_url}/cash-flow-statement/{ticker_symbol}?limit=1&apikey={self.api_key}",
                    timeout=config.HTTP_TIMEOUT
                ).json()
                cf: dict = cf_resp[0] if cf_resp else {}

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

            fcf: float = float(cf.get('freeCashFlow', 0.0) or 0.0)

            curr_price = float(profile.get('price', 0.0))
            prices = {
                'current': curr_price,
                '1d': curr_price,
                '1w': curr_price,
                '1m': curr_price,
                '1y': curr_price
            }

            return StockData(
                company_name=profile.get('companyName', ticker_symbol),
                currency=profile.get('currency', 'USD'),
                prices=prices,
                ebit=ebit,
                ev=ev,
                nopat=nopat,
                invested_capital=invested_capital,
                ebitda=ebitda,
                pe=pe,
                ps=ps,
                peg=peg,
                fcf=fcf,
                fcf_history=[fcf] if cf else []
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete FMP: {str(e)}")


class TwelveDataProvider(DataProvider):
    """Provider di riserva aggiuntivo: Twelve Data (richiede API key gratuita)."""

    name = "Twelve Data"

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = api_key

    @_retry_request
    def fetch(self, ticker_symbol: str) -> StockData:
        """
        Recupera i dati da Twelve Data.

        Args:
            ticker_symbol (str): Simbolo del ticker.

        Returns:
            StockData: Dati finanziari.
        """
        if not self.api_key:
            raise ValueError("Nessuna API Key Twelve Data configurata.")

        base_url: str = "https://api.twelvedata.com"

        try:
            with requests.Session() as session:
                # Riepilogo di valutazione e bilancio in un'unica chiamata
                stats_resp = session.get(
                    f"{base_url}/statistics",
                    params={"symbol": ticker_symbol, "apikey": self.api_key},
                    timeout=config.HTTP_TIMEOUT
                ).json()

                quote_resp = session.get(
                    f"{base_url}/quote",
                    params={"symbol": ticker_symbol, "apikey": self.api_key},
                    timeout=config.HTTP_TIMEOUT
                ).json()

            if not isinstance(stats_resp, dict) or stats_resp.get('status') == 'error' or not stats_resp.get('statistics'):
                message = stats_resp.get('message', 'Azienda non trovata su Twelve Data.') if isinstance(stats_resp, dict) else 'Risposta non valida da Twelve Data.'
                raise ValueError(message)

            meta: dict = stats_resp.get('meta', {}) or {}
            stats: dict = stats_resp.get('statistics', {}) or {}
            valuations: dict = stats.get('valuations_metrics', {}) or {}
            financials: dict = stats.get('financials', {}) or {}
            income: dict = financials.get('income_statement', {}) or {}
            balance: dict = financials.get('balance_sheet', {}) or {}
            stock_stats: dict = stats.get('stock_statistics', {}) or {}

            ev: float = float(valuations.get('enterprise_value', 0.0) or 0.0)
            ebitda: float = float(income.get('ebitda', 0.0) or 0.0)
            ebit: float = ebitda * DEFAULT_EBIT_MARGIN_PROX

            pe: float = float(valuations.get('trailing_pe', 0.0) or 0.0)
            ps: float = float(valuations.get('price_to_sales_ttm', 0.0) or 0.0)
            peg: float = float(valuations.get('peg_ratio', 0.0) or 0.0)

            tax_rate: float = 0.21
            nopat: float = ebit * (1 - tax_rate)

            total_debt: float = float(balance.get('total_debt_mrq', 0.0) or 0.0)
            book_value_per_share: float = float(balance.get('book_value_per_share_mrq', 0.0) or 0.0)
            shares_outstanding: float = float(stock_stats.get('shares_outstanding', 0.0) or 0.0)
            equity: float = book_value_per_share * shares_outstanding
            invested_capital: float = (total_debt + equity) if equity > 0 else (ev * 0.8 if ev > 0 else 0.0)

            curr_price: float = float((quote_resp or {}).get('close', 0.0) or 0.0) if isinstance(quote_resp, dict) else 0.0
            prices = {
                'current': curr_price,
                '1d': curr_price,
                '1w': curr_price,
                '1m': curr_price,
                '1y': curr_price
            }

            return StockData(
                company_name=meta.get('name', ticker_symbol),
                currency=meta.get('currency', 'USD'),
                prices=prices,
                ebit=ebit,
                ev=ev,
                nopat=nopat,
                invested_capital=invested_capital,
                ebitda=ebitda,
                pe=pe,
                ps=ps,
                peg=peg
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete Twelve Data: {str(e)}")


class EodhdProvider(DataProvider):
    """Provider di riserva aggiuntivo: EOD Historical Data (richiede API key gratuita)."""

    name = "EODHD"

    def __init__(self, api_key: str = "") -> None:
        self.api_key: str = api_key

    @staticmethod
    def _to_eodhd_symbol(ticker_symbol: str) -> str:
        """EODHD richiede sempre un suffisso di borsa (es. 'AAPL.US'). I ticker
        senza suffisso (convenzione Yahoo per i listini USA) vengono assunti
        US; i ticker gia' con suffisso (es. 'ENI.MI') vengono passati cosi'
        come sono."""
        return ticker_symbol if '.' in ticker_symbol else f"{ticker_symbol}.US"

    @_retry_request
    def fetch(self, ticker_symbol: str) -> StockData:
        """
        Recupera i dati da EOD Historical Data (EODHD).

        Args:
            ticker_symbol (str): Simbolo del ticker.

        Returns:
            StockData: Dati finanziari.
        """
        if not self.api_key:
            raise ValueError("Nessuna API Key EODHD configurata.")

        eodhd_symbol: str = self._to_eodhd_symbol(ticker_symbol)
        base_url: str = "https://eodhd.com/api"

        try:
            with requests.Session() as session:
                fund_resp = session.get(
                    f"{base_url}/fundamentals/{eodhd_symbol}",
                    params={"api_token": self.api_key, "fmt": "json"},
                    timeout=config.HTTP_TIMEOUT
                ).json()

                quote_resp = session.get(
                    f"{base_url}/real-time/{eodhd_symbol}",
                    params={"api_token": self.api_key, "fmt": "json"},
                    timeout=config.HTTP_TIMEOUT
                ).json()

            if not isinstance(fund_resp, dict) or not fund_resp.get('General'):
                raise ValueError(f"Ticker '{eodhd_symbol}' non trovato su EODHD.")

            general: dict = fund_resp.get('General', {}) or {}
            highlights: dict = fund_resp.get('Highlights', {}) or {}
            valuation: dict = fund_resp.get('Valuation', {}) or {}
            financials: dict = fund_resp.get('Financials', {}) or {}

            income_yearly: dict = ((financials.get('Income_Statement', {}) or {}).get('yearly', {})) or {}
            balance_yearly: dict = ((financials.get('Balance_Sheet', {}) or {}).get('yearly', {})) or {}

            def _latest_period(yearly: dict) -> dict:
                """L'API restituisce i periodi annuali come mappa data->voci,
                non necessariamente ordinata: si prende la data piu' recente."""
                if not yearly:
                    return {}
                latest_date = max(yearly.keys())
                return yearly.get(latest_date, {}) or {}

            income: dict = _latest_period(income_yearly)
            balance: dict = _latest_period(balance_yearly)

            ev: float = float(valuation.get('EnterpriseValue', 0.0) or 0.0)
            ebitda: float = float(highlights.get('EBITDA', 0.0) or income.get('ebitda', 0.0) or 0.0)
            ebit: float = float(income.get('ebit', 0.0) or (ebitda * DEFAULT_EBIT_MARGIN_PROX))

            pe: float = float(highlights.get('PERatio', 0.0) or 0.0)
            ps: float = float(valuation.get('PriceSalesTTM', 0.0) or 0.0)
            peg: float = float(highlights.get('PEGRatio', 0.0) or 0.0)

            tax_rate: float = 0.21
            income_before_tax: float = float(income.get('incomeBeforeTax', 0.0) or 0.0)
            income_tax_expense: float = float(income.get('incomeTaxExpense', 0.0) or 0.0)
            if income_before_tax > 0:
                tax_rate = min(max(income_tax_expense / income_before_tax, 0.15), 0.35)

            nopat: float = ebit * (1 - tax_rate)

            total_debt: float = float(balance.get('shortLongTermDebtTotal', 0.0) or 0.0)
            equity: float = float(balance.get('totalStockholderEquity', 0.0) or 0.0)
            invested_capital: float = (total_debt + equity) if equity > 0 else (ev * 0.8 if ev > 0 else 0.0)

            curr_price: float = float((quote_resp or {}).get('close', 0.0) or 0.0) if isinstance(quote_resp, dict) else 0.0
            prices = {
                'current': curr_price,
                '1d': curr_price,
                '1w': curr_price,
                '1m': curr_price,
                '1y': curr_price
            }

            return StockData(
                company_name=general.get('Name', ticker_symbol),
                currency=general.get('CurrencyCode', 'USD'),
                prices=prices,
                ebit=ebit,
                ev=ev,
                nopat=nopat,
                invested_capital=invested_capital,
                ebitda=ebitda,
                pe=pe,
                ps=ps,
                peg=peg
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore di rete EODHD: {str(e)}")


class FinancialDataFetcher:
    """
    Orchestratore dei provider di dati azionari (pattern Strategy).

    Include:
    - Caching locale dei dati
    - Richieste "hedged": se il provider primario (Yahoo) non risponde entro
      HEDGE_DELAY_SECONDS, il primo provider di riserva configurato parte in
      parallelo e vince il primo risultato utile, riducendo l'attesa nel caso
      peggiore senza sprecare quota quando Yahoo risponde subito.
    - Provider di riserva aggiuntivi (es. Twelve Data, EODHD) tentati in
      sequenza solo se sia il primario sia il primo di riserva falliscono
      entrambi.
    - Fallback finale a dati statici per i ticker piu' comuni
    """

    def __init__(self, fmp_api_key: str = "", twelvedata_api_key: str = "", eodhd_api_key: str = "") -> None:
        self.fmp_api_key: str = fmp_api_key
        self.twelvedata_api_key: str = twelvedata_api_key
        self.eodhd_api_key: str = eodhd_api_key

    def _providers(self) -> List[DataProvider]:
        """Catena ordinata dei provider disponibili (il primo e' il preferito)."""
        providers: List[DataProvider] = [YahooProvider()]
        if self.fmp_api_key:
            providers.append(FmpProvider(self.fmp_api_key))
        if self.twelvedata_api_key:
            providers.append(TwelveDataProvider(self.twelvedata_api_key))
        if self.eodhd_api_key:
            providers.append(EodhdProvider(self.eodhd_api_key))
        return providers

    def fetch_data(self, ticker_symbol: str) -> StockData:
        """
        Recupera i dati fondamentali dell'azione dal miglior provider disponibile.

        Args:
            ticker_symbol (str): Simbolo del ticker (es. "AAPL").

        Returns:
            StockData: Dati finanziari completi.

        Raises:
            ValueError: Se tutti i provider falliscono.
        """
        if not ticker_symbol:
            raise ValueError("Inserire un Ticker valido.")

        ticker_upper = ticker_symbol.upper()
        cache_key = f"stock_{ticker_upper}"
        logger = logging.getLogger("QuantumValue")

        # 1. Prova con la cache
        cached_data = get_cached(cache_key)
        if cached_data:
            return StockData.from_dict(cached_data)

        providers = self._providers()
        primary = providers[0]
        backup = providers[1] if len(providers) > 1 else None
        extra_backups = providers[2:]
        errors: List[str] = []

        # 2. Provider primario, con hedge sul primo provider di riserva se lento
        executor = ThreadPoolExecutor(max_workers=2)
        try:
            primary_future = executor.submit(primary.fetch, ticker_upper)
            try:
                data = primary_future.result(timeout=HEDGE_DELAY_SECONDS)
                set_cached(cache_key, data.to_dict())
                return data
            except FutureTimeoutError:
                # Primario lento: non e' fallito, ma avviamo la riserva in parallelo
                logger.info(f"{primary.name} lento per {ticker_upper}: avvio hedge su provider di riserva.")
            except Exception as primary_error:
                errors.append(f"{primary.name}: {str(primary_error)}")
                logger.warning(f"{primary.name} fallito per {ticker_upper}: {str(primary_error)}")
                primary_future = None  # type: ignore[assignment]

            backup_future = executor.submit(backup.fetch, ticker_upper) if backup else None

            # Il primario, se ancora in corsa, resta preferito
            if primary_future is not None:
                try:
                    data = primary_future.result()
                    set_cached(cache_key, data.to_dict())
                    return data
                except Exception as primary_error:
                    errors.append(f"{primary.name}: {str(primary_error)}")
                    logger.warning(f"{primary.name} fallito per {ticker_upper}: {str(primary_error)}")

            # 3. Primo provider di riserva
            if backup_future is not None and backup is not None:
                try:
                    data = backup_future.result()
                    set_cached(cache_key, data.to_dict())
                    return data
                except Exception as backup_error:
                    errors.append(f"{backup.name}: {str(backup_error)}")
                    logger.error(f"{backup.name} fallito per {ticker_upper}: {str(backup_error)}")
        finally:
            # Non attende gli hedge ancora in volo: il loro risultato non serve piu'
            executor.shutdown(wait=False, cancel_futures=True)

        # 4. Provider di riserva aggiuntivi (es. Twelve Data), tentati in sequenza
        for extra_provider in extra_backups:
            try:
                data = extra_provider.fetch(ticker_upper)
                set_cached(cache_key, data.to_dict())
                return data
            except Exception as extra_error:
                errors.append(f"{extra_provider.name}: {str(extra_error)}")
                logger.error(f"{extra_provider.name} fallito per {ticker_upper}: {str(extra_error)}")

        # 5. Fallback a dati statici
        if ticker_upper in config.STATIC_FALLBACK:
            logger.warning(f"Utilizzo dati statici per {ticker_upper}")
            return StockData.from_dict(config.STATIC_FALLBACK[ticker_upper])

        detail = "\n".join(errors) if errors else "Nessun provider disponibile."
        raise ValueError(
            f"Fallimento totale provider per {ticker_upper}.\n{detail}\n"
            f"Nessun dato statico disponibile."
        )
