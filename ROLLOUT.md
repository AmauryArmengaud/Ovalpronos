# ROLLOUT.md

Implementation plan for Oval'Pronos. Current state: **V2 complete** (Sprints 1–13 done). Deployed on Hetzner CX22.

---

## Current State Inventory

### Done (2026-09-09)
- All V1 + V2 sprints complete (Sprints 1–13)
- Deployed on Hetzner CX22, PostgreSQL self-hosted, Gunicorn + deploy.sh via GitHub Actions
- All scheduled tasks run on VPS cron — zero GHA minutes for syncs/odds/notifications
- Automated odds update via Gemini 3.6 Flash every Tuesday 10:00 UTC
- Email notifications via Brevo (deadline reminders, results summary, missing odds alert)
- Cloudflare Turnstile CAPTCHA on register + login
- Private leagues scoped to competitions
- Custom admin interface (dashboard, themed, full actions)
- `Team.logo_url` dropped — local PNGs at `static/img/teams/<slug>.png` are source of truth

### On hold / not worth it now
- `rankings.UserScore` — `rank` field exists in the model but is never written; ranking is computed in Python in `_build_leaderboard()`. Pre-calculating it in DB would only help at scale (thousands of users/leagues). Parked until there's a real need.

---

## V1 — MVP

Target: functional app on Render free + Neon, usable by beta testers. ~3–4 focused weekends.

---

### Sprint 1 — Foundation ✓ DONE (2026-05-22)

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

### Sprint 2 — Auth & Base Templates ✓ DONE (2026-05-22)

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

### Sprint 3 — Predictions Page ✓ DONE (2026-05-22)

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

### Sprint 4 — Rankings & Static Content ✓ DONE (2026-05-22)

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

### Sprint 5 — Admin, Sync Endpoint, CI ✓ DONE (2026-05-22)

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

### Sprint 6 — Deploy & Smoke Test ✓ DONE (2026-05-27)

**6.1 — Render + Neon setup** ✓
- `render.yaml` updated: cron job removed (GitHub Actions handles sync), `SYNC_SECRET_TOKEN` + email env vars added, database plan set to `free`
- `ovalpronos/settings.py`: email settings added — `console` backend in dev (controlled by `EMAIL_BACKEND` env var), Ionos SMTP in prod
- Manual steps on first deploy:
  - ✓ Create Neon PostgreSQL, paste connection string into `DATABASE_URL` on Render
  - ✓ Set `RAPIDAPI_KEY`, `SYNC_SECRET_TOKEN`, `EMAIL_HOST_PASSWORD` manually in Render dashboard
  - ✓ Set GitHub secrets: `APP_URL`, `SYNC_SECRET_TOKEN`
- Fixes applied during deploy: Python pinned to 3.12, buildCommand chained with `&&`, CompressedStaticFilesStorage, curl timeout 60s

**6.2 — Smoke test checklist**
- ✓ Register a new account → redirects to `/predictions/`
- ✓ Submit a prediction → Network tab shows HTMX POST → card re-renders with saved values
- ✓ Enter cotes in admin → form appears on predictions page
- ✓ Manually trigger sync from GitHub Actions → endpoint returns 200
- [ ] Match finishes → predictions show badge with points and result_type color
- ✓ Password reset email arrives via Ionos SMTP (validated locally — Render free tier blocks outbound SMTP; switch to Brevo API in V2)
- ✓ `python manage.py test apps.predictions.tests` — all 11 scoring tests pass

---

## V2 — Engagement + Infrastructure (~4€/month)

Target: private leagues, user profiles, automated cotes, Hetzner migration. Implement after V1 is stable with real users.

---

### Sprint 7 — Profile Page & Progress Bar ✓ DONE (2026-05-28)

Goal: users have a personal stats page. Predictions page shows round completion.

**7.1 — Profile page**
- `apps/accounts/views.py`: `ProfileView` (LoginRequired) — season stats aggregated from `Prediction`: total points, count by result_type, rank
- `apps/accounts/urls.py`: `profile/` → `ProfileView` (name=`profile`)
- `templates/accounts/profile.html`: display_name, avatar placeholder, season stats cards (Points, Exact, Écart, Vainqueur), weekend score summary ("Ce week-end tu as marqué X pts — tu gagnes 3 places !")
- Navbar: add Profile link when authenticated

