import os
import logging
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.journal_db import (
    init_db, add_trade, list_trades, update_trade, delete_trade, compute_stats
)

logger = logging.getLogger(__name__)
router = APIRouter()
init_db()


class TradeIn(BaseModel):
    datum: str
    ticker: str
    richtung: str  # LONG | SHORT
    einstieg: float
    ausstieg: Optional[float] = None
    stueck: float = 1
    signal: Optional[str] = None
    notiz: Optional[str] = None


class TradeUpdate(BaseModel):
    datum: Optional[str] = None
    ticker: Optional[str] = None
    richtung: Optional[str] = None
    einstieg: Optional[float] = None
    ausstieg: Optional[float] = None
    stueck: Optional[float] = None
    signal: Optional[str] = None
    notiz: Optional[str] = None


@router.get("/trades")
def get_trades():
    trades = list_trades()
    stats = compute_stats(trades)
    return {"trades": trades, "stats": stats}


@router.post("/trades")
def create_trade(body: TradeIn):
    try:
        trade = add_trade(
            datum=body.datum, ticker=body.ticker, richtung=body.richtung,
            einstieg=body.einstieg, ausstieg=body.ausstieg, stueck=body.stueck,
            signal=body.signal, notiz=body.notiz,
        )
        return trade
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/trades/{trade_id}")
def patch_trade(trade_id: str, body: TradeUpdate):
    updated = update_trade(trade_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Trade not found")
    return updated


@router.delete("/trades/{trade_id}")
def remove_trade(trade_id: str):
    if not delete_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"ok": True}


@router.post("/analyze")
def analyze_journal():
    trades = list_trades()
    stats = compute_stats(trades)
    closed = [t for t in trades if t.get("ausstieg") is not None]
    if len(closed) < 2:
        raise HTTPException(status_code=400, detail="Mindestens 2 abgeschlossene Trades für Analyse nötig")

    trade_lines = []
    for t in closed[-30:]:  # max 30 für Kontext
        sign = 1 if t["richtung"] == "LONG" else -1
        pct = sign * (t["ausstieg"] - t["einstieg"]) / t["einstieg"] * 100
        trade_lines.append(
            f"{t['datum']} | {t['ticker']} {t['richtung']} | "
            f"Ein: ${t['einstieg']} → Aus: ${t['ausstieg']} | "
            f"Stück: {t['stueck']} | {pct:+.2f}% | "
            f"Signal: {t.get('signal') or '–'} | Notiz: {t.get('notiz') or '–'}"
        )

    prompt = f"""Du bist ein erfahrener Trading-Coach. Analysiere dieses Trading-Journal und erkenne Muster.

## Stats
- Trades gesamt: {stats['closed_trades']} abgeschlossen, {stats['open_trades']} offen
- Win Rate: {stats['win_rate']}%
- Ø Return: {stats['avg_return_pct']}%
- Bester Trade: +{stats['best_trade_pct']}%
- Schlechtester Trade: {stats['worst_trade_pct']}%
- Gesamt P&L: ${stats['total_pnl']}

## Trades (neueste zuerst)
{chr(10).join(trade_lines)}

## Dein Auftrag
Antworte auf Deutsch. Kurz, direkt, wie ein Profi-Coach — keine Floskeln.

**Mustererkennung:** Welche Ticker, Signale oder Marktphasen performen gut vs. schlecht?
**Verhaltensfehler:** Gibt es erkennbare Fehler (zu früh raus, zu spät rein, bestimmte Sektoren meiden)?
**Positionsgröße:** Für €1000 Kapital pro Trade (aggressiv, kein Stop-Loss-Filter): wie viele Stück sollte ich kaufen und bei welchem Preisniveau wäre das sinnvoll basierend auf meiner Trefferquote?
**1 konkrete Maßnahme:** Was soll ich ab morgen anders machen?

Max 250 Wörter."""

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"analysis": msg.content[0].text, "stats": stats}
    except Exception as e:
        logger.exception("Journal analysis failed")
        raise HTTPException(status_code=500, detail=str(e))
