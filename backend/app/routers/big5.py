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

        prompt = f"""You are a senior hedge fund portfolio manager reviewing a quantitative backtest.

Strategy: S&P 500 Top-5 by market cap rotation ({req.indicator}{req.period}), {req.from_date} to {req.to_date}.
8 entry/exit/filter combinations were tested. Results:

{metrics_summary}

Combination key:
A = Buy: first close above {req.indicator}{req.period} after Top5 entry
B = Buy: on Top5 entry day (if close above {req.indicator}{req.period})
C = Sell: only when close < {req.indicator}{req.period} (ignore Top5 exit)
D = Sell: immediately on Top5 exit
E = Signal: 1 day in Top5 = signal
F = Signal: 5 consecutive days in Top5 = signal

Write a compact, data-driven analyst report with these exact sections (use these as headers):

## Executive Summary
2-3 sentences. What does this strategy do and what is the headline finding?

## Best Combination: {best.kombination}
Why this combination outperforms on a risk-adjusted basis. Reference Sharpe, Max DD, trade count.

## Worst Combination: {worst.kombination}
Why this combination underperforms. What structural flaw does it reveal?

## Risk Assessment
Key risks: concentration (only 5 stocks), data snooping, liquidity, execution slippage, survivorship bias.

## Strategic Recommendation
Which combination to trade live and why. Position sizing suggestion (e.g. equal-weight or Kelly fraction). One concrete rule the portfolio manager would add.

Be precise and concise. No generic disclaimers. Write like you are presenting to an investment committee."""

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
