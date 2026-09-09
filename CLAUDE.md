# CLAUDE.md — Oval'Pronos

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Comments

**Why, not what. If the code is clear, skip it.**

- English only.
- Inline comments for non-obvious logic only — not for readable operations.
- No docstrings on self-evident functions.
- One short sentence. No filler, no trailing period on inline comments.
- If a workaround or constraint isn't obvious from the code, explain the reason.

```python
# cotes stored as odds × 10 — integer arithmetic avoids float rounding  ✓
# multiply cote_winner to get points                                      ✗
```

---

## Project Overview

**Oval'Pronos** is a Django 5 rugby predictions web app. Users predict match scores for Top 14, Champions Cup, and 6 Nations, then compete in a global ranking or private leagues. Match data is synced from the rugby-live-data RapidAPI via a GitHub Actions cron that calls a secured Django endpoint.

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

# Maintenance commands
python manage.py deactivate_ended_competitions  # Set is_active=False on competitions past end_date
python manage.py cleanup_bot_accounts           # Purge fake accounts (--dry-run / --since / --yes)

# Run tests (mandatory before deploy)
python manage.py test apps.predictions.tests apps.matches.tests

# Collect static files (production)
python manage.py collectstatic --no-input
```

## Environment Variables

Create a `.env` file at the project root (uses `python-decouple`):

```
SECRET_KEY=<django-secret-key>
DEBUG=True
DATABASE_URL=              # Omit for SQLite in dev; PostgreSQL URL for prod (e.g. postgres://user:pass@localhost/ovalpronos)
RAPIDAPI_KEY=<key>
RUGBY_SEASON=2025
ALLOWED_HOSTS=localhost,127.0.0.1

# Sync endpoint — shared with GitHub Actions secret SYNC_SECRET_TOKEN
SYNC_SECRET_TOKEN=<random-token>

# Cloudflare Turnstile CAPTCHA (register + login pages)
TURNSTILE_SITE_KEY=<site-key>          # Use 1x00000000000000000000AA for local dev (always passes)
TURNSTILE_SECRET_KEY=<secret-key>      # Use 1x0000000000000000000000000000000AA for local dev

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
| `/leagues/` | `leagues` | Private leagues |
| `/rules/` | `matches` | Scoring rules page |
| `/api/sync-scores/` | `matches` | Secured score sync endpoint (POST, Bearer token) |
| `/api/upcoming-matches/` | `matches` | Returns upcoming SCHEDULED matches for next 14 days (GET, Bearer token) |
| `/api/update-odds/` | `matches` | Writes bookmaker odds to matches (POST, Bearer token) |
| `/api/notify/missing-odds/` | `matches` | Emails superusers if upcoming matches have no odds (POST, Bearer token) |
| `/admin/` | Django admin | Staff-only admin interface (see Admin Interface section) |

### Key Models

- **`accounts.CustomUser`** — extends AbstractUser; adds `display_name`, `avatar`, `favorite_team` (FK to Team)
- **`matches.Competition`** — has `scoring_system` (`COTES` or `FIXED`), `good_gap_pts` (gap threshold for ×2 tier), `end_date` (used by `deactivate_ended_competitions` command to auto-set `is_active=False`)
- **`matches.Team`** — has `slug` field; logos are local PNG files at `static/img/teams/<slug>.png`
- **`matches.Match`** — has `cote_home/cote_draw/cote_away` (integers = bookmaker odds × 10, sourced via Gemini); computed properties `is_locked`, `has_odds`, `result`, `closes_soon`, `time_until_kickoff`
- **`predictions.Prediction`** — unique per `(user, match)`; `result_type` field: EXACT / GAP / WIN / MISS / CANCELLED
- **`leagues.League`** — `invite_code` (5-char, auto-generated), `creator` FK, `members` M2M, `competitions` M2M → Competition (required at creation, scopes the league leaderboard and predictions). `is_active` is a computed property: `True` if any linked competition is active. League detail page has a "Copy link" button that copies the full join URL (`/leagues/join/?code=XXXXX`); the join page pre-fills the code when `?code=` is present.
- **`rankings.UserScore`** — denormalized score cache; one row per (user, global) and (user, competition); updated by `refresh_user_scores_for_match()` after each match is scored

→ Full field tables: **ARCHITECTURE.md §2**

### Scoring System

Odds-based (COTES mode, default). Cotes stored as integers = bookmaker odds × 10. The stored integer is used directly — no division. Example: cote 6.30 → stored as 63 → exact prediction earns 63 × 3 = 189 pts.

