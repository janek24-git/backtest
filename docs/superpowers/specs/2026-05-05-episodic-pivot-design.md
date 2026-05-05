# Episodic Pivot (EP) Screener + Backtest — Design Spec
**Date:** 2026-05-05
**Status:** Approved

---

## Overview

Add Episodic Pivot (EP) strategy to the existing stocks-backtest platform:
1. **EP Screener** — täglich 20:00 UTC (22:00 MESZ), Telegram-Alert "YOLO STRATEGIE BUY"
2. **EP Backtest** — 10 Jahre (2016–2026), neuer Tab im Frontend neben "Big 5"

---

## Strategie-Definition (Episodic Pivot)

- **Signal:** Gap-up > 10% mit Katalysator (Earnings-Überraschung oder News)
- **Bestätigung:** Relatives Volumen > 2× 20T-Schnitt
- **Ideal:** Lange, flache Konsolidierungs-Base vor dem Gap (ATR-Kontraktion)
- **Einstieg:** Opening Range Breakout (ORB) — 5min oder 30min nach Open
- **Stop:** Low of the Day (LOTD)
- **Haltedauer:** Wochen bis Monate (PEAD-Effekt)
- **Win-Rate:** ~30%, aber Gewinner übertreffen Verlierer massiv (Asymmetrie)

---

## Backend-Architektur

### Neue Dateien
```
backend/app/services/ep_scanner.py     — Screening-Pipeline
backend/app/services/ep_backtest.py    — Backtest-Engine (2016–2026)
backend/app/routers/ep.py              — API-Routen: /ep/scan, /ep/backtest, /ep/alert
.github/workflows/ep-alert.yml         — Schedule: täglich 20:00 UTC
```

### Bestehende Dateien (unverändert)
Alle anderen Screener, Routen und Workflows bleiben exakt wie sie sind.

---

## ep_scanner.py — Pipeline

1. **Polygon grouped daily** → alle US-Stocks mit Gap-up > 10%
   `gap = (close_heute / close_gestern) - 1 > 0.10`
2. **Earnings-Filter** → Finnhub earnings calendar: Earnings ±1 Tag → Katalysator = "Earnings"
3. **News-Filter** → Finnhub company news: News in letzten 24h → Katalysator = "News"
4. **Volume-Filter** → relatives Volumen > 2× 20T-Schnitt via yfinance
5. **Base-Check** → ATR(20) vor dem Gap niedrig (< 50% des aktuellen ATR) → Konsolidierung erkannt
6. **Score-Berechnung** (0–10):
   - Earnings-Katalysator: +3
   - News-Katalysator: +2
   - Volumen > 3×: +2 | > 2×: +1
   - Base > 20T: +2 | > 10T: +1
   - Gap 10–20%: +2 | > 20%: +1 (zu groß = riskanter)
7. **Filter:** Score ≥ 5 → Alert

### Score-Kommentar
| Score | Kommentar |
|-------|-----------|
| 9–10  | "Perfektes Setup — alle Signale grün." |
| 7–8   | "Guter Trend, solide Basis." |
| 5–6   | "Hohes Risiko, aber im Marktfluss." |
| < 5   | Kein Alert |

---

## Invest-Vorschlag-Logik

**Kapital-Default:** €1.000 (konfigurierbar via ENV `EP_KAPITAL`)
**Ziel:** €10.000

### Safe Play (Interactive Brokers — Aktie)
- Risiko: 5% des Kapitals = €50
- Stop-Abstand: `(entry - LOTD) / entry`
- Stückzahl: `floor(50 / (entry * stop_pct))`
- Ziel: +20% auf Aktienposition

### YOLO Play (Trade Republic — Optionsschein)
- Risiko: 10% des Kapitals = €100
- Delta-Guide: Black-Scholes mit 30T-Historical-Vol als IV-Proxy
- Empfehlung: ATM–5% OTM CALL, 6M Laufzeit, Hebel ~10×
- Ziel: +20% Aktie → ~+200% Schein

---

## Telegram-Nachricht Format

