"""
Modulo View (Interfaccia Grafica PyQt6).

Contiene esclusivamente le finestre di dialogo e l'interfaccia principale
(MainWindow), delegando i calcoli ai Models e l'asincronia ai Controllers.

Autore: Enrico Martini
Versione: Dinamica (via config.py)
"""

import os
import sys
from typing import Optional, Dict, Union, Tuple, List, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QGroupBox, QGridLayout,
    QDialog, QTextBrowser, QDialogButtonBox, QTableWidget, QRadioButton,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QScrollArea, QTabWidget, QStackedWidget, QApplication
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices, QScreen, QIcon
from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl

# Importazioni corrette dei moduli interni funzionali
import utils
import models
from config import APP_NAME, VERSION, AUTHOR, GITHUB_REPO
from controllers import UpdateCheckWorker, SearchWorker, FetchWorker, EtfFetchWorker


class GuideDialog(QDialog):
    """Finestra di dialogo estesa per Azioni ed ETF."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guida Strategica: Valore, Occasioni ed ETF")
        self.setMinimumSize(800, 750)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        html_content: str = """
        <h1 style='color: #2c3e50;'>La Strategia dell'Analisi Fondamentale</h1>
        <p>Questa applicazione si basa sui principi del <i>Value Investing</i> per valutare la reale qualità e convenienza di un'azienda sul mercato, abbinandoli a un'analisi rapida delle <b>Occasioni in Borsa</b> e degli <b>ETF</b>.</p>
        <hr>

        <h2 style='color: #2980b9;'>Analisi Core: Qualità e Valore (Value Investing)</h2>
        <h3 style='color: #2980b9;'>1. Earnings Yield (EY) - Il "Re" del Valore</h3>
        <p>L'Earnings Yield è il reciproco del rapporto P/E ed è calcolato nella sua forma più robusta (utilizzata da Joel Greenblatt nella <i>Magic Formula</i>).</p>
        <ul>
            <li><b>Formula:</b> EBIT / Enterprise Value (EV)</li>
            <li><b>Perché funziona:</b> A differenza del semplice P/E, l'EV include il debito e sottrae la cassa, fornendo una visione reale di quanto "costa" l'intera azienda rispetto ai suoi utili operativi.</li>
            <li><b>Dati Statistici:</b> Strategie basate sull'acquisto del decile con il più alto Earnings Yield hanno storicamente sovraperformato l'S&P 500 con un <i>win rate</i> superiore al <b>65-70%</b> su orizzonti di 10 anni.</li>
        </ul>

        <h3 style='color: #2980b9;'>2. Return on Invested Capital (ROIC) - Il Proxy della Qualità</h3>
        <p>Il ROIC misura l'efficienza con cui un'azienda genera profitti dal capitale investito (sia debito che equity).</p>
        <ul>
            <li><b>Formula:</b> NOPAT / Capitale Investito</li>
            <li><b>Perché funziona:</b> Identifica le aziende con un "Moat" (fossato economico) elevato. Un ROIC costantemente superiore al costo del capitale (WACC) è il principale motore della creazione di valore a lungo termine.</li>
            <li><b>Dati Statistici:</b> L'integrazione del ROIC in una strategia "Magic Formula" (combinato con l'Earnings Yield) ha prodotto rendimenti medi annui del <b>26,4% nel periodo 1991-2024</b>, battendo il mercato in 23 anni su 34 (win rate del <b>67,6%</b>).</li>
        </ul>

        <h3 style='color: #2980b9;'>3. Enterprise Value to EBITDA (EV/EBITDA) - L'Indicatore di Resilienza</h3>
        <p>Questo multiplo è considerato molto più affidabile del Price-to-Book (P/B) o del P/E per confrontare aziende con diverse strutture di capitale.</p>
        <ul>
            <li><b>Perché funziona:</b> L'EBITDA è meno soggetto a manipolazioni contabili rispetto all'utile netto, e l'EV neutralizza le differenze di leva finanziaria tra le aziende.</li>
            <li><b>Dati Statistici:</b> Studi di <i>O'Shaughnessy Asset Management</i> indicano che l'EV/EBITDA ha un "quintile spread" (la differenza di rendimento tra i titoli più economici e quelli più costosi) del <b>6,0%</b>, superando significativamente il 2,8% del P/B e il 5,1% del P/E.</li>
        </ul>
        <hr>

        <h2 style='color: #27ae60;'>Come trovare Occasioni in Borsa (I 4 Indicatori Rapidi)</h2>
        <p>Questa sezione si concentra sui multipli di mercato essenziali per capire se si sta pagando il giusto prezzo in rapporto alla crescita e ai ricavi:</p>
        <ul>
            <li><b>P/E (Price/Earnings):</b> Indica quanto stai pagando per ogni euro di utile. <b>Ideale se P/E < 20</b>. Buon prezzo rispetto agli utili.</li>
            <li><b>P/S (Price/Sales):</b> Misura quanto il mercato paga un'azienda rispetto ai suoi ricavi. <b>Ideale se P/S < 2</b>. Buon prezzo rispetto ai ricavi.</li>
            <li><b>PEG (Price/Earnings to Growth):</b> Indica quanto stai pagando per ogni euro di utile, considerando anche il tasso di crescita atteso. <b>Ideale se PEG < 1</b>. Buon prezzo rispetto alla crescita degli utili.</li>
            <li><b>EV/EBITDA:</b> Indica quanto stai pagando per l'intero business, debiti inclusi. <b>Ideale se EV/EBITDA < 10</b>. Buon prezzo rispetto ai flussi operativi.</li>
        </ul>
        <hr>

        <h2 style='color: #8e44ad;'>Valutazione ETF (Exchange Traded Funds)</h2>
        <p>Gli ETF sono strumenti passivi. La loro valutazione si basa sull'efficienza dei costi, la liquidità e il tracking dell'indice:</p>
        <ul>
            <li><b>TER (Total Expense Ratio):</b> Misura i costi annuali di gestione. <b>Ideale se < 0.25%</b>. Costi bassi massimizzano l'interesse composto nel lungo termine.</li>
            <li><b>AUM (Dimensione del Fondo):</b> Misura il capitale totale gestito (in Milioni). <b>Ideale se > 500M</b>. Fondi più grandi sono più liquidi e hanno un rischio minore di chiusura o delisting.</li>
            <li><b>Rendimento (Performance 1Y/3Y):</b> Valuta la bontà del trend. Rendimenti positivi e costanti indicano un asset in salute.</li>
        </ul>
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
        self.results: List[Tuple[str, str, str]] = results
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
        selected_row: int = self.table.currentRow()
        if selected_row >= 0:
            item = self.table.item(selected_row, 0)
            if item: self.selected_ticker = item.text()
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
    """
    Finestra Principale dell'applicazione (View).
    Completamente disaccoppiata dalle classi contenitore artificiali legacy,
    interagisce in modo thread-safe e pulito con le funzioni pure dei moduli.
    """

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(AUTHOR.replace(" ", ""), APP_NAME.replace(" ", ""))
        self.fmp_api_key: str = str(self.settings.value("fmp_api_key", ""))

        self.fetcher = models.FinancialDataFetcher(self.fmp_api_key)

        self.fetch_worker: Optional[FetchWorker] = None
        self.search_worker: Optional[SearchWorker] = None
        self.update_worker: Optional[UpdateCheckWorker] = None
        self.etf_worker: Optional[EtfFetchWorker] = None

        self.currency_symbol: str = ""
        self.inputs: Dict[str, QLineEdit] = {}
        self.etf_inputs: Dict[str, QLineEdit] = {}

        self._init_ui()
        QTimer.singleShot(200, self._check_first_run_setup)
        QTimer.singleShot(1000, lambda: self._check_for_updates(silent=True))

    def _check_first_run_setup(self) -> None:
        asked: bool = self.settings.value("fmp_asked_once", False, type=bool)
        if not asked and not self.fmp_api_key:
            dialog = FmpSetupDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.api_key:
                self.fmp_api_key = dialog.api_key
                self.settings.setValue("fmp_api_key", self.fmp_api_key)
                self.fetcher.fmp_api_key = self.fmp_api_key
                self.statusBar().showMessage("API Key FMP configurata. Resilienza dati attivata.")
            self.settings.setValue("fmp_asked_once", True)

    def _center_and_lock_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            w = max(800, min(int(screen_geom.width() * 0.6), 1100))
            h = max(780, min(int(screen_geom.height() * 0.72), 920))
            self.setFixedSize(w, h)
            self.move((screen_geom.width() - w) // 2, (screen_geom.height() - h) // 2)

    def _init_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath(".")
        icon_path = os.path.join(base_path, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._center_and_lock_window()
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QGroupBox { font-weight: bold; border: 1px solid #c8d6e5; border-radius: 6px; margin-top: 10px; background-color: white; }
            QLineEdit { border: 1px solid #c8d6e5; border-radius: 4px; padding: 5px; }
            QPushButton { font-weight: bold; border-radius: 4px; }
            QTabWidget::pane { border: 1px solid #c8d6e5; background: white; border-radius: 6px; }
            QTabBar::tab { background: #e0e6ed; padding: 10px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;}
            QTabBar::tab:selected { background: white; color: #2980b9; border-bottom: 2px solid white; }
        """)

        self._create_menu_bar()
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        title_label = QLabel(APP_NAME)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        self._create_search_section(main_layout)
        self.stacked_inputs = QStackedWidget()

        self.page_azioni = QWidget()
        self._create_input_section_azioni(self.page_azioni)
        self.stacked_inputs.addWidget(self.page_azioni)

        self.page_etf = QWidget()
        self._create_input_section_etf(self.page_etf)
        self.stacked_inputs.addWidget(self.page_etf)
        main_layout.addWidget(self.stacked_inputs)

        self.tabs = QTabWidget()
        self.tab_value = QWidget()
        self.tab_opp = QWidget()
        self.tab_etf = QWidget()

        self.tabs.addTab(self.tab_value, "Analisi Strutturale Value")
        self.tabs.addTab(self.tab_opp, "Occasioni in Borsa")
        self.tabs.addTab(self.tab_etf, "Valutazione ETF")

        self._setup_tab_value(self.tab_value)
        self._setup_tab_opportunity(self.tab_opp)
        self._setup_tab_etf(self.tab_etf)
        main_layout.addWidget(self.tabs, stretch=1)

        self._toggle_asset_mode()

        exit_layout = QHBoxLayout()
        self.btn_exit = QPushButton("Esci dal Programma")
        self.btn_exit.setFixedWidth(200)
        self.btn_exit.setMinimumHeight(40)
        self.btn_exit.setStyleSheet("background-color: #e66767; color: white; padding: 10px; margin-top: 10px;")
        self.btn_exit.clicked.connect(self.close)
        exit_layout.addStretch()
        exit_layout.addWidget(self.btn_exit)
        exit_layout.addStretch()
        main_layout.addLayout(exit_layout)

        self.statusBar().showMessage("Pronto. Scrivi il Ticker, ISIN o Nome Azienda e premi Invio.")

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        reset_api_action = QAction("&Reimposta API FMP", self)
        reset_api_action.triggered.connect(self._reset_api_key)
        file_menu.addAction(reset_api_action)
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Esci", self, triggered=self.close))

        help_menu = menu_bar.addMenu("&?")
        help_menu.addAction(
            QAction("&Verifica Aggiornamenti", self, triggered=lambda: self._check_for_updates(silent=False)))
        help_menu.addSeparator()
        help_menu.addAction(QAction("&Guida Metriche", self, triggered=lambda: GuideDialog(self).exec()))
        help_menu.addSeparator()
        help_menu.addAction(QAction("&Info", self, triggered=lambda: InfoDialog(self).exec()))

    def _reset_api_key(self) -> None:
        self.settings.remove("fmp_api_key")
        self.settings.setValue("fmp_asked_once", False)
        self.fmp_api_key = ""
        self.fetcher.fmp_api_key = ""
        QMessageBox.information(self, "API Resettata",
                                "Impostazioni ripristinate. Al riavvio verrà richiesta la chiave.")

    def _check_for_updates(self, silent: bool = True) -> None:
        if not silent:
            self.statusBar().showMessage("Ricerca aggiornamenti su GitHub...")
        self.update_worker = UpdateCheckWorker(VERSION, GITHUB_REPO, parent=self)
        self.update_worker.finished.connect(lambda u, v, url: self._on_update_checked(u, v, url, silent))
        self.update_worker.error.connect(lambda e: self._on_update_error(e, silent))
        self.update_worker.start()

    def _on_update_checked(self, update_available: bool, new_version: str, download_url: str, silent: bool) -> None:
        if update_available:
            self.statusBar().showMessage(f"Nuovo aggiornamento disponibile: v{new_version}")
            reply = QMessageBox.question(
                self, "Aggiornamento Disponibile",
                f"È disponibile la versione <b>v{new_version}</b>.<br><br>Vuoi andare alla pagina di download?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl("https://mindnetwork.vip/download.php"))
        elif not silent:
            QMessageBox.information(self, "Nessun Aggiornamento", "Stai già utilizzando la versione più recente.")
            self.statusBar().showMessage("Software aggiornato.")

    def _on_update_error(self, error_msg: str, silent: bool) -> None:
        if not silent:
            QMessageBox.warning(self, "Errore Aggiornamento", error_msg)
        self.statusBar().showMessage("Pronto.")

    def _create_search_section(self, layout: QVBoxLayout) -> None:
        search_group = QGroupBox("1. Ricerca (Azienda o ETF)")
        search_layout = QHBoxLayout(search_group)
        self.rb_azione = QRadioButton("Azioni")
        self.rb_azione.setChecked(True)
        self.rb_etf = QRadioButton("ETF")
        self.rb_azione.toggled.connect(self._toggle_asset_mode)

        search_layout.addWidget(self.rb_azione)
        search_layout.addWidget(self.rb_etf)
        search_layout.addSpacing(15)

        self.input_ticker = QLineEdit()
        self.input_ticker.setPlaceholderText("Es. AAPL (Azione) oppure IE00B4L5Y983 (ETF)...")
        self.input_ticker.setMaximumWidth(320)
        self.input_ticker.textChanged.connect(self._force_uppercase_ticker)
        self.input_ticker.returnPressed.connect(self._on_search_requested)
        search_layout.addWidget(self.input_ticker)

        self.btn_fetch = QPushButton(" Cerca/Scarica Dati")
        self.btn_fetch.setMaximumWidth(160)
        self.btn_fetch.setStyleSheet("background-color: #2e86de; color: white; padding: 5px 15px;")
        self.btn_fetch.clicked.connect(self._on_search_requested)
        search_layout.addWidget(self.btn_fetch)
        search_layout.addStretch()
        layout.addWidget(search_group)

    def _toggle_asset_mode(self) -> None:
        is_azione = self.rb_azione.isChecked()
        if is_azione:
            self.stacked_inputs.setCurrentWidget(self.page_azioni)
            self.tabs.setTabVisible(0, True)
            self.tabs.setTabVisible(1, True)
            self.tabs.setTabVisible(2, False)
            self.tabs.setCurrentIndex(0)
        else:
            self.stacked_inputs.setCurrentWidget(self.page_etf)
            self.tabs.setTabVisible(0, False)
            self.tabs.setTabVisible(1, False)
            self.tabs.setTabVisible(2, True)
            self.tabs.setCurrentIndex(2)

    def _force_uppercase_ticker(self, text: str) -> None:
        if not text.isupper() and text != "":
            cursor_pos: int = self.input_ticker.cursorPosition()
            self.input_ticker.blockSignals(True)
            self.input_ticker.setText(text.upper())
            self.input_ticker.blockSignals(False)
            self.input_ticker.setCursorPosition(cursor_pos)

    def _create_input_section_azioni(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        input_group = QGroupBox("2. Dati Finanziari Aziendali & Quotazione")
        grid_layout = QGridLayout(input_group)

        self.lbl_company_name = QLabel("Azienda: --")
        self.lbl_company_name.setStyleSheet("color: #2980b9; font-weight: bold; font-size: 14px;")
        grid_layout.addWidget(self.lbl_company_name, 0, 0, 1, 5)

        price_layout = QHBoxLayout()
        self.lbl_price = QLabel("Prezzo: --")
        self.lbl_price.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))

        var_layout = QHBoxLayout()
        var_layout.setSpacing(15)
        self.lbl_var_1d, self.lbl_var_1w, self.lbl_var_1m, self.lbl_var_1y = QLabel("--"), QLabel("--"), QLabel(
            "--"), QLabel("--")

        for lbl_title, lbl_val in [("1D:", self.lbl_var_1d), ("1W:", self.lbl_var_1w), ("1M:", self.lbl_var_1m),
                                   ("1Y:", self.lbl_var_1y)]:
            var_sublayout = QHBoxLayout()
            var_sublayout.addWidget(QLabel(f"<b>{lbl_title}</b>"))
            var_sublayout.addWidget(lbl_val)
            var_layout.addLayout(var_sublayout)

        price_layout.addWidget(self.lbl_price)
        price_layout.addSpacing(25)
        price_layout.addLayout(var_layout)
        price_layout.addStretch()
        grid_layout.addLayout(price_layout, 1, 0, 1, 5)

        grid_layout.setColumnStretch(4, 1)
        grid_layout.setHorizontalSpacing(30)

        fields = [
            ('ebit', 'EBIT:', 2, 0), ('ev', 'EV:', 2, 2),
            ('nopat', 'NOPAT:', 3, 0), ('invested_capital', 'Cap. Investito:', 3, 2),
            ('ebitda', 'EBITDA:', 4, 0), ('pe', 'P/E Ratio:', 4, 2),
            ('ps', 'P/S Ratio:', 5, 0), ('peg', 'PEG Ratio:', 5, 2)
        ]

        for key, text, row, col in fields:
            le = QLineEdit()
            le.setMaximumWidth(160)
            le.textChanged.connect(self._on_input_changed)
            grid_layout.addWidget(QLabel(text), row, col)
            grid_layout.addWidget(le, row, col + 1)
            self.inputs[key] = le

        layout.addWidget(input_group)

    def _create_input_section_etf(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        input_group = QGroupBox("2. Profilo ETF & Composizione")
        grid_layout = QGridLayout(input_group)

        self.lbl_etf_name = QLabel("Fondo/ETF: --")
        self.lbl_etf_name.setStyleSheet("color: #8e44ad; font-weight: bold; font-size: 14px;")
        grid_layout.addWidget(self.lbl_etf_name, 0, 0, 1, 5)

        self.lbl_etf_repl = QLabel("Replicazione: --")
        self.lbl_etf_repl.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        grid_layout.addWidget(self.lbl_etf_repl, 1, 0, 1, 5)

        grid_layout.setColumnStretch(4, 1)
        grid_layout.setHorizontalSpacing(30)

        fields = [
            ('ter', 'TER (%):', 2, 0), ('aum', 'AUM (Milioni):', 2, 2),
            ('ret_1y', 'Rendimento 1Y (%):', 3, 0), ('ret_3y', 'Rendimento 3Y (%):', 3, 2),
        ]

        for key, text, row, col in fields:
            le = QLineEdit()
            le.setMaximumWidth(160)
            le.textChanged.connect(self._on_etf_input_changed)
            grid_layout.addWidget(QLabel(text), row, col)
            grid_layout.addWidget(le, row, col + 1)
            self.etf_inputs[key] = le

        layout.addWidget(input_group)

    def _setup_tab_value(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        metrics_group = QGroupBox("Metriche Analizzate")
        inner_layout = QVBoxLayout(metrics_group)
        self.res_labels: Dict[str, QLabel] = {}
        self.res_eval_labels: Dict[str, QLabel] = {}

        for key, title in [('ey', 'Earnings Yield:'), ('roic', 'ROIC:'), ('ev_ebitda', 'EV/EBITDA:')]:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(title))
            lbl_val = QLabel("--")
            lbl_val.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            row_layout.addWidget(lbl_val)
            row_layout.addStretch()
            lbl_eval = QLabel("")
            lbl_eval.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_layout.addWidget(lbl_eval)
            self.res_labels[key] = lbl_val
            self.res_eval_labels[key] = lbl_eval
            inner_layout.addLayout(row_layout)

        layout.addWidget(metrics_group)
        eval_group = QGroupBox("Verdetto Qualità Aziendale")
        eval_layout = QVBoxLayout(eval_group)
        self.lbl_score = QLabel("- / 10")
        self.lbl_score.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_recommendation = QLabel("In attesa di dati...")
        self.lbl_recommendation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eval_layout.addSpacing(10)
        eval_layout.addWidget(self.lbl_score)
        eval_layout.addWidget(self.lbl_recommendation)
        layout.addWidget(eval_group)
        layout.addStretch()

    def _setup_tab_opportunity(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        opp_group = QGroupBox("Valutazione Multipli di Mercato")
        inner_layout = QVBoxLayout(opp_group)
        self.opp_labels: Dict[str, QLabel] = {}
        self.opp_eval_labels: Dict[str, QLabel] = {}

        metrics = [('pe', 'P/E (Prezzo/Utile):'), ('ps', 'P/S (Prezzo/Ricavi):'),
                   ('peg', 'PEG (P/E to Growth):'), ('ev_ebitda_occ', 'EV/EBITDA:')]
        for key, title in metrics:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(title))
            lbl_val = QLabel("--")
            lbl_val.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            row_layout.addWidget(lbl_val)
            row_layout.addStretch()
            lbl_eval = QLabel("")
            lbl_eval.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_layout.addWidget(lbl_eval)
            self.opp_labels[key] = lbl_val
            self.opp_eval_labels[key] = lbl_eval
            inner_layout.addLayout(row_layout)

        layout.addWidget(opp_group)
        eval_opp_group = QGroupBox("Verdetto Occasione in Borsa")
        eval_opp_layout = QVBoxLayout(eval_opp_group)
        self.lbl_opp_score = QLabel("- / 10")
        self.lbl_opp_score.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_opp_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_opp_recommendation = QLabel("In attesa di dati...")
        self.lbl_opp_recommendation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eval_opp_layout.addSpacing(10)
        eval_opp_layout.addWidget(self.lbl_opp_score)
        eval_opp_layout.addWidget(self.lbl_opp_recommendation)
        layout.addWidget(eval_opp_group)
        layout.addStretch()

    def _setup_tab_etf(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        etf_group = QGroupBox("Analisi Profilo ETF")
        inner_layout = QVBoxLayout(etf_group)
        self.etf_res_labels: Dict[str, QLabel] = {}
        self.etf_eval_labels: Dict[str, QLabel] = {}

        for key, title in [('ter', 'Costi TER:'), ('aum', 'Asset Gestiti (AUM):'), ('ret_1y', 'Rendimento Anno:')]:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(title))
            lbl_val = QLabel("--")
            lbl_val.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            row_layout.addWidget(lbl_val)
            row_layout.addStretch()
            lbl_eval = QLabel("")
            lbl_eval.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_layout.addWidget(lbl_eval)
            self.etf_res_labels[key] = lbl_val
            self.etf_eval_labels[key] = lbl_eval
            inner_layout.addLayout(row_layout)

        layout.addWidget(etf_group)
        eval_etf_group = QGroupBox("Giudizio Strumento Passivo")
        eval_etf_layout = QVBoxLayout(eval_etf_group)
        self.lbl_etf_score = QLabel("- / 10")
        self.lbl_etf_score.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.lbl_etf_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_etf_recommendation = QLabel("In attesa di dati...")
        self.lbl_etf_recommendation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eval_etf_layout.addSpacing(10)
        eval_etf_layout.addWidget(self.lbl_etf_score)
        eval_etf_layout.addWidget(self.lbl_etf_recommendation)
        layout.addWidget(eval_etf_group)
        layout.addStretch()

    def _on_search_requested(self) -> None:
        """Handler protetto contro chiamate concorrenti asincrone multiple."""
        query: str = self.input_ticker.text().strip()
        if not query:
            QMessageBox.warning(self, "Attenzione", "Inserire un Ticker, ISIN o Nome valido.")
            return

        if (self.search_worker and self.search_worker.isRunning()) or (self.etf_worker and self.etf_worker.isRunning()):
            self.statusBar().showMessage("Un'operazione è già in corso. Attendere il completamento...")
            return

        self.btn_fetch.setEnabled(False)
        self.statusBar().showMessage(f"Ricerca dati per '{query}' in corso...")

        if self.rb_azione.isChecked():
            self.lbl_price.setText("Prezzo: --")
            for lbl in (self.lbl_var_1d, self.lbl_var_1w, self.lbl_var_1m, self.lbl_var_1y):
                lbl.setText("--")

            self.search_worker = SearchWorker(query, parent=self)
            self.search_worker.finished.connect(self._on_search_success)
            self.search_worker.error.connect(self._on_search_error)
            self.search_worker.start()
        else:
            self.lbl_etf_name.setText("Fondo/ETF: --")
            self.etf_worker = EtfFetchWorker(query, parent=self)
            self.etf_worker.finished.connect(self._on_etf_fetch_success)
            self.etf_worker.error.connect(self._on_etf_fetch_error)
            self.etf_worker.start()

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
        QMessageBox.critical(self, "Errore Ricerca", error_msg)

    def _start_data_fetch(self, ticker: str) -> None:
        if self.fetch_worker and self.fetch_worker.isRunning():
            return
        self.btn_fetch.setEnabled(False)
        self.statusBar().showMessage(f"Download dati per {ticker} in corso...")

        self.fetch_worker = FetchWorker(self.fetcher, ticker, parent=self)
        self.fetch_worker.finished.connect(self._on_fetch_success)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.start()

    def _on_fetch_success(self, data: Dict[str, Any]) -> None:
        self.lbl_company_name.setText(f"Azienda: {data.pop('company_name', 'N/A')}")
        self.currency_symbol = data.pop('currency', '$')

        prices: Dict[str, float] = data.pop('prices', {})
        curr: float = prices.get('current', 0.0)
        self.lbl_price.setText(f"Prezzo: {curr:.2f} {self.currency_symbol}")

        def set_variation_label(lbl: QLabel, current: float, past: float) -> None:
            if past > 0 and past != current:
                diff: float = current - past
                pct: float = (diff / past) * 100
                color: str = "#27ae60" if diff >= 0 else "#c0392b"
                sign: str = "+" if diff >= 0 else ""
                lbl.setText(f"({sign}{pct:.2f}%)")
                lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
            else:
                lbl.setText("--")
                lbl.setStyleSheet("color: #7f8c8d;")

        set_variation_label(self.lbl_var_1d, curr, prices.get('1d', curr))
        set_variation_label(self.lbl_var_1w, curr, prices.get('1w', curr))
        set_variation_label(self.lbl_var_1m, curr, prices.get('1m', curr))
        set_variation_label(self.lbl_var_1y, curr, prices.get('1y', curr))

        for le in self.inputs.values(): le.blockSignals(True)
        for key, value in data.items():
            if key in self.inputs and isinstance(value, float):
                self.inputs[key].setText(utils.format_to_string(value))
        for le in self.inputs.values(): le.blockSignals(False)

        self._on_input_changed()
        self.btn_fetch.setEnabled(True)
        self.statusBar().showMessage("Dati scaricati e processati con successo.")

    def _on_fetch_error(self, error_msg: str) -> None:
        self.btn_fetch.setEnabled(True)
        self.statusBar().showMessage("Errore durante il download.")
        QMessageBox.critical(self, "Errore Dati", error_msg)

    def _on_input_changed(self, *args: Any) -> None:
        try:
            val_data: Dict[str, float] = {}
            for k, e in self.inputs.items():
                val_data[k] = utils.parse_to_float(e.text())

            results_core = models.calculate_metrics(val_data)
            self._display_results(results_core, val_data)
        except ValueError:
            self._reset_results()

    def _display_results(self, results_core: Dict[str, Union[float, str]], raw_data: Dict[str, float]) -> None:
        ey, roic, ev_eb = results_core.get('ey', 0.0), results_core.get('roic', 0.0), results_core.get('ev_ebitda', 0.0)
        pe, ps, peg = raw_data.get('pe', 0.0), raw_data.get('ps', 0.0), raw_data.get('peg', 0.0)

        def set_val_core(k: str, v: Union[float, str], suf: str) -> None:
            lbl = self.res_labels[k]
            if isinstance(v, (int, float)):
                lbl.setText(f"{v:.2f}{suf}")
                lbl.setStyleSheet("color: #222f3e;")
            else:
                lbl.setText(str(v))
                lbl.setStyleSheet("color: #e74c3c; font-size: 11px;")

        set_val_core('ey', ey, "%")
        set_val_core('roic', roic, "%")
        set_val_core('ev_ebitda', ev_eb, "x")

        def set_val_opp(k: str, v: float, suf: str) -> None:
            lbl = self.opp_labels[k]
            if v > 0:
                lbl.setText(f"{v:.2f}{suf}")
                lbl.setStyleSheet("color: #222f3e;")
            else:
                lbl.setText("N.D.")
                lbl.setStyleSheet("color: #e74c3c; font-size: 11px;")

        set_val_opp('pe', pe, "x")
        set_val_opp('ps', ps, "x")
        set_val_opp('peg', peg, "x")

        lbl_ev_occ = self.opp_labels['ev_ebitda_occ']
        if isinstance(ev_eb, (int, float)):
            lbl_ev_occ.setText(f"{ev_eb:.2f}x")
            lbl_ev_occ.setStyleSheet("color: #222f3e;")
        else:
            lbl_ev_occ.setText("N.D.")
            lbl_ev_occ.setStyleSheet("color: #e74c3c; font-size: 11px;")

        score, txt, color, details = models.evaluate_core(ey, roic, ev_eb)
        self.lbl_score.setText(f"{score} / 10")
        self.lbl_score.setStyleSheet(f"color: {color};")
        self.lbl_recommendation.setText(txt)
        self.lbl_recommendation.setStyleSheet(f"color: {color}; font-weight: bold;")

        for k in ['ey', 'roic', 'ev_ebitda']:
            if k in details:
                self.res_eval_labels[k].setText(details[k]['text'])
                self.res_eval_labels[k].setStyleSheet(f"color: {details[k]['color']};")

        opp_score, opp_txt, opp_color, opp_evals = models.evaluate_opportunity(pe, ps, peg, ev_eb)
        self.lbl_opp_score.setText(f"{opp_score} / 10")
        self.lbl_opp_score.setStyleSheet(f"color: {opp_color};")
        self.lbl_opp_recommendation.setText(opp_txt)
        self.lbl_opp_recommendation.setStyleSheet(f"color: {opp_color}; font-weight: bold;")

        for k in ['pe', 'ps', 'peg', 'ev_ebitda_occ']:
            if k in opp_evals:
                self.opp_eval_labels[k].setText(opp_evals[k]['text'])
                self.opp_eval_labels[k].setStyleSheet(f"color: {opp_evals[k]['color']};")

    def _on_etf_fetch_success(self, data: Dict[str, Any]) -> None:
        self.lbl_etf_name.setText(f"Fondo/ETF: {data.pop('company_name', 'N/A')}")
        self.lbl_etf_repl.setText(f"Replicazione: {data.pop('replication', 'N/A')}")
        self.currency_symbol = data.pop('currency', 'EUR')

        for le in self.etf_inputs.values(): le.blockSignals(True)
        for key, value in data.items():
            if key in self.etf_inputs and isinstance(value, float):
                if key == 'aum':
                    self.etf_inputs[key].setText(f"{value:.2f}")
                else:
                    self.etf_inputs[key].setText(utils.format_to_string(value))
        for le in self.etf_inputs.values(): le.blockSignals(False)

        self._on_etf_input_changed()
        self.btn_fetch.setEnabled(True)
        self.statusBar().showMessage("Dati ETF estratti con successo.")

    def _on_etf_fetch_error(self, error_msg: str) -> None:
        self.btn_fetch.setEnabled(True)
        self.statusBar().showMessage("Errore nel recupero dati ETF.")
        QMessageBox.critical(self, "Errore ETF", error_msg)

    def _on_etf_input_changed(self, *args: Any) -> None:
        try:
            val_data: Dict[str, float] = {}
            for k, e in self.etf_inputs.items():
                val_data[k] = utils.parse_to_float(e.text())
            self._display_etf_results(val_data)
        except ValueError:
            self._reset_etf_results()

    def _display_etf_results(self, val_data: Dict[str, float]) -> None:
        ter, aum, ret_1y = val_data.get('ter', 0.0), val_data.get('aum', 0.0), val_data.get('ret_1y', 0.0)

        self.etf_res_labels['ter'].setText(f"{ter:.2f}%")
        self.etf_res_labels['aum'].setText(f"{aum:.2f}M")
        self.etf_res_labels['ret_1y'].setText(f"{ret_1y:.2f}%")

        score, txt, color, details = models.evaluate_etf(ter, aum, ret_1y)
        self.lbl_etf_score.setText(f"{score} / 10")
        self.lbl_etf_score.setStyleSheet(f"color: {color};")
        self.lbl_etf_recommendation.setText(txt)
        self.lbl_etf_recommendation.setStyleSheet(f"color: {color}; font-weight: bold;")

        for k in ['ter', 'aum', 'ret_1y']:
            if k in details:
                self.etf_eval_labels[k].setText(details[k]['text'])
                self.etf_eval_labels[k].setStyleSheet(f"color: {details[k]['color']};")

    def _reset_results(self) -> None:
        for lbl in self.res_labels.values(): lbl.setText("--")
        for lbl in self.res_eval_labels.values(): lbl.setText("")
        for lbl in self.opp_labels.values(): lbl.setText("--")
        for lbl in self.opp_eval_labels.values(): lbl.setText("")
        self.lbl_score.setText("- / 10")
        self.lbl_score.setStyleSheet("color: #7f8c8d;")
        self.lbl_recommendation.setText("Dati incompleti o errati.")
        self.lbl_recommendation.setStyleSheet("color: #7f8c8d;")
        self.lbl_opp_score.setText("- / 10")
        self.lbl_opp_score.setStyleSheet("color: #7f8c8d;")
        self.lbl_opp_recommendation.setText("Dati incompleti o errati.")
        self.lbl_opp_recommendation.setStyleSheet("color: #7f8c8d;")

    def _reset_etf_results(self) -> None:
        for lbl in self.etf_res_labels.values(): lbl.setText("--")
        for lbl in self.etf_eval_labels.values(): lbl.setText("")
        self.lbl_etf_score.setText("- / 10")
        self.lbl_etf_score.setStyleSheet("color: #7f8c8d;")
        self.lbl_etf_recommendation.setText("Dati incompleti o errati.")
        self.lbl_etf_recommendation.setStyleSheet("color: #7f8c8d;")