| Result | Points |
|---|---|
| Exact score | `cote_winner × 3` |
| Gap within `good_gap_pts` | `cote_winner × 2` |
| Correct winner | `cote_winner × 1` |
| Wrong winner | `0` |
| Match cancelled | `0` with result_type=CANCELLED |

`Competition.scoring_system = 'FIXED'` uses 5 / 3 / 1 / 0 flat points instead. If `not match.has_odds`, the prediction form is hidden and submissions are blocked.

Scoring logic: `apps/predictions/services.py::calculate_points()`. Orchestration: `apps/matches/services.py::_calculate_points_for_match()`.

→ Full algorithm and design rationale: **ARCHITECTURE.md §3, §11**

### Data Flow

**Match sync (scores & schedule):** GitHub Actions cron → `POST /api/sync-scores/` → `sync_all_competitions()` → `sync_competition_matches(code)` → upserts matches → on FINISHED: `_calculate_points_for_match()` → `refresh_user_scores_for_match()`.

**Odds update (weekly):** GitHub Actions cron (Tuesday 12:00 Paris) → `.github/scripts/update_odds.py` → Gemini 3.6 Flash with Google Search grounding → `POST /api/update-odds/` → `POST /api/notify/missing-odds/`.

Test script: `.github/scripts/test_odds.py` — runs standalone with `GOOGLE_API_KEY=... python .github/scripts/test_odds.py`, no Django needed.

→ Full flow diagrams and service call chains: **ARCHITECTURE.md §4**

### HTMX Prediction Auto-Save

The predictions page uses `hx-post` + `hx-trigger="change"` — no submit button. The view returns a re-rendered match card partial (`partials/match_card.html`) via `hx-swap="outerHTML"`. Lock and odds validation are enforced server-side on every POST.

The predictions page shows matches in chronological order (day → competition → time), with a competition badge separator between groups. Matches with odds are shown directly; matches without odds are hidden behind a Bootstrap collapse toggle. Progress bar counts only odds-bearing matches.

### i18n

- All code, URLs, and comments: English
- All displayed UI text: via `{% trans "..." %}` in templates and `_("...")` in Python
- Default locale: French (`LANGUAGE_CODE = 'fr'`)
- Locale files: `locale/fr/LC_MESSAGES/django.po`

## Frontend

Bootstrap 5 + HTMX. Font: Barlow (Google Fonts). Icons: Tabler Icons (`ti ti-*`). All colors use CSS variables defined in `static/css/main.css` — no hardcoded hex values in templates (V4 white-label requirement). Templates in `templates/<app>/`. HTMX partials in `templates/partials/`.

## Admin Interface

Custom Django admin themed with the app's own design system (Bootstrap 5, Barlow, Tabler Icons, `main.css` CSS variables). No third-party admin package. All admin actions reuse service functions from `apps/matches/services.py` — no duplication.

→ Theme files, per-model capabilities, and custom admin views: **ARCHITECTURE.md §9**

## Deployment

**Production:** Hetzner CX22 VPS (~4€/month) — Gunicorn + self-hosted PostgreSQL. App lives at `/home/amaury/Ovalpronos/`.

**Deploy trigger:** Every push to `main` runs the GitHub Actions `deploy.yml` workflow, which SSHs into the server and executes `~/deploy.sh`:

```bash
cd /home/amaury/Ovalpronos
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --no-input
python manage.py collectstatic --no-input
sudo systemctl restart gunicorn
```

**GitHub Actions secrets required:**

| Secret | Used by | Purpose |
|---|---|---|
| `DEPLOY_HOST` | `deploy.yml` | Hetzner server IP/hostname |
| `DEPLOY_USER` | `deploy.yml` | SSH user (`amaury`) |
| `DEPLOY_KEY` | `deploy.yml` | SSH private key |
| `APP_URL` | `sync_matches.yml`, `sync_live.yml`, `update_odds.yml`, `email_notifications.yml` | Full app URL (e.g. `https://ovalpronos.com`) |
| `SYNC_SECRET_TOKEN` | `sync_matches.yml`, `sync_live.yml`, `update_odds.yml`, `email_notifications.yml` | Bearer token for secured API endpoints |
| `GOOGLE_API_KEY` | `update_odds.yml` | Google AI Studio key for Gemini 3.6 Flash |
| `GITHUB_TOKEN` | `keepalive.yml` | Auto-injected by GitHub Actions |

**To deploy manually:** push to `main`, or SSH in and run `~/deploy.sh` directly.

## GitHub Actions Workflows

