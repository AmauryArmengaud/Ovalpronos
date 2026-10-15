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

### CSS variables modified in `:root`

| Variable | Old value | New value | Reason |
|---|---|---|---|
| `--color-text-secondary` | `rgba(43,52,103,0.55)` (~3.2:1 contrast) | `rgba(43,52,103,0.75)` (~5.4:1) | WCAG AA on cream background |

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
| `.match-team-logo` height | 60px | 52px |
| `.match-team-logo` max-width | 80px | 68px |
| `.match-team-logo-fallback` | 52×52px, 0.875rem | 44×44px, 0.75rem |
| `.match-score-input` width | 52px | 44px |
| `.match-score-input` font-size | 1.375rem | 1.125rem |
| `.match-team-col` width | 38% | 35% |
| `.match-center-col` width | 24% | 30% (wider to fit inputs) |
| `.match-team-name` min-height | — | 2.8rem (reserves 2 lines at 17px×1.6) |
| `.match-card-body` padding | Bootstrap default | 0.75rem 0.625rem |

### Saved state

- **Persistent:** `.match-saved-state` — rendered by server whenever `prediction` exists.
  Shows `✓ {home}–{away}` in `--color-brand-rugby` (green), always visible.
- **Transient:** `.match-saved-indicator` — inline `<span>` rendered only when `saved=True` (view context).
  Fades out over 2s via `saved-fade` keyframe. Reduced-motion: `opacity: 0` immediately.

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

### admin.css — standalone, V4 debt

`static/css/admin.css` does NOT `@import main.css`. It duplicates the CSS variable declarations
independently. When you change a variable in `main.css`, you must also update `admin.css` manually.

Changes already synced: `--color-text-secondary` bumped from 0.55 to 0.75.

V4 will consolidate these into a shared token file. Until then: both files must stay in sync.

---

## 4. Steps 1–7 — status

### Step 1 — Design system (DONE, commit `4a6c15d`)

Applied to all pages: CSS variables, pill buttons, Barlow font, cream background, tinted card
surfaces, navbar, footer, segment controls, flash messages, ranking table "You" highlight.

Remaining: nothing.

### Step 2 — Match card (DONE, commits `c2871c6`, `958706f`, `4553870`)

Match card partial (`templates/partials/match_card.html`) redesigned:
- All 9 match states covered: open, open-with-prediction, closes-soon, no-odds, locked,
  locked-with-live-score, finished (EXACT/GAP/WIN/MISS), cancelled, in-play.
- Logos: 60px desktop / 52px XS, initials fallback circle.
- Score inputs: pill-aligned, tabular-nums, no border.
- Odds bar: tone-separated columns, no vertical rules.
- Saved state: persistent `✓ score` + transient "Saved" animation.
- Potential points: 3-tier display (👑/🎯/✓) when prediction + odds exist.
- Mobile XS fixes applied: column widths, input sizes, `min-height` on team names.
- Progress bar: sticky, JS-updated on `htmx:afterSwap`.
- Focus restoration after swap implemented.
- `seed_ui_states.py` updated to use real DB teams for logo testing.
- French translation for "Saved" added.

Remaining: iOS keyboard restoration (Plan B) — activate if confirmed broken on device.

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

| Match | Expected state | What to verify |
|---|---|---|
| -1 | Open, no prediction | Form shown, microcopy "Fill both scores to save", potential preview in odds bar |
| -2 | Open, prediction saved | Form shown, `✓ 28–15` persistent state, potential points 3-tier |
| -3 | Closes soon | Orange "Closes in Xh" above form |
| -4 | No odds | "Odds coming soon" in centre, card in no-odds collapse |
| -5 | Locked (past kickoff) | 🔒 Locked badge, `✓ 21–17` shown, no form |
| -6 | In-play | Live score + pulsing dot, `✓ 30–10` shown |
| -7 | Finished EXACT | 👑 badge, exact score shown |
| -8 | Cancelled | ✗ badge, "Cancelled" |
| -9 | Long name + no logo | Long name wraps (no ellipsis), initials circle fallback |

### HTMX save flow

1. On match -1: enter home score, tab/auto-advance to away, enter away score.
2. Verify: card swaps, `✓ score` appears, "Enregistré" fades out.
3. Update a score on match -2: change home input, tab to away (already filled), verify `change`
   fires, card swaps with updated persistent state.
4. Verify progress bar counter increments.

### Mobile (local network)

Access from phone: `http://<your-mac-ip>:8000/predictions/`

Checklist:
- [ ] Logos visible (Toulouse, Racing 92, La Rochelle, Clermont)
- [ ] Match -9 shows initials circles (no PNG for those slugs)
- [ ] All cards same height within each state group
- [ ] Score inputs fit inside center col without overflow
- [ ] Team names wrap to 2 lines, no ellipsis, no height jump
- [ ] "Enregistré" appears and fades after save
- [ ] Language toggle visible on profile page (mobile breakpoint)
- [ ] Keyboard behaviour when typing first prediction (new entry)
- [ ] Keyboard behaviour when updating an existing prediction (iOS Plan B trigger)

### i18n

Switch to French (default) and English: check all new strings translate correctly.
French strings to verify: "Enregistré", "Probabilités disponibles prochainement" (odds coming soon),
"Verrouillé" (locked), all match state labels.
