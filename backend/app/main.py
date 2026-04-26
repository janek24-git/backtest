# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routers import backtest, universe, big5, journal

app = FastAPI(title="Backtesting Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5200", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(universe.router, prefix="/universe", tags=["universe"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(big5.router, prefix="/big5", tags=["big5"])
app.include_router(journal.router, prefix="/journal", tags=["journal"])


@app.get("/health")
def health():
    return {"status": "ok"}
