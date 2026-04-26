"""
SQLite-basiertes Journal für Live-Trades.
DB-Datei: backend/journal.db
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent.parent.parent / "journal.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          TEXT PRIMARY KEY,
                datum       TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                richtung    TEXT NOT NULL CHECK(richtung IN ('LONG','SHORT')),
                einstieg    REAL NOT NULL,
                ausstieg    REAL,
                stueck      REAL NOT NULL DEFAULT 1,
                signal      TEXT,
                notiz       TEXT,
                created_at  TEXT DEFAULT (date('now'))
            )
        """)


def add_trade(datum: str, ticker: str, richtung: str, einstieg: float,
              ausstieg: float | None, stueck: float,
              signal: str | None, notiz: str | None) -> dict:
    trade_id = str(uuid.uuid4())
    with _conn() as con:
        con.execute(
            """INSERT INTO trades
               (id, datum, ticker, richtung, einstieg, ausstieg, stueck, signal, notiz)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (trade_id, datum, ticker.upper(), richtung.upper(),
             einstieg, ausstieg, stueck, signal, notiz)
        )
    return get_trade(trade_id)


def get_trade(trade_id: str) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    return dict(row) if row else {}


def list_trades(limit: int = 100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trades ORDER BY datum DESC, created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_trade(trade_id: str, **fields) -> dict:
    allowed = {"datum", "ticker", "richtung", "einstieg", "ausstieg", "stueck", "signal", "notiz"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_trade(trade_id)
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [trade_id]
    with _conn() as con:
        con.execute(f"UPDATE trades SET {cols} WHERE id=?", vals)
    return get_trade(trade_id)


def delete_trade(trade_id: str) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    return cur.rowcount > 0


def compute_stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("ausstieg") is not None]
    if not closed:
        return {
            "total_trades": len(trades),
            "closed_trades": 0,
            "open_trades": len(trades),
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "equity_curve": [],
        }

    returns = []
    for t in closed:
        sign = 1 if t["richtung"] == "LONG" else -1
        pct = sign * (t["ausstieg"] - t["einstieg"]) / t["einstieg"] * 100
        pnl = sign * (t["ausstieg"] - t["einstieg"]) * t["stueck"]
        returns.append({"pct": pct, "pnl": pnl, "datum": t["datum"], "ticker": t["ticker"]})

    returns.sort(key=lambda x: x["datum"])

    total_pnl = sum(r["pnl"] for r in returns)
    pcts = [r["pct"] for r in returns]
    winners = [p for p in pcts if p > 0]

    # Equity curve (kumuliert %)
    equity = 0.0
    curve = []
    for r in returns:
        equity += r["pct"]
        curve.append({"date": r["datum"], "ticker": r["ticker"], "equity": round(equity, 2)})

    return {
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(trades) - len(closed),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(len(winners) / len(pcts) * 100, 1),
        "avg_return_pct": round(sum(pcts) / len(pcts), 2),
        "best_trade_pct": round(max(pcts), 2),
        "worst_trade_pct": round(min(pcts), 2),
        "equity_curve": curve,
    }
