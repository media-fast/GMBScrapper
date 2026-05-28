import type { BusinessSummary, CreditColor } from "../lib/types";
import { cn } from "../lib/utils";

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

interface FilterDef {
  key: FilterKey;
  label: string;
  count: number;
  predicate: (b: BusinessSummary) => boolean;
}

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

  const filters: FilterDef[] = [
    {
      key: "all",
      label: `Tous (${total})`,
      count: total,
      predicate: () => true,
    },
    {
      key: "top2",
      label: `Top 2 Google (${top2})`,
      count: top2,
      predicate: (b) => b.google_rank !== null && b.google_rank <= 2,
    },
    {
      key: "with_vat",
      label: `Avec TVA (${withVat})`,
      count: withVat,
      predicate: (b) => !!b.vat_number,
    },
    {
      key: "without_vat",
      label: `Sans TVA (${withoutVat})`,
      count: withoutVat,
      predicate: (b) => !b.vat_number,
    },
    {
      key: "with_web",
      label: `Avec site (${withWeb})`,
      count: withWeb,
      predicate: (b) => !!b.website,
    },
    {
      key: "without_web",
      label: `Sans site (${withoutWeb})`,
      count: withoutWeb,
      predicate: (b) => !b.website,
    },
    {
      key: "without_phone",
      label: `Sans téléphone (${withoutPhone})`,
      count: withoutPhone,
      predicate: (b) => !b.phone,
    },
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
      filters.push({
        key,
        label: `${label} (${n})`,
        count: n,
        predicate: (b) => b.credit_color === color,
      });
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {filters.map((f) => (
        <button
          key={f.key}
          type="button"
          onClick={() => onChange(f.key)}
          className={cn(
            "px-3 py-1.5 rounded-full text-xs font-semibold transition",
            "ring-1 ring-inset",
            active === f.key
              ? "bg-brand-700 text-white ring-brand-700 shadow-sm"
              : "bg-white text-ink-700 ring-ink-200 hover:bg-ink-50",
          )}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Helper séparé : applique le filtre actif à la liste.
 * Garde la logique groupée avec les définitions.
 */
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
