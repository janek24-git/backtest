import os
import sqlite3
import uuid
import yfinance as yf
from pathlib import Path
from datetime import date, timedelta

_env_path = os.environ.get("FORWARD_DB_PATH")
DB_PATH = Path(_env_path) if _env_path else Path(__file__).parent.parent.parent / "forward.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS forward_trades (
                id            TEXT PRIMARY KEY,
                ticker        TEXT NOT NULL,
                signal_date   TEXT NOT NULL,
                entry_price   REAL NOT NULL,
                ema200        REAL NOT NULL,
                tp_price      REAL NOT NULL,
                sl_price      REAL NOT NULL,
                tp_pct        REAL NOT NULL DEFAULT 10.0,
                sl_pct        REAL NOT NULL DEFAULT 5.0,
                status        TEXT NOT NULL DEFAULT 'OPEN',
                exit_price    REAL,
                exit_date     TEXT,
                result_pct    REAL,
                source        TEXT NOT NULL DEFAULT 'MARKET',
                signal_type   TEXT NOT NULL DEFAULT 'EMA200_CROSS',
                rel_vol       REAL,
                pct_above_ema REAL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)


def _get(trade_id: str) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM forward_trades WHERE id=?", (trade_id,)).fetchone()
    return dict(row) if row else {}


def add_trade(
    ticker: str,
    signal_date: str,
    entry_price: float,
    ema200: float,
    tp_pct: float = 10.0,
    sl_pct: float = 5.0,
    source: str = "MARKET",
    rel_vol: float | None = None,
    pct_above_ema: float | None = None,
) -> dict:
    trade_id = str(uuid.uuid4())
    tp_price = round(entry_price * (1 + tp_pct / 100), 4)
    sl_price = round(entry_price * (1 - sl_pct / 100), 4)
    with _conn() as con:
        con.execute(
            """INSERT INTO forward_trades
               (id, ticker, signal_date, entry_price, ema200, tp_price, sl_price,
                tp_pct, sl_pct, source, rel_vol, pct_above_ema)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trade_id, ticker.upper(), signal_date, entry_price, ema200,
             tp_price, sl_price, tp_pct, sl_pct, source, rel_vol, pct_above_ema),
        )
    return _get(trade_id)


def list_trades(status: str | None = None, limit: int = 200) -> list[dict]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM forward_trades WHERE status=? ORDER BY signal_date DESC, created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM forward_trades ORDER BY signal_date DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def update_trade(trade_id: str, **fields) -> dict:
    allowed = {"ticker", "signal_date", "entry_price", "ema200", "tp_price", "sl_price",
               "tp_pct", "sl_pct", "status", "exit_price", "exit_date", "result_pct",
               "source", "rel_vol", "pct_above_ema"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return _get(trade_id)
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [trade_id]
    with _conn() as con:
        con.execute(f"UPDATE forward_trades SET {cols} WHERE id=?", vals)
    return _get(trade_id)


def close_trade(trade_id: str, exit_price: float, exit_date: str, status: str) -> dict:
    trade = _get(trade_id)
    if not trade:
        return {}
    result_pct = round((exit_price - trade["entry_price"]) / trade["entry_price"] * 100, 2)
    return update_trade(trade_id, exit_price=exit_price, exit_date=exit_date,
                        status=status, result_pct=result_pct)


def delete_trade(trade_id: str) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM forward_trades WHERE id=?", (trade_id,))
    return cur.rowcount > 0


def check_and_update_exits() -> list[dict]:
    open_trades = list_trades(status="OPEN")
    closed = []
    today = date.today().isoformat()
    for trade in open_trades:
        ticker = trade["ticker"]
        try:
            from_date = (date.today() - timedelta(days=5)).isoformat()
            raw = yf.download(ticker, start=from_date, progress=False, auto_adjust=True)
            if raw.empty:
                continue
            if hasattr(raw.columns, "droplevel"):
                try:
                    raw.columns = raw.columns.droplevel(1)
                except Exception:
                    pass
            current_price = float(raw["Close"].iloc[-1])
            tp = trade["tp_price"]
            sl = trade["sl_price"]
            if current_price >= tp:
                closed.append(close_trade(trade["id"], current_price, today, "TP_HIT"))
            elif current_price <= sl:
                closed.append(close_trade(trade["id"], current_price, today, "SL_HIT"))
        except Exception:
            continue
    return closed