**7.2 — Prediction progress bar**
- `apps/predictions/views.py`: `PredictionsView` — add per-round count of submitted vs total predictions
- `templates/predictions/index.html`: progress bar per round "N/M pronos soumis" above match list

**7.3 — Avatar & favorite team on profile**
- `apps/accounts/models.py`: `avatar` ImageField (blank=True), `favorite_team` FK already exists
- `apps/accounts/forms.py`: `ProfileForm` — fields: display_name, avatar, favorite_team
- `apps/accounts/views.py`: `ProfileEditView` (LoginRequired, UpdateView)
- `templates/accounts/profile_edit.html`

---

### Sprint 8 — Private Leagues ✓ DONE (2026-06-07)

Goal: users can create and join private leagues, compete on a dedicated leaderboard.

**8.1 — League model**
- `apps/leagues/` — new app, add to `INSTALLED_APPS`
- `apps/leagues/models.py`: `League` — `name`, `invite_code` (5-char, unique, auto-generated), `creator` FK to CustomUser, `members` M2M to CustomUser
- `apps/leagues/urls.py`: wire all league URLs
- `ovalpronos/urls.py`: `path('leagues/', include('apps.leagues.urls', namespace='leagues'))`
- Migration + admin panel

**8.2 — Create & join flow**
- `apps/leagues/views.py`:
  - `LeagueCreateView` (LoginRequired, CreateView): auto-generates invite code, adds creator as member
  - `LeagueJoinView` (LoginRequired, POST): looks up by invite code, adds user to members
  - `LeagueDetailView` (LoginRequired): league ranking — aggregate from `Prediction` filtered to members
- `templates/leagues/create.html`, `join.html`, `detail.html`
- URL: `/leagues/`, `/leagues/join/`, `/leagues/<pk>/`

**8.3 — League ranking tab**
- `templates/rankings/index.html`: add tab "Ma ligue" alongside global ranking
- `apps/rankings/views.py`: `RankingsView` — pass user's leagues + selected league context
- League rank shows same columns as global (Points, Exact, Écart, Vainqueur) filtered to league members

**8.4 — Profile league management**
- `templates/accounts/profile.html`: list user's leagues with invite code + leave button
- `apps/leagues/views.py`: `LeagueLeaveView` (LoginRequired, POST)

---

### Sprint 9 — UserScore Cache & Email Notifications ✓ DONE (2026-06-07)

Goal: rankings are fast on large datasets. Users get email reminders and result summaries.

**9.1 — UserScore cache**
- `apps/rankings/models.py`: `UserScore` — `user` FK, `competition` FK (nullable), `league` FK (nullable), `points`, `exact_count`, `gap_count`, `win_count`, `rank`; partial `UniqueConstraint` on `(user, competition, league)`
- `apps/matches/services.py`: `refresh_user_scores_for_match(match)` — called at end of `_calculate_points_for_match()`, bulk upserts `UserScore` rows
- `apps/rankings/views.py`: `RankingsView` — read from `UserScore` instead of aggregating `Prediction` directly; use window function for rank
- Migration

**9.2 — Email backend switch (Brevo)**
- `pip install django-anymail`
- `requirements.txt`: add `django-anymail`
- `ovalpronos/settings.py`: `EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'`, `ANYMAIL = {'BREVO_API_KEY': config('BREVO_API_KEY', default='')}`
- Hetzner `.env`: add `BREVO_API_KEY`

**9.3 — Email notifications**
- `apps/predictions/tasks.py` (management command, called via GitHub Actions):
  - `send_deadline_reminders()` — users with 0 predictions on upcoming round, send J-24h reminder
  - `send_results_summary()` — after round finishes, send per-user points earned that round
- `templates/accounts/emails/deadline_reminder.html`, `results_summary.html`
- `.github/workflows/email_notifications.yml`: cron J-24h before each round kickoff + post-round trigger

