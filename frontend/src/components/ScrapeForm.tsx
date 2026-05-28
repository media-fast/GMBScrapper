/**
 * Form Lancer un scrape — style Oui Allo original.
 *
 * Structure :
 *   - Card avec titre serif + sous-titre
 *   - Multi-select « Métiers ciblés » (chips violets + input recherche)
 *   - Input violet pâle « Métier(s) personnalisé(s) » séparés par virgule
 *   - Toggle switch « Inclure les variantes du métier (recommandé) »
 *   - 3 pills zone de prospection (Par arrondissement / Par commune / Par rayon)
 *   - Input contextuel selon le mode zone
 *   - Section repliable « Paramètres avancés »
 *   - Footer : estimation à gauche + bouton noir à droite
 */

import { useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { startScrape } from "../lib/api";

// Suggestions de métiers (suit le template Oui Allo). L'user peut aussi
// taper du texte libre dans le champ personnalisé.
const METIER_SUGGESTIONS = [
  "opticien",
  "dentiste",
  "garage automobile",
  "avocat",
  "agent immobilier",
  "agence immobilière",
  "restaurant",
  "boulangerie",
  "coiffeur",
  "pharmacie",
  "médecin généraliste",
  "kinésithérapeute",
  "vétérinaire",
  "comptable",
  "architecte",
  "plombier",
  "électricien",
  "menuisier",
  "couvreur",
  "peintre",
  "courtier en assurance",
  "agence de voyage",
  "fleuriste",
  "épicerie",
  "salle de sport",
  "magasin de vélos",
  "concessionnaire auto",
];

const ZONE_MODES = [
  { key: "arrondissement", label: "Par arrondissement" },
  { key: "commune", label: "Par commune" },
  { key: "radius", label: "Par rayon" },
] as const;

type ZoneMode = (typeof ZONE_MODES)[number]["key"];

interface Props {
  onStarted: (scrapeId: string) => void;
  disabled?: boolean;
}

export function ScrapeForm({ onStarted, disabled }: Props) {
  // Multi-select métiers (sélectionnés depuis la liste)
  const [selectedMetiers, setSelectedMetiers] = useState<string[]>([]);
  const [metierSearch, setMetierSearch] = useState("");
  const [showMetierList, setShowMetierList] = useState(false);
  const metierInputRef = useRef<HTMLInputElement>(null);

  // Métiers personnalisés (texte libre, virgule séparé)
  const [customMetiers, setCustomMetiers] = useState("");

  // Variantes
  const [includeVariants, setIncludeVariants] = useState(true);

  // Zone de prospection
  const [zoneMode, setZoneMode] = useState<ZoneMode | null>(null);
  const [zoneInput, setZoneInput] = useState("");

  // Paramètres avancés
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxPerCity, setMaxPerCity] = useState(30);
  const [strictCity, setStrictCity] = useState(true);
  const [requirePhone, setRequirePhone] = useState(false);
  const [doCreditScoring, setDoCreditScoring] = useState(false);
  const [headless, setHeadless] = useState(true);
  const [workers, setWorkers] = useState(6);

  // Calcul des métiers finaux
  const metiers = useMemo(() => {
    const customList = customMetiers
      .split(/[,;\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    return Array.from(new Set([...selectedMetiers, ...customList]));
  }, [selectedMetiers, customMetiers]);

  const cities = useMemo(
    () =>
      zoneInput
        .split(/[,;\n]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    [zoneInput],
  );

  // Suggestions filtrées
  const filteredSuggestions = useMemo(() => {
    const q = metierSearch.trim().toLowerCase();
    return METIER_SUGGESTIONS.filter(
      (m) => !selectedMetiers.includes(m) && (!q || m.toLowerCase().includes(q)),
    ).slice(0, 8);
  }, [metierSearch, selectedMetiers]);

  // Estimation
  const { estimateLow, estimateHigh, timeMin } = useMemo(() => {
    const nbCombos = metiers.length * cities.length;
    const cap = Math.min(maxPerCity, 30);
    let yieldHigh = strictCity ? 0.65 : 0.8;
    let yieldLow = strictCity ? 0.25 : 0.4;
    if (requirePhone) {
      yieldHigh *= 0.85;
      yieldLow *= 0.85;
    }
    const high = Math.floor(nbCombos * cap * yieldHigh);
    const low = Math.floor(nbCombos * cap * yieldLow);
    const rawFiches = Math.floor(nbCombos * cap * 0.7);
    const minTime = Math.max(1, Math.floor((rawFiches * 6) / 60));
    return { estimateLow: low, estimateHigh: high, timeMin: minTime };
  }, [metiers, cities, maxPerCity, strictCity, requirePhone]);

  const mutation = useMutation({
    mutationFn: startScrape,
    onSuccess: (data) => onStarted(data.scrape_id),
  });

  const canLaunch =
    !disabled &&
    !mutation.isPending &&
    metiers.length > 0 &&
    cities.length > 0;

  const handleLaunch = () => {
    if (!canLaunch) return;
    mutation.mutate({
      metiers,
      cities,
      max_per_city: maxPerCity,
      headless,
      strict_city: strictCity,
      require_phone: requirePhone,
      do_vat: true,
      do_bce: true,
      do_fin: true,
      do_credit_scoring: doCreditScoring,
      workers,
    });
  };

  const addMetier = (m: string) => {
    if (!selectedMetiers.includes(m)) {
      setSelectedMetiers((prev) => [...prev, m]);
    }
    setMetierSearch("");
    metierInputRef.current?.focus();
  };
  const removeMetier = (m: string) => {
    setSelectedMetiers((prev) => prev.filter((x) => x !== m));
  };

  const zonePlaceholder =
    zoneMode === "arrondissement"
      ? "ex : Bruxelles, Liège, Mons (un par ligne)"
      : zoneMode === "commune"
        ? "ex : Waterloo, Braine-l'Alleud, Nivelles"
        : zoneMode === "radius"
          ? "ex : Waterloo (rayon 15 km depuis cette commune)"
          : "Choisis d'abord un mode de zone ci-dessus";

  return (
    <div className="oa-form-card">
      <div className="oa-form-card__inner">
        <div className="oa-form-card__header">
          <div>
            <h2 className="oa-form-card__title">Nouvelle recherche</h2>
            <p className="oa-form-card__sub">
              Définis les métiers, les zones et les options d'enrichissement.
            </p>
          </div>
        </div>

        {/* Multi-select Métiers ciblés */}
        <div className="oa-form-field">
          <label className="oa-form-field__label" style={{ display: "flex", alignItems: "center" }}>
            Métiers ciblés
            <HelpTip title="Choisis dans la liste ou tape pour rechercher. Tu peux aussi ajouter des métiers personnalisés ci-dessous." />
          </label>
          <div
            className="oa-multiselect"
            onClick={() => {
              setShowMetierList(true);
              metierInputRef.current?.focus();
            }}
            onBlur={(e) => {
              // Ferme la liste si le focus quitte le composant entier
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                setTimeout(() => setShowMetierList(false), 150);
              }
            }}
            style={{ position: "relative" }}
            tabIndex={-1}
          >
            {selectedMetiers.map((m) => (
              <span key={m} className="oa-multiselect__chip">
                {m}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeMetier(m);
                  }}
                  aria-label={`Retirer ${m}`}
                >
                  ×
                </button>
              </span>
            ))}
            <input
              ref={metierInputRef}
              type="text"
              className="oa-multiselect__input"
              value={metierSearch}
              onChange={(e) => {
                setMetierSearch(e.target.value);
                setShowMetierList(true);
              }}
              onFocus={() => setShowMetierList(true)}
              placeholder={
                selectedMetiers.length === 0
                  ? "Choisis un ou plusieurs métiers (ou tape pour chercher)…"
                  : ""
              }
              disabled={disabled || mutation.isPending}
            />
            <span className="oa-multiselect__chevron">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </span>

            {/* Dropdown suggestions */}
            {showMetierList && filteredSuggestions.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 4px)",
                  left: 0,
                  right: 0,
                  background: "var(--paper)",
                  border: "1px solid var(--ink-200)",
                  borderRadius: 10,
                  boxShadow: "var(--shadow-md)",
                  zIndex: 10,
                  maxHeight: 280,
                  overflowY: "auto",
                }}
                onMouseDown={(e) => e.preventDefault()}
              >
                {filteredSuggestions.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => addMetier(m)}
                    style={{
                      width: "100%",
                      padding: "9px 14px",
                      background: "transparent",
                      border: "none",
                      textAlign: "left",
                      fontFamily: "inherit",
                      fontSize: 13,
                      color: "var(--ink-900)",
                      cursor: "pointer",
                      transition: "background .1s",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "var(--indigo-50)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "transparent")
                    }
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Métier personnalisé */}
        <div className="oa-form-field">
          <label className="oa-form-field__label">
            Métier(s) personnalisé(s) (séparés par virgule)
          </label>
          <input
            type="text"
            className="oa-form-field__input oa-form-field__input--violet"
            placeholder="ex : magasin de vélos, salle de sport, traiteur"
            value={customMetiers}
            onChange={(e) => setCustomMetiers(e.target.value)}
            disabled={disabled || mutation.isPending}
          />
        </div>

        {/* Toggle variantes */}
        <label
          className={`oa-toggle ${includeVariants ? "is-on" : ""}`}
        >
          <input
            type="checkbox"
            checked={includeVariants}
            onChange={(e) => setIncludeVariants(e.target.checked)}
            disabled={disabled || mutation.isPending}
          />
          <span className="oa-toggle__switch" />
          <span>
            Inclure les variantes du métier (recommandé)
            <HelpTip title="Étend automatiquement chaque métier avec des synonymes (« dentiste » → « cabinet dentaire », « orthodontiste », etc.) pour rater moins de fiches." />
          </span>
        </label>

        {/* Zone de prospection */}
        <div className="oa-form-field">
          <label className="oa-form-field__label">Zone de prospection</label>
          <div className="oa-zone-pills">
            {ZONE_MODES.map((mode) => (
              <button
                key={mode.key}
                type="button"
                className={`oa-zone-pill ${zoneMode === mode.key ? "is-active" : ""}`}
                onClick={() =>
                  setZoneMode(zoneMode === mode.key ? null : mode.key)
                }
                disabled={disabled || mutation.isPending}
              >
                {mode.label}
              </button>
            ))}
          </div>
          {zoneMode && (
            <textarea
              className="oa-form-field__input"
              placeholder={zonePlaceholder}
              value={zoneInput}
              onChange={(e) => setZoneInput(e.target.value)}
              disabled={disabled || mutation.isPending}
              rows={2}
              style={{ resize: "vertical", minHeight: 56, marginTop: 10 }}
            />
          )}
        </div>

        {/* Paramètres avancés (collapsible) */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            style={{
              background: "none",
              border: "1px solid var(--ink-200)",
              borderRadius: 10,
              padding: "10px 14px",
              color: "var(--ink-700)",
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              justifyContent: "flex-start",
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              style={{
                width: 14,
                height: 14,
                transition: "transform .2s",
                transform: showAdvanced ? "rotate(180deg)" : "",
              }}
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
            Paramètres avancés
          </button>
          {showAdvanced && (
            <div
              style={{
                marginTop: 12,
                padding: 16,
                background: "var(--cream)",
                borderRadius: 12,
                border: "1px solid var(--ink-100)",
                display: "grid",
                gap: 14,
                gridTemplateColumns: "1fr 1fr",
              }}
            >
              <NumberField
                label="Max par commune"
                value={maxPerCity}
                onChange={setMaxPerCity}
                min={5}
                max={500}
              />
              <NumberField
                label="Workers parallèles"
                value={workers}
                onChange={setWorkers}
                min={1}
                max={12}
              />
              <CheckField
                label="Strict ville (ne garder que les fiches dans la commune cible)"
                checked={strictCity}
                onChange={setStrictCity}
              />
              <CheckField
                label="Téléphone obligatoire"
                checked={requirePhone}
                onChange={setRequirePhone}
              />
              <CheckField
                label="Scoring crédit BNB (Playwright, +~4 s/fiche)"
                checked={doCreditScoring}
                onChange={setDoCreditScoring}
              />
              <CheckField
                label="Navigateur invisible (headless)"
                checked={headless}
                onChange={setHeadless}
              />
            </div>
          )}
        </div>

        {/* Footer : estimation + bouton */}
        <div className="oa-form-card__footer">
          <div className="oa-form-estimate">
            <div>
              <div className="oa-form-estimate__num">
                {metiers.length && cities.length
                  ? `${estimateLow}–${estimateHigh}`
                  : "0–0"}
              </div>
              <div className="oa-form-estimate__label">
                prospects estimés
                {metiers.length && cities.length ? (
                  <>
                    {" "}
                    · ~{timeMin} min · {metiers.length} requête(s) ×{" "}
                    {cities.length} commune(s) (
                    {strictCity ? "strict" : "tolérant"})
                  </>
                ) : null}
              </div>
            </div>
          </div>
          <button
            className="btn btn--primary"
            onClick={handleLaunch}
            disabled={!canLaunch}
            style={{
              opacity: canLaunch ? 1 : 0.4,
              cursor: canLaunch ? "pointer" : "not-allowed",
              padding: "11px 22px",
            }}
          >
            {mutation.isPending ? "Démarrage…" : "Lancer la recherche"}
          </button>
        </div>

        {mutation.error && (
          <div
            style={{
              padding: 12,
              background: "var(--red-50)",
              color: "var(--red-600)",
              borderRadius: 10,
              fontSize: 12,
            }}
          >
            Erreur : {(mutation.error as Error).message}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────

function HelpTip({ title }: { title: string }) {
  return (
    <span className="oa-help-icon" title={title}>
      ?
    </span>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
}) {
  return (
    <div className="oa-form-field">
      <label className="oa-form-field__label">{label}</label>
      <input
        type="number"
        className="oa-form-field__input"
        value={value}
        min={min}
        max={max}
        onChange={(e) =>
          onChange(Math.min(max, Math.max(min, Number(e.target.value) || min)))
        }
      />
    </div>
  );
}

function CheckField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        cursor: "pointer",
        fontSize: 13,
        color: "var(--ink-700)",
        lineHeight: 1.4,
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{
          marginTop: 3,
          width: 16,
          height: 16,
          accentColor: "var(--indigo-700)",
          cursor: "pointer",
        }}
      />
      <span>{label}</span>
    </label>
  );
}
