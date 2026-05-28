# POC React + FastAPI

Proof of concept d'une architecture back/front en remplacement de
Streamlit. La logique métier (scraper, enrichment, audit, storage)
reste **identique** ; on ne change que la couche UI/transport.

## Architecture

```
ScrapperGMB/
├── backend/                  ← FastAPI (Python)
│   ├── main.py              ← app + endpoints + CORS
│   └── schemas.py           ← Pydantic models
│
├── frontend/                 ← React + Vite + TypeScript
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts       ← axios client typé
│   │   │   ├── types.ts     ← miroir des schémas backend
│   │   │   └── utils.ts     ← palette crédit, helpers
│   │   ├── components/
│   │   │   ├── BusinessCard.tsx
│   │   │   ├── CreditPill.tsx
│   │   │   ├── FilterPills.tsx
│   │   │   └── ScrapeSelector.tsx
│   │   ├── layouts/
│   │   │   └── AppLayout.tsx (topbar + footer)
│   │   ├── pages/
│   │   │   ├── ResultsPage.tsx     ← grille + filtres + recherche
│   │   │   └── BusinessDetailPage.tsx
│   │   ├── App.tsx          ← router
│   │   ├── main.tsx         ← QueryClient + BrowserRouter
│   │   └── index.css        ← Tailwind + Oui Allo palette
│   └── vite.config.ts       ← proxy /api → :8000
│
├── storage/  scraper/  enrichment/  audit/   ← PARTAGÉS (zéro modif)
└── data/history.db                            ← PARTAGÉ
```

**Principe** : le backend lit la même `data/history.db` que Streamlit
et ré-utilise les fonctions de `storage.history`. Pas de duplication.

## Démarrage en 2 terminaux

### Terminal 1 — backend FastAPI

```bash
cd C:\Users\celin\Desktop\ScrapperGMB

# Premier lancement seulement :
pip install fastapi "uvicorn[standard]"

uvicorn backend.main:app --reload --port 8000
```

Endpoints exposés :

| Méthode | URL                                        | Description                            |
|--------|--------------------------------------------|----------------------------------------|
| GET    | `/api/health`                              | Ping                                   |
| GET    | `/api/searches?limit=100`                  | Liste des scrapes historiques          |
| GET    | `/api/searches/{id}/businesses`            | Fiches d'un scrape + credit_counts     |
| GET    | `/api/businesses/{dedup_key}`              | Détail complet d'une fiche             |
| GET    | `/docs`                                    | Swagger auto-généré                    |

### Terminal 2 — frontend React

```bash
cd C:\Users\celin\Desktop\ScrapperGMB\frontend
npm install   # première fois seulement
npm run dev
```

Ouvre **http://localhost:5173** dans le navigateur. Le proxy Vite envoie
les requêtes `/api/*` vers le backend `:8000` (donc pas de CORS en dev).

## Ce qui marche dans ce POC

**Page Résultats (`/`)**
- ✅ Sélecteur de scrape historique (dropdown des 100 derniers)
- ✅ 6 métriques compactes (fiches, top 2, téléphone, TVA, dirigeant, appelés)
- ✅ Filtres pills (Tous, Top 2, TVA, site web, téléphone) + filtres
      crédit (🟢 Bon payeur, 🟡 À surveiller, 🟠 À risque, 🔴 Mauvais
      payeur, ⚪ Non évalué) — pills crédit affichées seulement si count > 0
- ✅ Recherche full-text (nom, ville, TVA, dirigeants, etc.)
- ✅ Grille responsive 1/2/3 colonnes selon la taille d'écran
- ✅ Cards avec : nom + rank badge + status + pill crédit (tooltip
      raisons) + infos compactes + bouton Détails

**Page Détail (`/business/:dedup_key`)**
- ✅ Hero avec nom, sous-titre, pills crédit/statut
- ✅ Section Contact (téléphone, email, site, adresse + lien Maps)
- ✅ Section Identité légale (TVA, BCE, forme, statut, création, capital,
      dirigeants, NACE)
- ✅ Sidebar « Santé financière » avec pill couleur + raisons + timestamp
- ✅ Sidebar « Dépôts BNB » (exercice, date, modèle, total) + lien BNB
- ✅ Sidebar « Avis Google »
- ✅ Bouton retour

## Comparaison avec Streamlit

| Aspect                  | Streamlit                          | POC React + FastAPI           |
|-------------------------|------------------------------------|-------------------------------|
| Lignes de code (UI)     | ~6500 (app.py)                     | ~700 (8 fichiers ciblés)      |
| CSS hacks               | Beaucoup (scopes via iframe, !important, hidden buttons) | Zéro |
| État partagé            | `st.session_state` fragile         | TanStack Query (cache + invalidation propre) |
| Routing                 | Query params + `_check_detail_route` + `st.stop()` | `react-router-dom` natif |
| Reruns                  | Tout le script à chaque interaction | Re-render React ciblé        |
| Auth / multi-user       | Inexistant                         | Trivial à ajouter (Clerk, Supabase) |
| Mobile                  | Limité                             | Tailwind responsive natif     |
| Build time              | N/A                                | Vite : 1.3 s, bundle 360 kB (116 kB gzip) |

## Prochaines étapes possibles (hors POC)

- [ ] Endpoint POST `/api/scrapes` pour lancer un nouveau scrape depuis
       le frontend (avec WebSocket pour la progress en temps réel)
- [ ] Bouton « Appeler » qui pousse vers Ringover (réutilise
       `ringover/client.py`)
- [ ] Page Audit SEO IA + page Analyse crédit IA en popup
- [ ] Auth Clerk + multi-user
- [ ] Déploiement : backend sur Railway, frontend sur Vercel
- [ ] Tests E2E avec Playwright

## Tests

Le POC ne casse aucun test existant :

```bash
python -m pytest tests/
```

→ 140 passed (mêmes tests qu'avant, le backend ré-utilise les modules
existants).
