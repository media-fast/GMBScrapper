import type { SearchSummary } from "../lib/types";
import { formatRanAt } from "../lib/utils";

interface Props {
  searches: SearchSummary[];
  value: number | null;
  onChange: (id: number) => void;
}

export function ScrapeSelector({ searches, value, onChange }: Props) {
  return (
    <div style={{ position: "relative" }}>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{
          appearance: "none",
          background: "var(--paper)",
          border: "1px solid var(--ink-200)",
          borderRadius: 10,
          padding: "10px 36px 10px 14px",
          fontSize: 13,
          fontWeight: 500,
          color: "var(--ink-900)",
          fontFamily: "inherit",
          cursor: "pointer",
          width: "100%",
          outline: "none",
        }}
        onFocus={(e) => {
          e.target.style.borderColor = "var(--indigo-600)";
          e.target.style.boxShadow = "0 0 0 3px rgba(79, 63, 240, 0.1)";
        }}
        onBlur={(e) => {
          e.target.style.borderColor = "var(--ink-200)";
          e.target.style.boxShadow = "";
        }}
      >
        {searches.map((s) => (
          <option key={s.id} value={s.id}>
            #{s.id} · {s.query} · {(s.cities || "").slice(0, 40)} ·{" "}
            {formatRanAt(s.ran_at)} ({s.total} fiches)
          </option>
        ))}
      </select>
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--ink-400)"
        strokeWidth="2"
        style={{
          position: "absolute",
          right: 12,
          top: "50%",
          transform: "translateY(-50%)",
          width: 16,
          height: 16,
          pointerEvents: "none",
        }}
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  );
}
