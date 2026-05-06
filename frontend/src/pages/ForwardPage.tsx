import { useState, useEffect, useRef } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import { fetchForwardTrades, checkForwardExits, deleteForwardTrade } from '../api/client';
import type { ForwardTrade } from '../types';

const STATUS_COLOR: Record<string, string> = {
  OPEN: '#F5A623',
  TP_HIT: '#00C48C',
  SL_HIT: '#FF4D4D',
  MANUALLY_CLOSED: '#8B8FA8',
};

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg p-4 flex flex-col gap-1" style={{ background: '#1A1D27' }}>
      <p className="text-xs" style={{ color: '#8B8FA8' }}>{label}</p>
      <p className="text-xl font-mono font-bold" style={{ color: color ?? '#E8EAED' }}>{value}</p>
    </div>
  );
}

function MiniChart({ trade }: { trade: ForwardTrade }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 180,
      layout: { background: { type: ColorType.Solid, color: '#1A1D27' }, textColor: '#8B8FA8' },
      grid: { vertLines: { color: '#2A2D3E' }, horzLines: { color: '#2A2D3E' } },
      timeScale: { borderColor: '#2A2D3E' },
      rightPriceScale: { borderColor: '#2A2D3E' },
    });

    const series = chart.addSeries(LineSeries, { color: '#00C48C', lineWidth: 2 });

    // Entry + TP + SL as reference points
    const entryDate = trade.signal_date;
    series.setData([{ time: entryDate as any, value: trade.entry_price }]);

    // Price lines for TP and SL
    series.createPriceLine({ price: trade.tp_price, color: '#00C48C', lineWidth: 1, lineStyle: 2, title: `TP +${trade.tp_pct}%` });
    series.createPriceLine({ price: trade.sl_price, color: '#FF4D4D', lineWidth: 1, lineStyle: 2, title: `SL -${trade.sl_pct}%` });
    series.createPriceLine({ price: trade.entry_price, color: '#8B8FA8', lineWidth: 1, lineStyle: 0, title: 'Entry' });

    if (trade.exit_price) {
      series.createPriceLine({ price: trade.exit_price, color: '#F5A623', lineWidth: 1, lineStyle: 2, title: 'Exit' });
    }

    chart.timeScale().fitContent();
    const obs = new ResizeObserver(() => chart.applyOptions({ width: ref.current!.clientWidth }));
    obs.observe(ref.current);
    return () => { chart.remove(); obs.disconnect(); };
  }, [trade]);

  return <div ref={ref} className="rounded-lg overflow-hidden" style={{ background: '#1A1D27' }} />;
}

