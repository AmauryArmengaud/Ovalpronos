# REDESIGN.md — L'Ovale design system

Reference for all future sessions working on the UI. Read this before touching any template, CSS, or JS.

---

## 1. Direction: L'Ovale

**Concept:** The rugby ball's oval shape governs every curve — pill buttons, pill chips, circular logo
fallbacks, progress bar. No sharp rectangles anywhere in the UI chrome.

**Palette:** Deep navy primary (#2B3467) on warm cream background (#FCFFF9). Accent red (#EB455F) for
live states and CTAs only. Brand green (#1a7f37) for positive feedback (saved state).

**What was decided:**

| Decision | Rationale |
|---|---|
| Pill border-radius on all `.btn-*` | Oval motif — no rectangular buttons |
| Cards: no border, no shadow, tinted surface (`rgba primary 0.06`) | Tone steps replace elevation — cleaner on cream |
| Body font-size 17px (1.0625rem) | Barlow reads better slightly larger; matches sports app convention |
| Logo fallback: circle, `rgba primary 0.15` bg, bold initials | Visible against card (surface-raised is 0.06 — invisible) |
| `.match-score-input`: no border, tinted surface, tabular-nums | Score inputs read as content, not form controls |
| Score input focus: `rgba primary 0.12` bg + 2px outline | Clear keyboard target without Bootstrap's blue ring |

**What was explicitly rejected — do not reintroduce:**

| Rejected | Reason |
|---|---|
| `btn-accent` on navbar logout | Accent red is for positive CTAs (login, sign-up); logout is destructive → discrete link style (`btn-nav-link`) |
| Two different font-sizes for live vs finished score | Same score, different size → layout inconsistency; unified to `1.5rem` via single `.match-score` class |
| `clip-path` on team logo images | PNG logos are cutout (transparent BG); clip-path bleeds fallback circle through transparency |
| Overlay approach for logo fallback (fallback always visible behind img) | Same issue — transparent PNG reveals the circle beneath |
| Dark background on score inputs | Feels like a separate widget; tinted surface integrates with card tone |
| `hx-trigger="blur from:[name=score_a]"` | (a) editing only home score, never touching away = save never fires = data loss; (b) HTMX `from:` resolves document-wide, not per-form — all cards fire on any `[name=score_a]` blur |
| Ellipsis truncation on `.match-team-name` | Content should never be silently hidden; use `min-height` to reserve space instead |
| JS-only saved feedback (animation only) | Animation may not fire if input is auto-advanced; persistent server-rendered state is the ground truth |
| Zone D footer | Round + time moved to Zone A; competition shown in comp-divider-chip above the card |

---

## 2. Numerical decisions

### CSS variables added to `:root` in `main.css`

| Variable | Value | Purpose |
|---|---|---|
| `--color-you-highlight` | `rgba(43,52,103,0.12)` | Rankings "You" row highlight |
| `--color-logo-fallback-bg` | `rgba(43,52,103,0.15)` | Logo initials fallback circle background |
| `--color-logo-bg` | `rgba(43,52,103,0.08)` | Neutral circle behind every team logo — pale logos visible, shapes harmonised |
| `--color-badge-exact-text` | `#5c4500` | Dark amber text on gold banner — 5.7:1 on `#F5C542` |
| `--color-badge-win-text` | `#235408` | Dark green text on lime banner — 5.8:1 on `#A8E063` |
| `--color-badge-win-light` | `rgba(168,224,99,0.25)` | Light lime tint for WIN result banner background |
| `--color-badge-gap-light` | `rgba(139,53,168,0.35)` | Medium purple tint for GAP result banner background |

All 7 variables above are also present in `admin.css` (standalone — see §3).

### CSS variables modified in `:root`

| Variable | Old value | New value | Reason |
|---|---|---|---|
| `--color-text-secondary` | `rgba(43,52,103,0.55)` (~3.2:1) | `rgba(43,52,103,0.75)` (~5.4:1) | WCAG AA on cream background |

### Typography scale

| Token | Value | Used for |
|---|---|---|
| `--text-sm` | `0.875rem` (14px) | Secondary labels, odds values |
| `--text-xs` | `0.75rem` (12px) | Card footer, badges, saved state |
| `--text-2xs` | `0.65rem` (~10.4px) | Closes-soon, microcopy, locked badge |
| Body | `1.0625rem` (17px) | Base — overrides Bootstrap default |

### Match card sizing

| Element | Desktop (≥576px) | Mobile XS (<576px) |
|---|---|---|
| `.match-team-logo-wrap` | 72×72px circle | 60×60px circle |
| `.match-team-logo` | 56×56px inside wrap | 52×52px inside wrap |
| `.match-team-logo-fallback` | 100%/100% of wrap, 0.875rem | 100%/100% of wrap, 0.75rem |
| `.match-score-input` width | 52px | 44px |
| `.match-score-input` font-size | 1.5rem | 1.5rem |
| `.match-team-col` width | 38% | 35% |
| `.match-center-col` width | 24% | 30% (wider to fit inputs) |
| `.match-team-name` min-height | none | 2.6rem (reserves 2 lines at 15px×1.5) |
| `.match-card-body` padding | 0.75rem | 0.625rem (uniform) |
| `.match-zone-a` min-height | 44px (flex-column, gap 2px) | 44px |
| `.match-center-content` min-height | 44px | 44px |
| `.match-zone-c` min-height | 56px (align-items: flex-start) | 56px |

**Desktop layout:** At `lg` (≥992px) the predictions page uses a 2-column CSS grid
(`.predictions-grid`). Day-dividers span both columns (`grid-column: 1 / -1`, left-aligned, no
uppercase). Comp-divider-chips also span both columns for the row break but keep their natural
pill width via `width: fit-content`. The whole page content is wrapped in `.predictions-page-wrap`
(max-width: 1140px, auto-centred). DOM order matches reading order (left-to-right, top-to-bottom),
so keyboard navigation is correct without JS changes.

Day separator date format: `date:"D j M"` — uses locale-aware abbreviated day and month names
(e.g. "dim. 6 sept." in French, "Sun 6 Sep" in English). Never hardcoded slashes or fixed locale.

### Saved state

- **On inputs:** `.match-score-input--saved` — added server-side when `prediction` exists in the open
  state. Gives a subtle green tint (`rgba brand-rugby 0.08`) + inset border. A small `ti ti-check` icon
  below the input row (`.match-inputs-saved-mark`) confirms the saved state. 44px min-height maintained.
- **Transient flash in Zone C:** `.match-saved-indicator` — rendered only when `saved=True`; the parent
  `.match-saved-zone` gets `--flash` modifier. The indicator overlays the potential points (`position:
  absolute`) and fades out over 2s (`saved-fade`); potential points reveal with a 0.7s delay
  (`pts-delay-reveal`). Reduced-motion: indicator hidden immediately, points visible.
- Zone C default (open + prediction): shows potential points only (no persistent icon).

### Progress bar

- **Track:** `.prediction-progress-track` — pill, 8px tall, `rgba primary 0.10` background.
- **Fill:** `.prediction-progress-bar` — primary color (`--color-primary`) while in progress.
- **Complete state:** `.prediction-progress-bar--complete` — switches fill to `--color-brand-rugby` at 100%.
- **Label:** `X/Y pronos` (French) / `X/Y predictions` (English) via `{% blocktrans count %}` — plural based on total `Y`.
- **Server-authoritative:** `SubmitPredictionView` appends an OOB fragment (`hx-swap-oob="true"`) after every save. `_prediction_progress(user)` is the single source of truth — counts `SCHEDULED/POSTPONED` matches with full odds and a future kickoff (`datetime > now`) across active leagues. No JS counting.
- **Denominator scope:** only matches with `datetime > now` are counted — matches past kickoff (even if still SCHEDULED in the DB) are excluded. POSTPONED matches are included only if their stored `datetime` is in the future (i.e., rescheduled); locked-postponed matches are excluded by the same rule.
- **Partial:** `templates/partials/predictions_progress.html` — rendered by both `PredictionsView` (initial page) and `SubmitPredictionView` (OOB update). Pass `oob=True` for the post-save fragment.
- **Touch-device hide:** while a `.match-score-input` is focused, body gets `.score-input-active`. `@media (hover: none)` fades `#predictions-progress` out via `opacity: 0; transform: translateY(-6px); pointer-events: none` — no layout shift. Restored on `focusout` (debounced via `setTimeout(0)` to avoid flicker during auto-advance). Body class is on `<body>` so it survives OOB swaps.

---

## 3. Technical constraints

### Viewport meta

```html
<meta name="viewport" content="width=device-width, initial-scale=1, interactive-widget=resizes-content">
```

`interactive-widget=resizes-content` makes Chrome Android resize the **layout** viewport (not just
the visual viewport) when the soft keyboard opens. This keeps `position: sticky` working correctly
without JS. iOS Safari ignores this hint (it uses `resizes-visual` by default) — the opacity/transform
hide on touch devices is the fallback for iOS.

### HTMX contract — do not break

The predictions page swaps the entire `#match-card-{pk}` div on every save:

```html
<form hx-post="{% url 'predictions:submit' match.pk %}"
      hx-trigger="change[this.querySelector('[name=score_h]').value !== '' && this.querySelector('[name=score_a]').value !== '']"
      hx-swap="outerHTML"
      hx-target="#match-card-{{ match.pk }}">
```

Rules:
- Field names are `score_h` / `score_a` (not `home`/`away` — avoids address-autofill heuristics on iOS).
- `hx-trigger` must stay `change[both non-empty]` — never switch to `blur from:`.
- `hx-swap="outerHTML"` replaces the whole card including the `<form>`. The view must return the full
  card partial, not just the form.
- Server-side lock/odds validation on every POST — never rely on client-side gate only.
- Input IDs must stay stable: `id="score-h-{pk}"` and `id="score-a-{pk}"`. These IDs are used by
  `htmx:afterSwap` to restore keyboard focus.

### Server-driven saved feedback

The `saved=True` context flag is set by the predictions view only on a successful POST response.
The transient "Saved" indicator is a server-rendered span — it exists in the DOM only on the swap
response. It fades via pure CSS animation; no JS reads or writes this state.

Consequence: if you add a separate partial response path (e.g., a 204 path), you must ensure `saved`
is passed correctly or the indicator will never appear.

### Focus restoration after outerHTML swap

`hx-swap="outerHTML"` destroys the focused `<input>` — focus falls to `<body>`. The restoration
mechanism in `templates/predictions/index.html`:

```javascript
var pendingFocusId = null;
document.addEventListener('focusin', function(e) {
  if (e.target.classList.contains('match-score-input') && e.target.id) {
    pendingFocusId = e.target.id;
  }
});
document.body.addEventListener('htmx:afterSwap', function(e) {
  if (!e.target.id || !e.target.id.startsWith('match-card-')) return;
  // restore focus
  if (pendingFocusId && (document.activeElement === document.body || ...)) {
    var el = document.getElementById(pendingFocusId);
    if (el) el.focus();
  }
  pendingFocusId = null;
});
```

**Select-all on focus:** score inputs use a `focusin` handler that calls `input.select()` — tapping
an existing score selects the whole value so typing replaces it immediately. This handler runs on the
original `focusin` event, before any swap.

**`pendingFocusId = null` before `blur()`:** When the last `away` input triggers a save via `blur()`,
`pendingFocusId` is cleared first. This prevents the `htmx:afterSwap` handler from re-focusing that
input after the swap, which would reopen the mobile keyboard unnecessarily.

**Select-all excluded from focus restoration:** The `htmx:afterSwap` restoration calls `el.focus()`
only — it does NOT call `el.select()`. Programmatic `select()` after a swap would fight with the
user's cursor intent when navigating between predictions.

**iOS Safari limitation:** Programmatic `focus()` after an async request does not reopen the
keyboard on iOS Safari. The above is best-effort for updating an existing prediction; the keyboard
stays open if the user is already typing (first prediction entry typically works).

**Plan B (decided: not needed):** iOS keyboard was tested and remains open across card swaps when
updating an existing prediction. The current `htmx:afterSwap` focus restoration is sufficient.

**Appendix — Plan B morph (retain for reference):** Idiomorph morph swap — `hx-swap="morph:outerHTML"` +
`htmx-ext-morph.js` (~2KB). Diffs the new HTML against the existing DOM and patches in place; the
focused `<input>` is never destroyed, so focus is naturally preserved without any JS restoration.
To implement if ever needed: add `htmx-ext-morph.js` to `base.html`, add `hx-ext="morph"` to the
form or a parent, change `hx-swap` to `morph:outerHTML`. See `ARCHITECTURE.md §morph-swap`.

### Animation replay

`saved-fade` replays every time the card is swapped. This is correct: each swap is triggered by a
user save. If the animation should NOT replay (e.g., on initial page load), do not include
`saved=True` in the view context on GET — only on POST responses.

The `htmx:afterSwap` progress bar update is server-driven (OOB swap) — no JS counting. Do not
read `.match-potential-points` to update the bar.

### i18n

All new UI strings must go through `{% trans %}` / `_()`. After adding strings:

```bash
python manage.py makemessages -l fr
# edit locale/fr/LC_MESSAGES/django.po — fill msgstr, never mark fuzzy (#, fuzzy)
python manage.py compilemessages
```

**Variable translations — `round_label` filter pattern:**
`makemessages` only extracts *literal* strings. For dynamic values sourced from the API (e.g.,
`match.round`), do NOT use `{% trans variable %}` in templates — the strings won't be extracted and
will be silently dropped as obsolete on the next `makemessages` run.

Instead, declare the known API strings in `apps/matches/templatetags/match_tags.py`:

```python
from django.utils.translation import gettext_lazy as _

ROUND_LABELS = {
    'Final':         _('Final'),        # → "Finale"
    'Semi-finals':   _('Semi-finals'),  # → "Demi-finales"
    # ...
}

@register.filter
def round_label(value):
    return ROUND_LABELS.get(value, value)  # falls back to raw API string
```

`makemessages` extracts `_('Final')` etc. from the Python file; the filter applies the translation at
runtime. Add new entries to `ROUND_LABELS` whenever the API introduces a new round name.

### Email templates — inline hex exception

Email templates (`templates/accounts/emails/`) use inline hex values for palette colors (`#2B3467`,
`#EB455F`, `#FCFFF9`) — approved exception since mail clients do not support CSS variables. Keep the
hex values synchronized with the CSS variables in `main.css`.

### admin.css — standalone, V4 debt

`static/css/admin.css` does NOT `@import main.css`. It duplicates the CSS variable declarations
independently. When you change a variable in `main.css`, you must also update `admin.css` manually.

Changes already synced to `admin.css`:
- `--color-text-secondary`: 0.55 → 0.75
- `--color-badge-exact-text`: added (#5c4500)
- `--color-badge-win-text`: added (#235408)
- `--color-badge-win-light`: added (rgba lime 0.25)
- `--color-badge-gap-light`: added (rgba purple 0.35)
- `--color-logo-bg`: added (rgba 0.08)
- `--color-badge-miss`: added (rgba 0.10) — background-only
- `--color-badge-miss-text`: rgba 0.50 → 0.75 — for text/icons expressing a MISS state — ~5.4:1 on cream (AA)
- `--color-badge-ended-text`: rgba 0.55 → 0.75 — ended league badge text — ~5.4:1 on cream (AA)
- `--color-rank-silver`: rgba 0.45 → 0.65 — rank 2 medal icon — ~4.1:1 on cream (>3:1 icon minimum)

V4 will consolidate these into a shared token file. Until then: both files must stay in sync.

### Static file cache-busting

nginx serves `/static/` directly without `Cache-Control` headers; browsers apply a heuristic cache
of several days. To force cache invalidation after a deploy that modifies CSS or JS, increment
`STATIC_VERSION` in `ovalpronos/settings.py`. The value is injected into all templates via the
`static_version` context processor and appended as a query string on local CSS/JS references
(`?2`, `?3`, etc.). No nginx or deployment changes required.

After each deploy touching static assets, bump `STATIC_VERSION` in `settings.py`.

**Post-merge task:** move to `ManifestStaticFilesStorage` (content-hash filenames) and configure
nginx with a long `Cache-Control: max-age` on `/static/`. This makes cache busting automatic and
removes the need for `STATIC_VERSION`.

---

## 4. Roadmap

### Pronos (DONE)

**Design system** (foundational): CSS variables, pill buttons, Barlow font, cream background, tinted
card surfaces, navbar, footer, segment controls, flash messages, ranking table "You" highlight.

**Match card** (`templates/partials/match_card.html`): 4-zone anatomy (see §6).

- All states covered: open (±prediction, ±closes-soon), no-odds, locked (±live score), in-play,
  finished (EXACT/GAP/WIN/MISS, ±prediction), cancelled.
- 3 constant-height zones (A, B, C) — card height never changes between states.
- Logos: 72×72px wrap / 56px logo desktop; 60×60px wrap / 52px logo XS. `--color-logo-bg` tint behind
  every logo.
- Score inputs: pill-aligned, tabular-nums, no border. Form wraps inputs only; Zone C is outside.
- Zone C result banner: full-width, graded intensity by tier (EXACT full gold / GAP medium purple tint
  / WIN light lime tint / MISS neutral). See result banner contrast table in §6.
- Saved state on inputs: `--saved` tint + small `ti-check` below inputs. "Enregistré" flash in Zone C.
- All icons: Tabler icons (`ti ti-*`).
- Zone A: `HH:mm · Jx` always. Status label on second line when applicable (closes-soon accent red,
  locked grey, live red pulsing, cancelled grey; finished: no second line).
- Round display: numeric → `J{n}` via `{% blocktrans %}`; non-numeric → `|round_label` filter.

**Predictions page chrome** (`templates/predictions/index.html`):

- Chronological list (day → competition → time). Day-divider: locale-aware date, no uppercase.
  Comp-divider-chip: natural pill width, spans both grid columns.
- At lg (≥992px): 2-column CSS grid (`.predictions-grid`), max-width 1140px centred.
- Progress bar: pill-shaped, 8px, primary → green at 100%. Label: `X/Y pronos`. Sticky top.
- Tabs (À venir / En direct / Passés): min-height 44px. Empty-state message + action for each tab.
  Live empty state links to upcoming tab.
- No-odds toggle: solid thin border, min-height 44px, pill shape.
- Matches without odds hidden behind Bootstrap collapse toggle.

### Classement (DONE)

Rankings leaderboard, row anatomy, competition filter chips, sticky "Toi" bar.

**Row anatomy** (`templates/rankings/_table.html`): `<ol>` list, 4 fixed zones per row.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Zone 1 (40px) │ Zone 2 (flex-grow)               │ Zone 3 │ Zone 4  │
│ rank / medal  │ avatar · name · "Toi" badge       │ lg+    │ 80px   │
│               │ [mobile line 2: tier chips ×3]   │ tiers  │ points  │
└──────────────────────────────────────────────────────────────────────┘
```

- **Zone 1 (rank, 40px, fixed):** `ti-crown` gold (rank 1) / `ti-medal` silver (rank 2) / `ti-medal` bronze (rank 3) / numeric in `--text-sm` muted for rank ≥4.
- **Zone 2 (player, flex-grow, `min-width:0`):** Avatar (profile photo if set, else initials circle `--color-logo-fallback-bg`), `display_name` with `text-overflow: ellipsis` + `title` attribute for full name. Mobile second line: `ti-crown N · ti-target N · ti-check N` in `--text-xs` with badge colors — always present for consistent row height.
- **Zone 3 (tier columns, `d-none d-lg-flex`):** Three centred `3rem` columns (EXACT/GAP/WIN), hidden on mobile. `.ranking-tier-col` uses `display:flex; justify-content:center` so header icons and data values share the same visual axis.
- **Zone 4 (points, 80px, right-aligned):** `tabular-nums; font-weight: 700`. Pronos count below in `--text-xs`, desktop only.

**Row rules:**
- `min-height: 56px` — matches Zone C of match cards.
- "You" row: `--color-you-highlight` bg + `3px solid var(--color-primary)` left border.
- `aria-current="true"` on the current user's `<li>` only (conditional on `entry.is_current_user`). `aria-label` (rank / name / pts) is on every `<li>`.
- Use `<ol aria-label="{% trans 'Leaderboard' %}">` — semantically ordered list.

**Shared ranks (sports convention 1,1,3):**
`_assign_ranks(entries)` in `apps/rankings/services.py` — pure function, fully unit-tested (10 tests in `apps/rankings/tests.py`). Two entries are tied when they share the same `total_points`, `count_exact`, and `count_gap`. Called by `_build_leaderboard` (rankings), `LeagueDetailView` (leagues), and `ProfileView` (accounts).

**Sticky "Toi" bar (mobile only):**
- `.ranking-you-sticky` — `position: fixed; bottom: 64px` (above `.mobile-bottom-nav`); `z-index: 1020`.
- Hidden by default (`opacity: 0; pointer-events: none; transform: translateY(6px)`), shown via `.visible` class.
- `IntersectionObserver` on `#current-user-row` toggles `.visible` when the row exits the viewport.
- `display: none !important` at `≥992px` — desktop never shows the bar.

**Header / data column alignment:**
Header row uses the **exact same column classes** as data rows (`ranking-rank`, `ranking-player`, `ranking-tier-cols`, `ranking-tier-col`, `ranking-points`) — single source of truth for widths and alignment. `.ranking-header` overrides only font-size, color, and font-weight for its direct children.

**Competition filter chips:**
`.ranking-comp-chip` / `.ranking-comp-chip--active` — `min-height: 44px` tap target. Inactive matches `.comp-divider-chip` style (light tinted bg, navy border). Active: filled navy (`--color-primary`).

When multiple active competitions share the same name (e.g. two seasons of Top 14), the view computes `comp.chip_label = "{name} {season}"` for duplicates; single-name competitions keep `chip_label = name`. Template renders `{{ comp.chip_label }}` with no condition.

**Django template underscore rule:**
Django blocks attribute access on names starting with `_`. Never set `obj._attr` and reference it in a template — compute a clean name in the view instead.

**Points formatting:** `{{ entry.total_points|intcomma }}` — locale-aware thousands separator via `django.contrib.humanize` (space in French, comma in English).

**New CSS variables** (added to both `main.css` and `admin.css`):
- `--color-rank-silver: rgba(43,52,103,0.65)` — rank 2 medal icon — ~4.1:1 on cream (>3:1 icon minimum)
- `--color-rank-bronze: rgba(184,105,37,0.75)` — rank 3 medal icon

**Tests** (`apps/rankings/tests.py`): 10 unit tests on `_assign_ranks` + 5 `RankingsViewTest` smoke tests covering `/rankings/`, `?comp=`, `?league=`, duplicate-name season disambiguation, and unknown comp pk.

**Seed data** (`seed_ui_states`): Competition switched to COTES scoring (`good_gap_pts=10`). 20 players (demo_main + player1-19). Demo League: 4 members (main rank 1). Demo Liga: all 20 members (global eligibility). demo_main ~rank 15 globally, rank 1 in Demo League. True ties: P8=P9 (rank 1), P2=P6 (rank 17), P3=P7 (rank 19, P7 = long name + 0 pts). Max score ~2103 pts (4 digits).

### Ligues (DONE)

League list, create, join, and detail pages.

**New CSS variables** (added to both `main.css` and `admin.css`):
- `--color-badge-ended-bg: rgba(43,52,103,0.08)` — ended league badge background
- `--color-badge-ended-text: rgba(43,52,103,0.75)` — ended league badge text — ~5.4:1 on cream (AA); distinct from `--color-badge-miss` which means "wrong prediction"

**League card anatomy** (`templates/leagues/list.html`): single-column stacking list, same rhythm as ranking rows.

```
┌───────────────────────────────────────────────────────────┐
│ Zone A  League name ·····················  [Ended badge?] │
├───────────────────────────────────────────────────────────┤
│ Zone B  [chip Comp A] [chip Comp B]                       │
├───────────────────────────────────────────────────────────┤
│ Zone C  N members   ·   CODE  [Copy] [Share]              │
└───────────────────────────────────────────────────────────┘
```

- Card is a full-width link (stretched link pattern) — entire surface navigates to detail.
- Copy/Share buttons sit above the stretched link via `position: relative; z-index: 2` on `.league-card-actions`.
- Zone A: `text-overflow: ellipsis` + `title` attr for long names. Ended badge uses `--color-badge-ended-*`. No `min-height` — natural content height.
- Zone B: `.comp-divider-chip` — same pill as pronos page, single row max.
- Zone C: member count muted, invite code monospace (secondary info), Copy/Share right. No `min-height`.

**League detail anatomy** (`templates/leagues/detail.html`):

```
Page header (flex-wrap, align-items-start):
  Left (flex-wrap, min-w-0): league name (.league-detail-title) [Ended badge?]
  Right (flex-shrink-0):     [Leave btn] [← My leagues]
  → On narrow screens (<320px), buttons wrap to a new line below the title.
────────────────────────────────────────────────────────────
Invite block (.league-invite-block, tinted surface): code [Copy code] [Share ↑]
  └─ share fallback input (readonly, shown when Web Share + clipboard both unavailable)
────────────────────────────────────────────────────────────
Comp chips (.comp-divider-chip)
Leaderboard: {% include "rankings/_table.html" %} — zero duplication
```

`.league-detail-title`: `overflow-wrap: anywhere; word-break: break-word` — long names wrap at any character, never cause horizontal scroll. No `text-truncate`.

**Invite code copy + share:**
- `[Copy code]` (`.copy-code-btn`): copies 5-char code to clipboard. Icon swaps to `ti-check` 1.5s.
- `[Share ↑]` (`.share-link-btn`): tries Web Share API (native share sheet on mobile) → clipboard fallback → read-only input fallback. URL rendered server-side in `data-url`; share text in `data-text` — no JS URL construction.
- Both buttons in a `.league-share-group` wrapper so the JS can find `.share-fallback-input`.
- **HTTPS note:** Web Share API and `navigator.clipboard` require HTTPS (or localhost). Cannot be tested on a phone over local HTTP — use ngrok, Tailscale, or deploy to staging.

**Leaderboard — all members shown:**
`LeagueDetailView` uses `Coalesce(Sum(...), 0)` + `Count(filter=...)` to annotate all members, including those with 0 predictions. A new member is visible immediately. `_assign_ranks()` produces 1,1,3 shared ranks (all-zero members tie at rank 1 in a new league). Imported from `apps/rankings/services.py`.

**`_assign_ranks` moved** to `apps/rankings/services.py` — shared by both `rankings/views.py` and `leagues/views.py`. Tests in `apps/rankings/tests.py` updated to import from services.

**Sticky "Toi" bar JS** extracted to `templates/partials/_ranking_sticky_js.html` — included by both `rankings/index.html` and `leagues/detail.html` via `{% include %}`. The `scrollIntoView` on page load is opt-in: pass `with scroll_on_load=True` to enable it (rankings does; league detail does not — page opens at top, sticky bar handles position awareness).

**Forms:**
- `create.html`: no crispy_forms. Name field uses `.form-control-44` (min-height 44px). Competitions rendered as `.league-comp-checkbox` pill labels (`CheckboxSelectMultiple` iterated as `BoundWidget`). `:has(input:checked)` toggles checked state.
- `join.html`: `.form-control-44` on the code input.

**Creator / Leave:**
- Creator: no Leave button.
- Non-creator: `btn-outline-secondary` trigger (discrete) → Bootstrap modal → `btn-danger` confirm. League name truncated to 40 chars in modal.

**Empty / ended states:**
- `_table.html` gains `league_ended` empty_reason case ("This league has ended. Final rankings are frozen.") — no CTA.
- League detail: if `not league.is_active`, an `alert-secondary` notice is shown above the leaderboard.
- Empty state on list page reuses `.ranking-empty` for consistent icon sizing.

**Seed** (`seed_ui_states`): 5 leagues total (+ Demo Liga already existing):
- `Demo League` — demo_main creator, 4 members (existing, rank 1 test)
- `Demo Liga` — demo_main creator, all 20 players (existing)
- `Demo Potes` — demo_player1 creator, demo_main is member → tests Leave button
- `Les Pronostiqueurs du Grand Stade du Midi-Pyrénées` — long name ellipsis/word-break test
- `Demo Saison Passée` — inactive comp, tests Ended badge + inactive notice

**Tests** (`apps/leagues/tests.py`):
- All members shown including 0-pt member
- 0-pt member has total_points=0 and count_predictions=0
- Two 0-pt members share rank 1 (shared-rank convention)
- `member_count` equals actual member count (guards against ORM M2M JOIN-reuse bug where `annotate(Count('members'))` always returned 1)
- `?code=` pre-fills `initial_code` in join view
- Unauthenticated GET `/leagues/join/?code=X` redirects preserving `?code=` in `?next=`

### Home (DONE)

**Route:** `/` — visitors only (authenticated users redirected to `/predictions/`).

**Section anatomy:**

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Hero — full-bleed navy (#2B3467)                              │
│    Title: "Tu sais pas plaquer, viens pronostiquer"              │
│    Sub: one sentence + "Gratuit."                                │
│    CTA primary: [S'inscrire] btn-accent pill 48px               │
│    CTA secondary: "Se connecter" — link style, cream 80% opacity│
│    Mascot: 240×240px, d-none d-lg-block, right column           │
│    Oval motif: 2 CSS-only ellipses (::before / ::after)         │
├──────────────────────────────────────────────────────────────────┤
│ 2. Comment ça marche — cream, container                          │
│    Scoring example: Clermont–Perpignan, odds 6.30 = 63 base pts │
│    4 rows reusing match card Zone C result banner colors         │
│    pts computed by get_example_points() — same source as /rules/ │
├──────────────────────────────────────────────────────────────────┤
│ 3. Compétitions — surface-raised tint                            │
│    Dynamic from Competition.objects.filter(is_active=True)      │
│    .comp-divider-chip pills — no hardcoded names                 │
├──────────────────────────────────────────────────────────────────┤
│ 4. Joue avec tes potes — cream, container                        │
│    Short copy + repeated [S'inscrire] CTA                        │
│    Mascot 100×100px, mobile only (d-lg-none)                    │
└──────────────────────────────────────────────────────────────────┘
```

**Brand expression rules:**
- Hero is always navy (`.home-hero`) — the one place where L'Ovale colours are fully expressed
- Oval motif: `::before` (560×360, top-right, rotate -12°) and `::after` (380×240, bottom-left, rotate 8°), both using `var(--color-hero-motif)` — never hardcoded rgba in rules
- Mascot (`boar-mascot.png`, 340×340 RGBA) appears in hero (desktop only) and social section (mobile only) — convivial, potache, never oversized
- No unverifiable claims ("first app", fake user counts)
- If `competitions` queryset is empty, the section is hidden (`{% if competitions %}`)

**Mobile bottom nav:** hidden on home page via `.home-visitor .mobile-bottom-nav { display: none !important }`. Body gets class `home-visitor` via `{% block body_class %}`. `padding-bottom: 0` restored at `<992px`. CTA visible without scroll at 375×667.

**`{% block main_class %}`** overridden to `p-0` — sections manage their own `.container`. Base default stays `container my-4`.

**New CSS variable:**
- `--color-hero-motif: rgba(252, 255, 249, 0.07)` — cream at 7% opacity for oval motif on navy

**Open Graph** (via `{% block og_title %}` etc. in base.html):
- Default title: "Oval'Pronos — Rugby predictions with friends" (i18n)
- Default description: scoring + competitions (i18n)
- Default image: `static/img/og-img.png` (1200×630, logo blanc + tagline on navy). `og:image:width=1200`, `og:image:height=630`, `og:image:alt` mirrors the page title.
- All four OG image meta tags use the `{% block og_image_path/width/height/alt %}` block system — overridable per page.

**`SECURE_PROXY_SSL_HEADER`** added to `settings.py` so `request.scheme` returns `https` behind Gunicorn in production (correct OG image URLs).

**New CSS classes:** `.home-hero`, `.home-hero__inner`, `.home-hero__content`, `.home-hero__title`, `.home-hero__sub`, `.home-hero__ctas`, `.home-hero__cta-primary`, `.home-hero__cta-secondary`, `.home-hero__mascot`, `.home-section__title`, `.home-section__sub`, `.home-example-rows`, `.home-example-row`, `.home-example-row--exact/gap/win/miss`, `.home-comps-section`, `.home-comps-label`, `.home-social-row`, `.home-social-content`, `.home-social-mascot`, `.home-visitor`.

**Tests:** `/` returns 200 for anon, redirects to `/predictions/` for logged-in users (covered by `apps.matches.tests`).

---

### Landing compétition (DONE)

**Route:** `/competitions/<code>/`, campaign entry point (WhatsApp ≈ 90 % mobile, LinkedIn). Reuses the home hero
with `.landing-hero` (compact padding on phones) and `body.landing-page`.

- Hero, in this order: competition name (h1), one-sentence promise, `Faire mes pronos` CTA, `Déjà inscrit ? Se connecter`,
  deadline line computed server-side from the next match, social proof only from 20 players (`SOCIAL_PROOF_MIN_PLAYERS`).
  Measured at 375×667: CTA top at 274 px (was 602 px).
- The consent banner renders after the hero on this page (`{% block consent_banner %}` in `base.html`); above it,
  it pushed the CTA below the fold.
- Landing CTAs are 1.2rem / 700: cream on accent is 3.75:1, which only passes AA as large text. Points pills use
  primary, not accent, for the same reason.
- Sticky CTA under 992 px, revealed by an IntersectionObserver once the hero buttons leave the screen; no JS = never shown.
- FAQ in `<details>`, no JS. JSON-LD `SportsEvent` for the next matches, `<` escaped.
- Share previews: `Competition.og_image` (1200×630, optional, falls back to `img/og-img.png`); `og:url` and
  `rel=canonical` drop the query string so campaign links stay one page; `og:locale`, `twitter:card`.
- Referral loop: the response to a player's very first prediction adds `partials/share_invite.html` (OOB into
  `#share-invite`): WhatsApp link + Web Share button pointing at the landing with `utm_source=referral`,
  `utm_campaign=<code>`, `utm_content=<referral_code(user)>` (12-char HMAC of the user id, not reversible).

### Page d'invitation publique (DONE)

**Route:** `/leagues/invite/<code>/` — GET is public (no login required).

**Flow:**
```
Visitor GET → show invite page (league name, signup/login CTAs)
  ↓ clicks "Créer mon compte"
  → /accounts/register/?next=/leagues/invite/<code>/
  ↓ after registration, Django redirects to ?next
  → GET /leagues/invite/<code>/ (authenticated)
  → auto-join + redirect to /leagues/<pk>/

Visitor GET → "J'ai déjà un compte"
  → /accounts/login/?next=/leagues/invite/<code>/
  → same auto-join path
```

- Invalid code: renders error state (HTTP 200) + link to home. No 404.
- Authenticated non-member: added to `league.members` + redirect to detail.
- Authenticated already-member: renders invite page with `already_member=True` context — shows "You're already in {name}" with a link to the league (no silent redirect, no duplicate).
- Analytics: `league_joined` event captured with `via: 'invite_link'`.

**OG overrides:**
- `og:title`: "Rejoins {nom} sur Oval'Pronos" (`{% blocktrans %}` with league name)
- `og:description`: "Prédis des scores de rugby, affronte tes potes. Gratuit." (FR) / "Predict rugby scores, beat your friends. Free." (EN)

**Body class:** `home-visitor` — bottom nav hidden (same as home page).

**Share URL:** `LeagueListView` and `LeagueDetailView` now build absolute URLs pointing to `/leagues/invite/<code>/` (not `/leagues/join/?code=`). The existing `join.html` remains for manual code entry by authenticated users.

**New CSS classes:** `.invite-hero`, `.invite-hero__inner`, `.invite-hero__title`, `.invite-league-name` (full cream `--color-text-on-primary`, not gold — stands out vs 80%-opacity sub text), `.invite-hero__sub`, `.invite-hero__ctas`, `.invite-hero__cta-primary/secondary`, `.invite-page`.

**Hero — no mascot:** the invite hero omits the boar mascot image. Hero content only; no right-column image.

**Registration → auto-join fix (`RegisterView`):**
- After successful registration, user is auto-logged-in (`login(request, self.object)`).
- `?next=` is read from `POST['next']` then `GET['next']`, validated with `url_has_allowed_host_and_scheme`, and followed on success.
- `next_url` is passed to context so the template can render a hidden `<input name="next">` inside the form — survives Turnstile failures and field errors.
- Fallback `success_url` is `predictions:index` (was `accounts:login`).
- "Log in" link in `register.html` carries `?next={{ next_url }}`.

**Tests** (`apps/leagues/tests.py`, class `LeaguePublicInviteViewTest`, 7 cases):
- Unauthenticated GET → 200 + league in context
- Invalid code → 200 + `invalid=True` in context
- Authenticated non-member → auto-joined + redirect to detail
- Authenticated already-member → 200 + `already_member=True` in context (no redirect, no duplicate)
- Post-register flow (simulated) → auto-joined ✓
- Post-login flow (simulated) → auto-joined ✓
- `already_member` in `LeaguePublicInviteViewTest.test_already_member_sees_message` ✓

**Tests** (`apps/accounts/tests.py`, 4 cases):
- Register → auto-logged-in + redirected to predictions
- Register with `?next=` → redirected to next URL
- Register CAPTCHA failure → form re-renders, `next_url` in context
- Register with `?next=` invite URL → after auto-login, GET invite URL auto-joins league

### Comptes (DONE)

Register, login, profile, and password reset pages.

**Navy background rule:**

**Navy is reserved for `.home-hero` and the public invite page only.** Auth forms (login, register,
password reset) use the default cream container — no banner, no logo repeat. The navbar already
carries the brand; adding a second navy strip duplicates the logo and pushes the form below the
fold on mobile.

**Auth page layout:**

- Standard `container my-4` (default `{% block main_class %}`).
- Centred column: `col-12 col-sm-10 col-md-6/7 col-lg-5/6` depending on form width.
- `h1` title at top of content (same style as Pronos and Rankings pages).
- **Invitation context** (when `next=` points to a league invite): `.auth-invite-context` chip
  below the `h1` — tinted surface (`--color-surface-raised`), `ti-users` icon, league name.
  Never shows raw URL content — league name is resolved from DB via `_get_invite_league()`.

**`_get_invite_league(next_url, request_host)`** in `views.py`:
1. Returns `None` if `next_url` is empty.
2. Validates with `url_has_allowed_host_and_scheme` — prevents open redirect exploitation.
3. Calls `resolve(path)` — returns `None` on `Resolver404`.
4. Checks `match.view_name == 'leagues:public_invite'` — no false positives.
5. Queries `League.objects.filter(invite_code=...)` — returns `None` for unknown codes.

Called from both `LoginView.get_context_data` (reads `GET['next']`) and
`RegisterView.get_context_data` (reads `POST['next']` or `GET['next']`).

**Form layout decisions:**

- No card wrapper — form sits directly in the centred column.
- All inputs use `.form-control-44` (min-height 44px) for 44px tap targets.
- Primary CTA: `btn btn-accent btn-lg` (red pill) — not `btn-primary` (navy).
- `autocomplete` attributes set on all fields for password managers.
- Register form: `first_name` + `last_name` side-by-side on `sm+` (`col-12 col-sm-6`).
- Hidden `<input name="next">` in register form preserves `next_url` through Turnstile failures and validation errors.
- Login form: no hidden `next` input — Django's `LoginView` reads `?next=` from the query string directly (the form POSTs to the current URL which already contains `?next=`).

**Profile page — section anatomy:**

Four `.profile-section` blocks, separated by `margin-top: 2rem` via the CSS `+` sibling selector
(no border — removed in mobile pass to reduce visual noise):

1. **Identity** — `.profile-identity` (avatar + name block, flex row), edit button top-right.
   Avatar: `.profile-avatar` if set, else `.profile-avatar-initials` (circle, initials, fallback
   bg `--color-logo-fallback-bg`). 80px mobile / 96px `sm+`. Below avatar: display_name as `h1`,
   `@username` shown only when `bool(display_name) and display_name != username` — hidden if no
   display_name set or if it matches the username exactly. Favorite team logo + name below.
   **Username origin:** username is user-chosen at registration (explicit form field), never derived
   from email — safe to display. The `show_username` guard still applies so it only shows when the
   user has set a distinct display_name.

2. **Stats** — hidden entirely when zero scored predictions (shows CTA to predictions instead).
   Primary stat row: `profile-stat-primary` (2rem, tabular-nums) for points (`|intcomma`) and rank
   (`{{ rank|ordinal_local }}` — "1er" / "2e" fr, "1st" / "2nd" en) + `{% blocktrans with
   total=total_ranked %}out of {{ total }}{% endblocktrans %}` → "16e sur 21". Rank computed via
   `_assign_ranks()` from `apps/rankings/services.py` — same 1,1,3 convention as rankings page.
   Hidden if no ranked entry (no scored predictions).
   Secondary tier row: `.profile-tier-row` with four `.profile-tier-item` items (column layout —
   value on top, label below) reusing `.match-badge-label-exact/gap/win/miss` classes. Each item
   has `.profile-tier-item__value` (icon + count) and `.profile-tier-item__label` (text label).
   Icon discipline: `ti-crown` EXACT / `ti-target` GAP / `ti-check` WIN / `ti-x` MISS.

3. **Leagues** — uses `{% include "partials/league_card.html" %}` — no duplication vs. the leagues
   list page. `ProfileView` annotates each league with `member_count` and `join_url` (absolute URL
   to `/leagues/invite/<code>/`) before passing to context.
   Create / Join CTAs at the bottom of the section: `btn-outline-secondary` (discrete) — not accent
   red, which is reserved for auth CTAs and positive primary actions.

4. **Settings** — language toggle (mobile only, `d-lg-none`) + logout button.
   Logout uses `.btn-nav-link` (discrete link style) — not `btn-outline-secondary`. Matches the
   design decision documented in §1 ("btn-accent on navbar logout" rejected).

**Mobile bottom nav color:**
`.mobile-bottom-nav` uses `background: var(--color-primary)` (navy). Was previously
`var(--color-accent)` (red); changed during the profile pass — accent red is reserved for CTAs only.
Inactive icon opacity `0.60` (cream at 60% = ~5.1:1 contrast on `--text-2xs`).

**League card partial (`templates/partials/league_card.html`):**

Extracted from `leagues/list.html` into a shared partial. Both `leagues/list.html` and
`accounts/profile.html` use `{% include "partials/league_card.html" %}`. The partial requires the
`league` variable to have `league.member_count` and `league.join_url` set (computed in the view,
not via ORM `.count()` in the template). Existing CSS (`.league-card`, `.league-card-zone-*`,
`.league-card-actions`, `.badge-ended`, etc.) is unchanged.

**Password reset flow:**

All four password reset templates (`password_reset.html`, `password_reset_done.html`,
`password_reset_confirm.html`, `password_reset_complete.html`) use the same standard cream container
layout as login/register (no banner, no `.auth-header`/`.auth-body`). `btn-accent` on all CTAs.
`password_reset_done.html` and `password_reset_complete.html` use centered icon + copy layout (no form).

**Email template (`templates/accounts/emails/password_reset_email.html`):**

Converted from hardcoded French to `{% trans %}` / `{% blocktrans %}` for i18n. CTA button
`border-radius` updated from `6px` to `99px` (pill — aligns with L'Ovale motif). Inline hex
values kept (approved exception — see §3 Email templates).

**New templatetag (`apps/accounts/templatetags/account_tags.py`):**
`ordinal_local` filter — locale-aware ordinal suffix. "1er"/"2e" (fr), "1st"/"2nd" (en).
`{% load account_tags %}` required in any template using it.

**New CSS classes (added to `main.css`):**
`.auth-invite-context`, `.profile-identity`, `.profile-avatar`, `.profile-avatar-initials`,
`.profile-stat-primary`, `.profile-stat-label`, `.profile-tier-row`, `.profile-tier-item`,
`.profile-tier-item__value`, `.profile-tier-item__label`, `.profile-section + .profile-section`.

**Seed (`seed_ui_states`):** Three profile states covered:
- `demo_main` — predictions + leagues + generated navy avatar (80×80 PNG, Pillow)
- `demo_no_pronos` — no predictions, no leagues (empty stats + empty leagues sections)
- `demo_no_league` — scored predictions (EXACT M-7 + WIN M-11), not in any league

**Tests (`apps/accounts/tests.py`):**
- `RegisterAutoLoginTest` (3 cases) — pre-existing
- `RegisterThenJoinLeagueTest` (1 case) — pre-existing
- `RegisterNextValidationTest` (1 case) — validation error preserves `next_url` in context; then valid re-submit redirects correctly
- `RegisterInviteLeagueContextTest` (3 cases) — `invite_league` in context for valid invite `next`; `None` for non-invite next; `None` for unknown code

### Règles (fait)

Four tier rows (EXACT / GAP / WIN / MISS) reusing `.home-example-rows` / `.home-example-row--{tier}`
CSS — same colours and icons as match result banners. Exact: gold / `ti-crown`. Gap: purple tint /
`ti-target`. Win: lime tint / `ti-check`. Miss: neutral / `ti-x`.

- Odds explanation: bookmakers × 10 → base pts (e.g. 6.30 → 63); multiplier per tier; formula spelled out (63 × 3 = 189)
- Bon écart: |pred_gap − real_gap| ≤ threshold, with the 15–22 / 17–22 example
- Threshold: live from DB (`good_gap_pts`); single value or per-competition list if they differ
- Example pts: computed by `get_example_points()` in `apps/predictions/services.py` — used by both
  home page and rules page, tested in `ExamplePointsTest` + `RulesViewExampleTest` + `HomeViewExampleTest`
- Edge cases covered: draw (3 sub-cases), cancelled, kickoff lock, no-odds, FIXED mode (conditional)
- FIXED mode points computed via `calculate_points()` with `scoring_system='FIXED'`
- OG tags: `og_title` / `og_description` blocks overridden
- All text via `{% trans %}` / `{% blocktrans %}`; new FR translations added to `django.po`

### Micro-interactions (DONE)

Shared polish pass: hover states, focus rings, transitions, entrance animation.

- **Button press:** all `.btn` get `transform: scale(0.98)` on `:active`. Hover lift
  (`translateY(-1px)`) wrapped in `@media (hover: hover)` — pointer devices only.
- **League cards:** `transform: translateY(-2px)` on hover, wrapped in `@media (hover: hover)`.
- **Copy success:** `.copy-code-btn.copy-success i` scales to 1.2 for 200ms — icon pulse only,
  no bounce.
- **Card entrance:** `@keyframes card-enter` (fade + 6px slide up) on `.page-entering .predictions-grid > *`.
  nth-child stagger: 50ms per card, capped at 8 positions (total animation window < 0.6s). JS adds
  `page-entering` on `DOMContentLoaded`, removes it after 600ms. **Never triggered on HTMX swap.**
- **Reduced motion:** global `*` override (`animation-duration: 0.01ms !important` etc.) inside
  `@media (prefers-reduced-motion: reduce)`. Live dot `@keyframes live-pulse` gets `animation: none`
  with explicit fallback `opacity: 1; transform: scale(1)` so the dot stays visible. The progress bar
  touch-hide transition (`opacity 0.15s ease, transform 0.15s ease`) becomes instant under this override.

### Accessibilité finale (DONE)

Full keyboard navigation audit, ARIA labels, colour-contrast pass.

- **`<html lang>`:** dynamic via `{% get_current_language as CURRENT_LANG %}` — changes with
  language toggle. Never hardcoded `lang="fr"`.
- **Skip link:** `<a href="#main-content" class="skip-link">` in `base.html`, visually hidden until
  focused (`.skip-link` in CSS: `position: absolute; top: -100%; left: 0; ...`).
- **Landmarks:** `<header>` wraps the navbar; `<main id="main-content">` is the content anchor.
- **Predictions tabs:** `<nav aria-label="{% trans 'Match filter' %}">` — nav links, NOT tablist.
  Active tab gets `aria-current="page"`.
- **Progress bar:** `role="progressbar" aria-valuenow aria-valuemin="0" aria-valuemax`. Updated
  server-side via OOB swap on every save — `aria-valuenow` and `aria-valuemax` always reflect the
  authoritative server count.
- **HTMX aria-live:** persistent `<div id="save-announcement" aria-live="polite" aria-atomic="true" class="visually-hidden">` in `base.html` — outside swapped cards. Card partial emits
  `data-saved-msg="{% trans 'Saved' %}"` on success. `htmx:afterSwap` reads the attribute and
  updates the region for 1.5s. Screen readers announce each save without losing focus.

**Inline style rules (enforced by guard tests):**

- No `style=""` in any app template. Approved exception: progress bar fill width (`widthratio`) —
  dynamic value with no static CSS alternative.
- No hardcoded hex colors in app templates. Exceptions: `templates/500.html` (standalone, no
  Django context processor — inline CSS required), `templates/emails/` and
  `templates/accounts/emails/` (mail clients don't support CSS variables).

**Quality guard tests (`apps/matches/tests_quality.py`, 4 tests):**
- `InlineStyleTest.test_no_inline_styles` — fails if `style=""` added outside approved exceptions.
- `HardcodedColorTest.test_no_hex_colors` — fails if hex color added outside excluded dirs.
- `PoFileQualityTest.test_no_fuzzy_app_entries` — fails if `#, fuzzy` in app-level .po entries.
- `PoFileQualityTest.test_no_empty_msgstr_for_app_strings` — fails if untranslated app string.

Run with: `python manage.py test apps.matches.tests_quality`

---

## 5. How to test

### Set up demo data

```bash
python manage.py seed_ui_states --reset   # tear down + recreate all demo states
python manage.py runserver
```

Login: `demo_main` / `demo1234`

To see all result banner types (GAP / WIN / MISS), log in as `demo_player1` / `demo_player2` /
`demo_player3` respectively — they each have a prediction on match -7 (FINISHED).

To see the Live empty state: access `/predictions/?tab=live` on a day with no match in progress
(match -6 is IN_PLAY in demo data, so the Live tab is not empty with the seed).

### State checklist — predictions page (`/predictions/`)

| Match | State | Zone A (line 1 / line 2) | Centre | Zone C |
|---|---|---|---|---|
| -1 | Open, no pred | `HH:mm · J1` / _(none)_ | Inputs empty | Odds bar 3 cols |
| -2 | Open, with pred | `HH:mm · J2` / _(none)_ | Inputs `28–15` (green tint + `ti-check` below) | Potential pts + Ton prono : 28–15 |
| -3 | Closes soon, with pred | `HH:mm · J3` / `ti-clock` Ferme dans Xh | Inputs `22–10` (green tint) | Potential pts + Ton prono : 22–10 |
| -4 | No odds | `HH:mm · J4` / _(none)_ | `—` | "Cotes à venir" |
| -5 | Locked, with pred | `HH:mm · J5` / `ti-lock` Verrouillé | `—` | "Ton prono : 21–17" |
| -6 | In-play | `HH:mm · J6` / `●` En direct | `27–14` | "Ton prono : 30–10" |
| -7 | Finished EXACT | `HH:mm · J7` / _(none)_ | `24–17` | Gold banner `ti-crown +N pts` |
| -8 | Cancelled | `HH:mm · J8` / `ti-x` Annulé | `—` | "Match annulé, 0 pt" |
| -9 | Long name + no logo | `HH:mm · J9` / _(none)_ | Inputs | Odds bar + initials fallback |
| -10 | Open, non-numeric round | `HH:mm · Finale` / _(none)_ | Inputs | Odds bar |

All cards should be the **same height** within the list — this is the primary visual check.

Match -10 also verifies the `round_label` filter: Zone A should show "Finale" (not "Final").

### HTMX save flow

1. On match -1: enter home score, tab/auto-advance to away, enter away score.
2. Verify: card swaps, green tint + `ti-check` appears below inputs, "Enregistré" fades out in Zone C.
3. Update a score on match -2: change home input, tab to away (already filled), verify `change`
   fires, card swaps with updated persistent state.
4. Verify progress bar counter increments and turns green at 100%.

### Mobile (local network)

Access from phone: `http://<your-mac-ip>:8000/predictions/`

Checklist:
- [ ] **All cards the same height** — no card taller than the others
- [x] On desktop (≥992px): 2-column grid, day-dividers and comp-chips span both columns, centred at 1140px
- [x] Zone A shows correct label for each state (closes-soon accent red, locked grey, live red pulsing, cancelled grey, finished empty)
- [x] Logos visible (Toulouse, Racing 92, La Rochelle, Clermont)
- [x] Match -9 shows initials circles (no PNG for those slugs)
- [x] Match -10 Zone A shows "Finale" (not "Final") — `round_label` filter working
- [x] All logos have a subtle circular background tint (`--color-logo-bg`) — visible behind pale logos
- [x] Score inputs fit inside center col without overflow
- [x] Team names wrap to 2 lines, no ellipsis, no height jump
- [x] Match -3 (closes soon + prediction): Zone A shows "Ferme dans Xh", Zone C shows potential pts
- [x] Match -6 (in-play): Zone A shows pulsing dot + "En direct", centre shows "27–14"
- [x] Match -7 (finished): gold result banner with pts fills Zone C
- [x] "Enregistré" appears and fades after save (match -1 or -9)
- [x] Save on match -2: inputs stay pre-filled, Zone C updates, progress bar increments
- [x] Progress bar: primary colour while partial, green when 100%
- [x] Progress bar label: "X/Y pronos" — accurate count
- [x] Tabs: height ≥ 44px, live-dot visible on En direct when match -6 is in play
- [x] Live empty state (access ?tab=live when no live match): message + "Voir les matchs à venir" link
- [x] No-odds toggle: solid border, 44px height — tap target comfortable
- [x] Saved state on match -2: green tint + `ti-check` below inputs visible on page load (server-rendered)
- [ ] **Autofill suppression:** tap a score input — keyboard shows digits only, no password/address/card suggestions above it
- [ ] **Select-all on tap:** tapping an existing score selects the whole value; typing replaces it; auto-advance still works
- [ ] **Progress bar touch hide (Android):** open keyboard → bar fades out; close keyboard → bar reappears; bar shows correct count after OOB swap
- [ ] **Progress bar touch hide (iOS):** same fade; scroll with keyboard open — bar stays hidden, no misposition; auto-advance between inputs no flicker
- [ ] **Last prediction at 100%:** saving the last card → bar reappears green at 100% after keyboard closes
- [x] **Priority — keyboard on iOS:** modify only the home score of match -2 (existing prediction, not the first card). Keyboard must stay open after the card swaps. If it closes, activate Plan B morph.
- [x] **Priority — last card:** enter a prediction on the last visible card (no-odds section expanded if needed). "OK" / done key should save via blur, keyboard closes, card swaps correctly.

### i18n

Switch to French (default) and English: check all new strings translate correctly.
French strings to verify: "Enregistré", "Cotes à venir", "Verrouillé", all match state labels,
progress bar label ("X/Y pronos").

---

## 6. Match card anatomy — fixed zones

**Rule:** One card structure for all tabs and all states. Zone presence and height never change;
only zone content changes. No tab-specific conditions in the card template or the page loop.

```
┌──────────────────────────────────────────────┐
│ Zone A — time · round + opt. status  ~36px   │
├──────────┬───────────────────┬───────────────┤
│          │                   │               │
│  Logo    │  Zone B centre    │  Logo  ~100px │
│  Name    │  (min-height 44px)│  Name         │
│          │                   │               │
├──────────┴───────────────────┴───────────────┤
│ Zone C — player context      min-height 56px │
└──────────────────────────────────────────────┘
```

**Rule for each zone:**
- **Zone A** = `HH:mm · Jx` always (first line, muted). Second line: status label when applicable
  (closes-soon `--color-accent` red, locked grey, live red pulsing, cancelled grey). FINISHED: no
  second line.
- **Zone B centre** = match score: inputs (open), live score (in-play), final score (finished), `—` otherwise.
- **Zone C** = player perspective, always `min-height: 56px; align-items: flex-start`:
  open+prediction uses `.match-result-banner-pending` (transparent, 2-row: potential pts + stored prono)
  to match the height/structure of FINISHED result banners. Other states use placeholder text or odds bar.

**Page loop (all tabs, identical structure):**
```
{% ifchanged date %}  →  day-divider chip
{% ifchanged comp OR date %}  →  comp-divider-chip (resets at each new day)
match card
```

**Icon discipline:** All icons are Tabler icons (`ti ti-*`). Zone A: `ti-clock`, `ti-lock`, `ti-x`. Zone C result tiers: `ti-crown` (EXACT), `ti-target` (GAP), `ti-check` (WIN/saved), `ti-x` (MISS). Potential points: same tier icons.

**Score consistency:** `.match-score` uses a single unified style (`font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums`) for all states (live, finished). Score inputs use the same `font-size: 1.5rem`.

### Zone × State Matrix

| State | Zone A (line 1 / line 2) | Zone B centre | Zone C |
|---|---|---|---|
| Open, no prediction | `21:05 · J7` / _(none)_ | Inputs | Odds bar |
| Open, with prediction | `21:05 · J7` / _(none)_ | Inputs (green tint + `ti-check` below) | Pending banner: `ti-crown`N `ti-target`N `ti-check`N + Ton prono : X–Y |
| Closes soon, no pred | `21:05 · J7` / `ti-clock` Ferme dans Xh | Inputs | Odds bar |
| Closes soon, with pred | `21:05 · J7` / `ti-clock` Ferme dans Xh | Inputs (green tint + `ti-check` below) | Pending banner: potential pts + Ton prono : X–Y |
| No odds | `21:05 · J7` / _(none)_ | `—` | Cotes à venir |
| Locked, with pred | `21:05 · J7` / `ti-lock` Verrouillé | `—` | Ton prono : 21–17 |
| Locked, no pred | `21:05 · J7` / `ti-lock` Verrouillé | `—` | Pas de prono |
| In-play, with pred | `21:05 · J7` / `●` En direct | Live score `27–14` | Ton prono : 30–10 |
| In-play, no pred | `21:05 · J7` / `●` En direct | Live score `27–14` | Pas de prono |
| Finished + EXACT | `21:05 · J7` / _(none)_ | Final `24–17` | Gold banner: `ti-crown +N pts · Score exact` + `Ton prono : X–Y` |
| Finished + GAP | `21:05 · J7` / _(none)_ | Final `24–17` | Purple banner: `ti-target +N pts · Bon écart` + `Ton prono : X–Y` |
| Finished + WIN | `21:05 · J7` / _(none)_ | Final `24–17` | Green banner: `ti-check +N pts · Bon vainqueur` + `Ton prono : X–Y` |
| Finished + MISS | `21:05 · J7` / _(none)_ | Final `24–17` | Neutral banner: `ti-x 0 pt · Raté` + `Ton prono : X–Y` |
| Finished, no pred | `21:05 · J7` / _(none)_ | Final `24–17` | Pas de prono |
| Cancelled | `21:05 · J7` / `ti-x` Annulé | `—` | Match annulé, 0 pt |

### Result banner contrast (Zone C, finished)

Banners are graded by intensity — EXACT is the most salient, MISS the most subdued.

| Tier | Background | Text | Ratio |
|---|---|---|---|
| EXACT | `--color-badge-exact` #F5C542 (full gold) | `--color-badge-exact-text` #5c4500 | 5.7:1 ✓ |
| GAP | `--color-badge-gap-light` rgba(139,53,168,0.35) (medium tint) | `--color-primary` #2B3467 | 7.8:1 ✓ |
| WIN | `--color-badge-win-light` rgba(168,224,99,0.25) (light tint) | `--color-badge-win-text` #235408 | 7.8:1 ✓ |
| MISS | `--color-badge-miss` rgba(43,52,103,0.10) (neutral bg) | `--color-text-secondary` rgba(0.75) | ~5:1 ✓ |

`--color-badge-miss` is a background variable only (neutral tint, 10% primary).
Use `--color-badge-miss-text` for any text or icon expressing a MISS state (rules.html tier rows,
admin badge labels, rankings). Current usages: `templates/matches/rules.html` (MISS tier row via
`.home-example-row--miss`), `static/css/admin.css` (result badge labels).

---

## 11. Email templates

### 11.1 Base template

`templates/emails/base.html` — shared wrapper used by all transactional emails.

- Table-based layout, inline hex colors (CSS variables not supported by mail clients — **approved exception**).
- Max-width 560px, centered via `align="center"`.
- Navy header (#2B3467) with `logo_blanc.png` via absolute `{{ site_url }}` URL. No SVG (Gmail).
- Barlow via Google Fonts `<link>` with Arial fallback on all `font-family` declarations.
- Dark-mode: `<style>` block in `<head>` with `@media (prefers-color-scheme: dark)` + `!important` class overrides. Covers Apple Mail and Outlook Mac; Gmail web ignores `<head>` styles.
- Navy footer (#2B3467), text #b0bdd6 (≥5.5:1 on navy ✓).

### 11.2 Inline hex palette (email-only)

| Role | Hex |
|---|---|
| Page background | `#FCFFF9` |
| Card background | `#ffffff` |
| Header/footer | `#2B3467` |
| Body text | `#444444` |
| Headings | `#2B3467` |
| CTA button | `#EB455F` |
| Footer text | `#b0bdd6` |
| Muted text | `#595c7a` | desaturated navy — 6.5:1 on white (replaces #888888/#666666 which failed 4.5:1) |

Badge solid equivalents (RGBA → computed over white for email clients):

| Tier | Bg | Text | Ratio |
|---|---|---|---|
| EXACT | `#F5C542` | `#5c4500` | 5.7:1 ✓ |
| GAP | `#D6B8E1` | `#6a2585` | 5.3:1 ✓ |
| WIN | `#E9F7D8` | `#235408` | 8.3:1 ✓ |
| MISS | `#EAEBF0` | `#595c7a` | 5.6:1 ✓ |

### 11.3 Email inventory

| Email | Templates | Sent by | Tracking |
|---|---|---|---|
| Password reset | `emails/password_reset.html` + `.txt` + `_subject.txt` | Django `PasswordResetView` via `TrackingFreePasswordResetForm` | clicks + opens **disabled** (Brevo rewrites reset links) |
| Results summary | `emails/results_summary.html` + `.txt` | `tasks.send_results_summary()` | default (Brevo account setting) |
| Deadline reminder | **Brevo template #1 (external)** — no local HTML file | `tasks.send_deadline_reminders()` via `AnymailMessage(template_id=1)` | managed in Brevo template |

**Deadline reminder stays on Brevo template #1.** Migration to a local HTML template is out of scope for this redesign — the Brevo template is the single location for that email's content and tracking config.

### 11.4 Technical constraints

- `PASSWORD_RESET_TIMEOUT = 86400` (24 h). Displayed in the email via `{{ timeout_hours }}` from `extra_email_context`.
- Click/open tracking disabled per-message on password reset via `msg.track_clicks = False` / `msg.track_opens = False` on `EmailMultiAlternatives`. Anymail Brevo backend reads these; console backend ignores them.
- Dev: `EMAIL_BACKEND` defaults to console — never set `BREVO_API_KEY` locally.
- Preview command (DEBUG only): `python manage.py preview_emails` → writes to `/tmp/ovalpronos_emails/`.
- Tests: `apps/accounts/tests_emails.py` — 12 tests, locmem backend, no network calls.