---

### Sprint 9.5 — Admin Interface ✓ DONE (2026-06-11)

Goal: staff can manage all data from a polished admin UI matching the app's design system.

**9.5.1 — Custom theme**
- `templates/admin/base_site.html`: injects Bootstrap 5, Barlow, Tabler Icons, `main.css`, and `admin.css` — no third-party admin package
- `static/css/admin.css`: Django admin selector overrides using `var(--color-primary)` etc. from `main.css`; no CSS variable redefinitions

**9.5.2 — Dashboard**
- `templates/admin/index.html`: 4 metric cards (active users, upcoming matches, matches sans cotes, unscored predictions)
- `templates/admin/partials/dashboard_stats.html`: card partial rendered via inclusion tag
- `apps/matches/templatetags/admin_extras.py`: `dashboard_stats` inclusion tag

**9.5.3 — Admin actions & display**
- `CompetitionAdmin`: sync from API action, recalculate all scores action, match count column, per-row sync button
- `MatchAdmin`: status badge, odds badge, prediction count, `PredictionInline` (read-only), `UpcomingMatchFilter` (default = SCHEDULED), recalculate/refresh/hide/show actions
- `PredictionAdmin`: result-type badges using app token colors, match hyperlink, recalculate action
- `UserScoreAdmin`: registered (was empty), scope label, cache refresh action, fully read-only
- `CustomUserAdmin`: prediction count column, activate/deactivate actions
- `LeagueAdmin`: regenerate invite code action
- `admin_views.py`: fix hardcoded redirect → `reverse('admin:matches_competition_change', ...)`

---

### Sprint 10.5 — Anti-Bot, League Scoping & UX Polish ✓ DONE (2026-09-02)

**10.5.1 — Cloudflare Turnstile CAPTCHA** ✓
- `apps/accounts/views.py`: `RegisterView` verifies Turnstile token server-side before account creation
- `apps/accounts/management/commands/cleanup_bot_accounts.py`: purges existing fake accounts (criteria: no predictions, no leagues, non-staff); flags `--dry-run` / `--since` / `--yes`
- `ovalpronos/settings.py`: `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` (test keys as defaults)
- `templates/accounts/register.html`: Turnstile widget injected via `extra_head` block
- Also added to login page (06e6c0d)

**10.5.2 — Leagues scoped to competitions** ✓
- `apps/leagues/models.py`: `League.competitions` M2M → Competition (required at creation); `is_active` computed property
- League leaderboard and prediction display scoped to member competitions only
- `apps/matches/models.py`: `Competition.end_date` DateField (null/blank)
- `apps/matches/management/commands/deactivate_ended_competitions.py`: sets `is_active=False` on competitions past `end_date`
- Champions Cup (1464) + Challenge Cup (1470) season 2027 added to `RUGBY_COMPETITIONS` in settings

**10.5.3 — Sync from settings, not DB** ✓
- `sync_all_competitions()` now iterates `settings.RUGBY_COMPETITIONS` so new competitions are synced immediately without pre-existing DB rows

**10.5.4 — Predictions page: chronological ordering** ✓
- Matches sorted by day → competition → kickoff time (instead of competition tab → round)
- Competition badge separator between groups; no-odds matches still behind Bootstrap collapse toggle

**10.5.5 — Global rankings: competition filter chips** ✓
- Replace per-competition tabs with a single "Global" tab + pill chips to filter by competition
- League tabs remain as main navigation
- CSS: `.filter-chip` in `static/css/main.css` using `border` style (not transparent bg)

---

### Sprint 10 — Automated Cotes & Hetzner Migration ✓ DONE (2026-06-12)

Goal: cotes are filled automatically. App moves to paid VPS.

**10.1 — ~~The Odds API integration~~ → superseded by Sprint 11 (Gemini)**
- No API covers Top 14 adequately. Replaced by Gemini 3.6 Flash + Google Search grounding.