```
YOLO STRATEGIE BUY — DD.MM.YYYY

━━━━━━━━━━━━━━━━━━━━
[TICKER]  ·  [Name]
Katalysator: [Earnings Surprise X% | News: Titel]
Gap-up: X%  |  Vol: X× Schnitt
MarktKap: XB  ·  Sektor: X

── ENTRY ──────────────────
Morgen 9:30 ET — ORB-Einstieg
Entry-Zone: $X – $Y  (30min Hoch)
Stop: $Z  (LOTD)

── SAFE PLAY (IB) ──────────
Aktie direkt
Position: N Stück  ca. EURx
Max Verlust: EUR50  (5% von EUR1.000)
Ziel +20%: EURx Gewinn

── YOLO PLAY (TR) ──────────
Optionsschein CALL
Budget: EUR100  (10% von EUR1.000)
Delta 0.40–0.55  ·  6M  ·  Hebel ~10×
Ziel: +20% Aktie ca. +200% Schein

── RISIKO-AMPEL ────────────
Katalysator: [Earnings/News] [✓/✗]
Volumen: X× [✓/✗]
Base: [kurz/lang] (XT)
Gap-Groesse: X% — [optimal/gross]

Score: X/10 — [STARK/SOLIDE/RISKANT]
"[Score-Kommentar]"

━━━━━━━━━━━━━━━━━━━━
```

---

## ep_backtest.py — Engine

### Datenquellen
- **Gap-Erkennung (historisch):** Polygon aggregates daily (2016–2026)
- **Intraday ORB:** Polygon aggregates 5min/30min — approximiert für Backtest mit Tages-Open
- **Earnings-History:** Finnhub earnings calendar historical
- **Preise:** yfinance daily OHLCV

### Backtest-Logik
1. Iteriere alle Handelstage 2016–2026
2. Finde Gap-up > 10% Events via Polygon
3. Prüfe Earnings ±1T via Finnhub
4. Prüfe Vol > 2× (yfinance)
5. Simuliere Entry: Tages-Open + 0.1% Slippage
6. Simuliere Stop: LOTD (Tages-Low)
7. Messe PEAD-Drift: Close nach +5T, +10T, +20T, +60T

### Metrics
- Win-Rate (%), Avg-Win (%), Avg-Loss (%)
- Expectancy = (WinRate × AvgWin) - (LossRate × AvgLoss)
- Sharpe Ratio (annualisiert)
- Max Drawdown
- Equity-Kurve

---

## Frontend — Neuer Tab "EP Scanner"

### Tab-Struktur (neben "Big 5")
- **Kandidaten-Tabelle:** Ticker | Gap% | Vol-Faktor | Score | Katalysator | Datum
- **Detail-View** (Klick): TradingView Lightweight Chart mit Polygon-Intraday-Kerzen, Entry-Zone, Stop, Invest-Vorschlag
- **Backtest-Seite:** Zeitraum-Picker, Metrics-Cards (Win-Rate, Expectancy, Sharpe, MaxDD), Trade-Tabelle

---

## GitHub Actions Workflow

```yaml
# .github/workflows/ep-alert.yml
name: EP Scanner (täglich)
on:
  schedule:
    - cron: '0 20 * * 1-5'   # 20:00 UTC = 22:00 MESZ Mo-Fr
  workflow_dispatch:
```

---

## API-Keys

| Key | Variable | Status |
|-----|----------|--------|
| Polygon.io | `MASSIVE_API_KEY` | vorhanden |
| Finnhub | `FINNHUB_API_KEY` | neu eingetragen |
| Telegram | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | vorhanden |

---

## Was unverändert bleibt

- EMA200 Daily Alert
- WSB Squeeze Scanner
- Intraday EMA Alert (DE40/US100)
- Big 5 Backtest Engine
- Alle bestehenden API-Routen

---

## Offene Punkte

- Polygon-Plan prüfen: Intraday-History (5min/30min) verfügbar?
- `EP_KAPITAL` ENV-Variable in Railway konfigurieren (default €1000)
