import logging
import os
import anthropic
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    Big5BacktestRequest, Big5BacktestResponse,
    Big5ComboResult, Big5ComboMetrics, Big5Trade,
    Big5AnalysisRequest, Big5AnalysisResponse,
)
from app.services.big5_top5 import fetch_candidate_data, compute_top5_history
from app.services.big5_engine import run_all_combinations
from app.services.telegram_alerts import send_telegram_alert, get_current_status
from app.services.news_digest import send_news_digest
from app.services.intraday_alerts import send_intraday_alert
from app.services.wsb_scanner import send_wsb_alert, scan_wsb

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=Big5BacktestResponse)
async def run_big5_backtest(req: Big5BacktestRequest):
    try:
        # Fetch price data for all candidates
        price_data = await fetch_candidate_data(req.from_date, req.to_date)
        if not price_data:
            raise HTTPException(status_code=500, detail="No price data available")

        # Build daily top5 history
        top5_history = compute_top5_history(price_data)

        # Run all 8 combinations
        raw_results = run_all_combinations(
            price_data, top5_history,
            indicator=req.indicator,
            period=req.period,
            entry_threshold=0.005 if req.optimized else 0.0,
            min_hold_days=5 if req.optimized else 0,
        )

        results = []
        for r in raw_results:
            trades = [Big5Trade(**t) for t in r["trades"]]
            metrics = Big5ComboMetrics(**r["metrics"])
            results.append(Big5ComboResult(kombination=r["kombination"], trades=trades, metrics=metrics))

        return Big5BacktestResponse(
            results=results,
            indicator=req.indicator,
            period=req.period,
            from_date=req.from_date,
            to_date=req.to_date,
            optimized=req.optimized,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Big5 backtest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=Big5AnalysisResponse)
