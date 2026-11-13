import type { ReactNode } from "react";

export interface SegmentedOption<T extends string> {
  id: T;
  label: ReactNode;
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}

/** Tab-style switch used for task filters and the admin page tabs. */
export default function Segmented<T extends string>({ options, value, onChange, label }: SegmentedProps<T>) {
  return (
    <div className="segmented" role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          aria-selected={value === option.id}
          className={value === option.id ? "active" : ""}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
