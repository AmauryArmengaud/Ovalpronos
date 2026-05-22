# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Oval'Pronos** is a Django 5 rugby predictions web app. Users predict match scores for Top 14, Champions Cup, and 6 Nations, then compete in a global ranking or private leagues. Match data is synced from api-sports.io via a GitHub Actions cron that calls a secured Django endpoint.

**Tagline:** "Tu sais pas plaquer, viens pronostiquer"

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Database
python manage.py makemigrations
python manage.py migrate

# Run development server
python manage.py runserver

# i18n — generate/compile French translations
python manage.py makemessages -l fr
python manage.py compilemessages

# Sync matches from api-sports.io (manual trigger)
python manage.py sync_matches                  # All competitions
python manage.py sync_matches --comp TOP14     # Single competition

# Run scoring tests (mandatory before deploy)
python manage.py test apps.predictions.tests

# Collect static files (production)
python manage.py collectstatic --no-input
```

## Environment Variables

Create a `.env` file at the project root (uses `python-decouple`):

```
SECRET_KEY=<django-secret-key>
DEBUG=True
DATABASE_URL=              # Omit for SQLite in dev; Neon URL for prod
APISPORTS_KEY=<key>
RUGBY_SEASON=2024-2025
ALLOWED_HOSTS=localhost,127.0.0.1

# Sync endpoint — shared with GitHub Actions secret SYNC_SECRET_TOKEN
SYNC_SECRET_TOKEN=<random-token>

# Email (dev: set EMAIL_BACKEND to console in settings instead)
EMAIL_HOST=smtp.ionos.fr
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@ovalpronos.com
EMAIL_HOST_PASSWORD=<ionos-password>
```

In development, use `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` — emails print to terminal.

## Architecture

All Django apps live under `apps/`. URL routing (all paths in English):

| URL prefix | App | Description |
|---|---|---|
| `/` | `matches` | Landing page (redirects to `/predictions/` if authenticated) |
| `/accounts/` | `accounts` | Register, login, password reset, profile |
| `/predictions/` | `predictions` | Prediction entry with HTMX auto-save |
| `/rankings/` | `rankings` | Global and league leaderboards |
| `/leagues/` | `leagues` | Private leagues (V2) |
| `/rules/` | `matches` | Scoring rules page |
| `/api/sync-scores/` | `matches` | Secured score sync endpoint (POST, Bearer token) |

### Key Models

- **`accounts.CustomUser`** — extends AbstractUser; adds `display_name`, `avatar`, `favorite_team` (FK to Team)
- **`matches.Competition`** — has `scoring_system` (`COTES` or `FIXED`), `good_gap_pts` (gap threshold for ×2 tier)
- **`matches.Team`** — has `slug` field; logos are local PNG files at `static/img/teams/<slug>.png`
- **`matches.Match`** — has `cote_home/cote_draw/cote_away` (integers = Unibet odds × 10); computed properties `is_locked`, `has_odds`, `result`, `closes_soon`, `time_until_kickoff`
- **`predictions.Prediction`** — (renamed from `Pronostic`) unique per `(user, match)`; `result_type` field: EXACT / GAP / WIN / MISS / CANCELLED
- **`leagues.League`** — 5-char invite code, creator FK, members M2M (V2)
- **`rankings.UserScore`** — denormalized score cache with global/competition/league scopes (V2)

### Scoring System

Odds-based (COTES mode, default). Cotes stored as integers = Unibet odds × 10.

| Result | Points |
|---|---|
| Exact score | `cote_winner × 3` |
| Gap within `good_gap_pts` | `cote_winner × 2` |
| Correct winner | `cote_winner × 1` |
| Wrong winner | `0` |
| Match cancelled | `0` with result_type=CANCELLED |

`Competition.scoring_system = 'FIXED'` uses 5 / 3 / 1 / 0 flat points instead. If `not match.has_odds`, the prediction form is hidden and submissions are blocked.

Scoring logic lives in `apps/predictions/services.py` as a standalone function (not a model method). See ARCHITECTURE.md §3 for full pseudocode.

### Data Flow

1. **GitHub Actions cron** triggers every 2h (every 15min on weekends) via `POST /api/sync-scores/` with a Bearer token.
2. **Sync endpoint** validates token, calls `sync_all_competitions()`.
3. **`sync_competition_matches(code)`** fetches from api-sports.io, upserts Competition/Team/Match records.
4. When a match reaches FINISHED: `calculate_points()` runs for every associated Prediction → updates `points_earned` and `result_type`.

### HTMX Prediction Auto-Save

The predictions page uses `hx-post` + `hx-trigger="change"` — no submit button. The view returns a re-rendered match card partial (`partials/match_card.html`) via `hx-swap="outerHTML"`. Lock and odds validation are enforced server-side on every POST.

### i18n

- All code, URLs, and comments: English
- All displayed UI text: via `{% trans "..." %}` in templates and `_("...")` in Python
- Default locale: French (`LANGUAGE_CODE = 'fr'`)
- Locale files: `locale/fr/LC_MESSAGES/django.po`

## Frontend

Bootstrap 5 + HTMX. Font: Barlow (Google Fonts). Icons: Tabler Icons (`ti ti-*`). All colors use CSS variables defined in `static/css/main.css` — no hardcoded hex values in templates (V4 white-label requirement). Templates in `templates/<app>/`. HTMX partials in `templates/partials/`.

## Deployment

**Phase 1 (beta, 0€/month):** Render free tier + Neon PostgreSQL. Cold start ~30s after 15min inactivity.

**Phase 2 (production, ~4€/month):** Hetzner CX22 VPS + self-hosted PostgreSQL. Migration is a one-evening operation — only env vars change, code stays the same.

GitHub Actions handles the sync cron in both phases (free; no Render paid cron needed).

## Known Issues / Migration TODOs

These divergences exist between the current code and the specs. Fix during Sprint 1 (see ROLLOUT.md):

- `pronostics` app must be renamed to `predictions`; model `Pronostic` → `Prediction`; add `result_type` field
- `Competition` model is missing `scoring_system` and `good_gap_pts` fields
- `Team` model is missing `slug` and `short_name`; has `logo_url` (replaced by local SVG pattern)
- `Match` model is missing `cote_home`, `cote_draw`, `cote_away` and computed properties `has_odds`, `closes_soon`, `time_until_kickoff`
- `CustomUser.favorite_team` is a CharField — must become FK to Team
- URL routes are in French (`/compte/`, `/pronos/`, `/classement/`) — must migrate to English
- `dj-database-url` is imported in `settings.py` but missing from `requirements.txt`
- `locale/` directory does not exist yet
- `django-crontab` in `INSTALLED_APPS` — remove; sync is handled by GitHub Actions
- No test suite yet — scoring tests are mandatory before V1 production deploy
- No GitHub Actions workflow exists yet
