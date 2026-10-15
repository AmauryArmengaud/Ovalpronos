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
| Emojis in Zone C (👑 🎯 ✓ ✗) | Rendering inconsistent across devices; replaced with Tabler icons (same family as Zone A) |
| `btn-accent` on navbar logout | Accent red is for positive CTAs (login, sign-up); logout is destructive → discrete link style (`btn-nav-link`) |
| Persistent `ti-check` in Zone C (`.match-saved-state`) | On mobile it was indistinguishable from a 4th tier icon; moved to input level (`--saved` tint + `ti-check` below inputs) |
| Two different font-sizes for live vs finished score | Same score, different size → layout inconsistency; unified to `1.5rem` via single `.match-score` class |
| `clip-path` on team logo images | PNG logos are cutout (transparent BG); clip-path bleeds fallback circle through transparency |
| Overlay approach for logo fallback (fallback always visible behind img) | Same issue — transparent PNG reveals the circle beneath |
| Dark background on score inputs | Feels like a separate widget; tinted surface integrates with card tone |
| `hx-trigger="blur from:[name=away]"` | Two problems: (a) editing only home score, never touching away = save never fires = data loss; (b) HTMX `from:` resolves document-wide, not per-form — all cards fire on any `[name=away]` blur |
| Ellipsis truncation on `.match-team-name` | Content should never be silently hidden; use `min-height` to reserve space instead |
| JS-only saved feedback (animation only) | Animation may not fire if input is auto-advanced; persistent server-rendered state is the ground truth |

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

### Typography scale (unchanged since step 1)

| Token | Value | Used for |
|---|---|---|
| `--text-sm` | `0.875rem` (14px) | Secondary labels, odds values |
| `--text-xs` | `0.75rem` (12px) | Card footer, badges, saved state |
| `--text-2xs` | `0.65rem` (~10.4px) | Closes-soon, microcopy, locked badge |
| Body | `1.0625rem` (17px) | Base — overrides Bootstrap default |

### Match card sizing

| Element | Desktop | Mobile XS (<576px) |
|---|---|---|
| `.match-team-logo-wrap` | 64×64px circle | 60×60px circle |
| `.match-team-logo` | 48×48px inside wrap | 52×52px inside wrap |
| `.match-team-logo-fallback` | 100%/100% of wrap, 0.875rem | 100%/100% of wrap, 0.75rem |
| `.match-score-input` width | 52px | 44px |
| `.match-score-input` font-size | 1.5rem | 1.5rem (unified with score display) |
| `.match-team-col` width | 38% | 35% |
| `.match-center-col` width | 24% | 30% (wider to fit inputs) |
| `.match-team-name` min-height | none (no desktop min-height) | 2.6rem (reserves 2 lines at 15px×1.5) |
| `.match-card-body` padding | Bootstrap default | 0.625rem (uniform) |
| `.match-zone-a` min-height | 36px (flex-column, gap 2px) | 36px |
| `.match-center-content` min-height | 44px | 44px |
| `.match-zone-c` min-height | 56px (align-items: flex-start) | 56px |
| `.match-card-body` padding | 0.75rem | 0.625rem (uniform) |

**Desktop max-width:** Match cards are rendered inside `col-12 col-lg-7 col-xl-6` on the predictions
page. This caps card width at ~840px on large screens. No additional `max-width` on the card itself.

### Saved state

- **On inputs:** `.match-score-input--saved` — added server-side when `prediction` exists in the open
  state. Gives a subtle green tint (`rgba brand-rugby 0.08`) + inset border. A small `ti ti-check` icon
  below the input row (`.match-inputs-saved-mark`) confirms the saved state. 44px min-height maintained.
- **Transient flash in Zone C:** `.match-saved-indicator` — rendered only when `saved=True`; the parent
  `.match-saved-zone` gets `--flash` modifier. The indicator overlays the potential points (`position:
  absolute`) and fades out over 2s (`saved-fade`); potential points reveal with a 0.7s delay
  (`pts-delay-reveal`). Reduced-motion: indicator hidden immediately, points visible.
- Zone C default (open + prediction): shows only potential points (no persistent checkmark).

---

## 3. Technical constraints

### HTMX contract — do not break

The predictions page swaps the entire `#match-card-{pk}` div on every save:

```html
<form hx-post="{% url 'predictions:submit' match.pk %}"
      hx-trigger="change[this.querySelector('[name=home]').value !== '' && this.querySelector('[name=away]').value !== '']"
      hx-swap="outerHTML"
      hx-target="#match-card-{{ match.pk }}">
```

Rules:
- `hx-trigger` must stay `change[both non-empty]` — never switch to `blur from:`.
- `hx-swap="outerHTML"` replaces the whole card including the `<form>`. The view must return the full
  card partial, not just the form.
