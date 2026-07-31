"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { formatInrFromPaise } from "@/lib/format";

const PRESET_AMOUNTS_IN_PAISE = [50100, 100100, 250100, 500100];

interface AmountPickerProps {
  valueInPaise: number | null;
  onChange: (amountInPaise: number | null) => void;
  customAmountInput: string;
  onCustomAmountInputChange: (value: string) => void;
}

export function AmountPicker({
  valueInPaise,
  onChange,
  customAmountInput,
  onCustomAmountInputChange,
}: AmountPickerProps) {
  const [isCustomFocused, setIsCustomFocused] = useState(false);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {PRESET_AMOUNTS_IN_PAISE.map((preset) => {
          const isSelected =
            valueInPaise === preset && customAmountInput === "" && !isCustomFocused;
          return (
            <button
              key={preset}
              type="button"
              onClick={() => {
                onCustomAmountInputChange("");
                onChange(preset);
              }}
              className={cn(
                "rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors",
                isSelected
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input bg-background hover:border-primary/50 hover:bg-accent",
              )}
            >
              {formatInrFromPaise(preset)}
            </button>
          );
        })}
      </div>

      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted-foreground">
          ₹
        </span>
        <input
          type="text"
          inputMode="numeric"
          placeholder="Enter a custom amount"
          value={customAmountInput}
          onFocus={() => setIsCustomFocused(true)}
          onBlur={() => setIsCustomFocused(false)}
          onChange={(e) => {
            const digitsOnly = e.target.value.replace(/[^0-9]/g, "");
            onCustomAmountInputChange(digitsOnly);
            onChange(digitsOnly ? Number(digitsOnly) * 100 : null);
          }}
          className="border-input bg-background flex h-10 w-full rounded-lg border pl-7 pr-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
        />
      </div>
    </div>
  );
}
