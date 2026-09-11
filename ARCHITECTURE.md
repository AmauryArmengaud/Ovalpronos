# ARCHITECTURE.md

Technical reference for Oval'Pronos. Read this before implementing new features.

---

## 1. Project Layout

```
ovalpronos/              # Django project config
  settings.py
  urls.py                # Root URL conf — all paths in English
  analytics.py           # PostHog capture() utility — lazy Posthog instance, swallows exceptions
  context_processors.py  # Exposes POSTHOG_API_KEY to all templates

apps/
  accounts/              # CustomUser, auth views, profile
  matches/               # Competition, Team, Match, sync service, admin views
  predictions/           # Prediction model, HTMX submission view
  rankings/              # Ranking views (on-the-fly aggregation)
  leagues/               # League model, create/join/leave flow

templates/
  base.html
  accounts/
  matches/
  predictions/
  rankings/
  leagues/
  partials/              # HTMX swap targets (match cards, etc.)

static/
  css/main.css           # CSS variables, global styles
  js/
  img/teams/             # <slug>.png — one file per team

locale/
  fr/LC_MESSAGES/
    django.po
    django.mo
```

---

## 2. Data Models

### `accounts.CustomUser` (extends AbstractUser)

| Field | Type | Notes |
|---|---|---|
| `email` | EmailField | unique, login identifier |
| `first_name` | CharField | required |
| `last_name` | CharField | required |
| `display_name` | CharField(50) | shown in rankings; falls back to username |
| `favorite_team` | FK → Team | null/blank, set after teams are imported |
| `avatar` | ImageField | optional, upload_to='avatars/' |

### `matches.Competition`

| Field | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | unique api-sports.io ID |
| `name` | CharField | "Top 14" |
| `code` | CharField | "TOP14" |
| `season` | CharField | "2024-2025" |
| `is_active` | BooleanField | current season flag; set to False by `deactivate_ended_competitions` when past `end_date` |
| `end_date` | DateField | null/blank; when set, `deactivate_ended_competitions` auto-deactivates |
| `scoring_system` | CharField | 'COTES' or 'FIXED' |
| `good_gap_pts` | IntegerField | max gap diff for ×2 tier (default 3) |

One competition per code can be `is_active=True` at a time. Rankings filter on this flag.

### `matches.Team`

| Field | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | unique api-sports.io ID |
| `name` | CharField | "Stade Toulousain" |
| `short_name` | CharField | "STA" |
| `slug` | SlugField | "stade-toulousain" — key for local PNG |
| `country` | CharField | used for national teams |

Logo resolution: `static/img/teams/<slug>.png`. No external logo URLs.

### `matches.Match`

| Field | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | unique api-sports.io ID |
| `competition` | FK → Competition | |
| `home_team` | FK → Team | |
| `away_team` | FK → Team | |
| `round` | CharField | "Round 12", "Semi-final" — English |
| `datetime` | DateTimeField | stored UTC, displayed Europe/Paris |
| `venue` | CharField | optional |
| `status` | CharField | SCHEDULED / IN_PLAY / FINISHED / POSTPONED / CANCELLED |
| `home_score` | IntegerField | null until played |
| `away_score` | IntegerField | null until played |
| `cote_home` | IntegerField | null until entered in admin; Unibet odds × 10 |
| `cote_draw` | IntegerField | null until entered in admin; Unibet odds × 10 |
| `cote_away` | IntegerField | null until entered in admin; Unibet odds × 10 |

Computed properties (no DB storage):
- `is_locked` → `now() >= datetime`
- `has_odds` → all three cote fields are non-null
- `result` → 'home' / 'away' / 'draw' / None
- `closes_soon` → kickoff within 24h but not yet locked
- `time_until_kickoff` → formatted string "2h14", "45min", "3d"

**Prediction blocking rule:** if `not match.has_odds`, the match card shows "Odds coming soon" and the form is hidden. The submission view also rejects POSTs when odds are missing.

**CANCELLED handling:** all associated Predictions get `points_earned=0`, `result_type='CANCELLED'`. UserScore `count_cancelled` is incremented.

### `predictions.Prediction`

Rename of current `pronostics.Pronostic`. New field: `result_type`.

| Field | Type | Notes |
|---|---|---|
| `user` | FK → CustomUser | |
| `match` | FK → Match | |
| `predicted_home_score` | IntegerField | |
| `predicted_away_score` | IntegerField | |
| `points_earned` | IntegerField | null = not yet calculated |
| `result_type` | CharField | EXACT / GAP / WIN / MISS / CANCELLED / null |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto |

