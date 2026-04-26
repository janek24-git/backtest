import { useEffect, useRef } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { Big5Trade } from '../types';

interface Props {
  trades: Big5Trade[];
}

export function EquityCurve({ trades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Only VERKAUF trades have perf_pct; sort by date
    const verkauf = trades
      .filter(t => t.typ === 'VERKAUF')
      .sort((a, b) => a.datum.localeCompare(b.datum));

    if (verkauf.length === 0) return;

    // Compound from 10,000€
    let value = 10000;
    const points: { time: string; value: number }[] = [];
    // Add starting point one day before first trade (same date is fine)
    points.push({ time: verkauf[0].datum, value });
    for (const t of verkauf) {
      value = value * (1 + t.perf_pct / 100);
      points.push({ time: t.datum, value: parseFloat(value.toFixed(2)) });
    }

    // Deduplicate: if same date appears multiple times keep last value
    const dedupMap = new Map<string, number>();
    for (const p of points) dedupMap.set(p.time, p.value);
    const data = Array.from(dedupMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, val]) => ({ time, value: val }));

    const chart = createChart(containerRef.current!, {
      layout: {
        background: { type: ColorType.Solid, color: '#0F1117' },
        textColor: '#8B8FA8',
      },
      grid: {
        vertLines: { color: '#1E2130' },
        horzLines: { color: '#1E2130' },
      },
      rightPriceScale: {
        borderColor: '#1E2130',
      },
      timeScale: {
        borderColor: '#1E2130',
      },
      width: containerRef.current!.clientWidth,
      height: 260,
    });

    const finalValue = data[data.length - 1]?.value ?? 10000;
    const totalReturn = ((finalValue / 10000) - 1) * 100;
    const lineColor = totalReturn >= 0 ? '#00C48C' : '#FF4757';

    const lineSeries = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    });

    lineSeries.setData(data as any);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [trades]);

  const verkauf = trades.filter(t => t.typ === 'VERKAUF');
  const finalValue = verkauf.reduce((v, t) => v * (1 + t.perf_pct / 100), 10000);
  const totalReturn = ((finalValue / 10000) - 1) * 100;

  return (
    <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>Equity Kurve</p>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span style={{ color: '#8B8FA8' }}>Start: 10.000 €</span>
          <span style={{ color: '#8B8FA8' }}>→</span>
          <span style={{ color: totalReturn >= 0 ? '#00C48C' : '#FF4757', fontWeight: 600 }}>
            {finalValue.toLocaleString('de-DE', { maximumFractionDigits: 0 })} €
          </span>
          <span style={{ color: totalReturn >= 0 ? '#00C48C' : '#FF4757', fontWeight: 600 }}>
            ({totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(1)}%)
          </span>
        </div>
      </div>
      <div ref={containerRef} className="w-full rounded overflow-hidden" style={{ minHeight: 260 }} />
      <p className="text-xs mt-2" style={{ color: '#5A5D70' }}>
        Kompoundiert · {verkauf.length} Trades · Kein Rebalancing · Transaktionskosten nicht eingerechnet
      </p>
    </div>
  );
}
