import { AgGridReact } from '@ag-grid-community/react';
import { ClientSideRowModelModule } from '@ag-grid-community/client-side-row-model';
import '@ag-grid-community/styles/ag-grid.css';
import '@ag-grid-community/styles/ag-theme-alpine.css';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { TickerResult, PeriodKey } from '../types';
import { filterByPeriod } from '../utils/period';

interface Props {
  results: TickerResult[];
  period: PeriodKey;
}

function signalColor(value: string) {
  return { color: value === 'LONG' ? '#00C48C' : '#FF4757' };
}

function returnColor(value: number | null) {
  if (value == null) return {};
  return { color: value >= 0 ? '#00C48C' : '#FF4757' };
}

export function ResultsTable({ results, period }: Props) {
  const navigate = useNavigate();

  const rowData = useMemo(() =>
    results.map((r) => {
      const filtered = filterByPeriod(r, period);
      const lastTrade = filtered.trades[filtered.trades.length - 1];
      return {
        ticker: r.ticker,
        last_signal: r.last_signal === 1 ? 'LONG' : 'FLAT',
        buy_date: lastTrade?.entry_date ?? '-',
        sell_date: lastTrade?.exit_date ?? '-',
        hold_days: lastTrade?.hold_days ?? '-',
        return_pct: filtered.metrics?.total_return ?? null,
        win_rate: filtered.metrics?.win_rate ?? null,
        sharpe: filtered.metrics?.sharpe_ratio ?? null,
        max_dd: filtered.metrics?.max_drawdown ?? null,
        num_trades: filtered.metrics?.num_trades ?? 0,
        _ticker: r.ticker,
      };
    }),
    [results, period]
  );

  const columnDefs = useMemo(() => [
    { field: 'ticker', headerName: 'Ticker', width: 100, pinned: 'left' as const },
    {
      field: 'last_signal', headerName: 'Signal', width: 90,
      cellStyle: (p: any) => signalColor(p.value),
    },
    { field: 'buy_date', headerName: 'Buy Date', width: 120 },
    { field: 'sell_date', headerName: 'Sell Date', width: 120 },
    { field: 'hold_days', headerName: 'Hold (d)', width: 90 },
    {
      field: 'return_pct', headerName: 'Return %', width: 110,
      valueFormatter: (p: any) => p.value != null ? `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%` : '-',
      cellStyle: (p: any) => returnColor(p.value),
    },
    {
      field: 'win_rate', headerName: 'Win Rate', width: 100,
      valueFormatter: (p: any) => p.value != null ? `${p.value.toFixed(1)}%` : '-',
    },
    {
      field: 'sharpe', headerName: 'Sharpe', width: 90,
      valueFormatter: (p: any) => p.value != null ? p.value.toFixed(2) : '-',
    },
    {
      field: 'max_dd', headerName: 'Max DD', width: 100,
      valueFormatter: (p: any) => p.value != null ? `${p.value.toFixed(2)}%` : '-',
      cellStyle: (p: any) => returnColor(p.value),
    },
    { field: 'num_trades', headerName: 'Trades', width: 80 },
  ], []);

  return (
    <div className="ag-theme-alpine-dark w-full" style={{ height: 420 }}>
      <AgGridReact
        modules={[ClientSideRowModelModule]}
        rowData={rowData}
        columnDefs={columnDefs}
        defaultColDef={{ sortable: true, resizable: true }}
        onRowClicked={(e) => navigate(`/stock/${e.data._ticker}`)}
        rowStyle={{ cursor: 'pointer' }}
      />
    </div>
  );
}
