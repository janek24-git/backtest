#!/usr/bin/env python3
import json
import os
import httpx
import yfinance as yf
from datetime import date
from pathlib import Path

SIGNALS_FILE = Path(__file__).parent.parent / "signals" / "signals.json"


def get_price(ticker: str) -> float:
    try:
        raw = yf.download(ticker, period="2d", progress=False, auto_adjust=True)
        if raw.empty:
            return 0.0
        return float(raw["Close"].iloc[-1])
    except Exception:
        return 0.0


def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials missing")
        return
    httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def main():
    if not SIGNALS_FILE.exists():
        print("No signals file.")
        return

    signals = json.loads(SIGNALS_FILE.read_text())
    today = date.today().isoformat()

    due = [s for s in signals if s["check_date"] <= today]
    remaining = [s for s in signals if s["check_date"] > today]

    if not due:
        print("No signals due today.")
        return

    lines = [f"📊 <b>14-Tage Performance — {today}</b>", ""]
    wins, losses = 0, 0

    for s in due:
        current = get_price(s["ticker"])
        if current <= 0:
            print(f"  No price for {s['ticker']}, skipping")
            remaining.append(s)
            continue

        entry = s["entry_price"]
        perf = round((current - entry) / entry * 100, 2)
        tp = entry * (1 + s["tp_pct"] / 100)
        sl = entry * (1 - s["sl_pct"] / 100)

        if current >= tp:
            status = "✅ TP"
            wins += 1
        elif current <= sl:
            status = "❌ SL"
            losses += 1
        else:
            status = "⏳ Offen"
            if perf >= 0:
                wins += 1
            else:
                losses += 1

        icon = "🟢" if perf >= 0 else "🔴"
        lines += [
            "━━━━━━━━━━━━━━━━━━━━",
            f"{icon} <b>{s['ticker']}</b>  ·  {s['source']}  ·  {status}",
            f"📅 {s['signal_date']} → {today}",
            f"💰 ${entry:.2f} → ${current:.2f}",
            f"📐 <b>{perf:+.2f}%</b>  (TP +{s['tp_pct']}% / SL -{s['sl_pct']}%)",
            "",
        ]

    total = wins + losses
    win_rate = round(wins / total * 100) if total else 0
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏆 Win Rate: <b>{win_rate}%</b>  ({wins}/{total})",
    ]

    send_telegram("\n".join(lines))
    print(f"Report sent: {len(due)} signals, {wins}W/{losses}L")

    SIGNALS_FILE.write_text(json.dumps(remaining, indent=2))
    print(f"Removed {len(due)} processed, {len(remaining)} remaining.")


if __name__ == "__main__":
    main()
