/**
 * Form Lancer un scrape (style Oui Allo).
 *
 * - Métiers : input texte multi-valeurs (comma/newline separated)
 * - Communes : input texte multi-valeurs
 * - Options avancées (collapsible) : strict_city, require_phone, max_per_city,
 *   do_credit_scoring, headless, workers
 * - Estimation live (basée sur nb_metiers × nb_communes × max_per_city × yield)
 * - Bouton « Lancer la recherche »
 *
 * Sur submit → POST /api/scrapes → renvoie le scrape_id qu'on remonte
 * au parent pour démarrer le polling de progress.
 */

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { startScrape } from "../lib/api";

interface Props {
  onStarted: (scrapeId: string) => void;
  disabled?: boolean;
}

export function ScrapeForm({ onStarted, disabled }: Props) {
  const [metiersText, setMetiersText] = useState("");
  const [citiesText, setCitiesText] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Options avancées
  const [maxPerCity, setMaxPerCity] = useState(30);
  const [strictCity, setStrictCity] = useState(true);
  const [requirePhone, setRequirePhone] = useState(false);
  const [doCreditScoring, setDoCreditScoring] = useState(false);
  const [headless, setHeadless] = useState(true);
  const [workers, setWorkers] = useState(6);

  // Parsing métiers + communes
  const metiers = useMemo(
    () =>
      metiersText
        .split(/[,;\n]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    [metiersText],
  );
  const cities = useMemo(
    () =>
      citiesText
        .split(/[,;\n]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    [citiesText],
  );

  // Estimation : fourchette pessimiste/optimiste
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
    return {
      estimateLow: low,
      estimateHigh: high,
      timeMin: minTime,
    };
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

  return (
    <div className="oa-form-card">
      <div className="oa-form-card__inner">
        <div className="oa-form-card__header">
          <div>
            <h2 className="oa-form-card__title">
              Lancer une nouvelle recherche
            </h2>
            <p className="oa-form-card__sub">
              Métier + communes ciblées → scrape Google Maps + enrichissement
              BCE / BNB
            </p>
          </div>
        </div>

        <div className="oa-form-row">
          <div className="oa-form-field">
            <label className="oa-form-field__label">
              Métier(s) — un par ligne ou séparés par des virgules
            </label>
            <textarea
              className="oa-form-field__input"
              placeholder="opticien, dentiste, garage…"
              value={metiersText}
              onChange={(e) => setMetiersText(e.target.value)}
              disabled={disabled || mutation.isPending}
              rows={2}
              style={{ resize: "vertical", minHeight: 60 }}
            />
            {metiers.length > 0 && (
              <div
                style={{
                  fontSize: 11,
                  color: "var(--ink-500)",
                  marginTop: 2,
                }}
              >
                {metiers.length} métier(s) détecté(s) :{" "}
                <code className="mono">{metiers.slice(0, 5).join(" · ")}</code>
                {metiers.length > 5 && "…"}
              </div>
            )}
          </div>

          <div className="oa-form-field">
            <label className="oa-form-field__label">
              Communes — une par ligne ou séparées par des virgules
            </label>
            <textarea
              className="oa-form-field__input"
              placeholder="Waterloo, Braine-l'Alleud, Nivelles…"
              value={citiesText}
              onChange={(e) => setCitiesText(e.target.value)}
              disabled={disabled || mutation.isPending}
              rows={2}
              style={{ resize: "vertical", minHeight: 60 }}
            />
            {cities.length > 0 && (
              <div
                style={{
                  fontSize: 11,
                  color: "var(--ink-500)",
                  marginTop: 2,
                }}
              >
                {cities.length} commune(s) :{" "}
                <code className="mono">{cities.slice(0, 5).join(" · ")}</code>
                {cities.length > 5 && "…"}
              </div>
            )}
          </div>
        </div>

        {/* Options avancées (collapsible) */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            style={{
              background: "none",
              border: "none",
              color: "var(--indigo-700)",
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: "pointer",
              padding: 0,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              style={{
                width: 12,
                height: 12,
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
                marginTop: 14,
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
              <ToggleField
                label="Strict ville (ne garder que les fiches dans la commune cible)"
                checked={strictCity}
                onChange={setStrictCity}
              />
              <ToggleField
                label="Téléphone obligatoire"
                checked={requirePhone}
                onChange={setRequirePhone}
              />
              <ToggleField
                label="Scoring crédit BNB (Playwright, +~4 s/fiche)"
                checked={doCreditScoring}
                onChange={setDoCreditScoring}
              />
              <ToggleField
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
                  : "—"}
              </div>
              <div className="oa-form-estimate__label">
                {metiers.length && cities.length
                  ? `prospects estimés · ~${timeMin} min`
                  : "prospects estimés"}
              </div>
            </div>
            {metiers.length > 0 && cities.length > 0 && (
              <div
                style={{
                  fontSize: 11,
                  color: "var(--ink-500)",
                  paddingLeft: 10,
                  borderLeft: "1px solid var(--ink-200)",
                  lineHeight: 1.4,
                }}
              >
                {metiers.length} requête(s) × {cities.length} commune(s){" "}
                <br />
                ({strictCity ? "strict" : "tolérant"}
                {requirePhone ? ", tel obligatoire" : ""})
              </div>
            )}
          </div>
          <button
            className="btn btn--primary"
            onClick={handleLaunch}
            disabled={!canLaunch}
            style={{
              opacity: canLaunch ? 1 : 0.5,
              cursor: canLaunch ? "pointer" : "not-allowed",
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

// ─── Sub-fields ──────────────────────────────────────────────────────

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

function ToggleField({
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
