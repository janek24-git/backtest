import { useEffect, useRef } from 'react';
import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
} from 'lightweight-charts';
import type { SignalPoint, TradeRecord } from '../types';

interface Props {
  signals: SignalPoint[];
  trades: TradeRecord[];
}

export function CandleChart({ signals, trades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || signals.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0F1117' },
        textColor: '#8B8FA8',
      },
      grid: {
        vertLines: { color: '#1E2130' },
        horzLines: { color: '#1E2130' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      width: containerRef.current.clientWidth,
      height: 400,
    });

    // Candlestick series (v5 API)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00C48C',
      downColor: '#FF4757',
      borderUpColor: '#00C48C',
      borderDownColor: '#FF4757',
      wickUpColor: '#00C48C',
      wickDownColor: '#FF4757',
    });

    candleSeries.setData(
      signals.map((s) => ({
        time: s.date as any,
        open: s.open,
        high: Math.max(s.open, s.close),
        low: Math.min(s.open, s.close),
        close: s.close,
      }))
    );

    // EMA200 line (v5 API)
    const emaSeries = chart.addSeries(LineSeries, {
      color: '#F59E0B',
      lineWidth: 2,
      title: 'EMA 200',
    });

    emaSeries.setData(
      signals.map((s) => ({ time: s.date as any, value: s.ema200 }))
    );

    // Buy/Sell markers (v5 uses createSeriesMarkers plugin)
    const markers = trades.flatMap((t) => [
      {
        time: t.entry_date as any,
        position: 'belowBar' as const,
        color: '#00C48C',
        shape: 'arrowUp' as const,
        text: 'BUY',
      },
      ...(t.exit_date
        ? [
            {
              time: t.exit_date as any,
              position: 'aboveBar' as const,
              color: '#FF4757',
              shape: 'arrowDown' as const,
              text: `SELL ${t.return_pct >= 0 ? '+' : ''}${t.return_pct.toFixed(1)}%`,
            },
          ]
        : []),
    ]);

    if (markers.length > 0) {
      createSeriesMarkers(candleSeries, markers);
    }

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
  }, [signals, trades]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{ minHeight: 400 }}
    />
  );
}
