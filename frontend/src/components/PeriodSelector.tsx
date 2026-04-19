import type { PeriodKey } from '../types';

interface Props {
  value: PeriodKey;
  onChange: (period: PeriodKey) => void;
}

const periods: PeriodKey[] = ['1M', '3M', '6M', '1Y', '3Y', '5Y', 'ALL'];

export function PeriodSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {periods.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
            value === p
              ? 'bg-[#1E2130] text-[#00C48C] border border-[#00C48C]'
              : 'bg-[#1E2130] text-[#8B8FA8] hover:text-[#E8EAED]'
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
