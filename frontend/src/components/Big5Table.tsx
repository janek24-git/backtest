import { AgGridReact } from '@ag-grid-community/react';
import { ClientSideRowModelModule } from '@ag-grid-community/client-side-row-model';
import '@ag-grid-community/styles/ag-grid.css';
import '@ag-grid-community/styles/ag-theme-alpine.css';
import { useMemo, useState } from 'react';
import type { Big5Trade, Big5ComboMetrics } from '../types';

interface Props {
  trades: Big5Trade[];
  metrics: Big5ComboMetrics;
}

interface RoundTrip {
  nr: number;
  ticker: string;
  entry_datum: string;
  exit_datum: string;
  haltdauer: number;
  entry_preis: number;
  exit_preis: number;
  perf_pct: number;
  kum_perf_pct: number;
}

function buildRoundTrips(trades: Big5Trade[]): RoundTrip[] {
  const trips: RoundTrip[] = [];
  const openTrades: Map<string, Big5Trade> = new Map();
  let tripNr = 1;

  for (const t of trades) {
    if (t.typ === 'KAUF') {
      openTrades.set(t.ticker, t);
    } else {
      const entry = openTrades.get(t.ticker);
      if (entry) {
        trips.push({
          nr: tripNr++,
          ticker: t.ticker,
          entry_datum: entry.datum,
          exit_datum: t.datum,
          haltdauer: t.haltdauer,
          entry_preis: entry.open_preis,
          exit_preis: t.open_preis,
          perf_pct: t.perf_pct,
          kum_perf_pct: t.kum_perf_pct,
        });
        openTrades.delete(t.ticker);
      }
    }
  }
  return trips;
}

function colorVal(v: number | null) {
  if (v == null) return {};
  return { color: v >= 0 ? '#00C48C' : '#FF4757' };
}

