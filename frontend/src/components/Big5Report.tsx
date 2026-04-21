import React from 'react';
import {
  Document, Page, Text, View, StyleSheet, Svg, Polyline, Line,
} from '@react-pdf/renderer';
import type { Big5BacktestResponse } from '../types';

const C = {
  bg: '#0F1117', surface: '#1A1D27', border: '#2A2D3E',
  text: '#E8EAED', muted: '#8B8FA8', green: '#00C48C',
  red: '#FF4757', white: '#FFFFFF', gridLine: '#1E2130',
};

const s = StyleSheet.create({
  page: { backgroundColor: C.bg, padding: 36, fontFamily: 'Helvetica', color: C.text },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 18, borderBottomWidth: 1, borderBottomColor: C.border, paddingBottom: 10 },
  title: { fontSize: 17, fontFamily: 'Helvetica-Bold', color: C.white },
  subtitle: { fontSize: 8, color: C.muted, marginTop: 3 },
  secTitle: { fontSize: 9, fontFamily: 'Helvetica-Bold', color: C.green, marginBottom: 5, marginTop: 12, textTransform: 'uppercase', letterSpacing: 1 },
  th: { fontSize: 7.5, color: C.muted, fontFamily: 'Helvetica-Bold' },
  td: { fontSize: 7.5, color: C.text },
  footer: { position: 'absolute', bottom: 18, left: 36, right: 36, flexDirection: 'row', justifyContent: 'space-between' },
  footerText: { fontSize: 7.5, color: C.muted },
  bullet: { flexDirection: 'row', marginBottom: 2.5, paddingLeft: 2 },
  bulletDot: { fontSize: 8, color: C.muted, width: 10 },
  bulletText: { fontSize: 8, color: C.text, lineHeight: 1.55, flex: 1 },
});

// ── Inline bold ───────────────────────────────────────────────────────────────
function InlineText({ text, style }: { text: string; style?: any }) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  if (parts.length === 1) return <Text style={style}>{text}</Text>;
  return (
    <Text style={style}>
      {parts.map((p, i) =>
        i % 2 === 1 ? <Text key={i} style={{ fontFamily: 'Helvetica-Bold' }}>{p}</Text> : p
      )}
    </Text>
  );
}

// ── Markdown table ────────────────────────────────────────────────────────────
function MarkdownTable({ lines }: { lines: string[] }) {
  const dataLines = lines.filter(l => !l.match(/^\|[\s\-|:]+\|$/));
  const parse = (line: string) =>
    line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim());
  const [hdr, ...rows] = dataLines;
  const headers = parse(hdr || '');
  if (!headers.length) return null;
  const isRisk = headers[0]?.toLowerCase().includes('risik') || headers[0]?.toLowerCase().includes('risk');
  const widths = isRisk ? [90, 120, 255] : headers.map(() => Math.floor(465 / headers.length));
  return (
    <View style={{ marginVertical: 5 }}>
      <View style={{ flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 4, paddingHorizontal: 4, borderRadius: 3 }}>
        {headers.map((h, i) => <Text key={i} style={[s.th, { width: widths[i] }]}>{h.replace(/\*/g, '').toUpperCase()}</Text>)}
      </View>
      {rows.map((row, ri) => (
        <View key={ri} style={{ flexDirection: 'row', paddingVertical: 3.5, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
          {parse(row).map((cell, ci) => (
            <InlineText key={ci} text={cell} style={[s.td, { width: widths[ci], lineHeight: 1.5 }]} />
          ))}
        </View>
      ))}
    </View>
  );
}

// ── Section body renderer ─────────────────────────────────────────────────────
function SectionBody({ body }: { body: string }) {
  const lines = body.split('\n');
  const elements: React.ReactElement[] = [];
  let tbl: string[] = [];

  const flushTbl = (k: string) => {
    if (tbl.length > 1) elements.push(<MarkdownTable key={k} lines={tbl} />);
    tbl = [];
  };

  lines.forEach((line, i) => {
    const t = line.trim();
    if (t.startsWith('|')) { tbl.push(line); return; }
    if (tbl.length) flushTbl(`t${i}`);
    if (!t || t === '---') { elements.push(<View key={i} style={{ height: 3 }} />); return; }
    if (t.startsWith('- ') || t.startsWith('* ')) {
      elements.push(
        <View key={i} style={s.bullet}>
          <Text style={s.bulletDot}>·</Text>
          <InlineText text={t.slice(2)} style={s.bulletText} />
        </View>
      );
      return;
    }
    elements.push(<InlineText key={i} text={t} style={[{ fontSize: 8, color: C.text, lineHeight: 1.55, marginBottom: 2 }]} />);
  });
  if (tbl.length) flushTbl('tend');
  return <>{elements}</>;
}

// ── Equity chart with axes ────────────────────────────────────────────────────
function niceSteps(min: number, max: number, count: number): number[] {
  const range = (max - min) || 100;
  const rawStep = range / (count - 1);
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const step = Math.ceil(rawStep / mag) * mag;
  const start = Math.floor(min / step) * step;
  const vals: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) vals.push(Math.round(v));
  return vals;
}