**10.2 — Hetzner CX22 migration ✓ DONE**
- ✓ Provision Hetzner CX22 (Ubuntu) — ~4€/month
- ✓ Install: Python 3.12, PostgreSQL, gunicorn, certbot
- ✓ `pg_dump` Neon DB → import to Hetzner PostgreSQL
- ✓ Deploy script `~/deploy.sh` (git pull, migrate, collectstatic, restart gunicorn)
- ✓ GitHub Actions `deploy.yml`: SSH on push to `main` → runs `~/deploy.sh`
- ✓ Update `DATABASE_URL` env var
- ✓ Point domain DNS to Hetzner IP
- ✓ Update `ALLOWED_HOSTS`
- ✓ Decommission Render + Neon

**10.3 — Language selector ✓ DONE (2026-09-03)**
- `templates/base.html`: FR/EN toggle in desktop navbar — POST to `set_language`, stays on current page
- `ovalpronos/urls.py`: `path('i18n/', include('django.conf.urls.i18n'))`
- `locale/en/` created and compiled — source strings are English, no translation needed
- `.lang-toggle` style in `main.css`

---

### Sprint 13 — VPS Cron Migration ✓ DONE (2026-09-09)

Goal: zero GHA minutes for scheduled tasks — all crons on the VPS.

**13.1 — `sync_if_live` management command** ✓
- `apps/matches/management/commands/sync_if_live.py`: exits silently if no match is IN_PLAY or started within the last 2h; otherwise syncs all competitions
- Same fenêtre logic as `has_live_matches_api` view

**13.2 — VPS crontab (5 entries)** ✓
- `0 7 * * *` → `python manage.py sync_matches` (daily full sync)
- `*/10 * * * *` → `python manage.py sync_if_live` (live sync, silent when idle)
- `0 10 * * 2` → `python .github/scripts/update_odds.py` (Tuesday odds update)
- `0 10 * * *` → `python manage.py send_deadline_reminders` (daily deadline reminders)
- Logs in `/home/amaury/logs/`, rotated via `/etc/logrotate.d/ovalpronos`

**13.3 — GHA cleanup** ✓
- Deleted `sync_live.yml`, `keepalive.yml`
- Removed `schedule:` from `sync_matches.yml`, `update_odds.yml`, `email_notifications.yml` — `workflow_dispatch` kept for manual use
- Added `google-genai>=1.0.0` to `requirements.txt` (needed by `update_odds.py` on VPS)

---

### Sprint 12 — Integration Tests ✓ DONE (2026-09-09)

Goal: regression coverage for the production scoring bug.

**12.1 — Integration test suite** ✓
- `apps/matches/tests.py` — 12 `django.test.TestCase` tests (real DB, no new deps)
- Covers `_calculate_points_for_match()` and `refresh_user_scores_for_match()`
- Regression test: score correction after premature FINISHED status (hotfix `b24d0fa`)
- Hotfix backported locally: `points_earned__isnull=True` filter removed

---

### Sprint 11 — Automated Odds via Gemini ✓ DONE (2026-09-03)

Goal: cotes filled automatically each week without any manual intervention.

**11.1 — Django API endpoints** ✓
- `GET /api/upcoming-matches/` — returns SCHEDULED/POSTPONED matches in next 7 days (Bearer token)
- `POST /api/update-odds/` — validates and writes cotes (range `[10, 1000]`, rejects locked matches)
- `POST /api/notify/missing-odds/` — emails superusers if any upcoming match still has no odds

**11.2 — Gemini scraper script** ✓
- `.github/scripts/update_odds.py`: Gemini 3.6 Flash + Google Search grounding + `submit_odds` FunctionDeclaration
- Fetches matches → sends to Gemini → extracts `submit_odds` call from chat history → normalises protobuf → POSTs to Django
- `.github/scripts/test_odds.py`: standalone test (no Django needed), hardcoded Top 14 matches

**11.3 — GitHub Actions cron** ✓
- `.github/workflows/update_odds.yml`: every Tuesday 12:00 Paris (`0 10 * * 2`)
- Required secret: `GOOGLE_API_KEY` (Google AI Studio)

**11.4 — Cleanup** ✓
- `Team.logo_url` dropped — field was unused, local PNGs at `static/img/teams/<slug>.png` are source of truth

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
