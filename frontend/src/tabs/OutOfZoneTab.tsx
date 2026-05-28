/**
 * Tab Hors zone — placeholder pour le POC.
 * Implémentation complète : nécessite que le backend expose un endpoint
 * dédié pour les fiches écartées par le filtre géo (col `dropped` du
 * scrape_state, persisté en DB).
 */

export function OutOfZoneTab() {
  return (
    <div className="card" style={{ padding: 40 }}>
      <div className="empty-state">
        <div className="empty-state__icon">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
        </div>
        <div className="empty-state__title serif">
          Tab Hors zone (à venir)
        </div>
        <div className="empty-state__text">
          Liste les fiches écartées par le filtre géo (mauvaise commune, hors
          rayon). Sera implémenté avec l'endpoint{" "}
          <code className="mono">/api/scrapes/{`{id}`}/dropped</code>.
        </div>
      </div>
    </div>
  );
}
