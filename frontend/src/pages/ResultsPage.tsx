import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { getSearchBusinesses, listSearches } from "../lib/api";
import { ScrapeSelector } from "../components/ScrapeSelector";
import { BusinessCard } from "../components/BusinessCard";
import { FilterPills, applyFilter, type FilterKey } from "../components/FilterPills";

export function ResultsPage() {
  // ─── Liste des scrapes ──────────────────────────────────────────────
  const searchesQ = useQuery({
    queryKey: ["searches"],
    queryFn: () => listSearches(100),
  });

  const [activeSearchId, setActiveSearchId] = useState<number | null>(null);

  // Auto-sélection du scrape le plus récent quand les données arrivent
  const effectiveSearchId =
    activeSearchId ?? (searchesQ.data?.[0]?.id ?? null);

  // ─── Fiches du scrape sélectionné ───────────────────────────────────
  const businessesQ = useQuery({
    queryKey: ["businesses", effectiveSearchId],
    queryFn: () => getSearchBusinesses(effectiveSearchId!),
    enabled: effectiveSearchId !== null,
  });

  // ─── Filtres + recherche ────────────────────────────────────────────
  const [filter, setFilter] = useState<FilterKey>("all");
  const [searchText, setSearchText] = useState("");

  const filtered = useMemo(() => {
    if (!businessesQ.data) return [];
    let list = applyFilter(businessesQ.data.items, filter);
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      list = list.filter((b) =>
        [
          b.name,
          b.locality,
          b.city,
          b.category,
          b.address,
          b.managers,
          b.vat_number,
          b.phone,
        ].some((f) => f?.toLowerCase().includes(q)),
      );
    }
    return list;
  }, [businessesQ.data, filter, searchText]);

  // ─── États de chargement ────────────────────────────────────────────
  if (searchesQ.isLoading) {
    return (
      <div className="text-center py-20 text-ink-500">
        Chargement des scrapes…
      </div>
    );
  }
  if (searchesQ.error) {
    return (
      <ErrorPanel message={`Backend injoignable. Démarre-le avec :
uvicorn backend.main:app --reload --port 8000`} />
    );
  }
  if (!searchesQ.data?.length) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-6">
      {/* En-tête : sélecteur de scrape */}
      <div className="card p-5">
        <label className="block text-xs font-semibold text-ink-500 uppercase tracking-wider mb-2">
          Scrape affiché
        </label>
        <ScrapeSelector
          searches={searchesQ.data}
          value={effectiveSearchId}
          onChange={setActiveSearchId}
        />
      </div>

      {/* Métriques */}
      {businessesQ.data && (
        <Metrics
          total={businessesQ.data.total}
          businesses={businessesQ.data.items}
        />
      )}

      {/* Filtres + recherche */}
      {businessesQ.data && (
        <div className="card p-5 space-y-4">
          <FilterPills
            businesses={businessesQ.data.items}
            creditCounts={businessesQ.data.credit_counts}
            active={filter}
            onChange={setFilter}
          />
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Rechercher par nom, ville ou TVA…"
              className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-ink-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </div>
          <div className="text-xs text-ink-500">
            {filtered.length} fiche(s) affichée(s) sur {businessesQ.data.total}
          </div>
        </div>
      )}

      {/* Grille de cards */}
      {businessesQ.isLoading ? (
        <div className="text-center py-20 text-ink-500">
          Chargement des fiches…
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-ink-500">
          Aucune fiche ne correspond aux filtres.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((b) => (
            <BusinessCard key={b.dedup_key} business={b} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Sous-composants ─────────────────────────────────────────────────

function Metrics({
  total,
  businesses,
}: {
  total: number;
  businesses: import("../lib/types").BusinessSummary[];
}) {
  const top2 = businesses.filter(
    (b) => b.google_rank !== null && b.google_rank <= 2,
  ).length;
  const withPhone = businesses.filter((b) => b.phone).length;
  const withVat = businesses.filter((b) => b.vat_number).length;
  const withMgr = businesses.filter((b) => b.managers).length;
  const called = businesses.filter((b) => b.call_status === "Déjà appelé")
    .length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
      <Metric label="Fiches" value={total} />
      <Metric label="Top 2 Google" value={top2} />
      <Metric label="Avec téléphone" value={withPhone} />
      <Metric label="Avec TVA" value={withVat} />
      <Metric label="Avec dirigeant" value={withMgr} />
      <Metric label="Déjà appelé" value={called} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4">
      <div className="text-2xl font-bold text-ink-900">{value}</div>
      <div className="text-xs text-ink-500 mt-0.5">{label}</div>
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="card p-8 border-red-200 bg-red-50">
      <div className="font-semibold text-red-900 mb-2">Erreur</div>
      <pre className="text-xs text-red-800 whitespace-pre-wrap font-mono">
        {message}
      </pre>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card p-12 text-center">
      <div className="text-lg font-semibold text-ink-900 mb-2">
        Aucun scrape dans l'historique
      </div>
      <p className="text-sm text-ink-500">
        Lance un scrape depuis l'app Streamlit (
        <code className="text-xs">streamlit run app.py</code>) puis recharge
        cette page.
      </p>
    </div>
  );
}
