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
| Emojis anywhere in match card | Rendering inconsistent across devices; replaced with Tabler icons (same family as Zone A) |
| `btn-accent` on navbar logout | Accent red is for positive CTAs (login, sign-up); logout is destructive → discrete link style (`btn-nav-link`) |
| Persistent icon in Zone C (`.match-saved-state`) | On mobile it was indistinguishable from a 4th tier icon; moved to input level (`--saved` tint + `ti-check` below inputs) |
| Two different font-sizes for live vs finished score | Same score, different size → layout inconsistency; unified to `1.5rem` via single `.match-score` class |
| `clip-path` on team logo images | PNG logos are cutout (transparent BG); clip-path bleeds fallback circle through transparency |
| Overlay approach for logo fallback (fallback always visible behind img) | Same issue — transparent PNG reveals the circle beneath |
| Dark background on score inputs | Feels like a separate widget; tinted surface integrates with card tone |
| `hx-trigger="blur from:[name=away]"` | Two problems: (a) editing only home score, never touching away = save never fires = data loss; (b) HTMX `from:` resolves document-wide, not per-form — all cards fire on any `[name=away]` blur |
| Ellipsis truncation on `.match-team-name` | Content should never be silently hidden; use `min-height` to reserve space instead |
| JS-only saved feedback (animation only) | Animation may not fire if input is auto-advanced; persistent server-rendered state is the ground truth |
| Zone D footer | Round + time moved to Zone A; competition already shown in comp-divider-chip above the card |

---

## 2. Numerical decisions

### CSS variables added to `:root` in `main.css`

| Variable | Value | Purpose |
|---|---|---|
| `--color-you-highlight` | `rgba(43,52,103,0.12)` | Rankings "You" row highlight |
| `--color-logo-fallback-bg` | `rgba(43,52,103,0.15)` | Logo initials fallback circle background |
| `--color-logo-bg` | `rgba(43,52,103,0.08)` | Neutral circle behind every team logo — pale logos visible, shapes harmonised |
| `--color-badge-exact-text` | `#5c4500` | Dark amber text on gold banner — 5.7:1 on `#F5C542` |
| `--color-win-text` | `#235408` | Dark green text on lime banner — 5.8:1 on `#A8E063` |
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
| `.match-zone-a` min-height | 36px (flex-column, gap 2px) | 36px |
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
- Zone C default (open + prediction): shows only potential points (no persistent icon).

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

## 4. Steps 1–7 — final state

### Step 1 — Design system (DONE)

Applied to all pages: CSS variables, pill buttons, Barlow font, cream background, tinted card
surfaces, navbar, footer, segment controls, flash messages, ranking table "You" highlight.

### Step 2 — Match card (DONE)

Match card partial (`templates/partials/match_card.html`) fully restructured into the 4-zone anatomy
(see §6). Predictions page updated with 2-column grid at lg.

**Match card final state:**
- All states covered: open (±prediction, ±closes-soon), no-odds, locked (±live score), in-play,
  finished (EXACT/GAP/WIN/MISS, ±prediction), cancelled.
- 3 constant-height zones (A, B, C) — zone height never changes between states.
- Logos: 72×72px wrap / 56px logo desktop; 60×60px wrap / 52px logo XS. `--color-logo-bg` circle
  behind every logo.
- Score inputs: pill-aligned, tabular-nums, no border. Form wraps inputs only; Zone C is outside.
- Zone C result banner: full-width, graded intensity by tier (EXACT full gold / GAP medium purple
  tint / WIN light lime tint / MISS neutral), `text-align: center`, 4.5:1+ contrast on all backgrounds.
- Potential points in Zone C: `ti-crown`/`ti-target`/`ti-check` icons when prediction + odds exist.
- Saved state on inputs: `--saved` tint + small `ti-check` below inputs. "Enregistré" flash in Zone C.
- All icons are Tabler icons (`ti ti-*`) — no emojis anywhere.
- Zone A: `HH:mm · Jx` always. Status label on second line when applicable.
- Round display: numeric → `J{n}` via `{% blocktrans %}`; non-numeric → `|round_label` filter.
- Competition removed from card (shown in comp-divider-chip above); Zone D removed entirely.