async def analyze_big5(req: Big5AnalysisRequest):
    try:
        metrics_lines = []
        for r in req.results:
            m = r.metrics
            metrics_lines.append(
                f"{r.kombination}: Return={m.total_return:+.1f}% | Sharpe={m.sharpe:.2f} | "
                f"WinRate={m.win_rate:.1f}% | MaxDD={m.max_drawdown:.1f}% | Trades={m.num_trades}"
            )
        metrics_summary = "\n".join(metrics_lines)

        best = max(req.results, key=lambda r: r.metrics.sharpe)
        worst = min(req.results, key=lambda r: r.metrics.total_return)

        opt_note = (
            "\nMODUS: Optimiert (Rauschunterdrückung aktiv)\n"
            "- Einstieg nur wenn Schlusskurs mind. 0,5% über {ind}{per} liegt (verhindert marginale Crossovers)\n"
            "- Mindesthaltedauer 5 Handelstage nach Kauf (verhindert 1-Tages-Whipsaws)\n"
            "- WICHTIG: Die Mindesthaltedauer ist im Live-Betrieb nicht replizierbar — sie ist erst im Nachhinein bekannt.\n"
            "  Weise explizit darauf hin, dass Optimiert-Ergebnisse besser als live erzielbar sind.\n"
            .format(ind=req.indicator, per=req.period)
            if req.optimized else "\nMODUS: Raw (keine Filterung, alle Signale werden ausgeführt)\n"
        )

        prompt = f"""WICHTIG: Antworte AUSSCHLIESSLICH auf Deutsch.

Du bist ein erfahrener quantitativer Portfolio-Manager und schreibst einen präzisen Backtest-Report für ein Investment-Komitee.

## STRATEGIE-KONTEXT (lies das genau — das ist die Grundlage deiner Analyse)

**Universum:** Die 5 größten S&P-500-Unternehmen nach täglicher Marktkapitalisierung (dynamisch berechnet).
**Trendfilter:** {req.indicator}{req.period} — Kauf nur wenn Trend aufwärts zeigt.
**Zeitraum:** {req.from_date} bis {req.to_date}
{opt_note}
**Kauf-Logik im Detail:**
- A-Case (frisches Signal): Unternehmen tritt in Top5 ein. War der Kurs beim Eintrittstag bereits ÜBER dem {req.indicator}{req.period}, muss er erst wieder DARUNTER fallen und dann erneut darüber schließen ("Reset") — erst dann Kauf. War er beim Eintritt UNTER dem {req.indicator}{req.period}, wird gewartet bis der erste Schlusskurs darüber liegt — dann Kauf am nächsten Open. Ziel: nur echte, frische Trendbestätigungen.
- B-Case (sofort): Kauf genau am Tag des Top5-Eintritts, aber nur wenn der Kurs an diesem Tag bereits über dem {req.indicator}{req.period} schließt. Kein Reset nötig, kein Warten — entweder sofort oder gar nicht.

**Verkauf-Logik:**
- C: Verkauf nur wenn Schlusskurs unter {req.indicator}{req.period} fällt. Top5-Austritt wird ignoriert — Trend entscheidet.
- D: Sofortiger Verkauf sobald das Unternehmen aus den Top5 fällt (rangbasiert, nicht preisbasiert).

**Top5-Filter:**
- E: 1 Tag in Top5 reicht für Einstiegs-Berechtigung
- F: 5 aufeinanderfolgende Tage in Top5 nötig (filtert kurzfristige Rangverschiebungen heraus)

**Warum A besser als B sein sollte:** A verlangt einen frischen Crossover — der Kurs muss Schwäche zeigen und dann wieder Stärke beweisen. B kauft in bestehende Stärke hinein, ohne Bestätigung dass der Trend intakt bleibt.
**Warum F besser als E sein sollte:** F eliminiert Rauschen durch kurzfristige Marktcap-Schwankungen. Nur Unternehmen die 5 Tage stabil in den Top5 sind, bekommen ein Signal.
**Warum C besser als D sein sollte:** Rangverlust ≠ Trendwende. Ein Unternehmen kann Rang 6 werden obwohl sein Kurs weiter steigt — D würde hier fälschlicherweise verkaufen.

## ERGEBNISSE

{metrics_summary}

## DEIN AUFTRAG

Schreibe diese Abschnitte mit exakt diesen Überschriften. Keine Floskeln. Direkt und datengetrieben.
Verwende: Kauf-Signal, Verkauf-Signal, Haltedauer, Drawdown, Trendfilter, Top5-Eintritt, Top5-Austritt, Kumulierte Performance, Handelsanzahl, Trefferquote, Rendite-Risiko-Verhältnis.

## Zusammenfassung
3 Sätze: Was macht die Strategie, was ist das wichtigste Ergebnis, welche Kombination dominiert?

## Beste Kombination: {best.kombination}
Erkläre WARUM diese Kombination strukturell überlegen ist — nicht nur die Zahlen, sondern die Logik dahinter. Bestätigt das Ergebnis die Erwartung (A>B, F>E, C>D)? Wenn nicht, warum?

## Schwächste Kombination: {worst.kombination}
Welcher strukturelle Fehler steckt dahinter? Was sagt das über die Strategie-Logik aus?

## Überraschende Erkenntnisse
Gibt es Kombinationen die gegen die Erwartung performen? Z.B. B besser als A, oder E besser als F? Falls ja: warum könnte das sein?

## Risiken
Tabelle: Klumpenrisiko, Überanpassung, Survivorship Bias, Ausführungskosten, Replizierbarkeit (bei Optimiert-Modus). Mit Bewertung und Gegenmaßnahme.

## Handlungsempfehlung
Konkret: Welche Kombination live, Positionsgröße (Half-Kelly), eine sofort umsetzbare Zusatzregel.

Maximal 500 Wörter gesamt."""

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis_text = message.content[0].text
        return Big5AnalysisResponse(analysis=analysis_text)

    except Exception as e:
        logger.exception("Big5 analyze failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ema-status")
async def ema_status():
    """Current EMA200 position of all Big 5 tickers."""
    try:
        return {"status": get_current_status()}
    except Exception as e:
        logger.exception("EMA status failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news-digest")
async def trigger_news_digest():
    """Morning news digest — Top-News + Handlungsempfehlung via Telegram."""
    try:
        result = await send_news_digest()
        return result
    except Exception as e:
        logger.exception("News digest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intraday-alert")
async def trigger_intraday_alert():
    """DE40 + US100 EMA200 Crossover auf 30m/1h/12h → Telegram."""
    try:
        return await send_intraday_alert()
    except Exception as e:
        logger.exception("Intraday alert failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wsb-scan")
async def wsb_scan():
    """WSB + Reddit Scanner — Top Mentions inkl. PLTR."""
    try:
        return scan_wsb()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wsb-alert")
async def trigger_wsb_alert():
    """WSB Scanner → Telegram wenn PLTR oder Watchlist trending."""
    try:
        return await send_wsb_alert()
    except Exception as e:
        logger.exception("WSB alert failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ema-alert")
async def trigger_ema_alert():
    """Check trending + Big5 EMA200 bullish crossovers and send Telegram alert."""
    try:
        result = await send_telegram_alert()
        return result
    except Exception as e:
        logger.exception("EMA alert failed")
        raise HTTPException(status_code=500, detail=str(e))
