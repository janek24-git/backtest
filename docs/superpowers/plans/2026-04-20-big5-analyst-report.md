# Big5 Analyst Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hedge-fund-style analyst report to the Big5 Swing Backtest page: Claude-generated analysis + downloadable PDF with combo table, equity curve, trade log, and insights.

**Architecture:** Backend `/big5/analyze` calls Claude API with the 8 combo metrics → returns structured analysis text. Frontend `AnalysisSection` renders the text in-page. `Big5Report.tsx` uses `@react-pdf/renderer` to generate a downloadable PDF entirely in-browser.

**Tech Stack:** FastAPI, `anthropic` SDK (already installed), React 19, `@react-pdf/renderer`, TypeScript.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/models/schemas.py` | Add `Big5AnalysisRequest`, `Big5AnalysisResponse` |
| Modify | `backend/app/routers/big5.py` | Add `POST /big5/analyze` route |
| Modify | `frontend/src/api/client.ts` | Add `analyzeBig5` function |
| Modify | `frontend/src/types/index.ts` | Add `Big5AnalysisResponse` type |
| Create | `frontend/src/components/AnalysisSection.tsx` | Fetches analysis, shows text, triggers PDF download |
| Create | `frontend/src/components/Big5Report.tsx` | `@react-pdf/renderer` Document: cover, tables, equity curve, analysis |
| Modify | `frontend/src/pages/Big5Page.tsx` | Show `AnalysisSection` after results load |

---

## Task 1: Backend — `/big5/analyze` endpoint

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/routers/big5.py`

- [ ] **Step 1: Add schemas to `backend/app/models/schemas.py`**

Append at the end of the file:

```python
class Big5AnalysisRequest(BaseModel):
    results: list[Big5ComboResult]
    indicator: str
    period: int
    from_date: str
    to_date: str


class Big5AnalysisResponse(BaseModel):
    analysis: str  # Full markdown-style text, sections separated by \n\n
```

- [ ] **Step 2: Add analyze route to `backend/app/routers/big5.py`**

Add import at top of file:
```python
import os
import anthropic
```

Add import in the schemas import block:
```python
from app.models.schemas import (
    Big5BacktestRequest, Big5BacktestResponse,
    Big5ComboResult, Big5ComboMetrics, Big5Trade,
    Big5AnalysisRequest, Big5AnalysisResponse,
)
```

Append new route at end of file:
```python
@router.post("/analyze", response_model=Big5AnalysisResponse)
async def analyze_big5(req: Big5AnalysisRequest):
    try:
        # Build compact metrics summary for Claude
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
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis_text = message.content[0].text
        return Big5AnalysisResponse(analysis=analysis_text)

    except Exception as e:
        logger.exception("Big5 analyze failed")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: Test the endpoint manually**

Make sure `ANTHROPIC_API_KEY` is set in `backend/.env`. Start backend, then run a Big5 backtest in the browser and check that `/big5/analyze` returns a response (will be wired in Task 3, but can test via curl with dummy data if needed).

- [ ] **Step 4: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add backend/app/models/schemas.py backend/app/routers/big5.py
git commit -m "feat: add /big5/analyze endpoint with Claude hedge fund analysis"
```

---

## Task 2: Install `@react-pdf/renderer`

**Files:**
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install the package**

```bash
cd /Users/janekstrobel/stocks-backtest/frontend
npm install @react-pdf/renderer
```

- [ ] **Step 2: Verify install**

```bash
ls node_modules/@react-pdf/renderer/package.json
```
Expected: file exists.

- [ ] **Step 3: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: install @react-pdf/renderer"
```

---

## Task 3: Create `Big5Report.tsx` — PDF Document

**Files:**
- Create: `frontend/src/components/Big5Report.tsx`

This component uses `@react-pdf/renderer` to produce a 3-page PDF:
- **Page 1:** Header + combo overview table (8 rows)
- **Page 2:** Equity curve SVG (best combo) + round-trip trade table
- **Page 3:** Claude analysis text

- [ ] **Step 1: Create `frontend/src/components/Big5Report.tsx`**

```tsx
import React from 'react';
import {
  Document, Page, Text, View, StyleSheet, Svg, Polyline, Line, Rect,
} from '@react-pdf/renderer';
import type { Big5BacktestResponse } from '../types';

