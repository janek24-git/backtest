#!/usr/bin/env python3
import json
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

SIGNALS_FILE = Path(__file__).parent.parent / "signals" / "signals.json"


def get_price(ticker: str) -> float:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    except Exception:
        return 0.0


def load_signals() -> list:
    if SIGNALS_FILE.exists():
        return json.loads(SIGNALS_FILE.read_text())
    return []


def add_signal(signals: list, ticker: str, entry_price: float, source: str,
               tp_pct: float, sl_pct: float, extra: dict = None):
    if entry_price <= 0:
        print(f"  Skipped {ticker}: no price")
        return
    signals.append({
        "ticker": ticker,
        "signal_date": date.today().isoformat(),
        "entry_price": round(entry_price, 4),
        "source": source,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "check_date": (date.today() + timedelta(days=14)).isoformat(),
        **(extra or {}),
    })
    print(f"  Saved {source}: {ticker} @ {entry_price:.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=["EMA200", "WSB", "EP"])
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.file).read_text())
    except Exception as e:
        print(f"Error reading data: {e}")
        sys.exit(0)

    if not data.get("sent"):
        print("No signal sent, nothing to save.")
        sys.exit(0)

    signals = load_signals()

    if args.source == "EMA200":
        for sig in data.get("big5", []) + data.get("market", []):
            add_signal(signals, sig["ticker"], sig["close"], "EMA200",
                       tp_pct=10.0, sl_pct=5.0,
                       extra={"rel_vol": sig.get("rel_vol"), "pct_above_ema": sig.get("pct_above")})

    elif args.source == "WSB":
        warrant_ticker = data.get("warrant_ticker")
        if warrant_ticker:
            price = get_price(warrant_ticker)
            add_signal(signals, warrant_ticker, price, "WSB", tp_pct=20.0, sl_pct=10.0)

    elif args.source == "EP":
        for ticker in data.get("candidates", []):
            price = get_price(ticker)
            add_signal(signals, ticker, price, "EP", tp_pct=15.0, sl_pct=5.0)

    SIGNALS_FILE.parent.mkdir(exist_ok=True)
    SIGNALS_FILE.write_text(json.dumps(signals, indent=2))
    print(f"Total signals tracked: {len(signals)}")


if __name__ == "__main__":
    main()
