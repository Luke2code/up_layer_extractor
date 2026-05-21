interface SegmentedControlProps {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

export function SegmentedControl({ label, options, value, onChange }: SegmentedControlProps) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[11px] font-medium text-slate-600">{label}</span>
      <div className="inline-flex max-w-[32rem] overflow-x-auto bg-slate-100">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={`whitespace-nowrap px-2 py-1 text-[11px] focus:outline-none focus:ring-2 focus:ring-accent ${
              option === value ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-200"
            }`}
            aria-pressed={option === value}
            onClick={() => onChange(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