| Workflow | Déclencheur | Endpoint Django | Rôle |
|---|---|---|---|
| `deploy.yml` | Push sur `main` | SSH → `~/deploy.sh` | Déploiement prod |
| `sync_matches.yml` | 1×/jour à 07h00 UTC + `workflow_dispatch` | `POST /api/sync-scores/` | Sync scores + scoring pronostics |
| `sync_live.yml` | Toutes les 10min, sam/dim 12h–22h UTC + `workflow_dispatch` | `POST /api/sync-scores/` | Sync temps réel week-end |
| `update_odds.yml` | Mardi 10h00 UTC (12h Paris) + `workflow_dispatch` | Gemini → `POST /api/update-odds/` + `POST /api/notify/missing-odds/` | Mise à jour cotes bookmaker |
| `email_notifications.yml` | Quotidien 10h UTC (deadline_reminders) + `workflow_dispatch` (résultats) | `POST /api/notify/deadline-reminders/` ou `POST /api/notify/results-summary/` | Rappels si premier match dans 22–30h (vendredi midi → matchs samedi 14h/16h30) + résumés de round |
| `keepalive.yml` | 1er du mois 00h UTC + `workflow_dispatch` | GitHub API (enable workflow) | Réactive `sync_live.yml` (GitHub désactive les workflows inactifs après 60j) |

**`email_notifications.yml` — `workflow_dispatch` inputs :**
- `command` : `deadline_reminders` ou `results_summary`
- `competition_id` : ID DB de la compétition (pour `results_summary` seulement)
- `round_label` : ex. `"26"` (pour `results_summary` seulement)

## Known Issues / TODOs

Sprint 1 is complete. All migration items have been resolved:
- `predictions` app, `Prediction` model, `result_type` field — done
- `Competition.scoring_system` + `good_gap_pts` — done
- `Team.slug` + `short_name` — done
- `Match.cote_home/draw/away` + computed properties — done
- `CustomUser.favorite_team` is FK to Team — done
- URL routes in English — done
- `dj-database-url` in `requirements.txt` — done
- `locale/` directory — done
- `django-crontab` removed — done
- Scoring test suite (11 tests) — done
- GitHub Actions sync workflow — done

### Done — Sprint 12 (2026-09-09)

- Integration test suite for `_calculate_points_for_match()` and `refresh_user_scores_for_match()` — done
  - `apps/matches/tests.py` — 12 `django.test.TestCase` tests (real DB, no new deps)
  - Covers the production bug: score correction after premature FINISHED status now has a regression test
  - Hotfix `b24d0fa` backported locally (`points_earned__isnull=True` filter removed)

### Done — Sprint 11 (2026-09-03)

- Automated weekly odds update via Gemini 3.6 Flash + Google Search grounding — done
  - `GET /api/upcoming-matches/` — returns upcoming matches for Gemini to process
  - `POST /api/update-odds/` — writes bookmaker odds, validates range `[10, 1000]`, rejects locked matches
  - `POST /api/notify/missing-odds/` — emails superusers if any upcoming match has no odds after update
  - `.github/scripts/update_odds.py` — weekly GHA script (Gemini chat + `submit_odds` FunctionDeclaration)
  - `.github/scripts/test_odds.py` — standalone test script (no Django needed)
  - `.github/workflows/update_odds.yml` — cron every Tuesday 12:00 Paris, `GOOGLE_API_KEY` secret
- `Team.logo_url` dropped — field was unused, local PNGs at `static/img/teams/<slug>.png` are source of truth — done

### Done — Sprint 10 (2026-09-02)

- Cloudflare Turnstile CAPTCHA on register + login — server-side verification, `cleanup_bot_accounts` command — done
- Leagues scoped to competitions: `League.competitions` M2M required at creation, leaderboard and predictions scoped to those competitions — done
- `Competition.end_date` + `deactivate_ended_competitions` management command — done
- Champions Cup (1464) and Challenge Cup (1470) season 2027 added to `RUGBY_COMPETITIONS` in settings — done
- `sync_all_competitions()` now iterates `settings.RUGBY_COMPETITIONS` instead of active DB entries — done
- Predictions page: chronological ordering (day → competition → time) with competition badge separators — done
- Global rankings: single "Global" tab + competition filter chips (pill style) instead of per-competition tabs — done

### On hold / not worth it now

- `rankings.UserScore` — `rank` field exists in the model but is never written; ranking is computed in Python in `_build_leaderboard()`. Pre-calculating it in DB would only help at scale (thousands of users/leagues). Parked until there's a real need.