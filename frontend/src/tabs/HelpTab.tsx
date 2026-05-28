/**
 * Tab Aide — documentation du POC + liens vers les ressources.
 */

export function HelpTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="card" style={{ padding: 28 }}>
        <h2
          className="serif"
          style={{
            fontSize: 24,
            fontWeight: 600,
            color: "var(--ink-900)",
            marginTop: 0,
            marginBottom: 8,
          }}
        >
          Comment ça marche ?
        </h2>
        <p style={{ color: "var(--ink-500)", margin: 0, lineHeight: 1.6 }}>
          ScrapperGMB est un outil interne Media Fast pour la prospection B2B
          belge. Il combine Google Maps + BCE/KBO + dépôts BNB pour produire
          des fiches qualifiées en quelques minutes.
        </p>

        <h3
          className="serif"
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: "var(--ink-900)",
            marginTop: 28,
            marginBottom: 10,
          }}
        >
          Pipeline d'enrichissement
        </h3>
        <ul style={{ color: "var(--ink-700)", lineHeight: 1.7, paddingLeft: 20 }}>
          <li>
            <strong>Google Maps</strong> via Playwright stealth — extrait nom,
            adresse, téléphone, catégorie, rating, avis.
          </li>
          <li>
            <strong>KBO / BCE</strong> — résolution du numéro TVA + détail
            (dirigeants, forme juridique, NACE, capital).
          </li>
          <li>
            <strong>BNB</strong> — dépôts de comptes annuels (année, date,
            modèle, nombre).
          </li>
          <li>
            <strong>Heuristique crédit</strong> — coloration baromètre
            🟢🟡🟠🔴⚪ basée sur le statut BCE + l'âge + la régularité des
            dépôts.
          </li>
          <li>
            <strong>Audit IA</strong> — rapport SEO/GEO + analyse crédit IA
            sur demande (via OpenAI ou Anthropic).
          </li>
        </ul>
      </div>

      <div className="card" style={{ padding: 28 }}>
        <h3
          className="serif"
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: "var(--ink-900)",
            marginTop: 0,
            marginBottom: 12,
          }}
        >
          Configuration des clés API
        </h3>
        <div style={{ color: "var(--ink-700)", lineHeight: 1.6 }}>
          Ajoute ces variables dans <code className="mono" style={{ background: "var(--ink-100)", padding: "2px 6px", borderRadius: 4 }}>.env</code> à la racine :
          <pre
            className="mono"
            style={{
              marginTop: 12,
              padding: 16,
              background: "var(--cream)",
              borderRadius: 10,
              fontSize: 12,
              color: "var(--ink-800)",
              border: "1px solid var(--ink-100)",
              overflowX: "auto",
            }}
          >
{`# Click-to-call Ringover
RINGOVER_API_KEY=...

# Optionnel — accélère + fiabilise le scoring crédit BNB
NBB_API_KEY=...
# Inscription gratuite : https://developer.cbso.nbb.be

# Audit IA (au moins une des deux)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...`}
          </pre>
        </div>
      </div>

      <div className="card" style={{ padding: 28 }}>
        <h3
          className="serif"
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: "var(--ink-900)",
            marginTop: 0,
            marginBottom: 12,
          }}
        >
          POC React + FastAPI
        </h3>
        <p
          style={{
            color: "var(--ink-700)",
            lineHeight: 1.6,
            margin: 0,
          }}
        >
          Cette interface React consomme une API FastAPI qui réutilise les
          modules Python existants (
          <code className="mono">scraper</code>,{" "}
          <code className="mono">enrichment</code>,{" "}
          <code className="mono">storage</code>) — zéro duplication. Le
          formulaire de lancement de scrape sera ajouté avec un endpoint
          POST <code className="mono">/api/scrapes</code> + WebSocket pour la
          progression en temps réel.
        </p>
        <p
          style={{
            color: "var(--ink-500)",
            fontSize: 12,
            marginTop: 16,
            marginBottom: 0,
          }}
        >
          Doc API auto-générée :{" "}
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--indigo-700)" }}
          >
            http://localhost:8000/docs
          </a>
        </p>
      </div>
    </div>
  );
}
