# Analisi del Codice e Proposte di Ottimizzazione

Analisi della codebase di **QuantumValue Analysis** (architettura MVC: `config.py`, `models.py`, `controllers.py`, `views.py`, `utils.py`, `cache.py`). Di seguito i problemi individuati, in ordine di priorità, con riferimento a file e riga.

## 🔴 Bug critico

### 1. `NameError` non gestito nel fallback dati (`src/models.py:432`)
`FinancialDataFetcher.fetch_data` usa `logging.getLogger("QuantumValue")` quando Yahoo Finance fallisce, ma **il modulo `logging` non è mai importato in `models.py`** (in testa al file ci sono solo `sys`, `os`, `json` più gli import condizionali di `yfinance`/`httpx`).

Conseguenza: quando Yahoo Finance fallisce (caso frequente per i listini europei, come indicato nel README), invece di attivare il fallback su FMP/dati statici, il codice solleva un `NameError` non gestito **dentro il blocco `except`**, mascherando l'errore originale e rompendo l'intero "Airbag System" descritto come feature principale.

**Fix**: aggiungere `import logging` in cima a `src/models.py`.

## 🟠 Ottimizzazioni di robustezza e performance

### 2. Il retry con backoff non viene mai applicato
`src/models.py:43-48` definisce il decoratore `_retry_request` basato su `tenacity` (dipendenza dichiarata in `pyproject.toml`/`requirements.txt`), ma **non è usato da nessuna funzione**: né `_fetch_from_yahoo`, né `_fetch_from_fmp`, né `search_by_name`, né `check_for_updates`. Il risultato è che un singolo timeout di rete transitorio fa fallire subito la chiamata invece di ritentare, aumentando inutilmente la frequenza con cui scatta il fallback (o l'errore mostrato all'utente).

**Proposta**: applicare `@_retry_request` alle funzioni che eseguono chiamate HTTP dirette.

### 3. Cache SQLite scritta in una cartella temporanea quando l'app è pacchettizzata
`src/config.py:81` calcola `CACHE_DB_PATH` a partire da `_get_base_path()`, che con PyInstaller (`sys._MEIPASS`) punta a una cartella temporanea **ricreata e ripulita a ogni avvio dell'eseguibile**. Nella build distribuita (quella descritta nel README come normale modalità d'uso per gli utenti finali), la cache SQLite pensata per ridurre le chiamate ai provider **non persiste mai tra un avvio e l'altro**, vanificando l'ottimizzazione. `src/utils.py:40-41` risolve correttamente lo stesso problema per i log usando `~/.quantumvalue`; la cache dovrebbe seguire lo stesso pattern (es. `~/.quantumvalue/cache/quantumvalue_cache.db`).

### 4. Nuova connessione SQLite ad ogni operazione di cache
`get_cached`, `set_cached` e `_remove_cached` in `src/cache.py` aprono e chiudono una connessione SQLite ad ogni singola chiamata (righe 62-66, 98-107, 126-129). Durante uno screening con più ticker in sequenza questo introduce overhead I/O evitabile. Una connessione a livello di modulo (riutilizzabile grazie a `check_same_thread=False`, già impostato) ridurrebbe il costo per ogni lettura/scrittura.

### 5. Chiamate FMP sequenziali senza riuso della connessione
`_fetch_from_fmp` (`src/models.py:560-648`) esegue **4 richieste HTTP separate** (`profile`, `key-metrics-ttm`, `ratios-ttm`, `income-statement`), ciascuna con un `requests.get` indipendente invece di una `requests.Session()` condivisa. Questo path si attiva proprio quando Yahoo è già lento o ha fallito, quindi la latenza aggiuntiva (niente keep-alive TCP/TLS) pesa doppio sull'esperienza utente. Usare una sessione condivisa (o, se si vuole vera parallelizzazione, `httpx` già disponibile come dipendenza) ridurrebbe sensibilmente i tempi.

## 🟡 Pulizia del codice

### 6. Import duplicati/morti in `src/main.py`
Alle righe 23-24 il file fa `import utils` e `from views import MainWindow` (import "assoluti" resi possibili dalla manipolazione di `sys.path` alla riga 20), ma poco dopo, righe 46-47, fa `from . import utils` e `from . import views` (import relativi di pacchetto). I secondi sovrascrivono i nomi dei primi nel namespace del modulo, quindi le prime due righe **caricano comunque due copie indipendenti** di `utils` e `views` (una come modulo top-level, una come `src.utils`/`src.views`) senza che vengano più usate: tempo di avvio sprecato e rischio di stato duplicato (es. due logger). Vanno rimosse le righe 23-24.

### 7. Offuscamento (non cifratura reale) della API key FMP
`encrypt_api_key`/`decrypt_api_key` (`src/utils.py:163-212`) derivano la chiave Fernet da `AUTHOR + salt`, entrambi valori statici presenti nel sorgente pubblico del repository. Chiunque legga il codice open source può decifrare qualsiasi API key salvata con questo schema: non è sicurezza, è solo offuscamento contro una lettura casuale del file di config. Se questo è l'intento va bene, ma andrebbe documentato esplicitamente nel commento; se serve vera protezione, la chiave dovrebbe derivare da un segreto locale alla macchina (es. tramite il portachiavi di sistema, libreria `keyring`).

### 8. Ridondanza minore
`src/utils.py:210`: `except (ImportError, Exception):` — `Exception` copre già `ImportError`, la tupla può essere semplificata in `except Exception:`.

## 🔵 Copertura test

`tests/test_models.py` copre bene le funzioni pure di scoring (`calculate_metrics`, `evaluate_core`, `evaluate_opportunity`, `evaluate_etf`), ma:
- `src/cache.py` non ha test, nonostante sia logica pura testabile senza rete (get/set/scadenza/clear).
- `src/utils.py` (`parse_to_float`, `format_to_string`) non ha test, nonostante siano funzioni pure.
- `src/controllers.py` e `src/views.py` non hanno copertura (comprensibile per la GUI, ma i worker QThread potrebbero essere testati mockando `models`).

## Riepilogo priorità

| # | Problema | Impatto | Sforzo |
|---|----------|---------|--------|
| 1 | `import logging` mancante in `models.py` | Alto (rompe il fallback dati) | Minimo |
| 3 | Cache scritta in `_MEIPASS` | Alto (cache inefficace in produzione) | Basso |
| 2 | Retry `tenacity` mai applicato | Medio | Basso |
| 5 | Sessione HTTP condivisa per FMP | Medio | Basso |
| 4 | Connessione SQLite riutilizzabile | Basso/Medio | Basso |
| 6 | Import morti in `main.py` | Basso | Minimo |
| 7 | Offuscamento API key | Basso (da chiarire) | N/A |
| 8 | `except` ridondante | Cosmetico | Minimo |
