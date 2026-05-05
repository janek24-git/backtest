# Big 5 Swing Backtest — Design Spec
**Date:** 2026-04-19
**Status:** Approved

---

## Overview

Integration einer neuen Backtest-Strategie ("Big 5 Swing") in das bestehende stocks-backtest-Projekt. Separate Seite `/big5`, komplett getrennt vom bestehenden NAS100-Dashboard. Testzeitraum: 2000-01-01 bis 2025-12-31.

**Strategie:** EMA/SMA 200 Crossover auf den S&P500 Top-5 Unternehmen nach Marktkapitalisierung (dynamisch, historisch kuriert). 8 Strategie-Kombinationen werden simultan berechnet und verglichen.

---

## Architektur

```
stocks-backtest/
├── backend/app/
│   ├── routers/
│   │   └── big5.py                    # POST /big5/run
│   ├── services/
│   │   ├── big5_engine.py             # 8 Kombinationen, EMA+SMA, Holiday-Handling
│   │   ├── sp500_universe.py          # Kuratierte Top-5-Timeline 2000–2025
│   │   └── data_fetcher.py            # yfinance (ersetzt Massive)
│   └── models/
│       └── schemas.py                 # Big5-Pydantic-Models ergänzen
│
└── frontend/src/
    ├── pages/
    │   └── Big5Dashboard.tsx          # Neue Seite /big5
    └── components/
        ├── Big5ComboTable.tsx         # 8 Zeilen Kombinationsvergleich
        └── Big5TradeHistory.tsx       # Trade-Detail pro Kombination
```

---

## Data Layer

### Datenquelle: yfinance (ersetzt Massive/Polygon)

`data_fetcher.py` wird vollständig auf yfinance umgebaut:
- `fetch_ticker_data(ticker, from_date)` nutzt `yfinance.download()`
- Parquet-Cache bleibt identisch (23h Freshness, `cache/` Verzeichnis)
- NAS100-Seite profitiert automatisch (25 Jahre History statt 2)
- Kein API-Key erforderlich

### S&P500 Top-5 Universe (`sp500_universe.py`)

Hardcodierte Jahres-Snapshots basierend auf recherchierten Marktkapitalisierungsdaten (Quellen: FinHacker, Voronoi, Visual Capitalist, Fort Boise):

```python
SP500_TOP5_HISTORY = {
    2000: ["GE", "XOM", "PFE", "CSCO", "MSFT"],
    2001: ["GE", "MSFT", "XOM", "WMT", "C"],
    2002: ["MSFT", "XOM", "WMT", "C", "PFE"],
    2003: ["MSFT", "XOM", "PFE", "C", "WMT"],
    2004: ["GE", "MSFT", "C", "XOM", "WMT"],
    2005: ["GE", "XOM", "MSFT", "C", "WMT"],
    2006: ["XOM", "MSFT", "C", "BAC", "GE"],
    2007: ["XOM", "MSFT", "PG", "GE", "GOOGL"],
    2008: ["XOM", "WMT", "PG", "MSFT", "JNJ"],
    2009: ["XOM", "MSFT", "WMT", "GOOGL", "AAPL"],
    2010: ["XOM", "AAPL", "MSFT", "BRK-B", "WMT"],
    2011: ["XOM", "AAPL", "MSFT", "CVX", "GOOGL"],
    2012: ["AAPL", "XOM", "GOOGL", "WMT", "MSFT"],
    2013: ["AAPL", "XOM", "GOOGL", "MSFT", "BRK-B"],
    2014: ["AAPL", "XOM", "MSFT", "BRK-B", "GOOGL"],
    2015: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2016: ["AAPL", "GOOGL", "MSFT", "BRK-B", "XOM"],
    2017: ["AAPL", "GOOGL", "MSFT", "AMZN", "META"],
    2018: ["MSFT", "AAPL", "AMZN", "GOOGL", "BRK-B"],
    2019: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    2020: ["AAPL", "MSFT", "AMZN", "GOOGL", "META"],
    2021: ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    2022: ["AAPL", "MSFT", "GOOGL", "AMZN", "BRK-B"],
    2023: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    2024: ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"],
    2025: ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN"],
}
```

**Alle Unique Tickers (19):** `MSFT, AAPL, XOM, GE, GOOGL, WMT, C, PFE, AMZN, BRK-B, META, NVDA, TSLA, PG, JNJ, BAC, CVX, IBM, CSCO`

**Universe-Logik:** `year = date.year` → Jahressnapshot bestimmt aktives Top-5. Wechsel gilt ab dem ersten Handelstag des Folgejahres.

---

## Strategie-Kombinationen

### Basislogik

- **Signal:** Kerzenschluss (Daily, NY Time 0:00–23:59:59) über/unter EMA200 oder SMA200
- **Execution:** Open-Preis des nächsten Handelstages (NYSE-Kalender, Holiday-aware)
- **Indikator:** EMA oder SMA, Periode 200 (wählbar via UI-Toggle)

