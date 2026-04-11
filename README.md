# 📈 QuantumValue Analysis

![Version](https://img.shields.io/badge/version-Dinamica-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)

**QuantumValue Analysis** è uno strumento desktop professionale, sviluppato interamente in Python, progettato per l'analisi fondamentale, la valutazione quantitativa delle azioni mondiali e lo screening degli ETF. 

Il software trae ispirazione dai rigorosi princìpi del *Value Investing* (in particolare la *Magic Formula* di Joel Greenblatt) combinando l'analisi strutturale aziendale con lo screening dei multipli di mercato, il tutto racchiuso in un'interfaccia utente moderna e reattiva.

---

## ✨ Funzionalità Principali

### 🔍 1. Scoring Algoritmico Value (Analisi Core)
Il motore interno valuta la qualità intrinseca dell'azienda assegnando un punteggio (da 1 a 10) e un rating semaforico basato su tre pilastri:
* **Earnings Yield (EY):** Misura il rendimento operativo rispetto al costo totale dell'azienda (*EBIT / Enterprise Value*).
* **Return on Invested Capital (ROIC):** Valuta l'efficienza e l'esistenza di un vantaggio competitivo (*NOPAT / Capitale Investito*).
* **EV/EBITDA:** Un indicatore di valutazione neutrale rispetto alla struttura del debito.

### 🎯 2. Caccia alle "Occasioni in Borsa"
Un modulo dedicato per capire se il mercato sta prezzando l'azienda a sconto. Analizza i principali multipli di mercato:
* **P/E (Price to Earnings):** Prezzo rispetto agli utili storici.
* **P/S (Price to Sales):** Prezzo rispetto al fatturato.
* **PEG Ratio:** Rapporto P/E pesato per la crescita futura attesa.
* **EV/EBITDA:** Valutazione complessiva del business.

### 📊 3. Valutazione Strumenti Passivi (ETF)
Analizza fondi passivi tramite scraping dedicato (`justetf_scraping`) o fallback su API finanziarie, valutando:
* **TER (Total Expense Ratio):** L'efficienza dei costi di gestione.
* **AUM (Assets Under Management):** La liquidità e il rischio di chiusura del fondo.
* **Rendimenti Storici (1Y / 3Y):** Per valutare la bontà del trend.

### 🛡️ 4. Architettura Dati Resiliente (Airbag System)
Nessun blocco se un provider fallisce. Il sistema tenta prima il recupero dati live tramite **Yahoo Finance**. In caso di dati mancanti (frequente sui listini europei come MIB30, DAX, CAC40), interviene un sistema di **Fallback automatico** che interroga le API di **Financial Modeling Prep (FMP)**.

### 🔄 5. Sistema OTA (Over-The-Air) e CI/CD
* **Auto-Update Integrato:** Il software interroga le API di GitHub all'avvio. Se trova una nuova release, mostra una notifica e scarica l'aggiornamento in background tramite una progress bar dedicata, auto-installandolo.
* **Pipeline GitHub Actions:** La compilazione (PyInstaller), la creazione del Setup (Inno Setup) e il rilascio della Release pubblica sono **100% automatizzati**. Basta aggiornare il file `version.txt` e fare push.

---

## 🏗️ Architettura del Software

Il codice è scritto aderendo rigorosamente agli standard **PEP 8**, alla tipizzazione forte (**Type Hints**) e implementando il pattern architetturale **MVC (Model-View-Controller)**:

* **`config.py`**: Costanti globali, mappature borse e lettura dinamica della versione tramite file iniettato.
* **`models.py` (Model)**: Contiene l'ingegneria finanziaria, le formule, le classi di scraping e la logica di valutazione. Nessuna dipendenza dalla GUI.
* **`controllers.py` (Controller)**: Gestisce l'asincronia. Implementa classi derivate da `QThread` (PyQt6) per demandare a thread in background i task pesanti (download dati, ricerca, aggiornamenti OTA), mantenendo la UI sempre fluida (nessun freeze).
* **`views.py` (View)**: Interfaccia utente costruita in PyQt6. Gestisce finestre, layout dinamici (QStackedWidget per lo switch Azioni/ETF), formattazione visiva e finestre di dialogo.
* **`main.py`**: Entry point che inizializza l'applicazione e imposta un *Global Exception Handler* per catturare e mostrare a schermo i crash critici (evitando chiusure silenziose).

---

## 💻 Installazione e Utilizzo

### Opzione A: Per Utenti (Installazione Rapida)
Non è necessaria alcuna conoscenza di programmazione.
1. Vai nella sezione [Releases](../../releases) di questo repository.
2. Scarica l'ultimo file eseguibile `QuantumValue_Analysis_Setup_vX.X.X.exe`.
3. Avvia l'installazione. Il programma si aggiornerà da solo in futuro.

### Opzione B: Per Sviluppatori (Esecuzione da Sorgente)
1. Clona il repository:
   ```bash
   git clone [https://github.com/enkas79/QuantumValue.git](https://github.com/enkas79/QuantumValue.git)
   cd QuantumValue
