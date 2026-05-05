import { useState } from 'react';
import { scanEP, runEPBacktest } from '../api/client';
import type { EPScanResponse, EPBacktestResponse, EPCandidate, EPInvestProposal } from '../types';

type Tab = 'scanner' | 'backtest';

function ScoreBar({ score }: { score: number }) {
  const color = score >= 7 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: `${score * 10}%`, height: 6,
        background: color, borderRadius: 3,
        transition: 'width 0.3s',
      }} />
      <span style={{ color, fontWeight: 600 }}>{score}/10</span>
    </div>
  );
}

function CandidateCard({ c, proposal }: {
  c: EPCandidate;
  proposal?: EPInvestProposal;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      background: '#1a1a2e', border: '1px solid #333',
      borderRadius: 8, padding: 16, marginBottom: 12,
    }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setOpen(o => !o)}
      >
        <div>
          <span style={{ fontWeight: 700, fontSize: 18, color: '#e2e8f0' }}>{c.ticker}</span>
          <span style={{ color: '#94a3b8', marginLeft: 8 }}>{c.name}</span>
          <span style={{
            marginLeft: 12, padding: '2px 8px', borderRadius: 4,
            background: c.catalyst === 'Earnings' ? '#166534' : '#1e3a5f',
            color: '#fff', fontSize: 12,
          }}>{c.catalyst}</span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ color: '#22c55e', fontWeight: 600 }}>+{c.gap_pct}%</span>
          <span style={{ color: '#94a3b8' }}>Vol {c.rel_vol}×</span>
          <ScoreBar score={c.score} />
          <span style={{ color: '#94a3b8' }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {open && (
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>ENTRY</div>
            <div>Zone: <b>${c.entry_zone_low.toFixed(2)} – ${c.entry_zone_high.toFixed(2)}</b></div>
            <div>Stop: <b style={{ color: '#ef4444' }}>${c.lotd_stop.toFixed(2)}</b> (LOTD)</div>
            <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 12 }}>{c.catalyst_detail}</div>
            <div style={{ marginTop: 8, fontStyle: 'italic', color: '#64748b' }}>{c.score_comment}</div>
          </div>
          {proposal && (
            <div>
              <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>
                INVEST-VORSCHLAG (€{proposal.kapital.toFixed(0)})
              </div>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: '#22c55e', fontWeight: 600 }}>Safe Play (IB)</span>
                <div>
                  {proposal.safe_play_shares} Stück · €{proposal.safe_play_cost.toFixed(0)} · Max Loss €{proposal.safe_play_max_loss.toFixed(0)}
                </div>
              </div>
              <div>
                <span style={{ color: '#f59e0b', fontWeight: 600 }}>YOLO Play (TR)</span>
                <div>
                  €{proposal.yolo_play_budget.toFixed(0)} · Call · Delta {proposal.yolo_play_delta_low.toFixed(2)}–{proposal.yolo_play_delta_high.toFixed(2)} · 6M
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{
      background: '#1a1a2e', border: '1px solid #333',
      borderRadius: 8, padding: 16, textAlign: 'center',
    }}>
      <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function EPPage() {
  const [tab, setTab] = useState<Tab>('scanner');
  const [scanData, setScanData] = useState<EPScanResponse | null>(null);
  const [btData, setBtData] = useState<EPBacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requireEarnings, setRequireEarnings] = useState(false);
  const [universe, setUniverse] = useState<'sp500' | 'nasdaq100' | 'both'>('both');

  async function handleScan() {
    setLoading(true); setError(null);
    try { setScanData(await scanEP()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  async function handleBacktest() {
    setLoading(true); setError(null);
    try { setBtData(await runEPBacktest('2016-01-01', '2026-01-01', 0.10, 2.0, requireEarnings, universe)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }

  const m = btData?.metrics;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24, fontFamily: 'monospace', color: '#e2e8f0' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>EP Scanner</h1>
      <p style={{ color: '#64748b', marginBottom: 24 }}>Episodic Pivot — Gap-up &gt; 10% mit Katalysator</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {(['scanner', 'backtest'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
            background: tab === t ? '#3b82f6' : '#1e293b',
            color: '#fff', fontWeight: tab === t ? 700 : 400,
          }}>{t === 'scanner' ? 'Heutiger Scan' : '10J Backtest'}</button>
        ))}
      </div>

      {tab === 'scanner' && (
        <div>
          <button onClick={handleScan} disabled={loading} style={{
            padding: '10px 24px', borderRadius: 6, border: 'none',
            background: '#3b82f6', color: '#fff', cursor: 'pointer',
            fontWeight: 600, marginBottom: 20,
          }}>{loading ? 'Scanne...' : 'Scan starten'}</button>

          {error && <div style={{ color: '#ef4444', marginBottom: 12 }}>{error}</div>}

          {scanData && (
            <div>
              <div style={{ color: '#64748b', marginBottom: 16 }}>
                {scanData.candidates.length} Kandidaten · {scanData.timestamp}
              </div>
              {scanData.candidates.length === 0
                ? <div style={{ color: '#64748b' }}>Heute keine EP-Kandidaten (Score &lt; 5)</div>
                : scanData.candidates.map(c => (
                  <CandidateCard
                    key={c.ticker}
                    c={c}
                    proposal={scanData.proposals[c.ticker]}
                  />
                ))
              }
            </div>
          )}
        </div>
      )}

      {tab === 'backtest' && (
        <div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
            <select
              value={universe}
              onChange={e => setUniverse(e.target.value as 'sp500' | 'nasdaq100' | 'both')}
              style={{ padding: '8px 12px', borderRadius: 6, background: '#1e293b', color: '#e2e8f0', border: '1px solid #333' }}
            >
              <option value="both">S&P500 + Nasdaq-100</option>
              <option value="sp500">S&P500</option>
              <option value="nasdaq100">Nasdaq-100</option>
            </select>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
              <input type="checkbox" checked={requireEarnings}
                     onChange={e => setRequireEarnings(e.target.checked)} />
              Nur Earnings-Katalysator
            </label>
            <button onClick={handleBacktest} disabled={loading} style={{
              padding: '10px 24px', borderRadius: 6, border: 'none',
              background: '#3b82f6', color: '#fff', cursor: 'pointer', fontWeight: 600,
            }}>{loading ? 'Berechne...' : 'Backtest 2016–2026'}</button>
          </div>

          {error && <div style={{ color: '#ef4444', marginBottom: 12 }}>{error}</div>}

          {m && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
                <MetricCard label="Trades" value={String(m.num_trades)} />
                <MetricCard label="Win Rate" value={`${m.win_rate.toFixed(1)}%`} />
                <MetricCard label="Expectancy" value={`${m.expectancy.toFixed(2)}%`} sub="pro Trade" />
                <MetricCard label="Sharpe" value={m.sharpe.toFixed(2)} />
                <MetricCard label="Max DD" value={`${Math.abs(m.max_drawdown).toFixed(1)}%`} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                <MetricCard label="Avg Win" value={`+${m.avg_win.toFixed(2)}%`} />
                <MetricCard label="Avg Loss" value={`${m.avg_loss.toFixed(2)}%`} />
                <MetricCard label="PEAD +5T" value={`${m.pead_5d.toFixed(2)}%`} sub="Ø nach 5 Tagen" />
                <MetricCard label="PEAD +20T" value={`${m.pead_20d.toFixed(2)}%`} sub="Ø nach 20 Tagen" />
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #333', color: '#64748b' }}>
                      {['Ticker','Entry','Exit','Gap%','RelVol','Catalyst','Hold','Perf%','Stop'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {btData!.trades.slice(0, 100).map((t, i) => (
                      <tr key={i} style={{
                        borderBottom: '1px solid #1e293b',
                        color: t.perf_pct > 0 ? '#22c55e' : '#ef4444',
                      }}>
                        <td style={{ padding: '6px 12px', fontWeight: 700 }}>{t.ticker}</td>
                        <td style={{ padding: '6px 12px' }}>{t.entry_date}</td>
                        <td style={{ padding: '6px 12px' }}>{t.exit_date}</td>
                        <td style={{ padding: '6px 12px' }}>+{t.gap_pct}%</td>
                        <td style={{ padding: '6px 12px' }}>{t.rel_vol}×</td>
                        <td style={{ padding: '6px 12px' }}>{t.catalyst}</td>
                        <td style={{ padding: '6px 12px' }}>{t.hold_days}d</td>
                        <td style={{ padding: '6px 12px', fontWeight: 700 }}>
                          {t.perf_pct > 0 ? '+' : ''}{t.perf_pct.toFixed(2)}%
                        </td>
                        <td style={{ padding: '6px 12px' }}>{t.hit_stop ? 'X' : '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {btData!.trades.length > 100 && (
                  <div style={{ color: '#64748b', marginTop: 8, fontSize: 12 }}>
                    Zeige 100 von {btData!.trades.length} Trades
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
