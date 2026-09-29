"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCurrency } from "@/lib/currency";

export function CurrencySwitcher() {
  const { code, codes, setCode } = useCurrency();
  return (
    <Select value={code} onValueChange={setCode}>
      <SelectTrigger size="sm" className="w-[5.5rem]" aria-label="Currency">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {codes.map((c) => (
          <SelectItem key={c} value={c}>
            {c}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