Constraint: `unique_together = ('user', 'match')`.

### `leagues.League`

| Field | Type | Notes |
|---|---|---|
| `name` | CharField | |
| `invite_code` | CharField(5) | auto-generated alphanumeric, unique |
| `creator` | FK → CustomUser | CASCADE — league is deleted if creator deletes account |
| `members` | M2M → CustomUser | active members (creator is automatically added) |
| `competitions` | M2M → Competition | required at creation; scopes league leaderboard and prediction display |
| `created_at` | DateTimeField | auto |

`is_active` is a computed property: `True` if any linked competition has `is_active=True`. Creator cannot leave their own league. Invite code is generated once on creation and never changes.

### `rankings.UserScore`

Denormalized score cache — one row per (user, scope). Three scopes:
- `(competition=None, league=None)` → global
- `(competition=<comp>, league=None)` → per competition
- League rankings are derived from global rows filtered to league members (no separate league rows written by `refresh_user_scores_for_match`).

| Field | Type | Notes |
|---|---|---|
| `user` | FK → CustomUser | |
| `competition` | FK → Competition | null = global scope |
| `league` | FK → League | null (league rows are not written by the sync service) |
| `points` | IntegerField | sum of `points_earned` across scored predictions |
| `prediction_count` | IntegerField | count of scored predictions |
| `exact_count` | IntegerField | |
| `gap_count` | IntegerField | |
| `win_count` | IntegerField | |

`rank` field exists in the model but is never written — ranking is computed in Python in `_build_leaderboard()`. Pre-calculating it would only help at scale.

---

## 3. Scoring Algorithm

Located in `apps/predictions/services.py` as a standalone function (not a model method) so it can be unit-tested without model instantiation.

```
calculate_points(prediction, match) -> (points: int, result_type: str) | None

Preconditions:
  match.status == FINISHED or CANCELLED
  match.has_odds == True

Steps:
  1. If CANCELLED → return (0, 'CANCELLED')
  2. If not FINISHED → return None
  3. real_gap = home_score - away_score
     pred_gap = predicted_home - predicted_away
  4. Select winning_cote:
       real_gap > 0  → cote_home
       real_gap < 0  → cote_away
       real_gap == 0 → cote_draw
  5. Draw special case (real_gap == 0 AND pred_gap == 0):
       exact scores match → (cote_draw × 3, 'EXACT')
       otherwise          → (cote_draw × 2, 'GAP')
  6. Wrong winner (sign(pred_gap) != sign(real_gap)):
       → (0, 'MISS')
  7. Exact score (pred_home == real_home AND pred_away == real_away):
       → (winning_cote × 3, 'EXACT')
  8. Gap within competition.good_gap_pts:
       abs(pred_gap - real_gap) <= good_gap_pts → (winning_cote × 2, 'GAP')
  9. Correct winner → (winning_cote × 1, 'WIN')
```

FIXED mode (when `competition.scoring_system == 'FIXED'`): same branching logic, replace multipliers with flat values 5 / 3 / 1 / 0.

**Numeric example** (from specs §7.5): match Clermont 17 — Perpignan 22, cote_away=63

| Prediction | gap pred | gap diff | Result | Points |
|---|---|---|---|---|
| 17 - 22 | -5 | 0 | EXACT | 63 × 3 = **189** |
| 15 - 22 | -7 | 2 ≤ 3 | GAP | 63 × 2 = **126** |
| 14 - 25 | -11 | 6 > 3 | WIN | 63 × 1 = **63** |
| 20 - 10 | +10 | — | MISS | **0** |

---

## 4. Sync Flow

### V1: GitHub Actions → Django endpoint

