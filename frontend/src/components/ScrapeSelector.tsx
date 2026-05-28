import { ChevronDown } from "lucide-react";
import type { SearchSummary } from "../lib/types";
import { formatRanAt } from "../lib/utils";

interface Props {
  searches: SearchSummary[];
  value: number | null;
  onChange: (id: number) => void;
}

export function ScrapeSelector({ searches, value, onChange }: Props) {
  return (
    <div className="relative">
      <select
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        className="appearance-none bg-white border border-ink-200 rounded-lg pl-4 pr-10 py-2.5 text-sm font-medium text-ink-800 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 cursor-pointer w-full"
      >
        {searches.map((s) => (
          <option key={s.id} value={s.id}>
            #{s.id} · {s.query} · {(s.cities || "").slice(0, 40)} ·{" "}
            {formatRanAt(s.ran_at)} ({s.total} fiches)
          </option>
        ))}
      </select>
      <ChevronDown
        className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400 pointer-events-none"
      />
    </div>
  );
}
