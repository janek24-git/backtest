import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { runBig5Backtest } from '../api/client';
import { Big5Table } from '../components/Big5Table';
import { EquityCurve } from '../components/EquityCurve';
import { AnalysisSection } from '../components/AnalysisSection';
import type { Big5BacktestResponse, Big5ComboResult } from '../types';

const OPTIMIZE_INFO = '0,5% Mindestabstand zur EMA beim Einstieg. Reduziert Noise und Whipsaws — im Live-Betrieb replizierbar.';




type CompareResults = { r100: Big5BacktestResponse; r200: Big5BacktestResponse };

export function Big5Page() {
  const navigate = useNavigate();
  const [indicator, setIndicator] = useState<'EMA' | 'SMA'>('EMA');
  const [period, setPeriod] = useState(200);
  const [optimized, setOptimized] = useState(false);
  const [universe, setUniverse] = useState<string>('SP500');

  const comboLegend = {
    A: `Kauf: ${indicator}-Crossover nach Top5-Eintritt — mit Reset (wenn beim Eintritt schon über ${indicator}, erst warten bis darunter)`,
    B: `Kauf: Direkt am Tag des Top5-Eintritts (auch wenn schon über ${indicator} — bewusst hinterherlaufen)`,
    K: `Kauf: Kontinuierlicher ${indicator}-Crossover in Top5 — kein Reset, sofort re-entry nach jedem Exit`,
    C: `Verkauf: Nur bei Close < ${indicator} (Top5-Austritt ignoriert)`,
    D: 'Verkauf: Sofort bei Top5-Austritt',
    E: '1 Tag Top5 = Einstiegs-Berechtigung',
    F: '5 aufeinanderfolgende Tage Top5 = Einstiegs-Berechtigung',
  };

  const universeLabel: Record<string, string> = {
    SP500: 'S&P 500 Top 5',
    NAS100: 'Nasdaq-100 Top 5',
    DAX: 'DAX Top 5',
    STOXX50: 'STOXX 50 Top 5',
    GOLD: 'Gold (GC=F)',
    SILVER: 'Silber (SI=F)',
    BITCOIN: 'Bitcoin (BTC-USD)',
    OIL: 'Rohöl WTI (CL=F)',
  };
  const [showOptInfo, setShowOptInfo] = useState(false);
  const [results, setResults] = useState<Big5BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCombo, setActiveCombo] = useState('ACE');
  const [compareResults, setCompareResults] = useState<CompareResults | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResults(null);
    setCompareResults(null);
    try {
      const data = await runBig5Backtest(indicator, period, '2000-01-01', '2025-12-31', optimized, universe);
      setResults(data);
      setActiveCombo('ACE');
    } catch (e: any) {
      setError(e?.message ?? 'Backtest fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  }

  async function handleCompare() {
    setCompareLoading(true);
    setError(null);
    setResults(null);
    setCompareResults(null);
    try {
      const [r100, r200] = await Promise.all([
        runBig5Backtest(indicator, 100, '2000-01-01', '2025-12-31', optimized),
        runBig5Backtest(indicator, 200, '2000-01-01', '2025-12-31', optimized),
      ]);
      setCompareResults({ r100, r200 });
    } catch (e: any) {
      setError(e?.message ?? 'Vergleich fehlgeschlagen');
    } finally {
      setCompareLoading(false);
    }
  }

  const activeResult = results?.results.find(r => r.kombination === activeCombo);
  const [csvCombo, setCsvCombo] = useState<string>('ACE');

  function downloadCsv(combos: Big5ComboResult[]) {
    const headers = ['Kombination', 'Nr', 'Typ', 'Ticker', 'Datum', 'Haltedauer', 'Preis', 'Perf_%', 'Kum_%', 'Kapital_EUR'];
    const rows: string[][] = [];
    for (const combo of combos) {
      for (const t of combo.trades) {
        rows.push([combo.kombination, String(t.nr), t.typ, t.ticker, t.datum, String(t.haltdauer), String(t.open_preis), String(t.perf_pct), String(t.kum_perf_pct), String(t.kapital_eur)]);
      }
    }
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `big5_${combos.length === 1 ? combos[0].kombination : 'alle'}_${results?.from_date}_${results?.to_date}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/screener')} className="text-sm" style={{ color: '#8B8FA8' }}>
            EMA Screener →
          </button>
          <button onClick={() => navigate('/journal')} className="text-sm" style={{ color: '#8B8FA8' }}>
            Journal →
          </button>
          <button onClick={() => navigate('/ep')} className="text-sm" style={{ color: '#8B8FA8' }}>
            EP Scanner →
          </button>
          <div>
            <h1 className="text-xl font-semibold tracking-tight" style={{ color: '#E8EAED' }}>
              Big 5 Swing Backtest
            </h1>
            <p className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
              {universeLabel[universe] ?? universe} · Dynamische Marktkapitalisierung · 2000–2025 · 12 Kombinationen
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
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Modus</p>
            <div className="flex gap-1 items-center">
              {(['Raw', 'Optimiert'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setOptimized(mode === 'Optimiert')}
                  className="px-3 py-2 rounded text-sm font-medium transition-colors"
                  style={optimized === (mode === 'Optimiert')
                    ? { background: '#F5A623', color: '#000' }
                    : { background: '#1E2130', color: '#8B8FA8' }}
                >
                  {mode}
                </button>
              ))}
              <div className="relative ml-1">
                <button
                  onClick={() => setShowOptInfo(v => !v)}
                  className="w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center"
                  style={{ background: '#2A2D3E', color: '#8B8FA8', border: '1px solid #3A3D4E' }}
                >
                  i
                </button>
                {showOptInfo && (
                  <div
                    className="absolute left-0 top-7 z-10 rounded p-3 text-xs w-72"
                    style={{ background: '#2A2D3E', color: '#C8CAD8', border: '1px solid #3A3D4E' }}
                  >
                    <p className="font-semibold mb-1" style={{ color: '#F5A623' }}>Optimiert-Modus</p>
                    <p>{OPTIMIZE_INFO}</p>
                    <button
                      onClick={() => setShowOptInfo(false)}
                      className="mt-2 text-xs"
                      style={{ color: '#8B8FA8' }}
                    >
                      Schließen
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Universum</p>
            <div className="space-y-1">
              {/* Equity Indices */}
              <div className="flex gap-1 flex-wrap">
                {[
                  { value: 'SP500', label: 'S&P 500' },
                  { value: 'NAS100', label: 'NAS100' },
                  { value: 'DAX', label: 'DAX' },
                  { value: 'STOXX50', label: 'STOXX 50' },
                ].map(u => (
                  <button
                    key={u.value}
                    onClick={() => setUniverse(u.value)}
                    className="px-3 py-1.5 rounded text-xs font-medium transition-colors"
                    style={universe === u.value
                      ? { background: '#7C3AED', color: '#fff' }
                      : { background: '#1E2130', color: '#8B8FA8' }}
                  >
                    {u.label}
                  </button>
                ))}
              </div>
              {/* Commodities & Crypto */}
              <div className="flex gap-1 flex-wrap">
                {[
                  { value: 'GOLD', label: 'Gold' },
                  { value: 'SILVER', label: 'Silber' },
                  { value: 'BITCOIN', label: 'Bitcoin' },
                  { value: 'OIL', label: 'Öl (WTI)' },
                ].map(u => (
                  <button
                    key={u.value}
                    onClick={() => setUniverse(u.value)}
                    className="px-3 py-1.5 rounded text-xs font-medium transition-colors"
                    style={universe === u.value
                      ? { background: '#F5A623', color: '#000' }
                      : { background: '#1E2130', color: '#8B8FA8' }}
                  >
                    {u.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="ml-auto flex gap-2">
            <button
              onClick={handleCompare}
              disabled={compareLoading || loading}
              className="px-4 py-2 rounded font-medium text-sm disabled:opacity-50"
              style={{ background: '#3B4FC8', color: '#fff' }}
            >
              {compareLoading ? 'Lädt...' : 'EMA100 vs EMA200'}
            </button>
            <button
              onClick={handleRun}
              disabled={loading || compareLoading}
              className="px-6 py-2 rounded font-medium text-sm disabled:opacity-50"
              style={{ background: '#00C48C', color: '#000' }}
            >
              {loading ? 'Lädt...' : 'Run Big5 Backtest'}
            </button>
          </div>
        </div>

        {/* Strategy legend */}
        <div className="rounded p-4 text-xs space-y-1" style={{ background: '#1A1D27', color: '#8B8FA8' }}>
          <p className="font-medium mb-2" style={{ color: '#E8EAED' }}>Kombinationslegende</p>
          {Object.entries(comboLegend).map(([k, v]) => (
            <p key={k}><span className="font-mono font-bold" style={{ color: '#00C48C' }}>{k}</span> — {v}</p>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="p-3 rounded text-sm" style={{ background: '#FF475720', color: '#FF4757' }}>
            {error}
          </div>
        )}

        {/* EMA100 vs EMA200 Comparison */}
        {compareResults && (
          <>
          <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
            <p className="text-sm font-medium mb-1" style={{ color: '#E8EAED' }}>
              {indicator}100 vs {indicator}200 — Vergleich
            </p>
            <p className="text-xs mb-4" style={{ color: '#8B8FA8' }}>
              2000–2025 · {compareResults.r100.optimized ? 'Optimiert' : 'Raw'} · Grün = besser
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ color: '#8B8FA8' }}>
                    <th className="text-left pb-2 pr-4">Kombi</th>
                    <th className="text-right pb-2 px-3">{indicator}100 Return</th>
                    <th className="text-right pb-2 px-3">{indicator}200 Return</th>
                    <th className="text-right pb-2 px-3">{indicator}100 Sharpe</th>
                    <th className="text-right pb-2 px-3">{indicator}200 Sharpe</th>
                    <th className="text-right pb-2 px-3">{indicator}100 WR%</th>
                    <th className="text-right pb-2 px-3">{indicator}200 WR%</th>
                    <th className="text-right pb-2 px-3">{indicator}100 MaxDD</th>
                    <th className="text-right pb-2 px-3">{indicator}200 MaxDD</th>
                    <th className="text-right pb-2 pl-3">{indicator}100 Trades</th>
                    <th className="text-right pb-2 pl-3">{indicator}200 Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {compareResults.r100.results.map((r100, i) => {
                    const r200 = compareResults.r200.results[i];
                    const m1 = r100.metrics;
                    const m2 = r200.metrics;
                    const better = (a: number, b: number, higherIsBetter = true) =>
                      higherIsBetter ? (a >= b ? '#00C48C' : '#8B8FA8') : (a <= b ? '#00C48C' : '#8B8FA8');
                    return (
                      <tr key={r100.kombination} style={{ borderTop: '1px solid #2A2D3E' }}>
                        <td className="py-2 pr-4 font-mono font-bold" style={{ color: '#E8EAED' }}>{r100.kombination}</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m1.total_return, m2.total_return) }}>{m1.total_return >= 0 ? '+' : ''}{m1.total_return.toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m2.total_return, m1.total_return) }}>{m2.total_return >= 0 ? '+' : ''}{m2.total_return.toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m1.sharpe, m2.sharpe) }}>{m1.sharpe.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m2.sharpe, m1.sharpe) }}>{m2.sharpe.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m1.win_rate, m2.win_rate) }}>{m1.win_rate.toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m2.win_rate, m1.win_rate) }}>{m2.win_rate.toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m1.max_drawdown, m2.max_drawdown, true) }}>{m1.max_drawdown.toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono" style={{ color: better(m2.max_drawdown, m1.max_drawdown, true) }}>{m2.max_drawdown.toFixed(1)}%</td>
                        <td className="py-2 pl-3 text-right font-mono" style={{ color: '#8B8FA8' }}>{m1.num_trades}</td>
                        <td className="py-2 pl-3 text-right font-mono" style={{ color: '#8B8FA8' }}>{m2.num_trades}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <AnalysisSection data={compareResults.r200} />
          </>
        )}

        {/* Results */}
        {results && (
          <>
            {/* Combo Overview */}
            <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
              <p className="text-xs mb-3" style={{ color: '#8B8FA8' }}>
                {indicator}{period} · {results.from_date} bis {results.to_date}
              </p>
              <div className="grid grid-cols-4 gap-2 mb-4" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
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
                    {r.metrics.portfolio_end_eur > 0 && (
                      <p className="text-xs" style={{ color: r.metrics.portfolio_end_eur >= 1000 ? '#00C48C' : '#FF4757' }}>
                        €{r.metrics.portfolio_end_eur.toLocaleString('de-DE', { maximumFractionDigits: 0 })}
                      </p>
                    )}
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
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>
                        Kombination {activeCombo}
                      </p>
                      {results.optimized && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: '#F5A62320', color: '#F5A623' }}>
                          Optimiert
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        value={csvCombo}
                        onChange={e => setCsvCombo(e.target.value)}
                        className="rounded text-xs px-2 py-1.5"
                        style={{ background: '#1E2130', color: '#8B8FA8', border: '1px solid #2A2D3E' }}
                      >
                        {results.results.map(r => (
                          <option key={r.kombination} value={r.kombination}>{r.kombination}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => {
                          if (!results) return;
                          const combo = results.results.find(r => r.kombination === csvCombo);
                          if (combo) downloadCsv([combo]);
                        }}
                        className="px-3 py-1.5 rounded text-xs font-medium"
                        style={{ background: '#1E2130', color: '#8B8FA8', border: '1px solid #2A2D3E' }}
                      >
                        ↓ CSV Einzel
                      </button>
                      <button
                        onClick={() => results && downloadCsv(results.results)}
                        className="px-3 py-1.5 rounded text-xs font-medium"
                        style={{ background: '#1E2130', color: '#8B8FA8', border: '1px solid #2A2D3E' }}
                      >
                        ↓ CSV Alle
                      </button>
                    </div>
                  </div>
                  <Big5Table trades={activeResult.trades} metrics={activeResult.metrics} />
                </div>
              )}
            </div>
            {activeResult && activeResult.trades.some(t => t.typ === 'VERKAUF') && (
              <EquityCurve trades={activeResult.trades} />
            )}
          <AnalysisSection data={results} />
        </>
      )}
      </div>
    </div>
  );
}