### Dimensionen

| Dimension | Option | Beschreibung |
|---|---|---|
| **Kaufsignal** | **A** | Erstes Close > 200er *nachdem* Unternehmen in Top-5 ist |
| | **B** | Am Tag des Top-5-Eintritts, wenn Close desselben Tages > 200er |
| **Verkauf bei Top-5-Austritt** | **C** | Halten bis Close < 200er (EMA/SMA-Signal entscheidet) |
| | **D** | Sofortverkauf am Tag des Austritts, unabhängig vom EMA/SMA |
| **Top-5-Definition** | **E** | 1 Tag in Top-5 reicht für Signal |
| | **F** | 5 aufeinanderfolgende Tage in Top-5 erforderlich |

### 8 Kombinationen

`ACE, ACF, ADE, ADF, BCE, BCF, BDE, BDF`

Alle 8 laufen in einem einzigen Datendurchlauf als parallele State-Machines.

---

## Backtest Engine (`big5_engine.py`)

### Input

```python
class Big5BacktestRequest(BaseModel):
    indicator: Literal["EMA", "SMA"] = "EMA"
    period: int = 200
    from_date: str = "2000-01-01"
    to_date: str = "2025-12-31"
```

### Algorithmus (pro Kombination)

```
Für jeden Handelstag t (chronologisch):
  1. Bestimme aktives Top-5-Universe (via sp500_universe, year = t.year)
  2. Für jede Aktie im Universe:
     a. Berechne EMA/SMA200 auf Close-Reihe bis t
     b. Vergleiche Close[t] mit Indikator[t] → Signal (LONG / FLAT)
  3. Top-5-Zugehörigkeit prüfen (E: 1 Tag, F: 5 konsekutive Tage)
  4. State-Machine pro Aktie + Kombination updaten:
     - Kaufbedingung erfüllt? → Entry bei Open[t+1]
     - Verkaufsbedingung erfüllt? → Exit bei Open[t+1]
  5. Holiday-Check: falls t+1 Feiertag → t+2 (NYSE-Kalender)
```

### Output pro Trade (exakt laut Spec)

```python
class Big5Trade(BaseModel):
    nr: int                    # Fortlaufende Nummer
    typ: Literal["KAUF", "VERKAUF"]
    datum: date                # Execution-Datum
    haltdauer: int             # Handelstage
    open_preis: float          # Open des Execution-Tages
    perf_pct: float            # % Performance Kauf→Verkauf
    kum_perf_pct: float        # Kumulierte % Performance
```

### Output gesamt

```python
class Big5Result(BaseModel):
    kombination: str           # z.B. "ACE"
    ticker: str
    trades: list[Big5Trade]
    total_return: float
    win_rate: float
    num_trades: int
    max_drawdown: float
    sharpe: float

class Big5BacktestResponse(BaseModel):
    results: list[Big5Result]  # 8 Kombinationen × N Ticker
    indicator: str
    period: int
    from_date: str
    to_date: str
```

---

## API

### `POST /big5/run`

**Request:**
```json
{
  "indicator": "EMA",
  "period": 200,
  "from_date": "2000-01-01",
  "to_date": "2025-12-31"
}
```

**Response:** `Big5BacktestResponse`

---

## Frontend

### Navigation

Neuer Link "Big 5" in der bestehenden Nav neben "Dashboard".

### `Big5Dashboard.tsx`

- EMA/SMA Toggle (2 Buttons)
- "Run Backtest" Button
- Zeitraum-Anzeige: fix "2000–2025"
- `Big5ComboTable` mit Ergebnissen

### `Big5ComboTable.tsx`

AG Grid Tabelle, eine Zeile pro Kombination:

| Kombi | Trades | Win Rate | Total Return | Sharpe | Max DD |
|---|---|---|---|---|---|
| ACE | | | | | |
| ACF | | | | | |
| ADE | | | | | |
| ADF | | | | | |
| BCE | | | | | |
| BCF | | | | | |
| BDE | | | | | |
| BDF | | | | | |

Click auf Zeile → `Big5TradeHistory` klappt auf (expandable row).

### `Big5TradeHistory.tsx`

Vollständige Trade-Liste pro Kombination:

| Nr | Typ | Datum | Ticker | Haltdauer | Open | Perf % | Kum. Perf % |
|---|---|---|---|---|---|---|---|

---

## Error Handling

| Fehler | Verhalten |
|---|---|
| Ticker kein yfinance-Data | Übersprungen, geloggt, kein Crash |
| Holiday-Kette > 5 Tage | Exception mit klarer Meldung |
| Kein Signal im Zeitraum | Leere Trade-Liste, Metriken = 0 |
| EMA200 nicht berechenbar (< 200 Datenpunkte) | Ticker übersprungen |

---

## Abhängigkeiten

**Neu hinzufügen:**
```
yfinance>=0.2.40
pandas-market-calendars>=4.3.0
```

**Entfernen:**
```
massive  # nicht mehr benötigt
```
