# ARCHITECTURE.md

Technical reference for Oval'Pronos. Read this before implementing new features.

---

## 1. Project Layout

```
ovalpronos/              # Django project config
  settings.py
  urls.py                # Root URL conf — all paths in English

apps/
  accounts/              # CustomUser, auth views, profile
  matches/               # Competition, Team, Match, sync service, admin views
  predictions/           # Prediction model, HTMX submission view (rename from pronostics)
  rankings/              # UserScore cache, ranking views
  leagues/               # League model, join flow (V2)

templates/
  base.html
  accounts/
  matches/
  predictions/
  rankings/
  partials/              # HTMX swap targets (match cards, etc.)

static/
  css/main.css           # CSS variables, global styles
  js/
  img/teams/             # <slug>.svg — one file per team

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
| `is_active` | BooleanField | current season flag |
| `scoring_system` | CharField | 'COTES' or 'FIXED' |
| `good_gap_pts` | IntegerField | max gap diff for ×2 tier (default 3) |

One competition per code can be `is_active=True` at a time. Rankings filter on this flag.

### `matches.Team`

| Field | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | unique api-sports.io ID |
| `name` | CharField | "Stade Toulousain" |
| `short_name` | CharField | "STA" |
| `slug` | SlugField | "stade-toulousain" — key for local SVG |
| `country` | CharField | used for national teams |

Logo resolution: `static/img/teams/<slug>.svg`. No external logo URLs.

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
| `cote_draw` | IntegerField | null until entered in admin |
| `cote_away` | IntegerField | null until entered in admin |

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

### `leagues.League` (V2)

| Field | Type | Notes |
|---|---|---|
| `name` | CharField | |
| `code` | CharField(5) | auto-generated alphanumeric, unique |
| `creator` | FK → CustomUser | null=True (creator may delete account) |
| `members` | M2M → CustomUser | active members |
| `competition` | FK → Competition | null = all active competitions |
| `is_active` | BooleanField | soft-delete |
| `created_at` | DateTimeField | |

### `rankings.UserScore` (V2)

Denormalized cache — one row per (user, scope, season). Updated after each `calculate_points()` call.

| Field | Type | Notes |
|---|---|---|
| `user` | FK → CustomUser | |
| `competition` | FK → Competition | null = global scope |
| `league` | FK → League | null = global or per-competition |
| `season` | CharField | "2024-2025" |
| `count_exact` | IntegerField | |
| `count_gap` | IntegerField | |
| `count_win` | IntegerField | |
| `count_cancelled` | IntegerField | |
| `count_prediction` | IntegerField | total predictions submitted |
| `points` | IntegerField | |
| `rank` | IntegerField | recalculated after each match batch |

Three uniqueness constraints using `UniqueConstraint` with partial index conditions (PostgreSQL-native). Standard `unique_together` cannot handle nullable FK fields correctly. See CONVENTIONS.md for the pattern.

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
  → for each active Competition:
      sync_competition_matches(competition.code)

sync_competition_matches(code)
  → GET v1.rugby.api-sports.io/games?league=<id>&season=<season>
  → for each game: update_or_create Match, Team (within transaction.atomic)
  → if match just reached FINISHED:
      _calculate_points_for_match(match)

_calculate_points_for_match(match)
  → Prediction.objects.filter(match=match, points_earned__isnull=True)
  → for each prediction:
      points, result_type = calculate_points(prediction, match)
      prediction.points_earned = points
      prediction.result_type = result_type
      prediction.save(update_fields=['points_earned', 'result_type'])
      update_user_score_cache(prediction.user, match)   # V2
```

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

## 6. UserScore Cache Pattern (V2)

`UserScore` is a write-through cache — rankings always read from `UserScore`, never from raw `Prediction` aggregates.

Update strategy after `calculate_points()` for a match: call `refresh_user_scores_for_match(match)` which:
1. Fetches all users who predicted that match
2. For each user, recalculates their global `UserScore`, per-competition `UserScore`, and any league `UserScore`
3. Recalculates `rank` for all affected scopes using a batch ranking query (window function or ordered annotation)

`rank` is recomputed as a batch after all predictions for a match are scored, not per-prediction.

In V1, rankings are computed on the fly (direct `Prediction` aggregation). `UserScore` is introduced in V2 as a performance optimization.

---

## 7. Rankings Proximity Display

For the global ranking view:

```
1. Fetch top 3 rows from UserScore (global, current season), ORDER BY points DESC
2. Fetch current user's UserScore → get their rank R
3. If R > 3:
   Render: [top 3] ... [R-3, R-2, R-1, R (highlighted), R+1, R+2, R+3]
4. If R <= 3:
   Render continuous top 10 with user highlighted
```

Columns: Rank | Display Name | Points | Predictions | Exact | GAP | WIN

---

## 8. League Invite Flow

```
/leagues/join/<code>/ (GET, unauthenticated)
  → LoginRequired redirects to /accounts/login/?next=/leagues/join/<code>/
  → After login, Django follows the ?next= parameter automatically (built into LoginView)

/leagues/join/<code>/ (GET, authenticated)
  → Look up League by code; 404 if not found or is_active=False
  → Add request.user to league.members (idempotent)
  → Redirect to /accounts/profile/ with success message
```

The `next` parameter is handled natively by Django's `LoginView` — no custom logic needed.

---

## 9. Admin Custom Views

Custom admin pages (non-standard ModelAdmin) use `staff_member_required` decorator and live in `apps/matches/admin_views.py`. URLs are registered in `ovalpronos/urls.py` under the `admin/` prefix.

```
/admin/matches/competition/<id>/import/
  GET  → render import form (templates/admin/matches/import.html)
  POST → call sync_competition_matches(competition.code)
       → Django messages with result counts
       → redirect to competition change page
```

---

## 10. Deployment Architecture

### Phase 1 — Beta (0€/month)

```
Internet → Render free tier → Gunicorn → Django → Neon PostgreSQL (serverless, 3GB)
                                                 → WhiteNoise (static files)
GitHub Actions cron → POST /api/sync-scores/ → Django → Neon
Email: Ionos SMTP (smtp.ionos.fr:587)
DNS: Ionos
```

Cold start: ~30s after 15min inactivity (acceptable for beta).

### Phase 2 — Production (~4€/month)

```
Internet → Ionos DNS → Hetzner CX22 → Nginx → Gunicorn → Django → PostgreSQL (local)
                                                                  → WhiteNoise (static files)
GitHub Actions cron → POST /api/sync-scores/ → Django → PostgreSQL
SSL: Let's Encrypt (certbot auto-renew)
Email: Ionos SMTP (unchanged)
```

Migration: `pg_dump` Neon → import to Hetzner → update DNS A record → update `DATABASE_URL` env var. Code does not change.
