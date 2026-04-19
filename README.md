# Backtest Terminal

EMA200 backtesting platform for NAS100 Top5/10/20.

## Local Development

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your MASSIVE_API_KEY + ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Deploy

- Backend → Railway: set env vars MASSIVE_API_KEY, ANTHROPIC_API_KEY, MASSIVE_BASE_URL
- Frontend → Vercel: update `vercel.json` with Railway URL, then `vercel --prod`

## Data

Powered by Massive (ex-Polygon.io). Requires paid API key (~$29/mo).
Daily OHLCV, adjusted for splits/dividends.