function EquityChart({ kumValues, exitDates }: { kumValues: number[]; exitDates: string[] }) {
  const W = 490; const H = 130;
  const ML = 42; const MB = 18; const MT = 6; const MR = 4;
  const cW = W - ML - MR; const cH = H - MT - MB;

  const minV = Math.min(...kumValues, 0);
  const maxV = Math.max(...kumValues, 0);
  const yVals = niceSteps(minV, maxV, 5);
  const yMin = yVals[0]; const yMax = yVals[yVals.length - 1];
  const yRange = yMax - yMin || 1;

  const toY = (v: number) => MT + cH - ((v - yMin) / yRange) * cH;
  const toX = (i: number) => ML + (i / Math.max(kumValues.length - 1, 1)) * cW;

  const points = kumValues.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(' ');

  const yearLabels: { label: string; x: number }[] = [];
  if (exitDates.length > 0) {
    const seen = new Set<number>();
    exitDates.forEach((d, i) => {
      const yr = parseInt(d.slice(0, 4));
      if (!seen.has(yr) && yr % 5 === 0) {
        seen.add(yr);
        yearLabels.push({ label: String(yr), x: toX(i) });
      }
    });
  }

  return (
    <View style={{ backgroundColor: C.surface, borderRadius: 4, marginBottom: 8, position: 'relative', width: W, height: H }}>
      {/* SVG: nur Linien, keine Texte */}
      <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {yVals.map(v => (
          <Line key={v}
            x1={String(ML)} y1={toY(v).toFixed(1)}
            x2={String(W - MR)} y2={toY(v).toFixed(1)}
            stroke={v === 0 ? '#3A3D4E' : '#1A1D27'}
            strokeWidth={v === 0 ? '1' : '0.5'}
          />
        ))}
        <Line x1={String(ML)} y1={String(MT)} x2={String(ML)} y2={String(MT + cH)} stroke="#3A3D4E" strokeWidth="0.8" />
        <Line x1={String(ML)} y1={String(MT + cH)} x2={String(W - MR)} y2={String(MT + cH)} stroke="#3A3D4E" strokeWidth="0.8" />
        {yearLabels.map(({ x }) => (
          <Line key={x} x1={x.toFixed(1)} y1={String(MT + cH)} x2={x.toFixed(1)} y2={String(MT + cH + 3)} stroke="#8B8FA8" strokeWidth="0.7" />
        ))}
        {points && <Polyline points={points} stroke={C.green} strokeWidth="1.5" fill="none" />}
      </Svg>

      {/* Y-Achsen-Labels: absolut positioniert über dem SVG */}
      {yVals.map(v => (
        <Text key={v} style={{
          position: 'absolute',
          left: 1,
          top: toY(v) - 4,
          width: ML - 3,
          fontSize: 6,
          color: C.muted,
          textAlign: 'right',
        }}>
          {v > 0 ? `+${v}` : `${v}`}%
        </Text>
      ))}

      {/* X-Achsen-Labels: Jahreszahlen */}
      {yearLabels.map(({ label, x }) => (
        <Text key={label} style={{
          position: 'absolute',
          left: x - 11,
          top: MT + cH + 5,
          width: 22,
          fontSize: 6,
          color: C.muted,
          textAlign: 'center',
        }}>
          {label}
        </Text>
      ))}
    </View>
  );
}

// ── Data helpers ──────────────────────────────────────────────────────────────
function buildRoundTrips(trades: any[]) {
  const trips: any[] = [];
  const open: Map<string, any> = new Map();
  let nr = 1;
  for (const t of trades) {
    if (t.typ === 'KAUF') { open.set(t.ticker, t); }
    else {
      const e = open.get(t.ticker);
      if (e) {
        trips.push({ nr: nr++, ticker: t.ticker, entry_datum: e.datum, exit_datum: t.datum, haltdauer: t.haltdauer, entry_preis: e.open_preis, exit_preis: t.open_preis, perf_pct: t.perf_pct, kum: t.kum_perf_pct });
        open.delete(t.ticker);
      }
    }
  }
  return trips;
}

function parseSections(text: string): { title: string; body: string }[] {
  const secs: { title: string; body: string }[] = [];
  let cur: { title: string; body: string } | null = null;
  for (const line of text.split('\n')) {
    if (line.startsWith('## ')) {
      if (cur) secs.push(cur);
      cur = { title: line.replace('## ', '').trim(), body: '' };
    } else if (cur) {
      cur.body += (cur.body ? '\n' : '') + line;
    }
  }
  if (cur) secs.push(cur);
  return secs.filter(s => s.title && s.body.trim());
}

