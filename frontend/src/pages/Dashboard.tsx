import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UniverseSelector } from '../components/UniverseSelector';
import { PeriodSelector } from '../components/PeriodSelector';
import { ResultsTable } from '../components/ResultsTable';
import { OptimizationBook } from '../components/OptimizationBook';
import { runBacktest } from '../api/client';
import type { UniverseType, UniverseSize, PeriodKey, BacktestResponse } from '../types';

export function Dashboard() {
  const navigate = useNavigate();
  const [universeType, setUniverseType] = useState<UniverseType>('SP500');
  const [universeSize, setUniverseSize] = useState<UniverseSize>(5);
  const [period, setPeriod] = useState<PeriodKey>('ALL');
  const [results, setResults] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showOptim, setShowOptim] = useState(false);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const data = await runBacktest(universeSize, universeType);
      setResults(data);
    } catch (e: any) {
      setError(e?.message ?? 'Backtest failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen p-6" style={{ background: '#0F1117' }}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight" style={{ color: '#E8EAED' }}>
              EMA200 Backtest
            </h1>
            <p className="text-xs mt-0.5" style={{ color: '#8B8FA8' }}>
              S&P 500 · Daily Close · yfinance · 2000–2025
            </p>
          </div>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded text-sm font-medium"
            style={{ background: '#1E2130', color: '#00C48C', border: '1px solid #00C48C' }}
          >
            ← Big 5 Swing
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Universe</p>
            <UniverseSelector
              universeType={universeType}
              universeSize={universeSize}
              onTypeChange={setUniverseType}
              onSizeChange={setUniverseSize}
            />
          </div>
          <div>
            <p className="text-xs mb-1.5" style={{ color: '#8B8FA8' }}>Period</p>
            <PeriodSelector value={period} onChange={setPeriod} />
          </div>
          <div className="ml-auto mt-5">
            <button
              onClick={handleRun}
              disabled={loading}
              className="px-6 py-2 rounded font-medium text-sm disabled:opacity-50"
              style={{ background: '#00C48C', color: '#000' }}
            >
              {loading ? 'Running...' : 'Run Backtest'}
            </button>
          </div>
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
            <div className="rounded-lg p-4" style={{ background: '#1A1D27' }}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm" style={{ color: '#8B8FA8' }}>
                  {results.universe_type} Top{results.universe_size} · {results.results.length} tickers · EMA{results.ema_period} · Click row for detail
                </p>
              </div>
              <ResultsTable results={results.results} period={period} />
            </div>

            {/* Optimization Book toggle */}
            <div>
              <button
                onClick={() => setShowOptim(!showOptim)}
                className="text-sm underline"
                style={{ color: showOptim ? '#00C48C' : '#8B8FA8' }}
              >
                {showOptim ? '▼ Hide' : '▶ Show'} Optimization Book
              </button>
              {showOptim && (
                <div className="mt-3">
                  <OptimizationBook universeSize={universeSize} universeType={universeType} currentResults={results} />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