**Predictions page final state:**
- Chronological list (day → competition → time) with day-divider chips and comp-divider chips.
- At lg (≥992px): 2-column CSS grid (`.predictions-grid`). Separators span both columns via
  `grid-column: 1 / -1`. DOM order = reading order — no JS changes needed for focus navigation.
- Matches without odds hidden behind Bootstrap collapse toggle.
- Mobile JS: `isVisible()` skips inputs inside `.collapse:not(.show)`; `enterkeyhint` managed per
  position; last away input blur triggers save and clears `pendingFocusId`.

### Step 3 — Landing page (TODO)

Apply L'Ovale direction: pill CTAs, cream background, oval motif, Barlow large display type.

### Step 4 — Predictions page chrome (TODO)

Full review of tab filter, competition divider chips, no-odds collapse toggle, progress bar.

### Step 5 — Rankings page (TODO)

Rankings table, leaderboard layout, competition filter chips.

### Step 6 — Leagues pages (TODO)

League list, create, join, detail pages.

### Step 7 — Account pages (TODO)

Register, login, profile, password reset.

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

**Icon discipline:** All icons are Tabler icons (`ti ti-*`) — no emojis anywhere. Zone A: `ti-clock`, `ti-lock`, `ti-x`. Zone C result tiers: `ti-crown` (EXACT), `ti-target` (GAP), `ti-check` (WIN/saved), `ti-x` (MISS). Potential points: same tier icons.

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

`--color-badge-miss` is a background variable only. Use `--color-badge-miss-text` for any text
or icon that needs to express a MISS state (e.g. in rules.html, admin badges labels).

---

## 5. How to test

### Set up demo data

```bash
python manage.py seed_ui_states --reset   # tear down + recreate all demo states
python manage.py runserver
```

Login: `demo_main` / `demo1234`

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
4. Verify progress bar counter increments.

### Mobile (local network)

Access from phone: `http://<your-mac-ip>:8000/predictions/`

Checklist:
- [ ] **All cards the same height** — no card taller than the others
- [ ] On desktop (≥992px): 2-column grid, day-dividers and comp-chips span both columns
- [ ] Zone A shows correct label for each state (closes-soon accent red, locked grey, live red pulsing, cancelled grey, finished empty)
- [ ] Logos visible (Toulouse, Racing 92, La Rochelle, Clermont)
- [ ] Match -9 shows initials circles (no PNG for those slugs)
- [ ] Match -10 Zone A shows "Finale" (not "Final") — `round_label` filter working
- [ ] All logos have a subtle circular background tint (`--color-logo-bg`) — visible behind pale logos
- [ ] Score inputs fit inside center col without overflow
- [ ] Team names wrap to 2 lines, no ellipsis, no height jump
- [ ] Match -3 (closes soon + prediction): Zone A shows "Ferme dans Xh", Zone C shows potential pts
- [ ] Match -6 (in-play): Zone A shows pulsing dot + "En direct", centre shows "27–14"
- [ ] Match -7 (finished): gold result banner with pts fills Zone C
- [ ] "Enregistré" appears and fades after save (match -1 or -9)
- [ ] Save on match -2: inputs stay pre-filled, Zone C updates, progress bar increments
- [ ] Language selector visible on profile page at mobile breakpoint
- [ ] Saved state on match -2: green tint + `ti-check` below inputs is visible on page load (server-rendered, not JS-injected)
- [ ] Keyboard behaviour when typing first prediction (new entry)
- [ ] Keyboard behaviour when updating an existing prediction (iOS Plan B trigger)

### i18n

Switch to French (default) and English: check all new strings translate correctly.
French strings to verify: "Enregistré", "Cotes à venir", "Verrouillé", all match state labels.
