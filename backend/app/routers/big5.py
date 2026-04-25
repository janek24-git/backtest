import logging
import os
import anthropic
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    Big5BacktestRequest, Big5BacktestResponse,
    Big5ComboResult, Big5ComboMetrics, Big5Trade,
    Big5AnalysisRequest, Big5AnalysisResponse,
)
from app.services.big5_top5 import fetch_candidate_data, compute_top5_history
from app.services.big5_engine import run_all_combinations

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
            "\nHINWEIS: Diese Ergebnisse wurden mit aktivierter Rauschunterdrückung berechnet "
            "(0,5% Mindestabstand zur EMA beim Einstieg + 5 Handelstage Mindesthaltedauer). "
            "Diese Optimierung ist im Live-Betrieb nicht vollständig replizierbar, da die Mindesthaltedauer "
            "erst im Nachhinein bekannt ist. Weise im Report explizit auf diesen Hinweis-Faktor hin."
            if req.optimized else ""
        )

        prompt = f"""WICHTIG: Antworte AUSSCHLIESSLICH auf Deutsch. Alle Überschriften, alle Texte, alle Begriffe müssen auf Deutsch sein.

Du bist ein erfahrener quantitativer Portfolio-Manager und schreibst einen Backtest-Report auf Deutsch für ein Investment-Komitee.
{opt_note}
Strategie: S&P 500 Top-5 nach Marktkapitalisierung, Trendfilter {req.indicator}{req.period}, Zeitraum {req.from_date} bis {req.to_date}.
8 Kombinationen aus Kauf-Signal, Verkauf-Signal und Top5-Filter wurden getestet. Ergebnisse:

{metrics_summary}

Kombinationslegende:
A = Kauf: Erster Schlusskurs über {req.indicator}{req.period} nach Top5-Eintritt
B = Kauf: Am Tag des Top5-Eintritts (wenn Schlusskurs bereits über {req.indicator}{req.period})
C = Verkauf: Nur wenn Schlusskurs unter {req.indicator}{req.period} fällt (Top5-Austritt wird ignoriert)
D = Verkauf: Sofort bei Top5-Austritt
E = Filter: 1 Tag in Top5 = Signal ausreichend
F = Filter: 5 aufeinanderfolgende Tage in Top5 nötig

Schreibe den Report auf einfachem, klaren Deutsch. Keine Anglizismen wo es geht. Verwende diese Begriffe: Kauf-Signal, Verkauf-Signal, Haltedauer, Drawdown, Trendfilter, Top5-Eintritt, Top5-Austritt, Kumulierte Performance, Handelsanzahl, Trefferquote (statt Win Rate), Rendite-Risiko-Verhältnis (statt Sharpe).

Schreibe diese Abschnitte mit exakt diesen Überschriften:

## Zusammenfassung
2-3 Sätze. Was macht diese Strategie, und was ist das wichtigste Ergebnis?

## Beste Kombination: {best.kombination}
Warum schneidet diese Kombination nach Rendite-Risiko am besten ab? Konkrete Zahlen nennen: Sharpe, Drawdown, Handelsanzahl, Trefferquote.

## Schwächste Kombination: {worst.kombination}
Welcher strukturelle Fehler führt zur Underperformance? Was lernen wir daraus?

## Risiken
Tabellarisch: Klumpenrisiko (nur 5 Titel), Überanpassung an historische Daten, Liquidität, Ausführungskosten, Überlebensfehler (Survivorship Bias). Jedes Risiko mit Bewertung und Gegenmaßnahme.

## Handlungsempfehlung
Welche Kombination für den Live-Einsatz, warum? Positionsgröße konkret (z.B. Half-Kelly). Eine zusätzliche Regel die du als Portfolio-Manager sofort einführen würdest.

Schreibe direkt und datengetrieben. Keine Floskeln. Maximal 400 Wörter gesamt."""

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
