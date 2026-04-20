import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { runBig5Backtest } from '../api/client';
import { Big5Table } from '../components/Big5Table';
import type { Big5BacktestResponse, Big5ComboResult } from '../types';

function exportCSV(result: Big5ComboResult, indicator: string, period: number) {
  const headers = ['Nr', 'Typ', 'Ticker', 'Datum', 'Haltdauer (Tage)', 'Preis (9:30 ET)', 'Performance %', 'Kum. Performance %'];
  const rows = result.trades.map(t => [
    t.nr, t.typ, t.ticker, t.datum,
    t.haltdauer || '',
    t.open_preis.toFixed(4),
    t.perf_pct !== 0 ? t.perf_pct.toFixed(4) : '',
    t.kum_perf_pct.toFixed(4),
  ]);
  const csv = [headers, ...rows].map(r => r.join(';')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Big5_${result.kombination}_${indicator}${period}_2000-2025.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const COMBINATIONS = ['ACE', 'ACF', 'ADE', 'ADF', 'BCE', 'BCF', 'BDE', 'BDF'];

const COMBO_LEGEND = {
  A: 'Kauf: Erster Close > EMA nach Top5-Eintritt',
  B: 'Kauf: Am Tag des Top5-Eintritts (falls Close > EMA)',
  C: 'Verkauf: Nur bei Close < EMA (Top5-Austritt ignoriert)',
  D: 'Verkauf: Sofort bei Top5-Austritt',
  E: '1 Tag Top5 = Signal',
  F: '5 aufeinanderfolgende Tage Top5 = Signal',
};

export function Big5Page() {
  const navigate = useNavigate();
  const [indicator, setIndicator] = useState<'EMA' | 'SMA'>('EMA');
  const [period, setPeriod] = useState(200);
  const [results, setResults] = useState<Big5BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCombo, setActiveCombo] = useState('ACE');

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data = await runBig5Backtest(indicator, period);
      setResults(data);
      setActiveCombo('ACE');
    } catch (e: any) {
      setError(e?.message ?? 'Backtest fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  }

  const activeResult = results?.results.find(r => r.kombination === activeCombo);

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/screener')} className="text-sm" style={{ color: '#8B8FA8' }}>
            EMA Screener →
          </button>
          <div>
            <h1 className="text-xl font-semibold tracking-tight" style={{ color: '#E8EAED' }}>
              Big 5 Swing Backtest
            </h1>
            <p className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
              S&P 500 Top 5 · Dynamische Marktkapitalisierung · 2000–2025 · 8 Kombinationen
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-6 flex-wrap">
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Indikator</p>
            <div className="flex gap-1">
              {(['EMA', 'SMA'] as const).map(ind => (
                <button
                  key={ind}
                  onClick={() => setIndicator(ind)}
                  className="px-3 py-2 rounded text-sm font-medium transition-colors"
                  style={indicator === ind
                    ? { background: '#00C48C', color: '#000' }
                    : { background: '#1E2130', color: '#8B8FA8' }}
                >
                  {ind}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Periode</p>
            <div className="flex gap-1">
              {[50, 100, 150, 200].map(p => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className="px-3 py-2 rounded text-sm font-medium transition-colors"
                  style={period === p
                    ? { background: '#3B4FC8', color: '#fff' }
                    : { background: '#1E2130', color: '#8B8FA8' }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="ml-auto">
            <button
              onClick={handleRun}
              disabled={loading}
              className="px-6 py-2 rounded font-medium text-sm disabled:opacity-50"
              style={{ background: '#00C48C', color: '#000' }}
            >
              {loading ? 'Lädt... (kann 30–60s dauern)' : 'Run Big5 Backtest'}
            </button>
          </div>
        </div>

        {/* Strategy legend */}
        <div className="rounded p-4 text-xs space-y-1" style={{ background: '#1A1D27', color: '#8B8FA8' }}>
          <p className="font-medium mb-2" style={{ color: '#E8EAED' }}>Kombinationslegende</p>
          {Object.entries(COMBO_LEGEND).map(([k, v]) => (
            <p key={k}><span className="font-mono font-bold" style={{ color: '#00C48C' }}>{k}</span> — {v}</p>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="p-3 rounded text-sm" style={{ background: '#FF475720', color: '#FF4757' }}>
            {error}
          </div>
        )}

        {/* Results */}
        {results && (
          <>
            {/* Combo Overview */}
            <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
              <p className="text-xs mb-3" style={{ color: '#8B8FA8' }}>
                {indicator}{period} · {results.from_date} bis {results.to_date}
              </p>
              <div className="grid grid-cols-4 gap-2 mb-4">
                {results.results.map(r => (
                  <button
                    key={r.kombination}
                    onClick={() => setActiveCombo(r.kombination)}
                    className="rounded p-3 text-left transition-all"
                    style={{
                      background: activeCombo === r.kombination ? '#2A2D3E' : '#1E2130',
                      border: activeCombo === r.kombination ? '1px solid #00C48C' : '1px solid transparent',
                    }}
                  >
                    <p className="font-mono font-bold text-sm" style={{ color: '#E8EAED' }}>{r.kombination}</p>
                    <p className="text-xs mt-1" style={{ color: r.metrics.total_return >= 0 ? '#00C48C' : '#FF4757' }}>
                      {r.metrics.total_return >= 0 ? '+' : ''}{r.metrics.total_return.toFixed(1)}%
                    </p>
                    <p className="text-xs" style={{ color: '#8B8FA8' }}>
                      {r.metrics.num_trades} Trades · WR {r.metrics.win_rate.toFixed(0)}%
                    </p>
                  </button>
                ))}
              </div>

              {/* Active Combination Detail */}
              {activeResult && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>
                      Kombination {activeCombo}
                    </p>
                    <button
                      onClick={() => exportCSV(activeResult, indicator, period)}
                      className="px-3 py-1.5 rounded text-xs font-medium"
                      style={{ background: '#1E2130', color: '#8B8FA8', border: '1px solid #2A2D3E' }}
                    >
                      ↓ CSV Export
                    </button>
                  </div>
                  <Big5Table trades={activeResult.trades} metrics={activeResult.metrics} />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