```
GitHub Actions cron
  schedule: every 2h (every 15min Sat/Sun)
  → POST /api/sync-scores/
    Authorization: Bearer <SYNC_SECRET_TOKEN>

sync_scores_api (apps/matches/views.py)
  → validate token against settings.SYNC_SECRET_TOKEN
  → call sync_all_competitions()
  → return JsonResponse {created, updated}

sync_all_competitions() (apps/matches/services.py)
  → for each competition in settings.RUGBY_COMPETITIONS (not filtered by DB is_active):
      sync_competition_matches(competition.code)

sync_competition_matches(code)
  → GET v1.rugby.api-sports.io/games?league=<id>&season=<season>
  → for each game: update_or_create Match, Team (within transaction.atomic)
  → if match just reached FINISHED:
      _calculate_points_for_match(match)

_calculate_points_for_match(match)
  → if CANCELLED: bulk-set all predictions to (0, 'CANCELLED'), return
  → if not has_odds: return early
  → Prediction.objects.filter(match=match)   # ALL predictions, including already-scored ones
  → for each prediction:
      points, result_type = calculate_points(prediction, match)
      if (points_earned, result_type) changed:   # skip write if unchanged
          prediction.save(update_fields=['points_earned', 'result_type'])
  → refresh_user_scores_for_match(match)
```

Note: the queryset deliberately omits `points_earned__isnull=True`. Filtering it would cause score corrections (e.g. a match mis-detected as FINISHED by the live sync, then corrected by the next sync) to be silently ignored.

### V2: AWS Lambda (future)

EventBridge (every 5min during match windows) → Lambda fetches api-sports.io scores → POST to `/api/sync-scores/` with full score payload → Django updates and calculates in one shot.

---

## 5. HTMX Prediction Auto-Save Flow

```
User types a score in either input field
  → change event fires on the <form>
  → HTMX sends POST /predictions/submit/<match_pk>/
    with both home + away inputs + CSRF token
    hx-trigger="change", hx-swap="outerHTML"

predictions:submit view
  1. Check match.is_locked → 403 if locked
  2. Check match.has_odds  → 400 if no odds
  3. Validate: both home and away present and >= 0
     (if only one field filled → return partial unchanged, no save)
  4. Prediction.objects.update_or_create(user=request.user, match=match, ...)
  5. Return: render partial "partials/match_card.html" with updated context
     (HTMX replaces the entire match card via outerHTML)

The response partial must include the same hx-post / hx-trigger attributes
so future changes continue to trigger saves.
```

---

## 6. UserScore Cache Pattern

`refresh_user_scores_for_match(match)` is called at the end of `_calculate_points_for_match()`. It:
1. Finds all users with a scored prediction on the match (`points_earned__isnull=False`)
2. For each user, `update_or_create` a global `UserScore` (competition=None) and a per-competition `UserScore`
3. Aggregates `points`, `prediction_count`, `exact_count`, `gap_count`, `win_count` from all scored predictions

Rankings read from `UserScore` for performance. The `rank` field is never written — final rank order is computed in Python in `_build_leaderboard()` at query time.

---

## 7. Rankings Display

Global rankings use a single "Global" tab with competition filter chips (pill-style). Clicking a chip filters the leaderboard to users who predicted that competition. League tabs remain as separate navigation items.

For the global ranking view:

```
1. Aggregate from Prediction (on-the-fly, V1 — no UserScore)
2. Apply competition filter if chip selected (filter to matches in that competition)
3. Sort by total points DESC, assign rank
4. Highlight current user row
```

Columns: Rank | Display Name | Points | Predictions | Exact | GAP | WIN

---

## 8. League Invite Flow

```
/leagues/join/ (GET, unauthenticated)
  → LoginRequired redirects to /accounts/login/?next=/leagues/join/
  → After login, Django follows the ?next= parameter automatically (built into LoginView)

/leagues/join/ (GET, authenticated)
  → Render form with invite code input field

/leagues/join/ (POST, authenticated)
  → Read invite_code from POST data
  → Look up League by invite_code; error message if not found
  → If already a member: info message, redirect to league detail
  → Add request.user to league.members
  → Redirect to /leagues/<pk>/ with success message
```

The `next` parameter is handled natively by Django's `LoginView` — no custom logic needed.

---

## 9. Admin Interface

### Theme

The admin uses Django's native admin with a custom theme that matches the main app's design system. No third-party admin package.

- `templates/admin/base_site.html` — injects Bootstrap 5, Barlow, Tabler Icons, `main.css`, and `admin.css`
- `static/css/admin.css` — overrides Django admin selectors using `var(--color-primary)`, `var(--color-accent)` etc. from `main.css`; **never redefines CSS variables**
- `templates/admin/index.html` — dashboard with 4 metric cards
- `apps/matches/templatetags/admin_extras.py` — `dashboard_stats` inclusion tag powering the dashboard

**Rule:** admin badge colors must use CSS variable names from `main.css` (e.g. `var(--color-badge-exact)`), not hardcoded hex.

