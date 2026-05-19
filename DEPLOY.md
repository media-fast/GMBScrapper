# Déploiement sur Plesk via Docker

Guide complet pour déployer ScrapperGMB sur un serveur Plesk avec Docker, en exposant l'app via un sous-domaine HTTPS avec authentification.

---

## ⚠️ À lire avant de commencer

### Risque de blocage Google sur IP datacenter
Sur ton PC, ton IP est résidentielle → Google laisse passer. Sur un VPS Plesk, l'IP appartient à un datacenter (OVH, Hetzner, Scaleway…) → **Google est beaucoup plus agressif et peut bloquer dès 50-100 requêtes**.

Mitigations dans l'ordre de coût croissant :
1. **Démarrer doucement** : peu de villes, peu de résultats par ville, espacer les recherches dans la journée.
2. **Désactiver le mode headless** côté serveur → cf. variable d'env `STREAMLIT_HEADLESS_OVERRIDE=false`. Plus difficile à détecter mais plus lent.
3. **Proxy résidentiel** (Bright Data, Smartproxy, Oxylabs) — ~5–10 €/Go. Le scraper passe par une IP résidentielle.
4. **API officielle Google Places** (~17 $ / 1000 fiches) — c'est la solution finale si l'usage devient régulier.

### Ressources serveur
Playwright + Chromium consomment **~1 Go RAM pendant un scrape**. Prévois :
- **Minimum** : 2 Go RAM, 2 vCPU, 10 Go disque (l'image Docker pèse ~1.5 Go)
- **Confortable** : 4 Go RAM, 2 vCPU, 20 Go disque

---

## Prérequis Plesk

- **Plesk Obsidian** (18.x ou plus)
- **Extension Docker** installée : `Plesk → Extensions → Docker`
- Un **sous-domaine** créé pour l'app : ex. `prospects.tondomaine.be`
- (Optionnel) **Let's Encrypt** activé sur ce sous-domaine

---

## Étape 1 — Mettre le code sur le serveur

### Option A : via Git (recommandé pour les mises à jour)
```bash
ssh root@ton-serveur
mkdir -p /opt/scrappergmb
cd /opt/scrappergmb
git clone <ton-repo>.git .
```

### Option B : via SFTP / Plesk File Manager
- Upload tout le dossier `ScrapperGMB` dans `/opt/scrappergmb` sur le serveur.

---

## Étape 2 — Construire et démarrer le conteneur

### Via SSH (le plus simple)
```bash
cd /opt/scrappergmb
docker compose build
docker compose up -d
docker compose logs -f
```
La première build prend **5–10 minutes** (téléchargement de Chromium et dépendances).

Vérifier que ça tourne :
```bash
curl http://127.0.0.1:8501/_stcore/health
# Doit retourner "ok"
```

### Via l'extension Plesk Docker (sans SSH)
1. `Plesk → Docker`
2. **Add Container** → onglet **Local Build** → pointer vers `/opt/scrappergmb/Dockerfile`
3. Nom : `scrappergmb`, port mapping : `127.0.0.1:8501 → 8501/tcp`
4. **Restart policy** : `unless-stopped`
5. **Memory limit** : 2048 MB
6. **Run**

---

## Étape 3 — Configurer le reverse proxy Plesk

⚠️ **Streamlit utilise des WebSockets** — la configuration par défaut de Plesk ne les supporte pas. Il faut adapter nginx.

### 3.1 — Reverse proxy de base
Dans Plesk :
1. Ouvre le sous-domaine `prospects.tondomaine.be`
2. **Docker Proxy Rules** → **Add Proxy Rule** :
   - **Hostname** : `prospects.tondomaine.be`
   - **Container** : `scrappergmb`
   - **Container port** : `8501`

### 3.2 — Activer le support WebSocket
Plesk → ton sous-domaine → **Apache & nginx Settings** → **Additional nginx directives**, colle :

```nginx
location / {
    proxy_pass http://127.0.0.1:8501;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
    proxy_buffering off;
}

location /_stcore/stream {
    proxy_pass http://127.0.0.1:8501/_stcore/stream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400s;
}
```

**Sauvegarde**. Sans ça, l'UI Streamlit se chargera mais resterait bloquée avec « Connecting… ».

### 3.3 — HTTPS via Let's Encrypt
Plesk → sous-domaine → **SSL/TLS Certificates** → **Install free basic certificate via Let's Encrypt**. Coche aussi *Redirect HTTP to HTTPS*.

---

## Étape 4 — Protéger l'accès (auth basique)

L'app n'a pas d'authentification intégrée. Le plus simple :

Plesk → sous-domaine → **Password-Protected Directories** → **Add Protected Directory** :
- Directory : `/`
- Title : `Prospection`
- Ajouter un utilisateur (login + mot de passe pour le commercial)

Le navigateur demandera login / mot de passe avant d'afficher l'app.

### Alternative : whitelist IP
Si tu veux limiter à l'IP du bureau plutôt qu'un mot de passe, dans les directives nginx additionnelles :

```nginx
location / {
    allow 1.2.3.4;       # IP fixe du bureau
    deny all;
    # … reste du proxy_pass au-dessus
}
```

---

## Étape 5 — Vérifier que tout marche

1. Ouvre `https://prospects.tondomaine.be`
2. Login / mot de passe basique → l'interface Streamlit s'affiche
3. Lance une recherche **petite** (1 ville, 3 résultats) pour valider que le scraping fonctionne depuis le serveur
4. Si l'interface se charge mais reste sur « Connecting… » → reviens à l'étape 3.2 (WebSocket pas configuré)
5. Si Google bloque immédiatement → cf. section *Mitigations* en haut

---

## Mises à jour

### Si tu as utilisé Git
```bash
cd /opt/scrappergmb
git pull
docker compose build
docker compose up -d
```

### Si tu modifies les fichiers via SFTP
Upload puis :
```bash
cd /opt/scrappergmb
docker compose build
docker compose up -d
```

---

## Diagnostiquer un problème

| Symptôme | Vérifier |
|---|---|
| Page blanche / 502 | `docker compose logs -f scrappergmb` |
| « Connecting… » qui tourne | WebSocket non configuré → étape 3.2 |
| Google bloque immédiatement | IP datacenter flaggée → décocher headless, baisser le débit, proxy résidentiel |
| OOM (out of memory) | Augmenter `mem_limit` dans `docker-compose.yml` ou redimensionner le VPS |
| `chrome-headless-shell` introuvable | Reconstruire l'image : `docker compose build --no-cache` |

### Voir les logs en temps réel
```bash
docker compose logs -f scrappergmb
```

### Redémarrer
```bash
docker compose restart
```

### Entrer dans le conteneur
```bash
docker compose exec scrappergmb bash
```

---

## Configuration avancée

### Variables d'environnement utiles
Ajouter dans `docker-compose.yml` sous `environment:` :

```yaml
TZ: Europe/Brussels                   # déjà présent
STREAMLIT_THEME_PRIMARYCOLOR: "#2563eb"  # override thème
```

### Persister les exports
Le `docker-compose.yml` monte déjà un volume `exports:`. Pour le récupérer côté hôte :
```bash
docker volume inspect scrappergmb_exports
# montre le chemin sur l'hôte
```

### Snapshot avant mise à jour
```bash
docker compose down
tar czf /backup/scrappergmb-$(date +%F).tar.gz /opt/scrappergmb
docker compose up -d
```
