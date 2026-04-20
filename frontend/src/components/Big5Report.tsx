import React from 'react';
import {
  Document, Page, Text, View, StyleSheet, Svg, Polyline, Line,
} from '@react-pdf/renderer';
import type { Big5BacktestResponse } from '../types';

const C = {
  bg: '#0F1117',
  surface: '#1A1D27',
  border: '#2A2D3E',
  text: '#E8EAED',
  muted: '#8B8FA8',
  green: '#00C48C',
  red: '#FF4757',
  white: '#FFFFFF',
};

const s = StyleSheet.create({
  page: { backgroundColor: C.bg, padding: 36, fontFamily: 'Helvetica', color: C.text },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20, borderBottomWidth: 1, borderBottomColor: C.border, paddingBottom: 12 },
  title: { fontSize: 18, fontFamily: 'Helvetica-Bold', color: C.white },
  subtitle: { fontSize: 9, color: C.muted, marginTop: 3 },
  sectionTitle: { fontSize: 10, fontFamily: 'Helvetica-Bold', color: C.green, marginBottom: 6, marginTop: 14, textTransform: 'uppercase', letterSpacing: 1 },
  tableHeader: { flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 5, paddingHorizontal: 6, borderRadius: 3, marginBottom: 2 },
  tableRow: { flexDirection: 'row', paddingVertical: 4, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.border },
  tableRowBest: { flexDirection: 'row', paddingVertical: 4, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: '#00C48C18' },
  th: { fontSize: 8, color: C.muted, fontFamily: 'Helvetica-Bold' },
  td: { fontSize: 8, color: C.text },
  tdGreen: { fontSize: 8, color: C.green },
  tdRed: { fontSize: 8, color: C.red },
  footer: { position: 'absolute', bottom: 20, left: 36, right: 36, flexDirection: 'row', justifyContent: 'space-between' },
  footerText: { fontSize: 8, color: C.muted },
  analysisSection: { marginBottom: 10 },
  analysisHeader: { fontSize: 10, fontFamily: 'Helvetica-Bold', color: C.green, marginBottom: 3 },
  analysisText: { fontSize: 8, color: C.text, lineHeight: 1.6 },
});

const COL = { combo: 55, ret: 72, sharpe: 55, wr: 60, dd: 72, trades: 50 };