### ModelAdmin capabilities

| Admin | Key additions |
|---|---|
| `CompetitionAdmin` | Sync action, recalculate scores action, match count column, per-row sync button |
| `MatchAdmin` | Status/odds badges, prediction count, `PredictionInline` (read-only), `UpcomingMatchFilter` (default=SCHEDULED), recalculate/refresh/hide actions |
| `PredictionAdmin` | Result-type badges, match link, recalculate action; no add/change permission |
| `UserScoreAdmin` | Scope label, cache refresh action; no add/change permission |
| `CustomUserAdmin` | Prediction count, activate/deactivate actions |
| `LeagueAdmin` | Regenerate invite code action |

### Admin service calls

Admin actions call existing service functions directly — no duplication:
- `sync_competition_matches(code)` — `apps/matches/services.py`
- `_calculate_points_for_match(match)` — `apps/matches/services.py`
- `refresh_user_scores_for_match(match)` — `apps/matches/services.py`

### Custom admin views

Non-standard ModelAdmin pages use `@staff_member_required` and live in `apps/matches/admin_views.py`. URLs registered in `ovalpronos/urls.py` under the `admin/` prefix.

```
/admin/matches/competition/<id>/import/
  GET  → render import form (templates/admin/matches/import.html)
  POST → call sync_competition_matches(competition.code)
       → Django messages with result counts
       → redirect to competition change page (via reverse())
```

---

## 10. Deployment Architecture

### Production (~4€/month)

```
Internet → Ionos DNS → Hetzner CX22 → Gunicorn → Django → PostgreSQL (local)
                                                         → WhiteNoise (static files)
GitHub Actions cron → POST /api/sync-scores/ → Django → PostgreSQL
GitHub Actions push  → SSH → ~/deploy.sh (git pull, migrate, collectstatic, restart gunicorn)
Email: Ionos SMTP (smtp.ionos.fr:587)
SSL: Let's Encrypt (certbot)
```

App directory: `/home/amaury/Ovalpronos/`. Deploy runs on every push to `main`.

---

## 11. Key design decisions

**Why `calculate_points()` is a standalone function, not a model method.**
It can be unit-tested without DB fixtures and is importable by both the sync service and
management commands. Keeping models thin avoids circular imports between `matches` and
`predictions`.

**Why cotes are stored as integers (odds × 10).**
Float arithmetic on odds (e.g. 6.30) introduces rounding errors when multiplied by the
score multipliers (×1, ×2, ×3). Storing as integers (63) keeps all arithmetic exact.
The raw integer is used directly in `calculate_points()` — no division needed.

**Why HTMX returns a full card partial on every save.**
`hx-swap="outerHTML"` replaces the entire match card, including its `hx-post`/`hx-trigger`
attributes. This avoids stale event bindings after a re-render without writing any JS
re-initialisation logic.

**Why `sync_all_competitions()` iterates `settings.RUGBY_COMPETITIONS`, not DB entries.**
New competitions in config are synced and created on first run without any manual DB insert.
An admin does not have to pre-create a Competition row before the first sync.

**Why `UserScore` is V2, not V1.**
On-the-fly aggregation from `Prediction` is fast enough at the current user count. Adding
`UserScore` now would require cache invalidation logic with no measurable benefit. It will
be introduced when ranking queries become slow (thousands of concurrent users/leagues).

**Why `capture()` swallows all exceptions.**
Analytics must never cause a 500. The PostHog SDK makes network calls; any transient failure (DNS, timeout, package not yet installed during a deploy window) would otherwise crash views. The try/except in `capture()` ensures analytics is always best-effort.

**Why PostHog is identified by `user.pk`, not email or username.**
`user.pk` is an opaque integer in PostHog's database — it cannot be reverse-engineered to a real person without access to the Django DB. This avoids sending PII to a third-party service and keeps GDPR compliance structural rather than procedural.

**Why `localStorage` persistence instead of cookies.**
The ePrivacy Directive's cookie consent requirement does not apply to `localStorage` when no PII is stored. This eliminates the need for a cookie consent banner while keeping GDPR compliance.

**Why `League.is_active` is a computed property.**
A league's activity is derived from its linked competitions — having a separate boolean field
would require synchronising it every time a competition is deactivated, creating a second
source of truth. The property delegates to `competitions.filter(is_active=True).exists()`.
