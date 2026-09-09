# Oval'Pronos

Application de pronostics rugby couvrant le **Top 14**, la **Champions Cup** et le **6 Nations**.

**Tagline :** "Tu sais pas plaquer, viens pronostiquer"

Stack : **Django 5** · **Bootstrap 5 + HTMX** · **PostgreSQL** · **api-sports.io (Rugby)** · **Hetzner CX22**

Admin : interface Django native thématisée avec le design system de l'app (Bootstrap 5, Barlow, Tabler Icons, CSS variables).

---

## Démarrage rapide (développement local)

### 1. Prérequis
- Python 3.11+
- Git

### 2. Cloner et installer

```bash
git clone <ton-repo>
cd ovalpronos

python -m venv venv
source venv/bin/activate       # Mac/Linux
# ou : venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 3. Configuration

Crée un fichier `.env` à la racine :

```
SECRET_KEY=<django-secret-key>
DEBUG=True
DATABASE_URL=              # Omit for SQLite in dev
RAPIDAPI_KEY=<key>
RUGBY_SEASON=2024-2025
ALLOWED_HOSTS=localhost,127.0.0.1
SYNC_SECRET_TOKEN=<random-token>
# Email: console backend by default in dev, no config needed
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend  # uncomment for SMTP
```

### 4. Base de données et premier lancement

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Ouvre http://127.0.0.1:8000.

### 5. Synchroniser les matchs

```bash
python manage.py sync_matches           # Toutes les compétitions
python manage.py sync_matches --comp TOP14
```

### 6. Tests

```bash
# Tests de scoring — obligatoires avant déploiement
python manage.py test apps.predictions.tests   # 11/11
```

---

## Structure du projet

```
ovalpronos/
├── ovalpronos/               # Configuration Django (settings, urls, wsgi)
├── apps/
│   ├── accounts/             # CustomUser, auth views, register/login/reset, admin
│   ├── matches/              # Competition, Team, Match, sync service, admin + import view
│   ├── predictions/          # Prediction model, HTMX auto-save, scoring service, tests
│   ├── rankings/             # RankingsView (on-the-fly aggregation, global + league tabs)
│   └── leagues/              # League model, create/join/leave flow, league leaderboard
├── templates/
│   ├── base.html             # Bootstrap 5, HTMX, Barlow, Tabler Icons, CSS vars
│   ├── accounts/             # login, register, password reset (×4), email template
│   ├── matches/              # home (landing), rules
│   ├── predictions/          # index (tab Upcoming/Live/Past)
│   ├── rankings/             # index (leaderboard with medals, global + league tabs)
│   ├── leagues/              # list, create, join, detail
│   ├── partials/             # match_card.html (6 états HTMX)
│   ├── admin/
│   │   ├── base_site.html    # Injecte Bootstrap 5, Barlow, Tabler Icons, main.css + admin.css
│   │   ├── index.html        # Dashboard avec 4 cartes métriques
│   │   ├── partials/         # dashboard_stats.html (templatetag inclusion)
│   │   └── matches/          # import.html (déclencheur sync api-sports.io)
│   └── 404.html
├── static/
│   ├── css/main.css          # CSS variables — aucune couleur hex en dur
│   ├── css/admin.css         # Overrides Django admin (utilise les vars de main.css)
│   └── img/teams/            # <slug>.svg — un fichier par équipe
├── locale/fr/LC_MESSAGES/    # django.po / django.mo
├── .github/workflows/
│   └── sync_matches.yml      # Cron 2h + 15min week-end + workflow_dispatch
├── requirements.txt
│   └── deploy.yml            # Déploiement SSH sur Hetzner (push → ~/deploy.sh)
```

---

## Interface d'administration

Accessible à `/admin/` (staff uniquement). Thème : design system de l'app (Bootstrap 5, police Barlow, icônes Tabler, variables CSS de `main.css`) — aucun package tiers.

**Actions disponibles par modèle :**

| Modèle | Actions clés |
|---|---|
| `Competition` | Sync depuis l'API, recalculer tous les points, bouton sync par ligne |
| `Match` | Recalculer les points, rafraîchir le cache UserScore, masquer/afficher ; vue inline des pronostics (lecture seule) ; filtre par défaut = SCHEDULED |
| `Prediction` | Recalculer les points ; badges résultat avec les couleurs du design system ; lecture seule |
| `UserScore` | Portée (Global / Compétition / Ligue) ; rafraîchir le cache ; lecture seule |
| `CustomUser` | Compteur pronostics ; activer/désactiver les comptes |
| `League` | Régénérer le code d'invitation |

**Dashboard** (`/admin/`) : 4 cartes métriques — joueurs actifs, matchs cette semaine, matchs sans cotes (alerte), pronostics non calculés (alerte).

---

## Barème des points

Mode **COTES** (défaut) — cotes stockées en entiers = cote Unibet × 10 :

| Résultat | Points |
|---|---|
| Score exact | `cote_vainqueur × 3` |
| Bon écart (≤ `good_gap_pts`) | `cote_vainqueur × 2` |
| Bon vainqueur | `cote_vainqueur × 1` |
| Mauvais pronostic | `0` |
| Match annulé | `0` (result_type=CANCELLED) |

Mode **FIXED** : 5 / 3 / 1 / 0 points fixes. Configurable par compétition dans l'admin (`Competition.scoring_system`).

---

## Synchronisation des matchs

La sync est déclenchée par **GitHub Actions** via `POST /api/sync-scores/` avec un token Bearer :

- Toutes les 2h en semaine
- Toutes les 15 minutes le week-end
- Manuellement via `workflow_dispatch`

GitHub Secrets requis : `APP_URL`, `SYNC_SECRET_TOKEN`.

En développement, déclencher manuellement :
```bash
python manage.py sync_matches
```

---

## Déploiement (Hetzner CX22)

Tout push sur `main` déclenche le workflow `deploy.yml` qui SSH sur le serveur et exécute `~/deploy.sh` :

```bash
cd /home/amaury/Ovalpronos && git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --no-input
python manage.py collectstatic --no-input
sudo systemctl restart gunicorn
```

**GitHub Secrets requis :**

| Secret | Usage |
|---|---|
| `DEPLOY_HOST` | IP/hostname Hetzner |
| `DEPLOY_USER` | Utilisateur SSH (`amaury`) |
| `DEPLOY_KEY` | Clé privée SSH |
| `APP_URL` | URL complète de l'app |
| `SYNC_SECRET_TOKEN` | Token Bearer pour `/api/sync-scores/` |

---

## Obtenir une clé RapidAPI (rugby-live-data)

1. Cherche "rugby live data" sur rapidapi.com
2. Souscris à l'API (plan gratuit disponible)
3. Copie la clé dans `.env` : `RAPIDAPI_KEY=ta-clé`
