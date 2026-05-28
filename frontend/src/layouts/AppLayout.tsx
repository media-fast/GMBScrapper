import { Outlet, Link, useLocation } from "react-router-dom";

/**
 * Layout principal.
 *
 * 2 modes :
 *   - Page Résultats (route /) → max-width container + topbar standard
 *   - Page Détail (/business/:id) → pleine largeur, le composant gère
 *     son propre layout Oui Allo (action-bar + shell)
 */
export function AppLayout() {
  const { pathname } = useLocation();
  const isDetail = pathname.startsWith("/business/");

  if (isDetail) {
    // La page détail Oui Allo gère son propre layout (action-bar + shell)
    return <Outlet />;
  }

  // Layout standard pour la page Résultats
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Topbar />
      <main
        style={{
          flex: 1,
          maxWidth: 1320,
          width: "100%",
          margin: "0 auto",
          padding: "32px 24px",
        }}
      >
        <Outlet />
      </main>
      <footer
        style={{
          borderTop: "1px solid var(--ink-100)",
          padding: "14px 0",
          textAlign: "center",
          fontSize: 11,
          color: "var(--ink-500)",
        }}
      >
        ScrapperGMB · Media Fast — POC React + FastAPI
      </footer>
    </div>
  );
}

function Topbar() {
  return (
    <header
      style={{
        background: "var(--paper)",
        borderBottom: "1px solid var(--ink-200)",
        position: "sticky",
        top: 0,
        zIndex: 20,
      }}
    >
      <div
        style={{
          maxWidth: 1320,
          margin: "0 auto",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link
          to="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            textDecoration: "none",
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 11,
              background:
                "linear-gradient(135deg, var(--indigo-600), var(--indigo-900))",
              display: "grid",
              placeItems: "center",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2.5"
              style={{ width: 20, height: 20 }}
            >
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          </div>
          <div>
            <div
              className="serif"
              style={{
                fontSize: 18,
                fontWeight: 600,
                color: "var(--ink-900)",
                lineHeight: 1.1,
              }}
            >
              ScrapperGMB
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--ink-500)",
                lineHeight: 1.1,
              }}
            >
              Prospection B2B · Media Fast
            </div>
          </div>
        </Link>
        <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
          <span style={{ fontWeight: 600, color: "var(--indigo-700)" }}>
            POC
          </span>{" "}
          React + FastAPI
        </div>
      </div>
    </header>
  );
}
