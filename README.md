# QuantumValue Analysis 📈

**QuantumValue Analysis** è uno strumento professionale sviluppato in Python per l'analisi fondamentale e quantitativa delle azioni mondiali. Si basa sui rigorosi princìpi del *Value Investing* (ispirati alla Magic Formula di J. Greenblatt).

## 🚀 Caratteristiche Principali
* **Scoring Algoritmico:** Calcolo automatico e valutazione da 1 a 10 di metriche chiave come Earnings Yield (EY), ROIC e multiplo EV/EBITDA.
* **Architettura Resiliente:** Acquisizione dati in tempo reale tramite le API di `yfinance` con sistema di *Fallback automatico* su Financial Modeling Prep (FMP) per garantire la massima copertura anche sui mercati europei (MIB30, CAC40, DAX).
* **Interfaccia Grafica (GUI):** Sviluppata interamente in PyQt6 con pattern MVC (Model-View-Controller) per una rigorosa separazione delle responsabilità.
* **Auto-Update (OTA):** Sistema integrato che interroga le API di GitHub per notificare all'utente la disponibilità di nuove versioni.

## 🛠️ Requisiti di Sistema e Installazione
Se desideri eseguire il software dal codice sorgente, assicurati di avere Python 3.10+ installato.

1. Clona la repository:
   ```bash
   git clone [https://github.com/TuoNome/QuantumValueRepo.git](https://github.com/TuoNome/QuantumValueRepo.git)