- Server-side lock/odds validation on every POST — never rely on client-side gate only.
- Input IDs must stay stable: `id="home-{pk}"` and `id="away-{pk}"`. These IDs are used by
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

**`pendingFocusId = null` before `blur()`:** When the last `away` input triggers a save via `blur()`,
`pendingFocusId` is cleared first. This prevents the `htmx:afterSwap` handler from re-focusing that
input after the swap, which would reopen the mobile keyboard unnecessarily.

**iOS Safari limitation:** Programmatic `focus()` after an async request does not reopen the
keyboard on iOS Safari. The above is best-effort for updating an existing prediction; the keyboard
stays open if the user is already typing (first prediction entry typically works).

**Plan B (not yet implemented):** Idiomorph morph swap — `hx-swap="morph:outerHTML"` +
`htmx-ext-morph.js` (~2KB). Diffs the new HTML against the existing DOM and patches in place; the
focused `<input>` is never destroyed, so focus is naturally preserved without any JS restoration.
To implement: add `htmx-ext-morph.js` to `base.html`, add `hx-ext="morph"` to the form or a parent,
change `hx-swap` to `morph:outerHTML`. See `ARCHITECTURE.md §morph-swap`.

Activate Plan B if users report keyboard closing on iOS when updating an existing prediction.

### Animation replay

`saved-fade` replays every time the card is swapped. This is correct: each swap is triggered by a
user save. If the animation should NOT replay (e.g., on initial page load), do not include
`saved=True` in the view context on GET — only on POST responses.

The `htmx:afterSwap` progress bar update reads `.match-potential-points` elements to count
predicted matches. This count must stay accurate; do not add that class to non-prediction elements.

### i18n

All new UI strings must go through `{% trans %}` / `_()`. After adding strings:

```bash
python manage.py makemessages -l fr
# edit locale/fr/LC_MESSAGES/django.po — fill msgstr, never mark fuzzy (#, fuzzy)
python manage.py compilemessages
```

The `"Saved"` → `"Enregistré"` entry was missing from the PO file and has been added.

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

### admin.css — standalone, V4 debt

`static/css/admin.css` does NOT `@import main.css`. It duplicates the CSS variable declarations
independently. When you change a variable in `main.css`, you must also update `admin.css` manually.

