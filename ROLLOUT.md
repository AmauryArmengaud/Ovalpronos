# ROLLOUT.md

Implementation plan for Oval'Pronos. Current state: **V1 code complete** (Sprints 1–6). Ready for deployment on Render + Neon.

---

## Current State Inventory

### Done
- Django project skeleton (`ovalpronos/settings.py`, `urls.py`, `wsgi.py`)
- Apps: `accounts`, `matches`, `predictions`, `rankings`
- All models correct and migrated: `CustomUser`, `Competition`, `Team`, `Match`, `Prediction`
- URLs in English (`/accounts/`, `/predictions/`, `/rankings/`, `/rules/`, `/api/sync-scores/`)
- i18n settings wired (`LocaleMiddleware`, `LANGUAGES`, `LOCALE_PATHS`)
- Base template (`templates/base.html`) — Bootstrap 5, HTMX, Barlow, Tabler Icons
- `static/css/main.css` — all CSS variables, no hardcoded colors
- Full auth flow: register, login, logout, password reset + email template
- Scoring service (`apps/predictions/services.py`) — COTES and FIXED modes
- Scoring tests (`apps/predictions/tests.py`) — 11/11 passing, no DB required
- Predictions page with HTMX auto-save (`PredictionsView`, `SubmitPredictionView`)
- Match card partial (`templates/partials/match_card.html`) — all 6 states
- Rankings page — on-the-fly aggregation, medals, current user highlighted
- Landing page (`templates/matches/home.html`) — hero + feature cards
- Rules page (`templates/matches/rules.html`) — scoring tiers, worked example
- 404 page (`templates/404.html`)
- Admin panels: `CompetitionAdmin`, `TeamAdmin`, `MatchAdmin` (cotes editable), `PredictionAdmin` (read-only), `CustomUserAdmin`
- Admin api-sports.io import view (`/admin/matches/competition/<id>/import/`)
- Sync service complete: `sync_competition_matches()`, `sync_all_competitions()`, `_calculate_points_for_match()` with CANCELLED handling
- Sync API endpoint (`POST /api/sync-scores/` with Bearer token)
- GitHub Actions workflow (cron every 2h + every 15min Sat/Sun + manual trigger)
- Email settings: console backend in dev, Ionos SMTP in prod (via `EMAIL_BACKEND` env var)
- `render.yaml` production-ready: no cron job, all required env vars declared