// ── Trade log pages ───────────────────────────────────────────────────────────
const TL_COLS = [24, 38, 68, 68, 28, 52, 52, 52, 54];
const TL_HEADS = ['Nr', 'Titel', 'Kauf', 'Verkauf', 'Tage', 'Kauf $', 'Verk. $', 'Perf. %', 'Kum. %'];

function TradeLogHeader() {
  return (
    <View style={{ flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 4, paddingHorizontal: 4, borderRadius: 3, marginBottom: 2 }}>
      {TL_HEADS.map((h, i) => <Text key={h} style={[s.th, { width: TL_COLS[i] }]}>{h}</Text>)}
    </View>
  );
}

function TradeRow({ rt }: { rt: any }) {
  return (
    <View style={{ flexDirection: 'row', paddingVertical: 2.8, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
      <Text style={[s.td, { width: TL_COLS[0] }]}>{rt.nr}</Text>
      <Text style={[s.td, { width: TL_COLS[1] }]}>{rt.ticker}</Text>
      <Text style={[s.td, { width: TL_COLS[2] }]}>{rt.entry_datum}</Text>
      <Text style={[s.td, { width: TL_COLS[3] }]}>{rt.exit_datum}</Text>
      <Text style={[s.td, { width: TL_COLS[4] }]}>{rt.haltdauer}d</Text>
      <Text style={[s.td, { width: TL_COLS[5] }]}>${rt.entry_preis.toFixed(2)}</Text>
      <Text style={[s.td, { width: TL_COLS[6] }]}>${rt.exit_preis.toFixed(2)}</Text>
      <Text style={[s.td, { width: TL_COLS[7], color: rt.perf_pct >= 0 ? C.green : C.red }]}>{rt.perf_pct >= 0 ? '+' : ''}{rt.perf_pct.toFixed(1)}%</Text>
      <Text style={[s.td, { width: TL_COLS[8], color: rt.kum >= 0 ? C.green : C.red }]}>{rt.kum >= 0 ? '+' : ''}{rt.kum.toFixed(1)}%</Text>
    </View>
  );
}

// ── Main Report ───────────────────────────────────────────────────────────────
interface ReportProps { data: Big5BacktestResponse; analysis: string; }

export function Big5Report({ data, analysis }: ReportProps) {
  const best = [...data.results].sort((a, b) => b.metrics.sharpe - a.metrics.sharpe)[0];
  const dateStr = new Date().toLocaleDateString('de-DE');
  const paramStr = `${data.indicator}${data.period} · ${data.from_date} bis ${data.to_date}`;
  const COL = { combo: 52, ret: 70, sharpe: 52, wr: 58, dd: 70, trades: 48 };

  const verkaufTrades = best.trades.filter(t => t.typ === 'VERKAUF');
  const kumValues = verkaufTrades.map(t => t.kum_perf_pct);
  const exitDates = verkaufTrades.map(t => t.datum);
  const roundTrips = buildRoundTrips(best.trades);
  const analysisSections = parseSections(analysis);

  // Split trade rows into pages (~32 per page)
  const ROWS_P1 = 28; // first trade page (less space due to chart)
  const ROWS_REST = 36;
  const tradePages: any[][] = [];
  tradePages.push(roundTrips.slice(0, ROWS_P1));
  for (let i = ROWS_P1; i < roundTrips.length; i += ROWS_REST) {
    tradePages.push(roundTrips.slice(i, i + ROWS_REST));
  }

  const Footer = () => (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>Big 5 Swing Backtest · {paramStr}</Text>
      <Text style={s.footerText} render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
    </View>
  );

  return (
    <Document title="Big5 Swing Backtest — Analyst Report" author="Backtest System">

      {/* Seite 1: Kombinations-Übersicht */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <View>
            <Text style={s.title}>Big 5 Swing Backtest</Text>
            <Text style={s.subtitle}>S&P 500 Top-5 · Dynamische Marktkapitalisierung · {paramStr}</Text>
          </View>
          <Text style={s.footerText}>{dateStr}</Text>
        </View>

        <Text style={s.secTitle}>Kombinations-Übersicht (8 Strategien)</Text>
        <View style={{ flexDirection: 'row', backgroundColor: C.surface, paddingVertical: 5, paddingHorizontal: 5, borderRadius: 3, marginBottom: 2 }}>
          <Text style={[s.th, { width: COL.combo }]}>KOMBO</Text>
          <Text style={[s.th, { width: COL.ret }]}>KUMULIERT</Text>
          <Text style={[s.th, { width: COL.sharpe }]}>SHARPE</Text>
          <Text style={[s.th, { width: COL.wr }]}>TREFFERQUOTE</Text>
          <Text style={[s.th, { width: COL.dd }]}>MAX. DRAWDOWN</Text>
          <Text style={[s.th, { width: COL.trades }]}>TRADES</Text>
        </View>
        {data.results.map(r => {
          const isBest = r.kombination === best.kombination;
          return (
            <View key={r.kombination} style={{ flexDirection: 'row', paddingVertical: 4, paddingHorizontal: 5, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: isBest ? '#00C48C18' : 'transparent' }}>
              <Text style={[s.td, { width: COL.combo, fontFamily: isBest ? 'Helvetica-Bold' : 'Helvetica', color: isBest ? C.green : C.text }]}>{r.kombination}{isBest ? ' ★' : ''}</Text>
              <Text style={[s.td, { width: COL.ret, color: r.metrics.total_return >= 0 ? C.green : C.red }]}>{r.metrics.total_return >= 0 ? '+' : ''}{r.metrics.total_return.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.sharpe, color: r.metrics.sharpe >= 1 ? C.green : C.red }]}>{r.metrics.sharpe.toFixed(2)}</Text>
              <Text style={[s.td, { width: COL.wr }]}>{r.metrics.win_rate.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.dd, color: C.red }]}>{r.metrics.max_drawdown.toFixed(1)}%</Text>
              <Text style={[s.td, { width: COL.trades }]}>{r.metrics.num_trades}</Text>
            </View>
          );
        })}
        <View style={{ marginTop: 7, padding: 8, backgroundColor: C.surface, borderRadius: 4, gap: 5 }}>
          <Text style={{ fontSize: 7.5, color: C.muted }}>
            ★ Beste Kombination nach Sharpe Ratio.  Kumuliert = arithmetische Summe der Einzel-Trades (nicht compounded).
          </Text>
          <View style={{ borderTopWidth: 1, borderTopColor: C.border, paddingTop: 5, gap: 4 }}>
            <Text style={{ fontSize: 7.5, color: C.muted }}>
              <Text style={{ fontFamily: 'Helvetica-Bold', color: C.text }}>Sharpe Ratio</Text>
              {' '}— Misst wie viel Rendite eine Strategie pro Einheit Risiko (Schwankung) erzielt. Unter 1 = schlecht · 1–2 = gut · über 3 = sehr gut. Ein Sharpe von 4 bedeutet: für jedes Prozent Schwankung wurden 4% Rendite erwirtschaftet. Je höher, desto effizienter die Strategie.
            </Text>
            <Text style={{ fontSize: 7.5, color: C.muted }}>
              <Text style={{ fontFamily: 'Helvetica-Bold', color: C.text }}>Max. Drawdown</Text>
              {' '}— Der größte Verlust vom höchsten zum tiefsten Punkt auf der Equity-Kurve. Entsteht wenn mehrere Verlust-Trades hintereinander kommen, oder ein einzelner Trade stark ins Minus läuft, bevor die Strategie wieder dreht. Ein Drawdown von -49% bedeutet: auf dem Weg zum Endwert war man zeitweise 49% unter dem vorherigen Höchststand. Kein Drawdown = keine einzige Verlustphase.
            </Text>
          </View>
        </View>
        <Footer />
      </Page>

      {/* Seite 2+: Equity-Kurve + Trade-Log */}
      {tradePages.map((pageRows, pi) => (
        <Page key={pi} size="A4" style={s.page}>
          <View style={s.header}>
            <Text style={s.title}>Beste Kombination: {best.kombination}</Text>
            <Text style={s.footerText}>{best.metrics.num_trades} Trades · Sharpe {best.metrics.sharpe.toFixed(2)} · Trefferquote {best.metrics.win_rate.toFixed(1)}%</Text>
          </View>

          {pi === 0 && (
            <>
              <Text style={s.secTitle}>Kumulierte Performance — Equity-Kurve</Text>
              <EquityChart kumValues={kumValues} exitDates={exitDates} />
            </>
          )}

          <Text style={s.secTitle}>
            Trade-Log — Alle {roundTrips.length} Round Trips{tradePages.length > 1 ? ` (Seite ${pi + 1}/${tradePages.length})` : ''}
          </Text>
          <TradeLogHeader />
          {pageRows.map(rt => <TradeRow key={rt.nr} rt={rt} />)}
          <Footer />
        </Page>
      ))}

      {/* Analyse-Seite */}
      <Page size="A4" style={s.page}>
        <View style={s.header}>
          <Text style={s.title}>Analyst Report</Text>
          <Text style={s.footerText}>Erstellt mit Claude AI · {dateStr}</Text>
        </View>
        {analysisSections.map(sec => (
          <View key={sec.title} style={{ marginBottom: 9 }}>
            <Text style={s.secTitle}>{sec.title}</Text>
            <SectionBody body={sec.body} />
          </View>
        ))}
        <Footer />
      </Page>
    </Document>
  );
}
