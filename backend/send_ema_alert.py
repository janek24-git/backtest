#!/usr/bin/env python3
"""
Standalone cron script: checks Big 5 EMA200 crossovers and sends Telegram alert.

Usage:
    python send_ema_alert.py           # only sends if crossover detected
    python send_ema_alert.py --force   # always sends (daily status update)

Cron example (täglich 22:00 Uhr nach US-Marktschluss):
    0 22 * * 1-5 cd /path/to/backend && ./venv/bin/python send_ema_alert.py --force
"""

import asyncio
import sys
import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.telegram_alerts import send_telegram_alert


async def main():
    print("Checking EMA200 bullish crossovers (Big5 + Polygon top volume)...")
    result = await send_telegram_alert()
    if result["sent"]:
        print(f"Alert sent! {result['signals']} bullish crossover(s):")
        for s in result.get("big5", []):
            print(f"  [Big5] {s['ticker']}: +{s['pct_above']}% above EMA200, vol {s['rel_vol']}×")
        for s in result.get("market", []):
            print(f"  [Market] {s['ticker']}: +{s['pct_above']}% above EMA200, vol {s['rel_vol']}×")
    else:
        print("No bullish crossovers today — no message sent.")


if __name__ == "__main__":
    asyncio.run(main())
