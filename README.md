# Oval'Pronos

Application de pronostics rugby couvrant le **Top 14**, la **Champions Cup** et le **6 Nations**.

**Tagline :** "Tu sais pas plaquer, viens pronostiquer"

Stack : **Django 5** · **Bootstrap 5 + HTMX** · **PostgreSQL** · **api-sports.io (Rugby)** · **Render + Neon**

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
APISPORTS_KEY=<key>
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
python manage.py sy![oval-pronos.png](../../Library/CloudStorage/GoogleDrive-amaury.lemaurarmengaud%40gmail.com/Mon%20Drive/Website%20dev/Ovalpronos/oval-pronos.png)nc_matches --comp TOP14
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
│   └── rankings/             # RankingsView (on-the-fly aggregation)
├── templates/
│   ├── base.html             # Bootstrap 5, HTMX, Barlow, Tabler Icons, CSS vars
│   ├── accounts/             # login, register, password reset (×4), email template
│   ├── matches/              # home (landing), rules
│   ├── predictions/          # index (tab Upcoming/Live/Past)
│   ├── rankings/             # index (leaderboard with medals)
│   ├── partials/             # match_card.html (6 états HTMX)
│   ├── admin/matches/        # import.html (api-sports.io trigger)
│   └── 404.html
├── static/
│   ├── css/main.css          # CSS variables — aucune couleur hex en dur
│   └── img/teams/            # <slug>.svg — un fichier par équipe
├── locale/fr/LC_MESSAGES/    # django.po / django.mo
├── .github/workflows/
│   └── sync_matches.yml      # Cron 2h + 15min week-end + workflow_dispatch
├── requirements.txt
└── render.yaml               # Déploiement Render (web service + Neon DB)
```

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

## Déploiement (Render + Neon)

1. Crée une base **Neon PostgreSQL**, copie l'URL de connexion
2. Crée un **Web Service** sur Render connecté au repo GitHub
3. Configure les variables d'environnement dans le dashboard Render :
   - `DATABASE_URL` — URL Neon
   - `APISPORTS_KEY` — clé API Rugby
   - `SYNC_SECRET_TOKEN` — token partagé avec GitHub Actions
   - `EMAIL_HOST_PASSWORD` — mot de passe SMTP Ionos
   - `EMAIL_BACKEND` — `django.core.mail.backends.smtp.EmailBackend`
4. Configure les GitHub Secrets : `APP_URL`, `SYNC_SECRET_TOKEN`
5. Render exécute automatiquement `collectstatic` et `migrate` au déploiement

---

## Obtenir une clé api-sports.io

1. https://api-sports.io/documentation/rugby/v1
2. Crée un compte (gratuit, 100 req/jour)
3. Copie la clé dans `.env` : `APISPORTS_KEY=ta-clé`
