# backend/app/services/ai_analyst.py
import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

ANALYSIS_PROMPT = """You are a professional quantitative analyst reviewing backtesting results.

Backtest data:
{data}

Provide a structured analysis in JSON with these exact keys:
- "patterns": list of 2-3 strings, notable patterns/anomalies observed
- "risk_assessment": list of 2-3 strings, risk/drawdown/volatility concerns
- "recommendations": list of 2-3 strings, EMA period and market regime recommendations
- "benchmark_comment": string, 1-2 sentences comparing strategy vs buy-and-hold

Be concise, professional, and data-driven. No generic advice. Return ONLY valid JSON."""


async def analyze_backtest_results(results: list[dict]) -> dict:
    summary = []
    for r in results:
        if r.get("metrics"):
            summary.append({
                "ticker": r["ticker"],
                "metrics": r["metrics"],
                "num_trades": len(r.get("trades", [])),
                "last_signal": r["last_signal"],
            })

    data_str = json.dumps(summary, indent=2)
    prompt = ANALYSIS_PROMPT.format(data=data_str)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
