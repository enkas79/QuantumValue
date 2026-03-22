"""
QuantumValue Analysis - Strumento di Analisi Fondamentale.

Modulo per l'analisi quantitativa azionaria (EY, ROIC, EV/EBITDA).
Funzionalità: yfinance, formattazione, scoring algoritmico, ricerca globale mercati.
Novità: Ripristino Guida Strategica Completa. Fix Threading PyQt6,
Gestione Eccezioni Globali (Airbag), Protezione PyInstaller.

Architettura: MVC (Model-View-Controller) con stretta separazione logica/UI.
Autore: Enrico Martini
Versione: 0.0.22
"""

import sys
import multiprocessing
import traceback
from typing import Optional, Dict, Union, Tuple, List, Any

# Gestione dipendenze esterne
try:
    import yfinance as yf
    import pandas as pd
    import requests
except ImportError as e:
    print(f"Errore: Librerie mancanti. Eseguire 'pip install yfinance pandas requests'.\nDettagli: {e}")
    sys.exit(1)

# Importazione librerie Qt6
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QMessageBox, QGroupBox, QGridLayout,
        QDialog, QTextBrowser, QDialogButtonBox, QTableWidget,
        QTableWidgetItem, QAbstractItemView, QHeaderView
    )
    from PyQt6.QtGui import QAction, QFont, QDesktopServices
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer, QUrl
except ImportError as e:
    print(f"Errore: PyQt6 non trovato. Eseguire 'pip install PyQt6'.\nDettagli: {e}")
    sys.exit(1)


# ==========================================
# GESTIONE ECCEZIONI GLOBALI (AIRBAG)
# ==========================================
def global_exception_handler(exc_type, exc_value, exc_tb) -> None:
    """Cattura crash imprevisti ed evita la chiusura silenziosa in modalità noconsole."""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Errore Fatale di Sistema")
    msg.setText("Il programma ha riscontrato un errore critico e deve essere chiuso.")
    msg.setInformativeText(str(exc_value))
    msg.setDetailedText(error_msg)
    msg.exec()


# ==========================================
# CONFIGURAZIONE E COSTANTI
# ==========================================
APP_NAME: str = "QuantumValue Analysis"
VERSION: str = "0.0.22"
AUTHOR: str = "Enrico Martini"
GITHUB_REPO: str = "enkas79/QuantumValue"

YAHOO_EXCHANGE_MAP: Dict[str, str] = {
    "NYQ": "NYSE", "NMS": "NASDAQ", "MIL": "MIB30", "PAR": "CAC40",
    "FRA": "DAX", "GER": "DAX", "LSE": "LSE", "MCE": "IBEX35",
    "AMS": "AEX", "HAN": "HAN", "EBS": "SWX"
}


# ==========================================
# LIVELLO LOGICA DI BUSINESS (MODEL)
# ==========================================

class GitHubUpdateManager:
    @staticmethod
    def check_for_updates(current_version: str, repo_path: str) -> Tuple[bool, str, str]:
        api_url: str = f"https://api.github.com/repos/{repo_path}/releases/latest"
        headers: Dict[str, str] = {'Accept': 'application/vnd.github.v3+json'}
        try:
            response = requests.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            latest_tag: str = data.get('tag_name', '').replace('v', '')
            html_url: str = data.get('html_url', '')
            if not latest_tag: return False, current_version, ""
            return latest_tag > current_version.replace('v', ''), latest_tag, html_url
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Impossibile verificare gli aggiornamenti: {str(e)}")

class DataFormatter:
    @staticmethod
    def parse_to_float(value_str: str) -> float:
        clean_str: str = value_str.strip().upper().replace(',', '.')
        if not clean_str: raise ValueError("Campo vuoto.")
        multiplier: float = 1.0
        if clean_str.endswith('K'): multiplier = 1_000.0; clean_str = clean_str[:-1]
        elif clean_str.endswith('M'): multiplier = 1_000_000.0; clean_str = clean_str[:-1]
        elif clean_str.endswith('B'): multiplier = 1_000_000_000.0; clean_str = clean_str[:-1]
        try: return float(clean_str) * multiplier
        except ValueError: raise ValueError(f"Formato non valido: '{value_str}'.")

    @staticmethod
    def format_to_string(value: float) -> str:
        abs_value: float = abs(value)
        if abs_value >= 1_000_000_000: formatted = f"{value / 1_000_000_000:.2f}B"
        elif abs_value >= 1_000_000: formatted = f"{value / 1_000_000:.2f}M"
        elif abs_value >= 1_000: formatted = f"{value / 1_000:.2f}K"
        else: formatted = f"{value:.2f}"
        return formatted.replace('.', ',')

