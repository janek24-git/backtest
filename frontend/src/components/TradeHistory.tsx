// frontend/src/components/TradeHistory.tsx
import type { TradeRecord } from '../types';

interface Props {
  trades: TradeRecord[];
}

export function TradeHistory({ trades }: Props) {
  const sorted = [...trades].reverse();

  return (
    <div className="overflow-auto max-h-72">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[#8B8FA8] border-b border-[#2A2D3E]">
            <th className="text-left py-2 pr-4">Entry Date</th>
            <th className="text-left py-2 pr-4">Exit Date</th>
            <th className="text-right py-2 pr-4">Hold (d)</th>
            <th className="text-right py-2 pr-4">Entry</th>
            <th className="text-right py-2 pr-4">Exit</th>
            <th className="text-right py-2">Return</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr key={i} className="border-b border-[#1E2130] hover:bg-[#1E2130]">
              <td className="py-2 pr-4 text-[#8B8FA8]">{t.entry_date}</td>
              <td className="py-2 pr-4 text-[#8B8FA8]">{t.exit_date}</td>
              <td className="py-2 pr-4 text-right">{t.hold_days}</td>
              <td className="py-2 pr-4 text-right">${t.entry_price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right">${t.exit_price.toFixed(2)}</td>
              <td
                className="py-2 text-right font-medium"
                style={{ color: t.return_pct >= 0 ? '#00C48C' : '#FF4757' }}
              >
                {t.return_pct >= 0 ? '+' : ''}{t.return_pct.toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
