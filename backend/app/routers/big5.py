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
from app.services.warrant_finder import build_warrant_links, build_warrant_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=Big5BacktestResponse)
async def run_big5_backtest(req: Big5BacktestRequest):
    try:
        # Fetch price data for all candidates
        price_data = await fetch_candidate_data(req.from_date, req.to_date, universe=req.universe)
        if not price_data:
            raise HTTPException(status_code=500, detail="No price data available")

        # Build daily top5 history
        top5_history = compute_top5_history(price_data, universe=req.universe)

        # Run all 8 combinations
        raw_results = run_all_combinations(
            price_data, top5_history,
            indicator=req.indicator,
            period=req.period,
            entry_threshold=0.005 if req.optimized else 0.0,
            min_hold_days=0,
            universe=req.universe,
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
            universe=req.universe,
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

        sorted_by_sharpe = sorted(req.results, key=lambda r: r.metrics.sharpe, reverse=True)
        top3 = sorted_by_sharpe[:3]
        top3_summary = "\n".join([
            f"{r.kombination}: Return={r.metrics.total_return:+.1f}% | Sharpe={r.metrics.sharpe:.2f} | "
            f"WinRate={r.metrics.win_rate:.1f}% | MaxDD={r.metrics.max_drawdown:.1f}% | Trades={r.metrics.num_trades} | Portfolio-End=€{r.metrics.portfolio_end_eur:.0f}"
            for r in top3
        ])

        opt_note = (
            f"\nMODUS: Optimiert (0,5% {req.indicator}-Threshold beim Einstieg)\n"
            if req.optimized else "\nMODUS: Raw (alle Signale, keine Filter)\n"
        )

        universe_desc = {
            "SP500": "Die 5 größten S&P-500-Unternehmen nach täglicher Marktkapitalisierung (dynamisch)",
            "NAS100": "Die 5 größten Nasdaq-100-Unternehmen nach täglicher Marktkapitalisierung (dynamisch)",
            "GOLD": "Gold (GC=F) — Einzel-Asset EMA-Strategie",
            "SILVER": "Silber (SI=F) — Einzel-Asset EMA-Strategie",
            "BITCOIN": "Bitcoin (BTC-USD) — Einzel-Asset EMA-Strategie",
            "OIL": "Rohöl WTI (CL=F) — Einzel-Asset EMA-Strategie",
            "DAX": "Die 5 größten DAX-Unternehmen nach Marktkapitalisierung",
            "STOXX50": "Die 5 größten EURO STOXX 50-Unternehmen nach Marktkapitalisierung",
        }.get(req.universe, req.universe)

        prompt = f"""WICHTIG: Antworte AUSSCHLIESSLICH auf Deutsch.

Du bist ein erfahrener Investor und systematischer Trader. Deine Aufgabe ist keine Schulaufgabe — du sollst ehrlich abwägen, philosophieren, Grautöne zeigen. Es gibt keine perfekte Kombination. Jede hat Vor- und Nachteile die vom Investor-Typ abhängen.

## STRATEGIE-KONTEXT

**Universum:** {universe_desc}
**Trendfilter:** {req.indicator}{req.period}
**Zeitraum:** {req.from_date} bis {req.to_date}
{opt_note}
**Entry-Modi:**
- A: {req.indicator}-Crossover in Top5, mit Reset beim Eintritt (wenn schon über {req.indicator} → erst warten bis darunter). Sauberster Einstieg, konservativ.
- B: Kauf direkt am Tag des Top5-Eintritts, auch wenn schon weit über {req.indicator}. Aggressiv, hinterherrennen bewusst.
- K: Kontinuierlicher {req.indicator}-Crossover während Top5-Mitgliedschaft, kein Reset. Maximale Aktivität, handelt jeden Auf/Ab-Zyklus.

**Exit-Modi:**
- C: Nur Verkauf wenn Close unter {req.indicator} fällt. Trendfolge pur, ignoriert Rang-Verlust.
- D: Sofortiger Verkauf bei Top5-Austritt. Rang-basiert, unabhängig vom Trend.

**Filter:**
- E: 1 Tag in Top5 reicht.
- F: 5 aufeinanderfolgende Tage in Top5 nötig. Filtert kurzfristige Fluktuationen.

## ALLE ERGEBNISSE

{metrics_summary}

## TOP 3 (nach Sharpe)

{top3_summary}

## DEIN AUFTRAG

Schreibe folgende Abschnitte. Sei ehrlich, nuanciert, denke laut. Kein "Kombination X ist klar der Gewinner" — sondern: für wen, unter welchen Umständen, mit welchen Kompromissen?

## Überblick
2-3 Sätze: Was zeigen die Daten insgesamt? Gibt es einen klaren Trend oder ist es uneinheitlich?

## Top 3 im Vergleich
Gehe durch die Top 3 Kombinationen. Für jede: Was spricht dafür? Was dagegen? Wer würde sie wählen — der aktive Trader, der passive Investor, der risikoscheue Anleger? Denke in Dimensionen: Rendite, Risiko (Drawdown), Aufwand (Handelsfrequenz), Psychologie (wie viele Trades kann man wirklich diszipliniert ausführen?), Replizierbarkeit im echten Leben.

## Spannungsfelder
Was sind die echten Zielkonflikte dieser Strategie? Z.B.: Mehr Trades = mehr Chancen, aber auch mehr Fehler und Kosten. Langer Halt = weniger Stress, aber größere Drawdowns. Diskutiere diese Abwägungen ohne falsche Auflösung — manche Fragen haben keine beste Antwort.

## Realitäts-Check
Was würde im echten Trading anders laufen als im Backtest? Slippage, Emotionen, Marktphasen die im Backtest nicht vorkamen (z.B. ein 2000er Crash der NVDA trifft). Sei konkret.

## Fazit ohne Dogma
Keine einzelne Empfehlung. Stattdessen: 2-3 Szenarien ("Wenn du X bist, dann Y — weil Z"). Lass den Leser selbst entscheiden.

Maximal 600 Wörter gesamt. Kein Marketingsprech."""

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-6",
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


@router.get("/wsb-debug")
async def wsb_debug():
    """Debug: Reddit raw response check."""
    import httpx
    results = []
    for sub in ["wallstreetbets", "stocks"]:
        for sort in ["hot", "new"]:
            try:
                r = httpx.get(
                    f"https://www.reddit.com/r/{sub}/{sort}.json?limit=5",
                    headers={"User-Agent": "Mozilla/5.0 SqueezeBot/2.0"},
                    timeout=10,
                )
                body = r.text[:200]
                try:
                    posts = r.json()["data"]["children"]
                    count = len(posts)
                except Exception:
                    posts = []
                    count = 0
                results.append({"sub": sub, "sort": sort, "status": r.status_code, "posts": count, "preview": body[:100]})
            except Exception as e:
                results.append({"sub": sub, "sort": sort, "error": str(e)})
    return results


@router.post("/wsb-alert")
async def trigger_wsb_alert():
    """WSB Scanner → Telegram wenn PLTR oder Watchlist trending."""
    try:
        return await send_wsb_alert()
    except Exception as e:
        logger.exception("WSB alert failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/warrants")
async def warrant_search(
    ticker:    str   = Query(..., description="z.B. NVDA"),
    direction: str   = Query("LONG", description="LONG oder SHORT"),
    budget:    float = Query(1000.0, description="Budget in EUR"),
):
    """Optionsschein-Finder: beste Calls/Puts für eine Trade-Idee."""
    try:
        data = build_warrant_links(ticker.upper(), direction.upper())
        return {"ticker": ticker.upper(), "direction": direction, **data}
    except Exception as e:
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