function buildEquityPoints(kumValues: number[], width: number, height: number): string {
  if (kumValues.length < 2) return '';
  const min = Math.min(...kumValues, 0);
  const max = Math.max(...kumValues, 0);
  const range = max - min || 1;
  const pad = 4;
  const w = width - pad * 2;
  const h = height - pad * 2;
  return kumValues.map((v, i) => {
    const x = pad + (i / (kumValues.length - 1)) * w;
    const y = pad + h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

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

function parseSections(text: string): { title: string; body: string }[] {
  const sections: { title: string; body: string }[] = [];
  let current: { title: string; body: string } | null = null;
  for (const line of text.split('\n')) {
    if (line.startsWith('## ')) {
      if (current) sections.push(current);
      current = { title: line.replace('## ', '').trim(), body: '' };
    } else if (current) {
      current.body += (current.body ? '\n' : '') + line;
    }
  }
  if (current) sections.push(current);
  return sections.filter(sec => sec.title && sec.body.trim());
}

interface ReportProps {
  data: Big5BacktestResponse;
  analysis: string;
}

export function Big5Report({ data, analysis }: ReportProps) {
  const best = [...data.results].sort((a, b) => b.metrics.sharpe - a.metrics.sharpe)[0];
  const dateStr = new Date().toLocaleDateString('de-DE');
  const paramStr = `${data.indicator}${data.period} · ${data.from_date} bis ${data.to_date}`;

  const kumValues = best.trades.filter(t => t.typ === 'VERKAUF').map(t => t.kum_perf_pct);
  const chartW = 520;
  const chartH = 110;
  const equityPoints = buildEquityPoints(kumValues, chartW, chartH);
  const zeroY = (() => {
    const min = Math.min(...kumValues, 0);
    const max = Math.max(...kumValues, 0);
    const range = max - min || 1;
    return (4 + (chartH - 8) - ((0 - min) / range) * (chartH - 8)).toFixed(1);
  })();

  const roundTrips = buildRoundTrips(best.trades).slice(0, 28);
  const analysisSections = parseSections(analysis);

  const Footer = () => (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>Big 5 Swing Backtest · {paramStr}</Text>
      <Text style={s.footerText} render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
    </View>
  );

  return (
    <Document title="Big5 Swing Backtest — Analyst Report" author="Backtest System">

      {/* PAGE 1: Combo overview table */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <View>
            <Text style={s.title}>Big 5 Swing Backtest</Text>
            <Text style={s.subtitle}>S&P 500 Top-5 · Dynamische Marktkapitalisierung · {paramStr}</Text>
          </View>
          <Text style={s.footerText}>{dateStr}</Text>
        </View>

        <Text style={s.sectionTitle}>Kombinations-Übersicht (8 Strategien)</Text>
        <View style={s.tableHeader}>
          <Text style={[s.th, { width: COL.combo }]}>KOMBO</Text>
          <Text style={[s.th, { width: COL.ret }]}>TOTAL RETURN</Text>
          <Text style={[s.th, { width: COL.sharpe }]}>SHARPE</Text>
          <Text style={[s.th, { width: COL.wr }]}>WIN RATE</Text>
          <Text style={[s.th, { width: COL.dd }]}>MAX DRAWDOWN</Text>
          <Text style={[s.th, { width: COL.trades }]}>TRADES</Text>
        </View>
        {data.results.map(r => {
          const isBest = r.kombination === best.kombination;
          const retColor = r.metrics.total_return >= 0 ? C.green : C.red;
          const sharpeColor = r.metrics.sharpe >= 0 ? C.green : C.red;
          return (
            <View key={r.kombination} style={isBest ? s.tableRowBest : s.tableRow}>
              <Text style={[s.td, { width: COL.combo, fontFamily: isBest ? 'Helvetica-Bold' : 'Helvetica', color: isBest ? C.green : C.text }]}>
                {r.kombination}{isBest ? ' ★' : ''}
              </Text>
              <Text style={[s.td, { width: COL.ret, color: retColor }]}>{r.metrics.total_return >= 0 ? '+' : ''}{r.metrics.total_return.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.sharpe, color: sharpeColor }]}>{r.metrics.sharpe.toFixed(2)}</Text>
              <Text style={[s.td, { width: COL.wr }]}>{r.metrics.win_rate.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.dd, color: C.red }]}>{r.metrics.max_drawdown.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.trades }]}>{r.metrics.num_trades}</Text>
            </View>
          );
        })}

        <View style={{ marginTop: 8, padding: 8, backgroundColor: C.surface, borderRadius: 4 }}>
          <Text style={{ fontSize: 8, color: C.muted }}>
            ★ Beste Kombination nach Sharpe Ratio.  Total Return = arithmetische Summe (nicht compounded).  Max Drawdown = größter kumulierter Verlust auf der Equity-Kurve.
          </Text>
        </View>

        <Footer />
      </Page>

      {/* PAGE 2: Equity curve + trade log */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <Text style={s.title}>Beste Kombination: {best.kombination}</Text>
          <Text style={s.footerText}>
            {best.metrics.num_trades} Trades · Sharpe {best.metrics.sharpe.toFixed(2)} · {best.metrics.total_return >= 0 ? '+' : ''}{best.metrics.total_return.toFixed(1)}%
          </Text>
        </View>

        <Text style={s.sectionTitle}>Equity-Kurve (kumulierte Performance)</Text>
        <View style={{ backgroundColor: C.surface, borderRadius: 4, padding: 6, marginBottom: 2 }}>
          <Svg width={chartW} height={chartH} viewBox={`0 0 ${chartW} ${chartH}`}>
            <Line x1="4" y1={zeroY} x2={(chartW - 4).toString()} y2={zeroY} stroke={C.border} strokeWidth="1" />
            {equityPoints ? <Polyline points={equityPoints} stroke={C.green} strokeWidth="1.5" fill="none" /> : null}
          </Svg>
        </View>

        <Text style={s.sectionTitle}>Trade-Log — Round Trips{roundTrips.length < buildRoundTrips(best.trades).length ? ' (erste 28)' : ''}</Text>
        <View style={{ flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 4, paddingHorizontal: 4, borderRadius: 3, marginBottom: 2 }}>
          {['Nr', 'Ticker', 'Kauf', 'Verkauf', 'Tage', 'Kauf $', 'Verk. $', 'Perf.'].map((h, i) => (
            <Text key={h} style={[s.th, { width: [28, 42, 72, 72, 30, 58, 58, 54][i] }]}>{h}</Text>
          ))}
        </View>
        {roundTrips.map(rt => (
          <View key={rt.nr} style={{ flexDirection: 'row', paddingVertical: 3, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={[s.td, { width: 28 }]}>{rt.nr}</Text>
            <Text style={[s.td, { width: 42 }]}>{rt.ticker}</Text>
            <Text style={[s.td, { width: 72 }]}>{rt.entry_datum}</Text>
            <Text style={[s.td, { width: 72 }]}>{rt.exit_datum}</Text>
            <Text style={[s.td, { width: 30 }]}>{rt.haltdauer}d</Text>
            <Text style={[s.td, { width: 58 }]}>${rt.entry_preis.toFixed(2)}</Text>
            <Text style={[s.td, { width: 58 }]}>${rt.exit_preis.toFixed(2)}</Text>
            <Text style={[s.td, { width: 54, color: rt.perf_pct >= 0 ? C.green : C.red }]}>{rt.perf_pct >= 0 ? '+' : ''}{rt.perf_pct.toFixed(1)}%</Text>
          </View>
        ))}

        <Footer />
      </Page>

      {/* PAGE 3: Claude analysis */}
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