class FinancialEvaluator:
    @staticmethod
    def evaluate(ey: float, roic: float, ev_ebitda: float) -> Tuple[float, str, str, Dict[str, Dict[str, str]]]:
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

class FinancialCalculator:
    @staticmethod
    def validate_inputs(data: Dict[str, str]) -> Dict[str, float]:
        return {k: DataFormatter.parse_to_float(v) for k, v in data.items()}

    @staticmethod
    def calculate_metrics(data: Dict[str, float]) -> Dict[str, Union[float, str]]:
        results: Dict[str, Union[float, str]] = {}
        try: results['ey'] = (data['ebit'] / data['ev']) * 100 if data['ev'] != 0 else "Err(EV=0)"
        except ZeroDivisionError: results['ey'] = "Errore"
        try: results['roic'] = (data['nopat'] / data['invested_capital']) * 100 if data['invested_capital'] != 0 else "Err(Cap=0)"
        except ZeroDivisionError: results['roic'] = "Errore"
        try: results['ev_ebitda'] = data['ev'] / data['ebitda'] if data['ebitda'] != 0 else "Err(EBITDA=0)"
        except ZeroDivisionError: results['ev_ebitda'] = "Errore"
        return results

class TickerSearcher:
    @staticmethod
    def search_by_name(query: str) -> List[Tuple[str, str, str]]:
        url: str = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10"
        headers: Dict[str, str] = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            results: List[Tuple[str, str, str]] = []
            for quote in data.get('quotes', []):
                if quote.get('quoteType') in ['EQUITY', 'ETF']:
                    symbol: str = quote.get('symbol', '')
                    name: str = quote.get('shortname', quote.get('longname', 'Sconosciuto'))
                    raw_exchange: str = quote.get('exchange', 'N/A')
                    mapped_exchange: str = YAHOO_EXCHANGE_MAP.get(raw_exchange, raw_exchange)
                    if symbol: results.append((symbol, name, mapped_exchange))
            return results
        except Exception as e:
            raise ValueError(f"Errore di rete durante la ricerca: {str(e)}")

