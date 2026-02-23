"use client";

type SegmentedControlOption = {
  value: string;
  label: string;
};

type SegmentedControlProps = {
  value: string;
  options: SegmentedControlOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
};

export function SegmentedControl({
  value,
  options,
  onChange,
  disabled = false,
}: SegmentedControlProps) {
  return (
    <div
      className={`segmented-control${disabled ? " is-disabled" : ""}`}
      role="radiogroup"
      aria-disabled={disabled}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            className={`segmented-control-option${active ? " is-active" : ""}`}
            onClick={() => {
              if (!disabled) onChange(option.value);
            }}
            role="radio"
            aria-checked={active}
            disabled={disabled}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
