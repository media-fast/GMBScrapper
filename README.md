# ScrapperGMB — Prospection Google My Business + TVA (Belgique)

Outil interne pour générer des listes de prospects B2B :

1. **Scrape Google Maps** pour un métier dans une liste de villes (sans clé API Google).
2. **Enrichit chaque fiche** avec le numéro de TVA belge :
   - via le site web de l'entreprise (mentions légales, footer, page contact)
   - via le **registre KBO/BCE** (banque-carrefour des entreprises)
3. **Interface web Streamlit** — le commercial lance les recherches lui-même.
4. **Export Excel** prêt pour le CRM.

---

## ⚠️ À savoir avant de l'utiliser

- Scraper Google Maps **viole les conditions d'utilisation de Google**. Pour un usage interne et modéré (quelques dizaines à centaines de fiches), c'est généralement toléré. Pour un usage industriel, il faudra basculer sur **Google Places API** (officielle, payante).
- Les données scrapées sont **publiques**. La prospection B2B est couverte par l'**intérêt légitime** sous le RGPD, mais il faut tenir un registre de traitement et permettre l'opt-out (mention dans les premiers contacts commerciaux).
- Google peut afficher un **CAPTCHA** ou bloquer temporairement l'IP en cas de volume excessif. L'outil est conçu pour des recherches ponctuelles, pas du scraping continu.

---

## Installation

Prérequis : **Python 3.11+** (testé sur 3.13).

```powershell
cd C:\Users\celin\Desktop\ScrapperGMB

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium chromium-headless-shell
```

L'installation des deux binaires par Playwright télécharge ~250 Mo, c'est normal.
Le `chromium-headless-shell` est requis pour le mode invisible (utilisé par défaut dans l'app).

---

## Lancer l'interface

```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
```

L'interface s'ouvre dans le navigateur sur http://localhost:8501.

### Utilisation

1. Dans le panneau de gauche : saisir le **métier** (ex : `opticien`) et la **liste des villes** (une par ligne).
2. Choisir le **nombre max de résultats par ville** (par défaut 25 — Google Maps en montre rarement plus de 80–100 pour une recherche).
3. Cocher / décocher les sources d'enrichissement TVA :
   - **Site web** (rapide, ~2s par entreprise, taux de réussite ~50–70 %)
   - **KBO/BCE** (plus lent, ~5–10s par entreprise, complète ce que le site n'a pas)
4. **Lancer la recherche**. Pour 5 villes × 25 résultats avec enrichissement, compter **15–30 minutes**.
5. Vérifier les résultats dans le tableau, puis **télécharger en Excel**.

### Mode debug

Si Google bloque (CAPTCHA, page vide…) : décocher **« Mode headless »** dans le panneau avancé. Le navigateur s'ouvre visuellement, on voit ce qui se passe, et Google détecte moins.

---

## Architecture

```
ScrapperGMB/
├── app.py                    # Interface Streamlit
├── requirements.txt
├── scraper/
│   ├── models.py             # Dataclass Business
│   └── gmaps.py              # Scraping Playwright de Google Maps
├── enrichment/
│   ├── website.py            # Extraction TVA depuis site web (regex)
│   ├── kbo.py                # Recherche KBO/BCE + fuzzy matching
│   └── vat.py                # Orchestration (site web → fallback KBO)
└── export/
    └── excel.py              # Export Excel formaté
```

### Flux de données

```
[métier + villes]
        │
        ▼
  Playwright → Google Maps  ──►  liste de Business
                                       │
                                       ▼
                              Pour chaque entreprise :
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
                Website regex (BE0xxx…)      KBO public search
                  (rapide)                    (fuzzy match)
                          │                         │
                          └────────────┬────────────┘
                                       ▼
                              Business + vat_number
                                       │
                                       ▼
                                Export Excel
```

---

## Limites et pistes d'évolution

| Limite actuelle                                     | Solution si besoin                                           |
| --------------------------------------------------- | ------------------------------------------------------------ |
| Google peut bloquer après ~200 requêtes / IP / jour | Proxy résidentiel (Bright Data, ~5 €/Go) ou API SerpApi      |
| Pas tous les sites web exposent leur TVA            | Déjà couvert par le fallback KBO                             |
| Matching KBO faible si le nom GMB diffère du légal  | Score affiché dans l'export — entrées <85 à vérifier à la main |
| Pas d'historique des recherches                     | Ajouter SQLite + page « Historique »                         |
| Pas de scraping en parallèle                        | `asyncio.gather` sur plusieurs villes (risque blocage Google)  |
| Pas d'authentification de l'interface              | Déployer derrière nginx + basic auth, ou Streamlit Cloud privé |

### Pour passer en production

- **Google Places API** (~17 $ / 1000 fiches) : code à réécrire dans `scraper/gmaps_api.py`, beaucoup plus stable.
- **KBO Open Data** (dump CSV mensuel, ~2 M entreprises) : remplacer le scraping live par un lookup local. Téléchargement gratuit après inscription sur https://kbopub.economie.fgov.be/kbo-open-data/login.