export function Big5Table({ trades, metrics }: Props) {
  const [view, setView] = useState<'roundtrip' | 'events'>('roundtrip');

  const roundTrips = useMemo(() => buildRoundTrips(trades), [trades]);

  const eventColDefs: any[] = useMemo(() => [
    { field: 'nr', headerName: 'Nr', width: 65, pinned: 'left' as const },
    {
      field: 'typ', headerName: 'Typ', width: 95,
      cellStyle: (p: any) => ({ color: p.value === 'KAUF' ? '#00C48C' : '#FF4757', fontWeight: 600 }),
    },
    { field: 'ticker', headerName: 'Ticker', width: 90 },
    { field: 'datum', headerName: 'Datum', width: 120 },
    {
      field: 'haltdauer', headerName: 'Haltdauer', width: 100,
      valueFormatter: (p: any) => p.value > 0 ? `${p.value}d` : '—',
    },
    {
      field: 'open_preis', headerName: 'Preis (9:30 ET)', width: 130,
      valueFormatter: (p: any) => `$${p.value.toFixed(2)}`,
    },
    {
      field: 'perf_pct', headerName: 'Perf. %', width: 110,
      valueFormatter: (p: any) => p.value !== 0 ? `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%` : '—',
      cellStyle: (p: any) => p.value !== 0 ? colorVal(p.value) : { color: '#8B8FA8' },
    },
    {
      field: 'kum_perf_pct', headerName: 'Kum. Perf. %', width: 120,
      valueFormatter: (p: any) => `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%`,
      cellStyle: (p: any) => colorVal(p.value),
    },
  ], []);

  const tripColDefs: any[] = useMemo(() => [
    { field: 'nr', headerName: 'Nr', width: 65, pinned: 'left' as const },
    { field: 'ticker', headerName: 'Ticker', width: 90 },
    { field: 'entry_datum', headerName: 'Kauf Datum', width: 120 },
    { field: 'exit_datum', headerName: 'Verkauf Datum', width: 130 },
    {
      field: 'haltdauer', headerName: 'Haltdauer', width: 100,
      valueFormatter: (p: any) => `${p.value}d`,
    },
    {
      field: 'entry_preis', headerName: 'Kauf Preis', width: 115,
      valueFormatter: (p: any) => `$${p.value.toFixed(2)}`,
    },
    {
      field: 'exit_preis', headerName: 'Verkauf Preis', width: 125,
      valueFormatter: (p: any) => `$${p.value.toFixed(2)}`,
    },
    {
      field: 'perf_pct', headerName: 'Perf. %', width: 110,
      valueFormatter: (p: any) => `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%`,
      cellStyle: (p: any) => colorVal(p.value),
    },
    {
      field: 'kum_perf_pct', headerName: 'Kum. Perf. %', width: 120,
      valueFormatter: (p: any) => `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%`,
      cellStyle: (p: any) => colorVal(p.value),
    },
  ], []);

  const m = metrics;

  const metricInfos = [
    {
      label: 'Trades',
      value: m.num_trades.toString(),
      title: 'Anzahl Trades',
      desc: 'Anzahl abgeschlossener Kauf-Verkauf-Paare. Wenige Trades = weniger statistische Aussagekraft.',
    },
    {
      label: 'Win Rate',
      value: `${m.win_rate.toFixed(1)}%`,
      color: colorVal(m.win_rate - 50).color,
      title: 'Win Rate',
      desc: 'Anteil der profitablen Trades. 50% = Break-even. Wichtig: Eine hohe Win Rate sagt nichts über die Höhe der Gewinne aus — wenige große Gewinner können viele kleine Verluste überkompensieren.',
    },
    {
      label: 'Total Return',
      value: `${m.total_return >= 0 ? '+' : ''}${m.total_return.toFixed(2)}%`,
      color: colorVal(m.total_return).color,
      title: 'Total Return (arithmetisch)',
      desc: 'Einfache Summe aller Trade-Returns. Nicht compounded — kein realer Portfolio-Return. Beispiel: +50% und -50% = 0%, nicht -25%. Dient als Vergleichsgröße zwischen Kombinationen.',
    },
    {
      label: 'Sharpe',
      value: m.sharpe.toFixed(2),
      color: colorVal(m.sharpe).color,
      title: 'Sharpe Ratio',
      desc: 'Misst Return im Verhältnis zum Risiko (Volatilität). < 1 = schlecht · 1–2 = gut · > 3 = sehr gut. Vorsicht bei wenigen Trades: Ein hoher Sharpe durch 2–3 Mega-Trades ist nicht reproduzierbar.',
    },
    {
      label: 'Max DD',
      value: `${m.max_drawdown.toFixed(2)}%`,
      color: '#FF4757',
      title: 'Max. Drawdown',
      desc: 'Größter kumulierter Verlust vom Hochpunkt bis zum Tiefpunkt aller Trades (auf der Equity-Kurve). Zeigt das Worst-Case-Szenario. -50% DD bedeutet: auf dem Weg zum Endwert war man zeitweise 50% im Minus.',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Metrics + Info Boxes */}
      <div className="grid grid-cols-5 gap-3">
        {metricInfos.map(({ label, value, color, title, desc }) => (
          <div key={label} className="rounded p-3 flex flex-col gap-2" style={{ background: '#1E2130' }}>
            <div>
              <p className="text-xs uppercase tracking-wider mb-1" style={{ color: '#8B8FA8' }}>{label}</p>
              <p className="text-lg font-semibold" style={{ color: color ?? '#E8EAED' }}>{value}</p>
            </div>
            <div className="rounded p-2" style={{ background: '#151720', borderLeft: '2px solid #2A2D3E' }}>
              <p className="text-xs font-medium mb-0.5" style={{ color: '#E8EAED' }}>{title}</p>
              <p className="text-xs leading-relaxed" style={{ color: '#6B6F85' }}>{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* View Toggle */}
      <div className="flex gap-1">
        {[
          { key: 'roundtrip', label: 'Round-Trip (Kauf + Verkauf)' },
          { key: 'events', label: 'Alle Events' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setView(key as any)}
            className="px-3 py-1.5 rounded text-xs font-medium transition-colors"
            style={view === key
              ? { background: '#00C48C', color: '#000' }
              : { background: '#1E2130', color: '#8B8FA8' }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      {trades.length > 0 ? (
        <div className="ag-theme-alpine-dark w-full" style={{ height: 500 }}>
          {view === 'roundtrip' ? (
            <AgGridReact
              modules={[ClientSideRowModelModule]}
              rowData={roundTrips}
              columnDefs={tripColDefs}
              defaultColDef={{ sortable: true, resizable: true }}
            />
          ) : (
            <AgGridReact
              modules={[ClientSideRowModelModule]}
              rowData={trades}
              columnDefs={eventColDefs}
              defaultColDef={{ sortable: true, resizable: true }}
            />
          )}
        </div>
      ) : (
        <div className="p-8 text-center rounded" style={{ background: '#1E2130', color: '#8B8FA8' }}>
          Keine Trades für diese Kombination
        </div>
      )}
    </div>
  );
}
