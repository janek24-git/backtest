import type { UniverseType, UniverseSize } from '../types';

interface Props {
  universeType: UniverseType;
  universeSize: UniverseSize;
  onTypeChange: (type: UniverseType) => void;
  onSizeChange: (size: UniverseSize) => void;
}

const SP500_SIZES: UniverseSize[] = [5, 10];
const NAS100_SIZES: UniverseSize[] = [5, 10, 20];

export function UniverseSelector({ universeType, universeSize, onTypeChange, onSizeChange }: Props) {
  function handleTypeChange(type: UniverseType) {
    onTypeChange(type);
    if (type === 'SP500' && universeSize === 20) {
      onSizeChange(5);
    }
  }

  const sizes = universeType === 'SP500' ? SP500_SIZES : NAS100_SIZES;

  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1">
        {(['SP500', 'NAS100'] as UniverseType[]).map((t) => (
          <button
            key={t}
            onClick={() => handleTypeChange(t)}
            className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
              universeType === t
                ? 'bg-[#00C48C] text-black'
                : 'bg-[#1E2130] text-[#8B8FA8] hover:bg-[#2A2D3E]'
            }`}
          >
            {t === 'SP500' ? 'S&P 500' : 'NAS100'}
          </button>
        ))}
      </div>

      <span style={{ color: '#2A2D3E' }}>|</span>

      <div className="flex gap-1">
        {sizes.map((s) => (
          <button
            key={s}
            onClick={() => onSizeChange(s)}
            className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
              universeSize === s
                ? 'bg-[#3B4FC8] text-white'
                : 'bg-[#1E2130] text-[#8B8FA8] hover:bg-[#2A2D3E]'
            }`}
          >
            Top {s}
          </button>
        ))}
      </div>
    </div>
  );
}
