# Produkt-Vision: Stocks Backtest Platform

## Was wir haben (Stand April 2026)

**Big5 Swing Backtest** — S&P500 Top5 nach Marktkapitalisierung, EMA200-Trendfilter, 8 Einstiegs-/Ausstiegs-Kombinationen, Raw/Optimiert-Modus, AI Analyst Report, PDF/CSV Export.

Kern-Logik: Unternehmen tritt in Top5 ein → EMA-Crossover als Kaufsignal (A-Case: frischer Crossover, B-Case: Eintrittstag).

---

## Nächste Ausbaustufe: Einzelaktien-Screener

### Idee
User gibt beliebigen Ticker ein (z.B. TSLA, NVDA, SAP) → Backtest läuft auf dieser Aktie mit der gleichen EMA-Strategie. Kein Universum-Ranking nötig, nur Kurs + EMA-Logik.

### Warum einfacher als das aktuelle System
- Kein Marktcap-Ranking
- Kein Constituency-Check
- Keine hardcodierten historischen Korrekturen
- Bestehende Engine (`backtest_engine.py`) direkt nutzbar

### Was gebraucht wird
- Ticker-Input im Frontend
- yfinance fetch für beliebigen Ticker
- EMA-Backtest mit bestehender Engine
- Gleiches Trade-Output-Format

### Mögliche Erweiterungen
- Mehrere Ticker gleichzeitig vergleichen
- Universum-Auswahl: S&P500 Top10/20/50 (Ranking-Logik bereits vorhanden)
- Andere Indizes: NAS100, DAX (neue Constituency-Daten nötig)
- Signale live (aktueller Close vs. EMA → Long/Flat)

---

## Wie Top5-Ranking aktuell funktioniert

Täglich berechnet via `compute_top5_history()`:
1. Preis-Daten via yfinance für ~20 Kandidaten
2. Marktcap = Close × Shares Outstanding (aktuelle Shares — Approximation für historische Daten)
3. Korrekturen für GE, XOM, CSCO etc. (Splits/Spin-offs verfälschen sonst Ranking)
4. S&P500-Mitgliedschaft via GitHub-Dataset (fja05680/sp500)
5. Ranking → Top5/10/20 pro Handelstag

**Limitation:** Shares Outstanding ist immer aktuell → historisches Ranking ist Annäherung, nicht exakt.

---

## Langfristige Vision

Eine Plattform die zwei Dinge kann:
1. **Strategie-Backtest** auf definierten Universen (Top5/10/50 nach Marktcap, Index-Mitglieder)
2. **Einzelaktien-Analyse** — beliebiger Ticker, EMA-Signal, Trade-History

Zielgruppe: Privatanleger und Semi-Profis die regelbasierte Strategien testen wollen ohne Bloomberg-Terminal.