const C = {
  bg: '#0F1117',
  surface: '#1A1D27',
  card: '#1E2130',
  border: '#2A2D3E',
  text: '#E8EAED',
  muted: '#8B8FA8',
  green: '#00C48C',
  red: '#FF4757',
  blue: '#3B4FC8',
  white: '#FFFFFF',
};

const s = StyleSheet.create({
  page: { backgroundColor: C.bg, padding: 36, fontFamily: 'Helvetica', color: C.text },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20, borderBottomWidth: 1, borderBottomColor: C.border, paddingBottom: 12 },
  title: { fontSize: 18, fontFamily: 'Helvetica-Bold', color: C.white },
  subtitle: { fontSize: 9, color: C.muted, marginTop: 3 },
  sectionTitle: { fontSize: 11, fontFamily: 'Helvetica-Bold', color: C.green, marginBottom: 8, marginTop: 16, textTransform: 'uppercase', letterSpacing: 1 },
  tableHeader: { flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 5, paddingHorizontal: 6, borderRadius: 3, marginBottom: 2 },
  tableRow: { flexDirection: 'row', paddingVertical: 4, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.border },
  tableRowBest: { flexDirection: 'row', paddingVertical: 4, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: '#00C48C18' },
  th: { fontSize: 8, color: C.muted, fontFamily: 'Helvetica-Bold' },
  td: { fontSize: 8, color: C.text },
  tdGreen: { fontSize: 8, color: C.green },
  tdRed: { fontSize: 8, color: C.red },
  footer: { position: 'absolute', bottom: 20, left: 36, right: 36, flexDirection: 'row', justifyContent: 'space-between' },
  footerText: { fontSize: 8, color: C.muted },
  analysisSection: { marginBottom: 12 },
  analysisHeader: { fontSize: 11, fontFamily: 'Helvetica-Bold', color: C.green, marginBottom: 4 },
  analysisText: { fontSize: 9, color: C.text, lineHeight: 1.6 },
});

// Column widths for combo table
const COL = { combo: 60, ret: 72, sharpe: 60, wr: 60, dd: 72, trades: 50 };

function comboTableHeader() {
  return (
    <View style={s.tableHeader}>
      <Text style={[s.th, { width: COL.combo }]}>KOMBO</Text>
      <Text style={[s.th, { width: COL.ret }]}>TOTAL RETURN</Text>
      <Text style={[s.th, { width: COL.sharpe }]}>SHARPE</Text>
      <Text style={[s.th, { width: COL.wr }]}>WIN RATE</Text>
      <Text style={[s.th, { width: COL.dd }]}>MAX DRAWDOWN</Text>
      <Text style={[s.th, { width: COL.trades }]}>TRADES</Text>
    </View>
  );
}

function valueColor(v: number) {
  return v >= 0 ? s.tdGreen : s.tdRed;
}

interface ReportProps {
  data: Big5BacktestResponse;
  analysis: string;
}

function buildEquityCurve(kum_values: number[], width: number, height: number): string {
  if (kum_values.length < 2) return '';
  const min = Math.min(...kum_values, 0);
  const max = Math.max(...kum_values, 0);
  const range = max - min || 1;
  const pad = 4;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const points = kum_values.map((v, i) => {
    const x = pad + (i / (kum_values.length - 1)) * w;
    const y = pad + h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return points.join(' ');
}

// Build round trips from trades (same logic as Big5Table.tsx)
function buildRoundTrips(trades: any[]) {
  const trips: any[] = [];
  const open: Map<string, any> = new Map();
  let nr = 1;
  for (const t of trades) {
    if (t.typ === 'KAUF') {
      open.set(t.ticker, t);
    } else {
      const entry = open.get(t.ticker);
      if (entry) {
        trips.push({ nr: nr++, ticker: t.ticker, entry_datum: entry.datum, exit_datum: t.datum, haltdauer: t.haltdauer, entry_preis: entry.open_preis, exit_preis: t.open_preis, perf_pct: t.perf_pct });
        open.delete(t.ticker);
      }
    }
  }
  return trips;
}

// Parse Claude analysis into sections
function parseSections(text: string): { title: string; body: string }[] {
  const sections: { title: string; body: string }[] = [];
  const lines = text.split('\n');
  let current: { title: string; body: string } | null = null;
  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (current) sections.push(current);
      current = { title: line.replace('## ', '').trim(), body: '' };
    } else if (current) {
      current.body += (current.body ? '\n' : '') + line;
    }
  }
  if (current) sections.push(current);
  return sections.filter(s => s.title && s.body.trim());
}