Changes already synced to `admin.css`:
- `--color-text-secondary`: 0.55 → 0.75
- `--color-badge-exact-text`: added (#5c4500)
- `--color-badge-win-text`: added (#235408)
- `--color-logo-bg`: added (rgba 0.08)
- `--color-badge-win-light`: added (rgba lime 0.25)
- `--color-badge-gap-light`: added (rgba purple 0.35)

V4 will consolidate these into a shared token file. Until then: both files must stay in sync.

---

## 4. Steps 1–7 — status

### Step 1 — Design system (DONE, commit `4a6c15d`)

Applied to all pages: CSS variables, pill buttons, Barlow font, cream background, tinted card
surfaces, navbar, footer, segment controls, flash messages, ranking table "You" highlight.

Remaining: nothing.

### Step 2 — Match card (DONE, commits `c2871c6`, `958706f`, `4553870`, subsequent fixes)

Match card partial (`templates/partials/match_card.html`) redesigned, then fully restructured into
the 4-zone anatomy (see §6):
- All states covered: open (±prediction, ±closes-soon), no-odds, locked (±live score), in-play,
  finished (EXACT/GAP/WIN/MISS, ±prediction), cancelled.
- Fixed anatomy: 4 constant-height zones — no more 64px gap between states with/without odds bar.
- Logos: 72×72px wrap / 56px logo desktop, 60×60px wrap / 52px logo XS. `--color-logo-bg`
  (`rgba primary 0.08`) circle behind every logo — pale logos visible, shape harmony.
- Score inputs: pill-aligned, tabular-nums, no border. Form wraps inputs only; Zone C is outside.
- Zone C result banner: full-width, graded intensity by tier (EXACT full gold / GAP medium purple
  tint / WIN light lime tint / MISS neutral), `text-align: center`, 4.5:1+ contrast on all backgrounds.
- Persistent saved state: `✓` checkmark always visible in Zone C when prediction exists.
  Transient "Enregistré" animation on save (server-rendered, fades via CSS, not JS-driven).
  Score not repeated — already visible in inputs.
- Potential points in Zone C: 3-tier display (👑/🎯/✓) when prediction + odds exist.
- Footer: **competition removed** (already shown in comp-divider-chip above the card), only round
  and date shown. Numeric rounds display as "J12"; non-numeric rounds use `|round_label` filter
  (see §3 i18n). `is_numeric` template filter added to `match_tags.py`.
- Desktop width: predictions page uses `col-12 col-lg-7 col-xl-6` — cards capped to ~840px.
- Desktop team name: removed `min-height: 3rem` (was creating excess vertical space in Zone C area).
- Language selector: visible on profile page at mobile breakpoint (added in step 2 bug fix).
- TEAM_OVERRIDES: added `'name'` key support; "Union Bordeaux-Bègles" (ID 131) corrected from API
  typo "Union Bordeaux-Begles" — applied on every sync.
- `seed_ui_states.py`: matches -1 to -10 cover all visual states including match -10 (`round='Final'`
  to test non-numeric round label rendering).
- French translations added: "Ton prono :", "Match annulé, 0 pt", "pt", "J%(r)s", playoff round
  labels ("Finale", "Demi-finales", "Quarts de finale").

Step 2 follow-up changes (this session):
- Zone A FINISHED: date/time (`D dd/mm · HH:mm`) replaces `ti-check-circle Terminé`.
- Zone D FINISHED: date removed (already in Zone A); only round shown.
- Day-group separators added for past tab in predictions index.
- All emojis replaced with Tabler icons: `ti-crown` (EXACT), `ti-target` (GAP), `ti-check` (WIN), `ti-x` (MISS).
- Points pluralisation: `{% blocktrans count %}` — 0→"0 pt", 1→"+1 pt", N→"+N pts"; no "+" on 0.
- Saved state moved from Zone C (persistent `ti-check`) to inputs: `--saved` tint + small `ti-check` below inputs.
- `match-saved-zone--flash`: "Enregistré" overlays and fades; potential points reveal with delay.
- Competition divider chip: filter style (light tint + border) replaces filled navy pill.
- Navbar logout: `btn-nav-link` (discrete) replaces `btn-accent`.
- Logo sizes: desktop 64×64px wrap / 48px logo (was 72×72 / 56px).
- Card body padding: 0.75rem desktop (was Bootstrap default 1rem).
- Score consistency: unified `.match-score` at `1.5rem tabular-nums`; removed finished-only override; inputs aligned to same 1.5rem.

Step 2 mobile JS fix (this session):
- `isVisible(el)` helper: skips inputs inside `.collapse:not(.show)` (no-odds collapsed section).
- `findNextCardHomeInput` / `findPrevCardAwayInput` now filter by `isVisible()`.
- `updateEnterkeyhint()`: sets `enterkeyhint="done"` on the last visible `away` input, `"next"` on all others. Called on page load, after each HTMX swap (`htmx:afterSwap`), and on Bootstrap collapse show/hide events.
- Last `away` input blur path: when no next visible input exists, `input` handler (2-digit) and `keydown` Enter handler both do `pendingFocusId = null; input.blur()` — triggers `change` event → HTMX saves.
- `pendingFocusId = null` before `blur()` prevents focus restoration reopening the keyboard after the save swap.

Remaining: iOS keyboard restoration (Plan B) — activate if confirmed broken on device. 2-column grid at lg (recommended, not yet implemented — see §6).

---

## 6. Match card anatomy — fixed zones, all tabs identical

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

Zone D is removed. Round + time live in Zone A.

**Rule for each zone:**
- **Zone A** = `HH:mm · Jx` always (first line, muted). Second line: status label when applicable
  (closes-soon orange, locked grey, live red pulsing, cancelled grey). FINISHED: no second line.
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

**Icon discipline:** All icons are Tabler icons (`ti ti-*`) — no emojis anywhere. Zone A: `ti-clock`, `ti-lock`, `ti-x`. Zone C result tiers: `ti-crown` (EXACT), `ti-target` (GAP), `ti-check` (WIN/saved), `ti-x` (MISS). Potential points: same tier icons.

**Score consistency:** `.match-score` uses a single unified style (`font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums`) for all states (live, finished). Score inputs use the same `font-size: 1.5rem` so the digit size is consistent whether the user is entering or viewing a score. The `.match-card-finished` font-size override has been removed.

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
| MISS | `--color-badge-miss` rgba(43,52,103,0.10) (neutral) | `--color-text-secondary` rgba(0.75) | ~5:1 ✓ |

The original GAP row used `--color-badge-gap` #8B35A8 solid + white text. It was changed to a tinted
background + `--color-primary` text to fit the WIN light → GAP medium → EXACT full gradation.
`--color-badge-exact-text` (#705500 → #5c4500) and `--color-badge-win-text` (#2d6b0e → #235408)
were darkened to meet 4.5:1. All changes reflected in both `main.css` and `admin.css`.

---

### Step 3 — Landing page (TODO)

The landing page (`templates/matches/landing.html`) has not been restyled. It currently uses
generic Bootstrap. Apply L'Ovale direction: pill CTAs, cream background, oval motif, Barlow large
display type.

### Step 4 — Predictions page chrome (TODO)

The predictions page outer chrome (tab filter, competition divider chips, no-odds collapse toggle,
progress bar container) has received minor styling but no step-level review. Verify against
direction sheet.

### Step 5 — Rankings page (TODO)

Rankings table, leaderboard layout, competition filter chips. "You" row highlight added in step 1.
Full step review pending.

### Step 6 — Leagues pages (TODO)

League list, create, join, detail pages. No L'Ovale treatment yet.

### Step 7 — Account pages (TODO)

Register, login, profile, password reset. Language toggle added to profile in step 2 bug fix.
Full step review pending.

---

## 5. How to test

### Set up demo data

```bash
python manage.py seed_ui_states --reset   # tear down + recreate all demo states
python manage.py runserver
```

Login: `demo_main` / `demo1234`

### State checklist — predictions page (`/predictions/`)

| Match | State | Zone A | Centre | Zone C | Zone D |
|---|---|---|---|---|---|
| -1 | Open, no pred | _(empty)_ | Inputs empty | Odds bar 3 cols | D1 · date |
| -2 | Open, with pred | _(empty)_ | Inputs `28–15` | `✓` + potential pts | D2 · date |
| -3 | Closes soon, with pred | `⏱ Ferme dans Xh` (red) | Inputs `22–10` | `✓` + potential pts | D3 · date |
| -4 | No odds | _(empty)_ | `—` | "Cotes à venir" | D4 · date |
| -5 | Locked, with pred | `🔒 Verrouillé` | `—` | "Ton prono : 21–17" | D5 · date |
| -6 | In-play | `● En direct` (pulsing) | `27–14` | "Ton prono : 30–10" | D6 · date |
| -7 | Finished EXACT | `✓ Terminé` | `24–17` | Gold banner 👑 +N pts | D7 · date |
| -8 | Cancelled | `✗ Annulé` | `—` | "Match annulé, 0 pt" | D8 · date |
| -9 | Long name + no logo | _(empty)_ | Inputs | Odds bar + initials fallback | D9 · date |
| -10 | Open, non-numeric round | _(empty)_ | Inputs | Odds bar | "Finale" · date |

All cards should be the **same height** within the list — this is the primary visual check.

Match -10 also verifies the `round_label` filter: Zone D should show "Finale" (not "Final").

### HTMX save flow

1. On match -1: enter home score, tab/auto-advance to away, enter away score.
2. Verify: card swaps, `✓ score` appears, "Enregistré" fades out.
3. Update a score on match -2: change home input, tab to away (already filled), verify `change`
   fires, card swaps with updated persistent state.
4. Verify progress bar counter increments.

### Mobile (local network)

Access from phone: `http://<your-mac-ip>:8000/predictions/`

Checklist:
- [ ] **All 10 cards the same height** — no card taller than the others
- [ ] On desktop (≥992px): cards constrained to ~840px, centred — not stretching full viewport
- [ ] Zone A shows correct label for each state (closes-soon orange, locked grey, live red pulsing, terminé/annulé grey)
- [ ] Logos visible (Toulouse, Racing 92, La Rochelle, Clermont)
- [ ] Match -9 shows initials circles (no PNG for those slugs)
- [ ] Match -10 footer shows "Finale" (not "Final") — `round_label` filter working
- [ ] All logos have a subtle circular background tint (`--color-logo-bg`) — visible behind pale logos
- [ ] Score inputs fit inside center col without overflow
- [ ] Team names wrap to 2 lines, no ellipsis, no height jump
- [ ] Match -3 (closes soon + prediction): Zone A shows "Ferme dans Xh", Zone C shows ✓ + potential pts
- [ ] Match -6 (in-play): Zone A shows pulsing dot + "En direct", centre shows "27–14"
- [ ] Match -7 (finished): gold result banner with pts fills Zone C
- [ ] "Enregistré" appears and fades after save (match -1 or -9)
- [ ] Save on match -2: inputs stay pre-filled, Zone C updates, progress bar increments
- [ ] Language selector visible on profile page at mobile breakpoint (added in step 2 bug fix)
- [ ] Persistent saved state: on match -2, `✓` checkmark is visible in Zone C on page load (no interaction needed) — it is server-rendered, not JS-injected
- [ ] Keyboard behaviour when typing first prediction (new entry)
- [ ] Keyboard behaviour when updating an existing prediction (iOS Plan B trigger)

### i18n

Switch to French (default) and English: check all new strings translate correctly.
French strings to verify: "Enregistré", "Probabilités disponibles prochainement" (odds coming soon),
"Verrouillé" (locked), all match state labels.