### Remaining before first deploy (manual)
- Create Neon PostgreSQL → paste connection string into `DATABASE_URL` on Render
- Set `APISPORTS_KEY`, `SYNC_SECRET_TOKEN`, `EMAIL_HOST_PASSWORD` in Render dashboard
- Set GitHub secrets: `APP_URL`, `SYNC_SECRET_TOKEN`
- Set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` in Render env vars
- Run smoke test checklist (Sprint 6.2)

### Must Fix Before New Work

| Issue | File | Fix | Status |
|---|---|---|---|
| Rename `pronostics` → `predictions`, `Pronostic` → `Prediction` | `apps/pronostics/` | Rename dir, update INSTALLED_APPS | ✓ Done |
| Add `result_type` to Prediction | `apps/predictions/models.py` | New CharField field | ✓ Done |
| Add `scoring_system`, `good_gap_pts` to Competition | `apps/matches/models.py` | New fields | ✓ Done |
| Add `slug`, `short_name` to Team | `apps/matches/models.py` | New fields | ✓ Done |
| Add `cote_home`, `cote_draw`, `cote_away` to Match | `apps/matches/models.py` | New IntegerFields | ✓ Done |
| Add `has_odds`, `closes_soon`, `time_until_kickoff` properties | `apps/matches/models.py` | Computed properties | ✓ Done |
| `CustomUser.favorite_team` CharField → FK to Team | `apps/accounts/models.py` | ForeignKey | ✓ Done |
| URL routes French → English | `ovalpronos/urls.py` | `/pronos/`→`/predictions/`, etc. | ✓ Done |
| Add `dj-database-url` to requirements.txt | `requirements.txt` | One line | ✓ Done |
| Create `locale/fr/LC_MESSAGES/` directory | — | mkdir | ✓ Done |

---

## V1 — MVP

Target: functional app on Render free + Neon, usable by beta testers. ~3–4 focused weekends.

---

### Sprint 1 — Foundation ✓ DONE

Goal: project runs cleanly, i18n wired, all models correct, URLs in English.

**1.1 — Fix requirements and settings** ✓
**1.2 — Rename `pronostics` app to `predictions`** ✓
**1.3 — Migrate models to specs** ✓
**1.4 — Fix URL routes** ✓ (partial — `rules/` and `api/` entries still needed in Sprint 5)
**1.5 — Create locale directory and run fresh migrations** ✓

Remaining from Sprint 1:
- Add email settings (SMTP Ionos for prod, console backend for dev) — deferred to Sprint 6
- `python manage.py makemessages -l fr` — run after first templates are written (Sprint 2)

---

### Sprint 2 — Auth & Base Templates ✓ DONE

Goal: users can register, log in, reset password. App has a shell layout.

**2.1 — Base template**
- `templates/base.html`: Bootstrap 5 CDN, HTMX CDN, Barlow font, CSS variables in `<style>`, navbar, messages block, content block, footer
- Navbar: logo, nav links (Predictions, Rankings, Rules), user display when authenticated + logout, Login/Register when not
- `static/css/main.css`: all CSS variables defined here (see CONVENTIONS.md)

**2.2 — Auth views and forms**
- `apps/accounts/views.py`: `RegisterView` (CreateView), use Django built-in `LoginView`, `LogoutView`, `PasswordResetView`, `PasswordResetDoneView`, `PasswordResetConfirmView`, `PasswordResetCompleteView`
- `apps/accounts/forms.py`: `RegistrationForm` — fields: email, password1, password2, first_name, last_name, display_name
- `apps/accounts/urls.py`: wire all auth URLs

**2.3 — Auth templates**
- `templates/accounts/login.html`
- `templates/accounts/register.html`
- `templates/accounts/password_reset.html` (+ `_done`, `_confirm`, `_complete` variants)
- `templates/accounts/emails/password_reset_email.html`
- All display text via `{% trans %}`. No hardcoded colors.

---

### Sprint 3 — Predictions Page ✓ DONE

Goal: authenticated users can submit predictions. Auto-save via HTMX works.

**3.1 — Scoring service**
- `apps/predictions/services.py`: `calculate_points(prediction, match) -> tuple[int, str] | None`
- Handles COTES mode and FIXED mode (branch on `match.competition.scoring_system`)

**3.2 — Scoring unit tests (mandatory before deploy)**
- `apps/predictions/tests.py`: 11/11 passing — `python manage.py test apps.predictions.tests`
- `test_exact_score`, `test_good_gap`, `test_good_gap_boundary`, `test_good_gap_over`, `test_win_only`, `test_miss`, `test_draw_exact`, `test_draw_gap`, `test_draw_miss`, `test_cancelled`, `test_no_odds`
- No DB access — uses `SimpleTestCase` + `MagicMock`

**3.3 — Predictions views**
- `apps/predictions/views.py`:
  - `PredictionsView` (LoginRequired, GET): matches grouped by competition + round, tab filter (Upcoming/Live/Past); existing predictions for current user
  - `SubmitPredictionView` (LoginRequired, POST, HTMX): validate lock + odds; `Prediction.objects.update_or_create`; return rendered `partials/match_card.html`
- `apps/predictions/urls.py`: `''` → `PredictionsView` (name=`index`), `submit/<int:match_pk>/` → `SubmitPredictionView` (name=`submit`)

**3.4 — Match card partial (6 states)**
- `templates/partials/match_card.html`
  1. Scheduled + odds + no prediction (open form)
  2. Scheduled + odds + prediction exists (pre-filled form)
  3. No odds (`has_odds=False`) → "Cotes à venir", form hidden
  4. Locked, not finished (readonly prediction, cotes displayed)
  5. Finished (real scores + points badge with result_type color)
  6. Cancelled (grey badge)
- HTMX form: `hx-post`, `hx-trigger="change"`, `hx-swap="outerHTML"`
- All text via `{% trans %}`. Local SVG logo pattern. CSS variables only.
- `templates/predictions/index.html`: extends base, renders grouped match cards with tab filter

---

### Sprint 4 — Rankings & Static Content ✓ DONE

Goal: global ranking page works. Landing page and rules page exist.

**4.1 — Rankings (V1, on-the-fly — no UserScore)**
- `apps/rankings/views.py`: `RankingsView` (LoginRequired) — aggregate from `Prediction` directly (sum `points_earned`, count by `result_type`)
- `templates/rankings/index.html`: table with Rank (🥇🥈🥉), Display Name, Points, Pronos, Exact, Écart, Vainqueur — current user highlighted

**4.2 — Landing page**
- `apps/matches/views.py`: `HomeView` — if authenticated redirect to `/predictions/`; else render `matches/home.html`
- `templates/matches/home.html`: hero with tagline + CTAs, two feature cards ("Pronostique tes matchs", "Affronte tes amis")

**4.3 — Rules page**
- `apps/matches/views.py`: `RulesView` (public)
- `templates/matches/rules.html`: four scoring-tier cards, cotes explanation, worked example table (Clermont–Perpignan), draw rule note. Title: "Flexion, liez, jeu"

**4.4 — 404 template**
- `templates/404.html`: "Cette page a botté en touche." with home link

---

### Sprint 5 — Admin, Sync Endpoint, CI ✓ DONE

Goal: admin can manage matches and cotes. Sync endpoint is secured. GitHub Actions cron is live.

**5.1 — Admin panels**
- `apps/matches/admin.py`: `CompetitionAdmin` (list_editable scoring_system/good_gap_pts), `TeamAdmin`, `MatchAdmin` (cotes inline-editable, date_hierarchy)
- `apps/predictions/admin.py`: `PredictionAdmin` — fully read-only (has_add/change_permission = False)
- `apps/accounts/admin.py`: `CustomUserAdmin` extending `UserAdmin` with Oval'Pronos fieldset

**5.2 — Admin import view**
- `apps/matches/admin_views.py`: `CompetitionImportView` (`@staff_member_required`, GET confirmation + POST triggers sync)
- `templates/admin/matches/import.html`
- URL: `/admin/matches/competition/<id>/import/`

**5.3 — Sync service updated**
- `apps/matches/services.py`: source de données = **rugby-live-data (RapidAPI)** — endpoint `/fixtures/{comp_id}/{season}`, headers `x-rapidapi-key` / `x-rapidapi-host`
- Mapping des champs : `home` / `away` / `home_id` / `away_id`, statuts en clair (`"Full Time"`, `"Not Started"`…), date ISO 8601, `game_week` → `round`
- `_calculate_points_for_match()` appelle `calculate_points()` depuis `predictions/services.py`, bulk update CANCELLED, `sync_all_competitions()` boucle sur les compétitions actives

**5.4 — Sync API endpoint**
- `apps/matches/views.py`: `sync_scores_api` — Bearer token validation, calls `sync_all_competitions()`, returns `JsonResponse({'created': n, 'updated': n})`
- `ovalpronos/urls.py`: `path('api/sync-scores/', sync_scores_api)`

**5.5 — GitHub Actions workflow**
- `.github/workflows/sync_matches.yml`: cron every 2h + every 15min Sat/Sun + `workflow_dispatch`
- Required GitHub Secrets: `APP_URL`, `SYNC_SECRET_TOKEN`

---

### Sprint 6 — Deploy & Smoke Test ✓ DONE (code-side)

**6.1 — Render + Neon setup**
- `render.yaml` updated: cron job removed (GitHub Actions handles sync), `SYNC_SECRET_TOKEN` + email env vars added, database plan set to `free`
- `ovalpronos/settings.py`: email settings added — `console` backend in dev (controlled by `EMAIL_BACKEND` env var), Ionos SMTP in prod
- Manual steps on first deploy:
  - Create Neon PostgreSQL, paste connection string into `DATABASE_URL` on Render
  - Set `RAPIDAPI_KEY`, `SYNC_SECRET_TOKEN`, `EMAIL_HOST_PASSWORD` manually in Render dashboard
  - Set GitHub secrets: `APP_URL`, `SYNC_SECRET_TOKEN`

**6.2 — Smoke test checklist** (run after deploy)
- [ ] Register a new account → redirects to `/predictions/`
- [ ] Submit a prediction → Network tab shows HTMX POST → card re-renders with saved values
- [ ] Enter cotes in admin → form appears on predictions page
- [ ] Manually trigger sync from GitHub Actions → endpoint returns 200
- [ ] Match finishes → predictions show badge with points and result_type color
- [ ] Password reset email arrives via Ionos SMTP
- [ ] `python manage.py test apps.predictions.tests` — all 11 scoring tests pass

---

## V2 — Engagement + Infrastructure (~4€/month)

Implement after V1 is stable with real users.

- **Private Leagues**: `League` model (apps/leagues/), `/leagues/join/<code>/` flow, profile page league management, league ranking tab, proximity ranking display
- **UserScore cache**: `rankings.UserScore` with partial `UniqueConstraint`, `refresh_user_scores_for_match()` after each score batch, window-function rank computation
- **Full profile page** (`/accounts/profile/`): season stats, exact/gap/win breakdown, weekend score summary ("This weekend you scored X pts 🔥 — you're up 3 places!")
- **Prediction progress bar**: per-round "N/M predictions submitted" on predictions page
- **Email notifications**: deadline reminder (J-24h) and results email per round (Ionos SMTP)
- **The Odds API**: automate cote entry (replaces manual admin entry)
- **TheSportsDB** (9$/mois) : envisager comme source de données alternative à rugby-live-data si couverture insuffisante (Champions Cup, 6 Nations) — API REST documentée, pas de limite de saison sur le plan payant
- **Language selector**: EN/FR toggle in header
- **Hetzner migration**: Render free → Hetzner CX22 (pg_dump → import → update DNS → update DATABASE_URL)
- **AWS Lambda rebuild**: replace GitHub Actions cron with EventBridge + Lambda for near-real-time scores

---

## V3 — Growth

- Pro D2, Nationale competitions
- Badges and achievements (first prediction, perfect round, top 10, etc.)
- Donation button ("aux marcassins")
- Social sharing (prediction results)

---

## V4 — White Label & SaaS

Transform into a multi-tenant product for clubs, federations, and media.

**Prepare from V2:** CSS variables already in place, all UI text through i18n, no hardcoded domain references.

- `django-tenants` with PostgreSQL schema isolation per tenant
- `TenantConfig` model: logo, CSS variable overrides, name, favicon, custom domain
- Per-tenant admin panel (restricted permissions)
- Private competitions (no external API dependency)
- Per-tenant scoring rules
- CSV export (rankings, predictions)
- Analytics dashboard

**Pricing tiers (indicative):** Starter ~50€/mo, Club ~150€/mo, Pro on quote.