class FinancialDataFetcher:
    def __init__(self, fmp_api_key: str = "") -> None:
        self.fmp_api_key = fmp_api_key

    def fetch_fundamental_data(self, ticker_symbol: str) -> Dict[str, Any]:
        if not ticker_symbol: raise ValueError("Inserire un Ticker valido.")
        try: return self._fetch_from_yahoo(ticker_symbol)
        except Exception as yf_error:
            if self.fmp_api_key:
                try: return self._fetch_from_fmp(ticker_symbol)
                except Exception as fmp_error: raise ValueError(f"Sia Yahoo Finance che FMP hanno fallito.\nYahoo: {yf_error}\nFMP: {fmp_error}")
            else: raise ValueError(f"Errore Yahoo Finance (nessuna API configurata): {str(yf_error)}")

    def _fetch_from_yahoo(self, ticker_symbol: str) -> Dict[str, Any]:
        ticker = yf.Ticker(ticker_symbol.upper())
        info = ticker.info
        if not info or 'shortName' not in info: raise ValueError(f"Ticker '{ticker_symbol}' non trovato.")

        ev: float = float(info.get('enterpriseValue', 0.0))
        ebitda: float = float(info.get('ebitda', 0.0))
        if ev == 0.0 and ebitda == 0.0: raise ValueError("Dati EV/EBITDA non forniti da Yahoo per questo titolo.")

        hist = ticker.history(period="1y")
        prices: Dict[str, float] = {'current': 0.0, '1d': 0.0}
        if not hist.empty:
            prices['current'] = float(hist['Close'].iloc[-1])
            prices['1d'] = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else prices['current']

        inc_stmt = ticker.income_stmt
        bal_sheet = ticker.balance_sheet

        ebit: float = float(inc_stmt.loc['EBIT'].iloc[0]) if not inc_stmt.empty and 'EBIT' in inc_stmt.index else ebitda * 0.85
        tax_prov: float = float(inc_stmt.loc['Tax Provision'].iloc[0]) if not inc_stmt.empty and 'Tax Provision' in inc_stmt.index else 0.0
        pretax: float = float(inc_stmt.loc['Pretax Income'].iloc[0]) if not inc_stmt.empty and 'Pretax Income' in inc_stmt.index else 1.0
        tax_rate: float = min(tax_prov / pretax, 0.35) if pretax > 0 and tax_prov > 0 else 0.21
        nopat: float = ebit * (1 - tax_rate)

        total_debt: float = float(info.get('totalDebt', 0.0))
        equity: float = float(info.get('bookValue', 0.0)) * float(info.get('sharesOutstanding', 0.0))
        if not bal_sheet.empty and 'Stockholders Equity' in bal_sheet.index:
            equity = float(bal_sheet.loc['Stockholders Equity'].iloc[0])

        return {
            'company_name': info.get('longName', ticker_symbol), 'currency': info.get('currency', 'USD'), 'prices': prices,
            'ebit': ebit, 'ev': ev, 'nopat': nopat, 'invested_capital': total_debt + equity, 'ebitda': ebitda
        }

    def _fetch_from_fmp(self, ticker_symbol: str) -> Dict[str, Any]:
        base_url = "https://financialmodelingprep.com/api/v3"
        try:
            prof_resp = requests.get(f"{base_url}/profile/{ticker_symbol}?apikey={self.fmp_api_key}", timeout=5).json()
            if not prof_resp: raise ValueError("Azienda non trovata nel database FMP.")
            profile = prof_resp[0]
            km_resp = requests.get(f"{base_url}/key-metrics-ttm/{ticker_symbol}?apikey={self.fmp_api_key}", timeout=5).json()
            km = km_resp[0] if km_resp else {}
            inc_resp = requests.get(f"{base_url}/income-statement/{ticker_symbol}?limit=1&apikey={self.fmp_api_key}", timeout=5).json()
            inc = inc_resp[0] if inc_resp else {}

            ev = km.get('enterpriseValueTTM', 0.0)
            ebitda = inc.get('ebitda', 0.0)
            ebit = inc.get('operatingIncome', ebitda * 0.85)

            tax_rate = 0.21
            if inc.get('incomeBeforeTax', 0) > 0: tax_rate = inc.get('incomeTaxExpense', 0) / inc.get('incomeBeforeTax', 1)
            nopat = ebit * (1 - min(max(tax_rate, 0.15), 0.35))
            invested_capital = km.get('investedCapitalTTM', ev * 0.8)

            return {
                'company_name': profile.get('companyName', ticker_symbol), 'currency': profile.get('currency', 'USD'),
                'prices': {'current': profile.get('price', 0.0), '1d': profile.get('price', 0.0)},
                'ebit': ebit, 'ev': ev, 'nopat': nopat, 'invested_capital': invested_capital, 'ebitda': ebitda
            }
        except requests.exceptions.RequestException as e: raise ValueError(f"Errore connessione API FMP: {str(e)}")


# ==========================================
# ASYNC WORKERS (Controller Utility)
# ==========================================

class UpdateCheckWorker(QThread):
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)
    def __init__(self, current_version: str, repo: str) -> None:
        super().__init__()
        self.current_version = current_version
        self.repo = repo
    def run(self) -> None:
        try:
            update_avail, new_ver, url = GitHubUpdateManager.check_for_updates(self.current_version, self.repo)
            self.finished.emit(update_avail, new_ver, url)
        except ValueError as e: self.error.emit(str(e))
        except Exception as e: self.error.emit(f"Errore fatale controllo aggiornamenti: {str(e)}")

class SearchWorker(QThread):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)
    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query
    def run(self) -> None:
        try:
            results = TickerSearcher.search_by_name(self.query)
            self.finished.emit(results, self.query)
        except Exception as e:
            self.error.emit(str(e))

class FetchWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    def __init__(self, fetcher: FinancialDataFetcher, ticker: str) -> None:
        super().__init__()
        self.fetcher = fetcher
        self.ticker = ticker
    def run(self) -> None:
        try:
            data = self.fetcher.fetch_fundamental_data(self.ticker)
            self.finished.emit(data)
        except ValueError as e: self.error.emit(str(e))
        except Exception as e: self.error.emit(f"Errore di sistema: {str(e)}")


# ==========================================
# USER INTERFACE LAYER (View / Controller)
# ==========================================