export function Big5Report({ data, analysis }: ReportProps) {
  const best = [...data.results].sort((a, b) => b.metrics.sharpe - a.metrics.sharpe)[0];
  const dateStr = new Date().toLocaleDateString('de-DE');
  const paramStr = `${data.indicator}${data.period} · ${data.from_date} bis ${data.to_date}`;

  // Equity curve: kum_perf_pct values from VERKAUF trades of best combo
  const kumValues = best.trades.filter(t => t.typ === 'VERKAUF').map(t => t.kum_perf_pct);
  const chartW = 520;
  const chartH = 120;
  const equityPoints = buildEquityCurve(kumValues, chartW, chartH);

  const roundTrips = buildRoundTrips(best.trades).slice(0, 30); // max 30 rows for space
  const analysisSections = parseSections(analysis);

  const Footer = () => (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>Big 5 Swing Backtest · {paramStr}</Text>
      <Text style={s.footerText} render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
    </View>
  );

  return (
    <Document title="Big5 Swing Backtest Report" author="Backtest System">
      {/* ── PAGE 1: Header + Combo Table ── */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <View>
            <Text style={s.title}>Big 5 Swing Backtest</Text>
            <Text style={s.subtitle}>S&P 500 Top-5 · Dynamische Marktkapitalisierung · {paramStr}</Text>
          </View>
          <Text style={s.footerText}>{dateStr}</Text>
        </View>

        <Text style={s.sectionTitle}>Kombinations-Übersicht</Text>
        {comboTableHeader()}
        {data.results.map(r => {
          const isBest = r.kombination === best.kombination;
          return (
            <View key={r.kombination} style={isBest ? s.tableRowBest : s.tableRow}>
              <Text style={[s.td, { width: COL.combo, fontFamily: isBest ? 'Helvetica-Bold' : 'Helvetica', color: isBest ? C.green : C.text }]}>{r.kombination}{isBest ? ' ★' : ''}</Text>
              <Text style={[valueColor(r.metrics.total_return), { width: COL.ret }]}>{r.metrics.total_return >= 0 ? '+' : ''}{r.metrics.total_return.toFixed(1)}%</Text>
              <Text style={[valueColor(r.metrics.sharpe), { width: COL.sharpe }]}>{r.metrics.sharpe.toFixed(2)}</Text>
              <Text style={[s.td, { width: COL.wr }]}>{r.metrics.win_rate.toFixed(1)}%</Text>
              <Text style={[s.tdRed, { width: COL.dd }]}>{r.metrics.max_drawdown.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.trades }]}>{r.metrics.num_trades}</Text>
            </View>
          );
        })}

        <View style={{ marginTop: 10, padding: 8, backgroundColor: C.surface, borderRadius: 4 }}>
          <Text style={{ fontSize: 8, color: C.muted }}>
            ★ Beste Kombination nach Sharpe Ratio. Total Return = arithmetische Summe (nicht compounded). Max Drawdown auf kumulierter Equity-Kurve.
          </Text>
        </View>

        <Footer />
      </Page>

      {/* ── PAGE 2: Equity Curve + Trade Log ── */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <Text style={s.title}>Beste Kombination: {best.kombination}</Text>
          <Text style={s.footerText}>{best.metrics.num_trades} Trades · Sharpe {best.metrics.sharpe.toFixed(2)} · {best.metrics.total_return >= 0 ? '+' : ''}{best.metrics.total_return.toFixed(1)}%</Text>
        </View>

        <Text style={s.sectionTitle}>Equity-Kurve (kumulierte Performance)</Text>
        <View style={{ backgroundColor: C.surface, borderRadius: 4, padding: 8, marginBottom: 4 }}>
          {equityPoints ? (
            <Svg width={chartW} height={chartH} viewBox={`0 0 ${chartW} ${chartH}`}>
              {/* Zero line */}
              {(() => {
                const min = Math.min(...kumValues, 0);
                const max = Math.max(...kumValues, 0);
                const range = max - min || 1;
                const zeroY = 4 + (chartH - 8) - ((0 - min) / range) * (chartH - 8);
                return <Line x1="4" y1={zeroY.toFixed(1)} x2={(chartW - 4).toString()} y2={zeroY.toFixed(1)} stroke={C.border} strokeWidth="1" />;
              })()}
              <Polyline points={equityPoints} stroke={C.green} strokeWidth="1.5" fill="none" />
            </Svg>
          ) : (
            <Text style={{ fontSize: 9, color: C.muted }}>Keine Daten</Text>
          )}
        </View>

        <Text style={s.sectionTitle}>Trade-Log — Round Trips (max. 30)</Text>
        <View style={{ flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 4, paddingHorizontal: 4, borderRadius: 3, marginBottom: 2 }}>
          {['Nr', 'Ticker', 'Kauf', 'Verkauf', 'Tage', 'Kauf €', 'Verk. €', 'Perf.'].map((h, i) => (
            <Text key={h} style={[s.th, { width: [30, 45, 72, 72, 32, 58, 58, 55][i] }]}>{h}</Text>
          ))}
        </View>
        {roundTrips.map(rt => (
          <View key={rt.nr} style={{ flexDirection: 'row', paddingVertical: 3, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={[s.td, { width: 30 }]}>{rt.nr}</Text>
            <Text style={[s.td, { width: 45 }]}>{rt.ticker}</Text>
            <Text style={[s.td, { width: 72 }]}>{rt.entry_datum}</Text>
            <Text style={[s.td, { width: 72 }]}>{rt.exit_datum}</Text>
            <Text style={[s.td, { width: 32 }]}>{rt.haltdauer}d</Text>
            <Text style={[s.td, { width: 58 }]}>${rt.entry_preis.toFixed(2)}</Text>
            <Text style={[s.td, { width: 58 }]}>${rt.exit_preis.toFixed(2)}</Text>
            <Text style={[rt.perf_pct >= 0 ? s.tdGreen : s.tdRed, { width: 55 }]}>{rt.perf_pct >= 0 ? '+' : ''}{rt.perf_pct.toFixed(1)}%</Text>
          </View>
        ))}

        <Footer />
      </Page>

      {/* ── PAGE 3: Claude Analysis ── */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <Text style={s.title}>Analyst Report</Text>
          <Text style={s.footerText}>Generiert via Claude AI · {dateStr}</Text>
        </View>

        {analysisSections.map(sec => (
          <View key={sec.title} style={s.analysisSection} wrap={false}>
            <Text style={s.analysisHeader}>{sec.title}</Text>
            <Text style={s.analysisText}>{sec.body.trim()}</Text>
          </View>
        ))}

        <Footer />
      </Page>
    </Document>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/components/Big5Report.tsx
git commit -m "feat: add Big5Report PDF document component"
```

---

## Task 4: Add types and API client function

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add `Big5AnalysisResponse` to `frontend/src/types/index.ts`**

Append at end:
```ts
export interface Big5AnalysisResponse {
  analysis: string;
}
```

- [ ] **Step 2: Add `analyzeBig5` to `frontend/src/api/client.ts`**

Add import at top (if not already):
```ts
import type { BacktestResponse, AIAnalysis, Big5BacktestResponse, Big5AnalysisResponse } from '../types';
```

Append function:
```ts
export async function analyzeBig5(data: Big5BacktestResponse): Promise<Big5AnalysisResponse> {
  const { data: res } = await api.post<Big5AnalysisResponse>('/big5/analyze', {
    results: data.results,
    indicator: data.indicator,
    period: data.period,
    from_date: data.from_date,
    to_date: data.to_date,
  });
  return res;
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat: add analyzeBig5 API client and type"
```

---

## Task 5: Create `AnalysisSection.tsx`

**Files:**
- Create: `frontend/src/components/AnalysisSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react';
import { pdf } from '@react-pdf/renderer';
import { analyzeBig5 } from '../api/client';
import { Big5Report } from './Big5Report';
import type { Big5BacktestResponse } from '../types';

interface Props {
  data: Big5BacktestResponse;
}

export function AnalysisSection({ data }: Props) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeBig5(data);
      setAnalysis(res.analysis);
    } catch (e: any) {
      setError(e?.message ?? 'Analyse fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    if (!analysis) return;
    setPdfLoading(true);
    try {
      const blob = await pdf(<Big5Report data={data} analysis={analysis} />).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Big5_AnalystReport_${data.indicator}${data.period}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setPdfLoading(false);
    }
  }

  // Render analysis text: split by ## headers
  function renderAnalysis(text: string) {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('## ')) {
        return (
          <p key={i} className="text-sm font-semibold mt-5 mb-1" style={{ color: '#00C48C' }}>
            {line.replace('## ', '')}
          </p>
        );
      }
      if (!line.trim()) return <div key={i} className="h-1" />;
      return (
        <p key={i} className="text-xs leading-relaxed" style={{ color: '#C8CAD8' }}>
          {line}
        </p>
      );
    });
  }

  return (
    <div className="rounded-lg p-4 mt-4" style={{ background: '#1A1D27' }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>Analyst Report</p>
        <div className="flex gap-2">
          {analysis && (
            <button
              onClick={handleDownloadPdf}
              disabled={pdfLoading}
              className="px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50"
              style={{ background: '#3B4FC8', color: '#fff' }}
            >
              {pdfLoading ? 'Generiert...' : '↓ PDF herunterladen'}
            </button>
          )}
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50"
            style={{ background: '#00C48C', color: '#000' }}
          >
            {loading ? 'Analysiert...' : analysis ? 'Neu analysieren' : 'Analyse starten'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-2 rounded text-xs mb-3" style={{ background: '#FF475720', color: '#FF4757' }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="p-4 text-center text-xs" style={{ color: '#8B8FA8' }}>
          Claude analysiert die Ergebnisse wie ein Hedge-Fund-Manager...
        </div>
      )}

      {analysis && !loading && (
        <div className="mt-2 p-3 rounded" style={{ background: '#151720' }}>
          {renderAnalysis(analysis)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/components/AnalysisSection.tsx
git commit -m "feat: add AnalysisSection component with Claude analysis and PDF download"
```

---

## Task 6: Wire into `Big5Page.tsx`

**Files:**
- Modify: `frontend/src/pages/Big5Page.tsx`

- [ ] **Step 1: Add import at top of `Big5Page.tsx`**

```tsx
import { AnalysisSection } from '../components/AnalysisSection';
```

- [ ] **Step 2: Add `<AnalysisSection>` after the results block**

In the `{results && (...)}` block, after the closing `</div>` of the combo results container, add:

```tsx
<AnalysisSection data={results} />
```

So the bottom of the results section looks like:
```tsx
          </div>
        </div>
        <AnalysisSection data={results} />
      </>
    )}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/janekstrobel/stocks-backtest/frontend
npx tsc --noEmit
```
Expected: no output (no errors).

- [ ] **Step 4: Commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add frontend/src/pages/Big5Page.tsx
git commit -m "feat: show AnalysisSection on Big5Page after backtest results"
```

---

## Task 7: End-to-end test

- [ ] **Step 1: Start backend**

```bash
cd /Users/janekstrobel/stocks-backtest/backend
source venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd /Users/janekstrobel/stocks-backtest/frontend
npm run dev
```

- [ ] **Step 3: Manual test flow**

1. Open `http://localhost:5200`
2. Run Big5 Backtest (EMA200) — wait for results
3. Click "Analyse starten" — wait ~10s for Claude response
4. Verify analysis text appears, split into sections with green headers
5. Click "↓ PDF herunterladen" — verify PDF downloads
6. Open PDF: check Page 1 (combo table), Page 2 (equity curve + trades), Page 3 (analysis)

- [ ] **Step 4: Final commit**

```bash
cd /Users/janekstrobel/stocks-backtest
git add -A
git commit -m "feat: complete Big5 analyst report with Claude analysis and PDF export"
```