export function ForwardPage() {
  const [trades, setTrades] = useState<ForwardTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [selected, setSelected] = useState<ForwardTrade | null>(null);
  const [checkMsg, setCheckMsg] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const t = await fetchForwardTrades();
      setTrades(t);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCheckExits() {
    setChecking(true);
    setCheckMsg(null);
    try {
      const { count } = await checkForwardExits();
      setCheckMsg(`${count} Trade${count !== 1 ? 's' : ''} geschlossen`);
      await load();
    } catch {
      setCheckMsg('Fehler beim Prüfen');
    } finally {
      setChecking(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteForwardTrade(id);
    if (selected?.id === id) setSelected(null);
    await load();
  }

  const open = trades.filter(t => t.status === 'OPEN').length;
  const tpHit = trades.filter(t => t.status === 'TP_HIT').length;
  const slHit = trades.filter(t => t.status === 'SL_HIT').length;
  const closed = trades.filter(t => t.result_pct !== null);
  const winRate = closed.length > 0
    ? Math.round(closed.filter(t => (t.result_pct ?? 0) > 0).length / closed.length * 100)
    : 0;

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight" style={{ color: '#E8EAED' }}>
              Forward Testing
            </h1>
            <p className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
              Auto-tracked EMA200 Crossover Signals · TP +10% · SL -5%
            </p>
          </div>
          <div className="flex items-center gap-3">
            {checkMsg && <span className="text-sm" style={{ color: '#8B8FA8' }}>{checkMsg}</span>}
            <button
              onClick={handleCheckExits}
              disabled={checking}
              className="px-4 py-2 rounded text-sm font-medium"
              style={{ background: '#1E2130', color: '#00C48C', border: '1px solid #00C48C', opacity: checking ? 0.6 : 1 }}
            >
              {checking ? 'Prüfe...' : 'TP/SL prüfen'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Offen" value={String(open)} color="#F5A623" />
          <StatCard label="TP Hit" value={String(tpHit)} color="#00C48C" />
          <StatCard label="SL Hit" value={String(slHit)} color="#FF4D4D" />
          <StatCard label="Win Rate" value={closed.length > 0 ? `${winRate}%` : '–'} color={winRate >= 50 ? '#00C48C' : '#FF4D4D'} />
        </div>

        {selected && (
          <div className="rounded-lg p-4 space-y-3" style={{ background: '#1A1D27', border: '1px solid #2A2D3E' }}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold" style={{ color: '#E8EAED' }}>
                {selected.ticker} · Entry ${selected.entry_price} · {selected.signal_date}
              </p>
              <button onClick={() => setSelected(null)} style={{ color: '#8B8FA8', fontSize: 18, lineHeight: 1 }}>×</button>
            </div>
            <MiniChart trade={selected} />
          </div>
        )}

        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #2A2D3E' }}>
          {loading ? (
            <div className="p-8 text-center" style={{ color: '#8B8FA8' }}>Lade...</div>
          ) : trades.length === 0 ? (
            <div className="p-8 text-center" style={{ color: '#8B8FA8' }}>
              Noch keine Trades. Nächstes EMA200-Signal wird automatisch erfasst.
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#1A1D27', borderBottom: '1px solid #2A2D3E' }}>
                  {['Ticker', 'Datum', 'Entry', 'TP', 'SL', 'Status', 'Ergebnis', 'Source', 'RelVol', ''].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#8B8FA8', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr
                    key={t.id}
                    onClick={() => setSelected(t)}
                    style={{
                      borderBottom: '1px solid #2A2D3E',
                      cursor: 'pointer',
                      background: selected?.id === t.id ? 'rgba(0,196,140,0.04)' : 'transparent',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                    onMouseLeave={e => (e.currentTarget.style.background = selected?.id === t.id ? 'rgba(0,196,140,0.04)' : 'transparent')}
                  >
                    <td style={{ padding: '10px 12px', color: '#E8EAED', fontWeight: 600 }}>{t.ticker}</td>
                    <td style={{ padding: '10px 12px', color: '#8B8FA8' }}>{t.signal_date}</td>
                    <td style={{ padding: '10px 12px', color: '#E8EAED', fontFamily: 'monospace' }}>${t.entry_price.toFixed(2)}</td>
                    <td style={{ padding: '10px 12px', color: '#00C48C', fontFamily: 'monospace' }}>${t.tp_price.toFixed(2)}</td>
                    <td style={{ padding: '10px 12px', color: '#FF4D4D', fontFamily: 'monospace' }}>${t.sl_price.toFixed(2)}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: `${STATUS_COLOR[t.status]}22`, color: STATUS_COLOR[t.status],
                      }}>
                        {t.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: t.result_pct == null ? '#8B8FA8' : t.result_pct >= 0 ? '#00C48C' : '#FF4D4D' }}>
                      {t.result_pct != null ? `${t.result_pct > 0 ? '+' : ''}${t.result_pct.toFixed(2)}%` : '–'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 11, background: '#1A1D27', color: '#8B8FA8' }}>{t.source}</span>
                    </td>
                    <td style={{ padding: '10px 12px', color: '#8B8FA8', fontFamily: 'monospace' }}>
                      {t.rel_vol != null ? `${t.rel_vol}×` : '–'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <button
                        onClick={e => { e.stopPropagation(); handleDelete(t.id); }}
                        style={{ color: '#8B8FA8', fontSize: 14, background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px' }}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  );
}