class GuideDialog(QDialog):
    """Finestra di dialogo dedicata alla spiegazione strategica delle metriche finanziarie."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guida Strategica alle Metriche Value")
        self.setMinimumSize(650, 650)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)

        html_content = """
        <h1 style='color: #2c3e50;'>La Strategia dell'Analisi Fondamentale</h1>
        <p>Questa applicazione si basa sui principi del <i>Value Investing</i> e della logica quantitativa per valutare la reale qualità e convenienza di un'azienda sul mercato.</p>
        <hr>

        <h2 style='color: #2980b9;'>1. Earnings Yield (EY) - Il "Re" del Valore</h2>
        <p>L'Earnings Yield è il reciproco del rapporto P/E ed è calcolato nella sua forma più robusta (utilizzata da Joel Greenblatt nella <i>Magic Formula</i>).</p>
        <ul>
            <li><b>Formula:</b> EBIT / Enterprise Value (EV)</li>
            <li><b>Perché funziona:</b> A differenza del semplice P/E, l'EV include il debito e sottrae la cassa, fornendo una visione reale di quanto "costa" l'intera azienda rispetto ai suoi utili operativi.</li>
            <li><b>Dati Statistici:</b> Strategie basate sull'acquisto del decile con il più alto Earnings Yield hanno storicamente sovraperformato l'S&P 500 con un <i>win rate</i> superiore al <b>65-70%</b> su orizzonti di 10 anni.</li>
        </ul>

        <h2 style='color: #2980b9;'>2. Return on Invested Capital (ROIC) - Il Proxy della Qualità</h2>
        <p>Il ROIC misura l'efficienza con cui un'azienda genera profitti dal capitale investito (sia debito che equity).</p>
        <ul>
            <li><b>Formula:</b> NOPAT / Capitale Investito</li>
            <li><b>Perché funziona:</b> Identifica le aziende con un "Moat" (fossato economico) elevato. Un ROIC costantemente superiore al costo del capitale (WACC) è il principale motore della creazione di valore a lungo termine.</li>
            <li><b>Dati Statistici:</b> L'integrazione del ROIC in una strategia "Magic Formula" (combinato con l'Earnings Yield) ha prodotto rendimenti medi annui del <b>26,4% nel periodo 1991-2024</b>, battendo il mercato in 23 anni su 34 (win rate del <b>67,6%</b>).</li>
        </ul>

        <h2 style='color: #2980b9;'>3. Enterprise Value to EBITDA (EV/EBITDA) - L'Indicatore di Resilienza</h2>
        <p>Questo multiplo è considerato molto più affidabile del Price-to-Book (P/B) o del P/E per confrontare aziende con diverse strutture di capitale.</p>
        <ul>
            <li><b>Perché funziona:</b> L'EBITDA è meno soggetto a manipolazioni contabili rispetto all'utile netto, e l'EV neutralizza le differenze di leva finanziaria tra le aziende.</li>
            <li><b>Dati Statistici:</b> Studi di <i>O'Shaughnessy Asset Management</i> indicano che l'EV/EBITDA ha un "quintile spread" (la differenza di rendimento tra i titoli più economici e quelli più costosi) del <b>6,0%</b>, superando significativamente il 2,8% del P/B e il 5,1% del P/E.</li>
        </ul>
        <hr>
        
        <h3 style='color: #7f8c8d;'>Glossario delle Grandezze di Base</h3>
        <p style='font-size: 12px;'>
        <b>EBIT:</b> Utile Operativo (prima di interessi e tasse).<br>
        <b>EV (Enterprise Value):</b> Valore dell'Azienda (Capitalizzazione di mercato + Debito Totale - Cassa).<br>
        <b>NOPAT:</b> Utile operativo al netto delle imposte (EBIT * (1 - Tax Rate)).<br>
        <b>Capitale Investito:</b> Totale dei fondi impiegati nel business (Debito + Patrimonio Netto/Equity).<br>
        <b>EBITDA:</b> Utile operativo al lordo di ammortamenti e svalutazioni.
        </p>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

class FmpSetupDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurazione Database Dati (Opzionale)")
        self.setMinimumSize(450, 200)
        self.api_key: str = ""
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        lbl_desc = QLabel(
            "<b>Migliora l'affidabilità dei dati!</b><br><br>"
            "Yahoo Finance a volte è incompleto, specialmente per le borse europee.<br>"
            "Puoi inserire gratuitamente una API Key di <b>Financial Modeling Prep (FMP)</b>."
        )
        layout.addWidget(lbl_desc)
        btn_link = QPushButton("Ottieni API Key FMP Gratuita")
        btn_link.setStyleSheet("color: #2980b9; text-align: left; border: none; text-decoration: underline;")
        btn_link.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://site.financialmodelingprep.com/developer/docs/")))
        layout.addWidget(btn_link)
        self.txt_api = QLineEdit()
        self.txt_api.setPlaceholderText("Incolla qui la tua API Key FMP...")
        layout.addWidget(self.txt_api)
        btn_box = QDialogButtonBox()
        btn_save = btn_box.addButton("Salva API Key", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_skip = btn_box.addButton("Salta (Usa solo Yahoo)", QDialogButtonBox.ButtonRole.RejectRole)
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_save(self) -> None:
        self.api_key = self.txt_api.text().strip()
        self.accept()

class TickerSearchDialog(QDialog):
    def __init__(self, results: List[Tuple[str, str, str]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Seleziona Azienda")
        self.setMinimumSize(450, 300)
        self.selected_ticker: Optional[str] = None
        self.results = results
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        lbl_info = QLabel("Seleziona l'azienda corretta e la relativa Borsa dalla lista:")
        lbl_info.setStyleSheet("color: #2c3e50; font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(lbl_info)
        self.table = QTableWidget(len(self.results), 3)
        self.table.setHorizontalHeaderLabels(["Simbolo", "Nome Azienda", "Borsa"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row, (sym, name, exch) in enumerate(self.results):
            self.table.setItem(row, 0, QTableWidgetItem(sym))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(exch))
        self.table.selectRow(0)
        self.table.itemDoubleClicked.connect(self._on_accept)
        layout.addWidget(self.table)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self) -> None:
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            self.selected_ticker = self.table.item(selected_row, 0).text()
            self.accept()

class InfoDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Informazioni sul Software")
        self.setFixedSize(320, 160)
        layout = QVBoxLayout(self)
        info_label = QLabel(
            f"<h2 style='color:#2980b9; margin-bottom: 5px;'>{APP_NAME}</h2>"
            f"<p style='font-size: 14px;'><b>Autore:</b> {AUTHOR}<br><b>Versione:</b> {VERSION}</p>"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        btn_close = QPushButton("Chiudi")
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedWidth(100)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(AUTHOR.replace(" ", ""), APP_NAME.replace(" ", ""))
        self.fmp_api_key = self.settings.value("fmp_api_key", "")

        self.calculator = FinancialCalculator()
        self.fetcher = FinancialDataFetcher(self.fmp_api_key)
        self.evaluator = FinancialEvaluator()

        self.fetch_worker: Optional[FetchWorker] = None
        self.search_worker: Optional[SearchWorker] = None
        self.update_worker: Optional[UpdateCheckWorker] = None

        self.price_history: Dict[str, float] = {}
        self.currency_symbol: str = ""

        self._init_ui()
        QTimer.singleShot(200, self._check_first_run_setup)
        QTimer.singleShot(1000, lambda: self._check_for_updates(silent=True))

    def _check_first_run_setup(self) -> None:
        asked = self.settings.value("fmp_asked_once", False, type=bool)
        if not asked and not self.fmp_api_key:
            dialog = FmpSetupDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.api_key:
                self.fmp_api_key = dialog.api_key
                self.settings.setValue("fmp_api_key", self.fmp_api_key)
                self.fetcher.fmp_api_key = self.fmp_api_key
                self.statusBar().showMessage("API Key FMP configurata. Resilienza dati attivata.")
            self.settings.setValue("fmp_asked_once", True)

    def _init_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.setMinimumSize(650, 650)
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QGroupBox { font-weight: bold; border: 1px solid #c8d6e5; border-radius: 6px; margin-top: 10px; background-color: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #222f3e; }
            QLineEdit { border: 1px solid #c8d6e5; border-radius: 4px; padding: 5px; background-color: #f5f6fa; }
            QLineEdit:focus { border: 1px solid #2e86de; }
        """)

        self._create_menu_bar()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel(APP_NAME)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        self._create_search_section(main_layout)
        self._create_input_section(main_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        self._create_results_section(bottom_layout)
        self._create_evaluation_section(bottom_layout)

        main_layout.addLayout(bottom_layout)
        main_layout.addStretch(1)

        self._create_action_buttons(main_layout)
        self.statusBar().showMessage("Pronto. Scrivi il Ticker o il Nome Azienda e premi Invio.")

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        reset_api_action = QAction("&Reimposta API FMP", self)
        reset_api_action.triggered.connect(self._reset_api_key)
        file_menu.addAction(reset_api_action)
        exit_action = QAction("&Esci", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("&?")
        update_action = QAction("&Verifica Aggiornamenti", self)
        update_action.triggered.connect(lambda: self._check_for_updates(silent=False))
        help_menu.addAction(update_action)
        help_menu.addSeparator()
        guide_action = QAction("&Guida Metriche", self)
        guide_action.triggered.connect(lambda: GuideDialog(self).exec())
        help_menu.addAction(guide_action)
        help_menu.addSeparator()
        about_action = QAction("&Info", self)
        about_action.triggered.connect(lambda: InfoDialog(self).exec())
        help_menu.addAction(about_action)

    def _reset_api_key(self) -> None:
        self.settings.remove("fmp_api_key")
        self.settings.setValue("fmp_asked_once", False)
        self.fmp_api_key = ""
        self.fetcher.fmp_api_key = ""
        QMessageBox.information(self, "API Resettata", "Impostazioni ripristinate. Al riavvio verrà richiesta la chiave.")

    def _check_for_updates(self, silent: bool = True) -> None:
        if not silent: self.statusBar().showMessage("Ricerca aggiornamenti su GitHub...")
        self.update_worker = UpdateCheckWorker(VERSION, GITHUB_REPO)
        self.update_worker.finished.connect(lambda u, v, url: self._on_update_checked(u, v, url, silent))
        self.update_worker.error.connect(lambda e: self._on_update_error(e, silent))
        self.update_worker.start()

    def _on_update_checked(self, update_available: bool, new_version: str, download_url: str, silent: bool) -> None:
        if update_available:
            self.statusBar().showMessage(f"Nuovo aggiornamento disponibile: v{new_version}")
            reply = QMessageBox.question(
                self, "Aggiornamento Disponibile",
                f"È disponibile la versione <b>v{new_version}</b>.<br><br>Vuoi scaricare il nuovo pacchetto?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes and download_url: QDesktopServices.openUrl(QUrl(download_url))
        elif not silent:
            QMessageBox.information(self, "Nessun Aggiornamento", "Stai già utilizzando la versione più recente.")
            self.statusBar().showMessage("Software aggiornato.")

    def _on_update_error(self, error_msg: str, silent: bool) -> None:
        if not silent:
            QMessageBox.warning(self, "Errore Aggiornamento", error_msg)
            self.statusBar().showMessage("Pronto.")

    def _create_search_section(self, layout: QVBoxLayout) -> None:
        search_group = QGroupBox("1. Ricerca Azienda")
        search_layout = QHBoxLayout(search_group)
        search_layout.setContentsMargins(10, 15, 10, 10)
        self.input_ticker = QLineEdit()
        self.input_ticker.setPlaceholderText("Es. AAPL oppure Apple...")
        self.input_ticker.textChanged.connect(self._force_uppercase_ticker)
        self.input_ticker.returnPressed.connect(self._on_search_requested)
        search_layout.addWidget(self.input_ticker, stretch=1)
        self.btn_fetch = QPushButton(" Cerca/Scarica")
        self.btn_fetch.setStyleSheet("background-color: #2e86de; color: white; border-radius: 4px; font-weight: bold; padding: 5px 15px;")
        self.btn_fetch.clicked.connect(self._on_search_requested)
        search_layout.addWidget(self.btn_fetch)
        layout.addWidget(search_group)

    def _create_input_section(self, layout: QVBoxLayout) -> None:
        input_group = QGroupBox("2. Dati Finanziari Aziendali & Quotazione")
        grid_layout = QGridLayout(input_group)
        self.lbl_company_name = QLabel("Azienda: --")
        self.lbl_company_name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_company_name.setStyleSheet("color: #2980b9;")
        grid_layout.addWidget(self.lbl_company_name, 0, 0, 1, 4)
        price_layout = QHBoxLayout()
        self.lbl_price = QLabel("Prezzo: --")
        self.lbl_price.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_variation = QLabel("")
        self.lbl_variation.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        price_layout.addWidget(self.lbl_price)
        price_layout.addSpacing(15)
        price_layout.addWidget(self.lbl_variation)
        price_layout.addStretch()
        grid_layout.addLayout(price_layout, 1, 0, 1, 4)
        self.inputs: Dict[str, QLineEdit] = {}
        fields = [('ebit', 'EBIT:', 2, 0), ('ev', 'Enterprise Value:', 2, 2),
                  ('nopat', 'NOPAT:', 3, 0), ('invested_capital', 'Capitale Investito:', 3, 2),
                  ('ebitda', 'EBITDA:', 4, 0)]
        for key, text, row, col in fields:
            le = QLineEdit()
            le.textChanged.connect(self._on_input_changed)
            grid_layout.addWidget(QLabel(text), row, col)
            grid_layout.addWidget(le, row, col + 1)
            self.inputs[key] = le
        layout.addWidget(input_group)

    def _create_results_section(self, layout: QHBoxLayout) -> None:
        res_group = QGroupBox("3. Metriche Analizzate")
        inner_layout = QVBoxLayout(res_group)
        self.res_labels: Dict[str, QLabel] = {}
        self.res_eval_labels: Dict[str, QLabel] = {}
        metrics = [('ey', 'Earnings Yield:'), ('roic', 'ROIC:'), ('ev_ebitda', 'EV/EBITDA:')]
        val_font = QFont("Consolas", 12, QFont.Weight.Bold)
        for key, title in metrics:
            row_layout = QVBoxLayout()
            top_row = QHBoxLayout()
            top_row.addWidget(QLabel(title))
            lbl_val = QLabel("--")
            lbl_val.setFont(val_font)
            top_row.addStretch()
            top_row.addWidget(lbl_val)
            lbl_eval = QLabel("")
            lbl_eval.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_layout.addLayout(top_row)
            row_layout.addWidget(lbl_eval)
            self.res_labels[key] = lbl_val
            self.res_eval_labels[key] = lbl_eval
            inner_layout.addLayout(row_layout)
        inner_layout.addStretch()
        layout.addWidget(res_group, stretch=1)

    def _create_evaluation_section(self, layout: QHBoxLayout) -> None:
        eval_group = QGroupBox("4. Verdetto Finale")
        eval_layout = QVBoxLayout(eval_group)
        eval_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.lbl_score = QLabel("- / 10")
        self.lbl_score.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_recommendation = QLabel("In attesa di dati...")
        self.lbl_recommendation.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_recommendation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eval_layout.addSpacing(20)
        eval_layout.addWidget(QLabel("Voto Complessivo:", alignment=Qt.AlignmentFlag.AlignCenter))
        eval_layout.addWidget(self.lbl_score)
        eval_layout.addWidget(self.lbl_recommendation)
        layout.addWidget(eval_group, stretch=1)

    def _create_action_buttons(self, layout: QVBoxLayout) -> None:
        self.btn_exit = QPushButton("Esci dal Programma")
        self.btn_exit.setMinimumHeight(40)
        self.btn_exit.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_exit.setStyleSheet("background-color: #e66767; color: white; border-radius: 4px;")
        self.btn_exit.clicked.connect(self.close)
        layout.addWidget(self.btn_exit)

    def _force_uppercase_ticker(self, text: str) -> None:
        if not text.isupper():
            cursor_pos = self.input_ticker.cursorPosition()
            self.input_ticker.blockSignals(True)
            self.input_ticker.setText(text.upper())
            self.input_ticker.blockSignals(False)
            self.input_ticker.setCursorPosition(cursor_pos)

    def _on_search_requested(self) -> None:
        query = self.input_ticker.text().strip()
        if not query:
            QMessageBox.warning(self, "Attenzione", "Inserire il nome o Ticker.")
            return

        self.btn_fetch.setEnabled(False)
        self.lbl_price.setText("Prezzo: --")
        self.lbl_variation.setText("")
        self.statusBar().showMessage(f"Ricerca globale per '{query}'...")

        self.search_worker = SearchWorker(query)
        self.search_worker.finished.connect(self._on_search_success)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_success(self, results: List[Tuple[str, str, str]], query: str) -> None:
        self.btn_fetch.setEnabled(True)
        if not results:
            QMessageBox.warning(self, "Nessun Risultato", f"Nessuna corrispondenza per '{query}'.")
            return

        exact_match = next((res for res in results if res[0].upper() == query.upper()), None)
        if exact_match:
            self._start_data_fetch(exact_match[0])
        else:
            dialog = TickerSearchDialog(results, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_ticker:
                self.input_ticker.setText(dialog.selected_ticker)
                self._start_data_fetch(dialog.selected_ticker)

    def _on_search_error(self, error_msg: str) -> None:
        self.btn_fetch.setEnabled(True)
        QMessageBox.critical(self, "Errore Ricerca API", error_msg)

    def _start_data_fetch(self, ticker: str) -> None:
        self.btn_fetch.setEnabled(False)
        self.statusBar().showMessage(f"Download dati per {ticker} (Yahoo + Fallback)...")
        self.fetch_worker = FetchWorker(self.fetcher, ticker)
        self.fetch_worker.finished.connect(self._on_fetch_success)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.start()

    def _on_fetch_success(self, data: Dict[str, Any]) -> None:
        self.lbl_company_name.setText(f"Azienda: {data.pop('company_name', 'N/A')}")
        self.currency_symbol = data.pop('currency', '$')

        prices = data.pop('prices', {})
        curr = prices.get('current', 0.0)
        past = prices.get('1d', curr)
        self.lbl_price.setText(f"Prezzo: {curr:.2f} {self.currency_symbol}")

        if past > 0:
            diff = curr - past
            color = "#27ae60" if diff >= 0 else "#c0392b"
            sign = "+" if diff >= 0 else ""
            self.lbl_variation.setText(f"({sign}{diff:.2f} | {sign}{(diff/past)*100:.2f}%)")
            self.lbl_variation.setStyleSheet(f"color: {color};")

        for key, value in data.items():
            if key in self.inputs:
                self.inputs[key].setText(DataFormatter.format_to_string(value))

        self.btn_fetch.setEnabled(True)
        self.statusBar().showMessage("Dati scaricati con successo.")

    def _on_fetch_error(self, error_msg: str) -> None:
        self.btn_fetch.setEnabled(True)
        QMessageBox.critical(self, "Errore Dati", error_msg)

    def _on_input_changed(self, *args) -> None:
        try:
            val_data = self.calculator.validate_inputs({k: e.text() for k, e in self.inputs.items()})
            results = self.calculator.calculate_metrics(val_data)
            self._display_results(results)
        except ValueError:
            self._reset_results()

    def _display_results(self, results: Dict[str, Union[float, str]]) -> None:
        ey, roic, ev_eb = results.get('ey'), results.get('roic'), results.get('ev_ebitda')

        def set_val(k: str, v: Union[float, str], suf: str):
            lbl = self.res_labels[k]
            if isinstance(v, float):
                lbl.setText(f"{v:.2f}{suf}"); lbl.setStyleSheet("color: #222f3e;")
            else:
                lbl.setText(str(v)); lbl.setStyleSheet("color: #e74c3c; font-size: 10px;")

        set_val('ey', ey, "%")
        set_val('roic', roic, "%")
        set_val('ev_ebitda', ev_eb, "x")

        if all(isinstance(x, float) for x in (ey, roic, ev_eb)):
            score, txt, color, details = self.evaluator.evaluate(float(ey), float(roic), float(ev_eb)) # type: ignore
            self.lbl_score.setText(f"{score} / 10")
            self.lbl_score.setStyleSheet(f"color: {color};")
            self.lbl_recommendation.setText(txt)
            self.lbl_recommendation.setStyleSheet(f"color: {color};")
            for k, detail in details.items():
                self.res_eval_labels[k].setText(detail['text'])
                self.res_eval_labels[k].setStyleSheet(f"color: {detail['color']};")
        else:
            self._reset_results()

    def _reset_results(self) -> None:
        for lbl in self.res_labels.values(): lbl.setText("--")
        for lbl in self.res_eval_labels.values(): lbl.setText("")
        self.lbl_score.setText("- / 10"); self.lbl_score.setStyleSheet("color: #7f8c8d;")
        self.lbl_recommendation.setText("Dati incompleti...")


def main() -> None:
    # Fondamentale per PyInstaller su Windows: impedisce la clonazione infinita dei processi in background
    multiprocessing.freeze_support()

    # Iniezione dell'Airbag Globale per intercettare i crash silenziosi
    sys.excepthook = global_exception_handler

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
