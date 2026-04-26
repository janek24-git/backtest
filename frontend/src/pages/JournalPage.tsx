import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { JournalTrade, JournalStats, JournalEquityPoint } from '../types';

const API = '/api';

async function fetchJournal(): Promise<{ trades: JournalTrade[]; stats: JournalStats }> {
  const r = await fetch(`${API}/journal/trades`);
  return r.json();
}

async function addTrade(body: Omit<JournalTrade, 'id'>): Promise<JournalTrade> {
  const r = await fetch(`${API}/journal/trades`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return r.json();
}

async function patchTrade(id: string, body: Partial<JournalTrade>): Promise<JournalTrade> {
  const r = await fetch(`${API}/journal/trades/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return r.json();
}

async function deleteTrade(id: string): Promise<void> {
  await fetch(`${API}/journal/trades/${id}`, { method: 'DELETE' });
}

async function analyzeJournal(): Promise<{ analysis: string; stats: JournalStats }> {
  const r = await fetch(`${API}/journal/analyze`, { method: 'POST' });
  if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
  return r.json();
}

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg p-4 flex flex-col gap-1" style={{ background: '#1A1D27' }}>
      <p className="text-xs" style={{ color: '#8B8FA8' }}>{label}</p>
      <p className="text-xl font-mono font-bold" style={{ color: color ?? '#E8EAED' }}>{value}</p>
    </div>
  );
}

// ── Equity curve ─────────────────────────────────────────────────────────────
function JournalEquityCurve({ curve }: { curve: JournalEquityPoint[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || curve.length === 0) return;
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 220,
      layout: { background: { type: ColorType.Solid, color: '#1A1D27' }, textColor: '#8B8FA8' },
      grid: { vertLines: { color: '#2A2D3E' }, horzLines: { color: '#2A2D3E' } },
      timeScale: { borderColor: '#2A2D3E' },
      rightPriceScale: { borderColor: '#2A2D3E' },
    });
    const series = chart.addSeries(LineSeries, {
      color: '#00C48C', lineWidth: 2, priceFormat: { type: 'custom', formatter: (v: number) => `${v.toFixed(1)}%` },
    });
    series.setData(curve.map(p => ({ time: p.date as any, value: p.equity })));
    chart.timeScale().fitContent();
    const obs = new ResizeObserver(() => chart.applyOptions({ width: ref.current!.clientWidth }));
    obs.observe(ref.current);
    return () => { chart.remove(); obs.disconnect(); };
  }, [curve]);
  if (curve.length === 0) return (
    <div className="rounded-lg flex items-center justify-center" style={{ background: '#1A1D27', height: 220 }}>
      <p className="text-sm" style={{ color: '#8B8FA8' }}>Noch keine abgeschlossenen Trades</p>
    </div>
  );
  return <div ref={ref} className="rounded-lg overflow-hidden" style={{ background: '#1A1D27' }} />;
}

// ── Add/Edit modal ────────────────────────────────────────────────────────────
const EMPTY_FORM = {
  datum: new Date().toISOString().slice(0, 10),
  ticker: '', richtung: 'LONG' as 'LONG' | 'SHORT',
  einstieg: '', ausstieg: '', stueck: '1', signal: '', notiz: '',
};

function TradeModal({ initial, onSave, onClose }: {
  initial?: JournalTrade;
  onSave: (data: any) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState(initial ? {
    datum: initial.datum, ticker: initial.ticker, richtung: initial.richtung,
    einstieg: String(initial.einstieg), ausstieg: initial.ausstieg ? String(initial.ausstieg) : '',
    stueck: String(initial.stueck), signal: initial.signal ?? '', notiz: initial.notiz ?? '',
  } : EMPTY_FORM);

  const set = (k: string) => (e: any) => setForm(f => ({ ...f, [k]: e.target.value }));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave({
      datum: form.datum, ticker: form.ticker.toUpperCase(), richtung: form.richtung,
      einstieg: parseFloat(form.einstieg),
      ausstieg: form.ausstieg ? parseFloat(form.ausstieg) : null,
      stueck: parseFloat(form.stueck) || 1,
      signal: form.signal || null, notiz: form.notiz || null,
    });
  }

  const inputStyle = {
    background: '#0F1117', color: '#E8EAED', border: '1px solid #2A2D3E',
    borderRadius: 6, padding: '8px 10px', width: '100%', fontSize: 13,
  };
  const labelStyle = { color: '#8B8FA8', fontSize: 11, marginBottom: 4, display: 'block' as const };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="rounded-xl p-6 w-full max-w-md" style={{ background: '#1A1D27', border: '1px solid #2A2D3E' }}>
        <h2 className="text-base font-semibold mb-4" style={{ color: '#E8EAED' }}>
          {initial ? 'Trade bearbeiten' : 'Neuer Trade'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle}>Datum</label>
              <input type="date" value={form.datum} onChange={set('datum')} style={inputStyle} required />
            </div>
            <div>
              <label style={labelStyle}>Ticker</label>
              <input value={form.ticker} onChange={set('ticker')} placeholder="AAPL" style={inputStyle} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle}>Richtung</label>
              <select value={form.richtung} onChange={set('richtung')} style={inputStyle}>
                <option value="LONG">LONG</option>
                <option value="SHORT">SHORT</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Stück</label>
              <input type="number" value={form.stueck} onChange={set('stueck')} style={inputStyle} min="0.001" step="any" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={labelStyle}>Einstieg $</label>
              <input type="number" value={form.einstieg} onChange={set('einstieg')} step="any" style={inputStyle} required />
            </div>
            <div>
              <label style={labelStyle}>Ausstieg $ <span style={{ color: '#555' }}>(opt.)</span></label>
              <input type="number" value={form.ausstieg} onChange={set('ausstieg')} step="any" style={inputStyle} placeholder="offen" />
            </div>
          </div>
          <div>
            <label style={labelStyle}>Signal</label>
            <input value={form.signal} onChange={set('signal')} placeholder="EMA200-Crossover / Vol-Spike / Manual …" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Notiz</label>
            <textarea value={form.notiz} onChange={set('notiz')} rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="Begründung, Marktlage, Fehler …" />
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" className="flex-1 py-2 rounded font-medium text-sm" style={{ background: '#00C48C', color: '#000' }}>
              Speichern
            </button>
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded text-sm" style={{ background: '#2A2D3E', color: '#8B8FA8' }}>
              Abbrechen
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Analysis panel ────────────────────────────────────────────────────────────
function AnalysisPanel({ analysis, onClose }: { analysis: string; onClose: () => void }) {
  return (
    <div className="rounded-xl p-5" style={{ background: '#1A1D27', border: '1px solid #3B4FC8' }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold" style={{ color: '#E8EAED' }}>Claude — Live-Analyse</p>
        <button onClick={onClose} className="text-xs" style={{ color: '#8B8FA8' }}>✕ Schließen</button>
      </div>
      <div className="text-sm whitespace-pre-wrap leading-relaxed" style={{ color: '#C8CAD8' }}>
        {analysis}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function JournalPage() {
  const navigate = useNavigate();
  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [modal, setModal] = useState<'add' | JournalTrade | null>(null);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  async function load() {
    const d = await fetchJournal();
    setTrades(d.trades);
    setStats(d.stats);
  }

  useEffect(() => { load(); }, []);

  async function handleSave(data: any) {
    if (modal === 'add') {
      await addTrade(data);
    } else if (modal && typeof modal === 'object') {
      await patchTrade(modal.id, data);
    }
    setModal(null);
    load();
  }

  async function handleDelete(id: string) {
    if (!confirm('Trade löschen?')) return;
    await deleteTrade(id);
    load();
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const r = await analyzeJournal();
      setAnalysis(r.analysis);
    } catch (e: any) {
      setAnalyzeError(e.message);
    } finally {
      setAnalyzing(false);
    }
  }

  // Compute P&L per trade for display
  function tradePnl(t: JournalTrade): number | null {
    if (t.ausstieg == null) return null;
    const sign = t.richtung === 'LONG' ? 1 : -1;
    return sign * (t.ausstieg - t.einstieg) * t.stueck;
  }
  function tradePct(t: JournalTrade): number | null {
    if (t.ausstieg == null) return null;
    const sign = t.richtung === 'LONG' ? 1 : -1;
    return sign * (t.ausstieg - t.einstieg) / t.einstieg * 100;
  }

  // Position size for €1000 aggressive (full position, 2% stop implied)
  function positionSize(t: JournalTrade): string {
    if (!t.einstieg) return '–';
    const shares = Math.floor(1000 / t.einstieg);
    return `${shares} Stück ≈ €${(shares * t.einstieg).toFixed(0)}`;
  }

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/')} className="text-sm" style={{ color: '#8B8FA8' }}>← Big 5</button>
            <div>
              <h1 className="text-xl font-semibold" style={{ color: '#E8EAED' }}>Trading Journal</h1>
              <p className="text-xs" style={{ color: '#8B8FA8' }}>Live Logbuch · EMA200 Strategie</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
              style={{ background: '#3B4FC8', color: '#fff' }}
            >
              {analyzing ? 'Analysiert …' : '🧠 Live analysieren'}
            </button>
            <button
              onClick={() => setModal('add')}
              className="px-4 py-2 rounded text-sm font-medium"
              style={{ background: '#00C48C', color: '#000' }}
            >
              + Trade
            </button>
          </div>
        </div>

        {/* Stats + Chart */}
        {stats && (
          <div className="grid grid-cols-12 gap-4">
            {/* Left: Stats */}
            <div className="col-span-12 lg:col-span-4 grid grid-cols-2 gap-3 content-start">
              <StatCard label="Gesamt P&L" value={`${stats.total_pnl >= 0 ? '+' : ''}$${stats.total_pnl.toFixed(0)}`}
                color={stats.total_pnl >= 0 ? '#00C48C' : '#FF4757'} />
              <StatCard label="Win Rate" value={`${stats.win_rate}%`}
                color={stats.win_rate >= 50 ? '#00C48C' : '#FF4757'} />
              <StatCard label="Ø Return" value={`${stats.avg_return_pct >= 0 ? '+' : ''}${stats.avg_return_pct}%`}
                color={stats.avg_return_pct >= 0 ? '#00C48C' : '#FF4757'} />
              <StatCard label="Trades" value={`${stats.closed_trades} / ${stats.total_trades}`} />
              <StatCard label="Bester Trade" value={`+${stats.best_trade_pct}%`} color="#00C48C" />
              <StatCard label="Schlechtester" value={`${stats.worst_trade_pct}%`} color="#FF4757" />
            </div>
            {/* Right: Equity curve */}
            <div className="col-span-12 lg:col-span-8">
              <p className="text-xs mb-2" style={{ color: '#8B8FA8' }}>Kumulierte Performance (%)</p>
              <JournalEquityCurve curve={stats.equity_curve} />
            </div>
          </div>
        )}

        {/* Analysis */}
        {analyzeError && (
          <div className="p-3 rounded text-sm" style={{ background: '#FF475720', color: '#FF4757' }}>{analyzeError}</div>
        )}
        {analysis && <AnalysisPanel analysis={analysis} onClose={() => setAnalysis(null)} />}

        {/* Trades table */}
        <div className="rounded-xl overflow-hidden" style={{ background: '#1A1D27' }}>
          <div className="p-4 border-b" style={{ borderColor: '#2A2D3E' }}>
            <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>Recent Trades</p>
          </div>
          {trades.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-sm" style={{ color: '#8B8FA8' }}>Noch keine Trades. Klicke „+ Trade" um zu beginnen.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ color: '#8B8FA8', borderBottom: '1px solid #2A2D3E' }}>
                    <th className="text-left p-3">Datum</th>
                    <th className="text-left p-3">Ticker</th>
                    <th className="text-left p-3">Richtung</th>
                    <th className="text-right p-3">Einstieg</th>
                    <th className="text-right p-3">Ausstieg</th>
                    <th className="text-right p-3">Stück</th>
                    <th className="text-right p-3">P&L</th>
                    <th className="text-right p-3">%</th>
                    <th className="text-left p-3">Pos. €1k</th>
                    <th className="text-left p-3">Signal</th>
                    <th className="text-left p-3">Notiz</th>
                    <th className="p-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map(t => {
                    const pnl = tradePnl(t);
                    const pct = tradePct(t);
                    const isOpen = t.ausstieg == null;
                    return (
                      <tr key={t.id} style={{ borderBottom: '1px solid #2A2D3E' }}
                        className="hover:bg-[#1E2130] transition-colors">
                        <td className="p-3 font-mono" style={{ color: '#C8CAD8' }}>{t.datum}</td>
                        <td className="p-3 font-mono font-bold" style={{ color: '#E8EAED' }}>{t.ticker}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded text-xs font-medium"
                            style={t.richtung === 'LONG'
                              ? { background: '#00C48C20', color: '#00C48C' }
                              : { background: '#FF475720', color: '#FF4757' }}>
                            {t.richtung}
                          </span>
                        </td>
                        <td className="p-3 text-right font-mono" style={{ color: '#C8CAD8' }}>${t.einstieg}</td>
                        <td className="p-3 text-right font-mono" style={{ color: isOpen ? '#F5A623' : '#C8CAD8' }}>
                          {isOpen ? 'offen' : `$${t.ausstieg}`}
                        </td>
                        <td className="p-3 text-right font-mono" style={{ color: '#8B8FA8' }}>{t.stueck}</td>
                        <td className="p-3 text-right font-mono" style={{ color: pnl == null ? '#8B8FA8' : pnl >= 0 ? '#00C48C' : '#FF4757' }}>
                          {pnl == null ? '–' : `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
                        </td>
                        <td className="p-3 text-right font-mono" style={{ color: pct == null ? '#8B8FA8' : pct >= 0 ? '#00C48C' : '#FF4757' }}>
                          {pct == null ? '–' : `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`}
                        </td>
                        <td className="p-3" style={{ color: '#8B8FA8' }}>{positionSize(t)}</td>
                        <td className="p-3" style={{ color: '#8B8FA8' }}>{t.signal ?? '–'}</td>
                        <td className="p-3 max-w-[160px] truncate" style={{ color: '#8B8FA8' }}>{t.notiz ?? '–'}</td>
                        <td className="p-3">
                          <div className="flex gap-2">
                            <button onClick={() => setModal(t)} className="text-xs px-2 py-1 rounded"
                              style={{ background: '#2A2D3E', color: '#8B8FA8' }}>✏️</button>
                            <button onClick={() => handleDelete(t.id)} className="text-xs px-2 py-1 rounded"
                              style={{ background: '#FF475715', color: '#FF4757' }}>✕</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {modal && (
        <TradeModal
          initial={modal === 'add' ? undefined : modal}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}
