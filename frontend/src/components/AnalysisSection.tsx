import React, { useState } from 'react';
import { pdf } from '@react-pdf/renderer';
import { analyzeBig5 } from '../api/client';
import { Big5Report } from './Big5Report';
import type { Big5BacktestResponse } from '../types';

interface Props {
  data: Big5BacktestResponse;
}

function renderAnalysis(text: string) {
  return text.split('\n').map((line, i) => {
    if (line.startsWith('## ')) {
      return (
        <p key={i} className="text-sm font-semibold mt-5 mb-1" style={{ color: '#00C48C' }}>
          {line.replace('## ', '')}
        </p>
      );
    }
    if (!line.trim()) return <div key={i} className="h-1" />;
    return (
      <p key={i} className="text-xs leading-relaxed" style={{ color: '#C8CAD8' }}>
        {line}
      </p>
    );
  });
}

export function AnalysisSection({ data }: Props) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeBig5(data);
      setAnalysis(res.analysis);
    } catch (e: any) {
      setError(e?.message ?? 'Analyse fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    if (!analysis) return;
    setPdfLoading(true);
    try {
      const blob = await pdf(<Big5Report data={data} analysis={analysis} />).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Big5_AnalystReport_${data.indicator}${data.period}_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <div className="rounded-lg p-4 mt-4" style={{ background: '#1A1D27' }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium" style={{ color: '#E8EAED' }}>Analyst Report</p>
        <div className="flex gap-2">
          {analysis && (
            <button
              onClick={handleDownloadPdf}
              disabled={pdfLoading}
              className="px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50"
              style={{ background: '#3B4FC8', color: '#fff' }}
            >
              {pdfLoading ? 'Generiert...' : '↓ PDF herunterladen'}
            </button>
          )}
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50"
            style={{ background: '#00C48C', color: '#000' }}
          >
            {loading ? 'Analysiert...' : analysis ? 'Neu analysieren' : 'Analyse starten'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-2 rounded text-xs mb-3" style={{ background: '#FF475720', color: '#FF4757' }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="p-6 text-center text-xs" style={{ color: '#8B8FA8' }}>
          Strategie wird analysiert...
        </div>
      )}

      {analysis && !loading && (
        <div className="mt-2 p-4 rounded" style={{ background: '#151720' }}>
          {renderAnalysis(analysis)}
        </div>
      )}
    </div>
  );
}
