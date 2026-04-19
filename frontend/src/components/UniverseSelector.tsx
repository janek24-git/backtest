import type { UniverseSize } from '../types';

interface Props {
  value: UniverseSize;
  onChange: (size: UniverseSize) => void;
}

const sizes: UniverseSize[] = [5, 10, 20];

export function UniverseSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {sizes.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            value === s
              ? 'bg-[#00C48C] text-black'
              : 'bg-[#1E2130] text-[#8B8FA8] hover:bg-[#2A2D3E]'
          }`}
        >
          Top {s}
        </button>
      ))}
    </div>
  );
}
