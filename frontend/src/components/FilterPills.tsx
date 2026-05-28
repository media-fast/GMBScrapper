/**
 * FilterPills — version Oui Allo (pas de Tailwind).
 */

import type { BusinessSummary, CreditColor } from "../lib/types";

export type FilterKey =
  | "all"
  | "top2"
  | "with_vat"
  | "without_vat"
  | "with_web"
  | "without_web"
  | "without_phone"
  | "credit_green"
  | "credit_yellow"
  | "credit_orange"
  | "credit_red"
  | "credit_gray";

interface Props {
  businesses: BusinessSummary[];
  creditCounts: Partial<Record<CreditColor, number>>;
  active: FilterKey;
  onChange: (key: FilterKey) => void;
}

export function FilterPills({
  businesses,
  creditCounts,
  active,
  onChange,
}: Props) {
  const total = businesses.length;
  const top2 = businesses.filter(
    (b) => b.google_rank !== null && b.google_rank <= 2,
  ).length;
  const withVat = businesses.filter((b) => b.vat_number).length;
  const withoutVat = total - withVat;
  const withWeb = businesses.filter((b) => b.website).length;
  const withoutWeb = total - withWeb;
  const withoutPhone = businesses.filter((b) => !b.phone).length;

  const filters: { key: FilterKey; label: string }[] = [
    { key: "all", label: `Tous (${total})` },
    { key: "top2", label: `Top 2 Google (${top2})` },
    { key: "with_vat", label: `Avec TVA (${withVat})` },
    { key: "without_vat", label: `Sans TVA (${withoutVat})` },
    { key: "with_web", label: `Avec site (${withWeb})` },
    { key: "without_web", label: `Sans site (${withoutWeb})` },
    { key: "without_phone", label: `Sans téléphone (${withoutPhone})` },
  ];

  // Filtres crédit : seulement ceux dont count > 0
  const creditFilters: Array<[FilterKey, CreditColor, string]> = [
    ["credit_green", "green", "🟢 Bon payeur"],
    ["credit_yellow", "yellow", "🟡 À surveiller"],
    ["credit_orange", "orange", "🟠 À risque"],
    ["credit_red", "red", "🔴 Mauvais payeur"],
    ["credit_gray", "gray", "⚪ Non évalué"],
  ];
  for (const [key, color, label] of creditFilters) {
    const n = creditCounts[color] || 0;
    if (n > 0) {
      filters.push({ key, label: `${label} (${n})` });
    }
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {filters.map((f) => {
        const isActive = active === f.key;
        return (
          <button
            key={f.key}
            type="button"
            onClick={() => onChange(f.key)}
            style={{
              padding: "7px 14px",
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: "pointer",
              transition: "all .15s ease",
              border: "1px solid",
              borderColor: isActive ? "var(--indigo-900)" : "var(--ink-200)",
              background: isActive ? "var(--indigo-900)" : "var(--paper)",
              color: isActive ? "white" : "var(--ink-700)",
              boxShadow: isActive ? "0 2px 6px rgba(26, 14, 92, 0.15)" : "none",
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.borderColor = "var(--indigo-600)";
                e.currentTarget.style.color = "var(--indigo-700)";
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.borderColor = "var(--ink-200)";
                e.currentTarget.style.color = "var(--ink-700)";
              }
            }}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}

/** Helper séparé : applique le filtre actif à la liste. */
export function applyFilter(
  businesses: BusinessSummary[],
  key: FilterKey,
): BusinessSummary[] {
  switch (key) {
    case "all":
      return businesses;
    case "top2":
      return businesses.filter(
        (b) => b.google_rank !== null && b.google_rank <= 2,
      );
    case "with_vat":
      return businesses.filter((b) => !!b.vat_number);
    case "without_vat":
      return businesses.filter((b) => !b.vat_number);
    case "with_web":
      return businesses.filter((b) => !!b.website);
    case "without_web":
      return businesses.filter((b) => !b.website);
    case "without_phone":
      return businesses.filter((b) => !b.phone);
    case "credit_green":
      return businesses.filter((b) => b.credit_color === "green");
    case "credit_yellow":
      return businesses.filter((b) => b.credit_color === "yellow");
    case "credit_orange":
      return businesses.filter((b) => b.credit_color === "orange");
    case "credit_red":
      return businesses.filter((b) => b.credit_color === "red");
    case "credit_gray":
      return businesses.filter((b) => b.credit_color === "gray");
  }
}
