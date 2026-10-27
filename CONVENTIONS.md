# CONVENTIONS.md

Coding conventions for Oval'Pronos. Follow these consistently — they exist to make the codebase predictable and to prepare for V4 white-label.

---

## Language Rules

**All code in English, all UI text in French via i18n.**

| Context | Language |
|---|---|
| Python code (variables, functions, classes, arguments) | English |
| URL patterns | English |
| Django model field names | English |
| Code comments | English |
| Git commit messages | English |
| Displayed UI text (templates, form labels, error messages) | French via i18n |
| `verbose_name` in models | `_("English")`, translated in `django.po` (the admin is multilingual too) |

```python
# Good
class Prediction(models.Model):
    points_earned = models.IntegerField(verbose_name=_("Points earned"))

# Bad — French variable name
class Pronostic(models.Model):
    points_gagnes = models.IntegerField()
```

---

## i18n Rules

Every string that appears in a rendered page must go through the translation system. This includes the admin: `@admin.action(description=...)`, `@admin.display(description=...)`, `short_description`, list filter titles and choices, `message_user()` and `messages.*`.

**In templates:**
```html
{% load i18n %}
<h1>{% trans "Predict upcoming matches" %}</h1>
<p>{% blocktrans with name=user.display_name %}Welcome, {{ name }}{% endblocktrans %}</p>
```

**In Python:**
```python
from django.utils.translation import gettext_lazy as _

# Model verbose names and choices
class Match(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', _('Scheduled')),
        ('FINISHED', _('Finished')),
    ]
    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matches")

# View messages and form errors
messages.error(request, _("This match is already locked."))

# Variables: named placeholders, never an f-string inside _()
self.message_user(request, _("Points recalculated for %(count)s match(es).") % {'count': count})
```

Use `gettext_lazy` (`_()`) everywhere except inside view functions where `gettext` is also fine.

**Same English word, different French text:** if a msgid already exists in `django.po` with another translation, use `pgettext("context", "...")` (`{% trans "..." context "..." %}` in templates) instead of changing the existing translation.

After adding new translatable strings:
```bash
python manage.py makemessages -l fr   # scan for new strings
# Edit locale/fr/LC_MESSAGES/django.po
python manage.py compilemessages      # compile .po → .mo
```

Without gettext installed, append the entries at the end of `django.po` by hand and compile the `.mo` with `polib`. Commit both files: `deploy.sh` does not run `compilemessages`, so a missing `.mo` means no translations in prod.

**Exceptions (French only, outside i18n):**
- email templates in `templates/emails/` and `templates/accounts/emails/` (subjects and bodies) and the plain-text alerts emailed to admins, for now;
- legal pages in `templates/legal/` (legal notice, privacy policy, terms): legal texts written under French law;
- `templates/500.html`: standalone page that must render even when the app is broken.

Management command output and log messages are not UI and are not translated.

---

## Team Logo Pattern

Use `Team.logo` (uploaded in the admin) when it is set, otherwise fall back to the static PNG `static/img/teams/<team.slug>.png`. Never use external URLs.

```html
{% load static %}
<img src="{% if team.logo %}{{ team.logo.url }}{% else %}{% static 'img/teams/' %}{{ team.slug }}.png{% endif %}"
     alt="{{ team.name }}"
     width="38" height="38">
```

In Python, `apps/matches/templatetags/match_tags.py::team_logo_url(team)` applies the same order.

File naming: `static/img/teams/<team.slug>.png`. When a team is imported via the RapidAPI sync, its `slug` must be set manually (via `TEAM_OVERRIDES` in `services.py`) before the static logo displays. If neither the upload nor the PNG exists, the browser shows a broken image — add a CSS fallback via `onerror` if needed.

---

## CSS Variables — No Hardcoded Colors

**No hardcoded colors — ever.** This covers hex values, `rgb()`/`rgba()`/`hsl()`, and color keywords such as `white` or `black`, in `.css` files, in `style="..."` attributes, and in HTML built in Python (admin badges). Only `tokens.css` contains literal colors.

All colors must use CSS custom properties declared in the `:root` block of `static/css/tokens.css`. Every new variable goes there and only there. `tokens.css` is loaded first by both `templates/base.html` and `templates/admin/base_site.html`; `main.css` and `admin.css` only reference variables, they never declare them. A V4 tenant theme therefore replaces a single `:root` and reaches the app and the admin alike.

Translucent shades are named variables too (for example `--color-primary-a07` for the primary navy at 7 %): never write `rgba()` outside `tokens.css`.

```css
/* Good */
.btn-primary { background: var(--color-accent); }
.team-name   { color: var(--color-text); }

/* Bad: breaks white-label */
.btn-primary { background: #EB455F; }
.card        { background: rgba(43, 52, 103, 0.07); }
```

**Exceptions:** email templates (`templates/emails/`, `templates/accounts/emails/`) use inline hex because mail clients ignore CSS variables; keep those values in sync with `tokens.css`. `templates/500.html` is standalone (it must render even when the app is broken) and keeps its inline palette.

Available variables (source of truth: the `:root` block of `static/css/tokens.css`):

| Variable | Value | Usage |
|---|---|---|
| `--color-primary` | `#2B3467` | Navy: headers, buttons, footer |
| `--color-background` | `#FCFFF9` | Off-white page background |
| `--color-accent` | `#EB455F` | Red/pink: CTAs, alerts |
| `--color-brand-rugby` | `#1a7f37` | Green: live status, positive states |
| `--color-text` | `#404771` | Body text, distinct from brand primary |
| `--color-text-on-primary` | `#FCFFF9` | Text on dark backgrounds |
| `--color-text-body` | `#3d3d3d` | Prose, feature copy |
| `--color-text-secondary` | `rgba(43, 52, 103, 0.75)` | Secondary text, ~5.4:1 on cream |
| `--color-surface-raised` | `rgba(43, 52, 103, 0.06)` | Raised surfaces |
| `--color-light` | `#BAD7E9` | Legacy light blue; prefer `--color-icon-muted` for icons |
| `--color-icon-muted` | `rgba(43, 52, 103, 0.28)` | Muted icons |
| `--color-you-highlight` | `rgba(43, 52, 103, 0.12)` | Rankings "You" row |
| `--color-rank-silver` | `rgba(43, 52, 103, 0.65)` | Rank 2 medal, 4.1:1 on cream |
| `--color-rank-bronze` | `rgba(184, 105, 37, 0.75)` | Rank 3 medal |
| `--color-logo-fallback-bg` | `rgba(43, 52, 103, 0.15)` | Team initials fallback |
| `--color-logo-bg` | `rgba(43, 52, 103, 0.08)` | Circle behind team logos |
| `--color-badge-exact` | `#F5C542` | Gold: exact score badge |
| `--color-badge-exact-text` | `#5c4500` | Text on the exact badge, 5.7:1 |
| `--color-badge-gap` | `#8B35A8` | Purple: good gap badge (background and text) |
| `--color-badge-win` | `#A8E063` | Lime: correct winner badge |
| `--color-badge-win-text` | `#235408` | Text on the win badge, 5.8:1 |
| `--color-badge-win-light` | `rgba(168, 224, 99, 0.25)` | Light result banner |
| `--color-badge-gap-light` | `rgba(139, 53, 168, 0.35)` | Medium result banner |
| `--color-badge-miss` | `rgba(43, 52, 103, 0.10)` | Neutral miss badge background |
| `--color-badge-miss-text` | `rgba(43, 52, 103, 0.75)` | Miss text and icons, ~5.4:1 |
| `--color-hero-motif` | `rgba(252, 255, 249, 0.07)` | Hero oval motif on navy |
| `--color-badge-ended-bg` | `rgba(43, 52, 103, 0.08)` | Ended league badge background |
| `--color-badge-ended-text` | `rgba(43, 52, 103, 0.75)` | Ended league badge text |
| `--color-white` | `#fff` | Admin panels and table rows |
| `--color-warning` | `#d97706` | Admin warning messages |
| `--color-warning-light` | `#ffc107` | Admin "postponed" badge, missing-odds icon |
| `--color-warning-light-text` | `#705500` | Text on `--color-warning-light` |
| `--color-success` | `#28a745` | Admin odds-present tick |

Translucent shades (`--color-<base>-aNN`, NN = opacity in %, `a025` = 2.5 %) are listed in `tokens.css` under their base color, together with `--border` (admin borders). `apps/matches/tests_quality.py::StylesheetColorTest` fails if a literal color appears in `main.css` or `admin.css`.

---

## Scoring Calculation Location

**The scoring logic lives in `apps/predictions/services.py`, nowhere else.**

`calculate_points()` is a standalone function, not a model method.

```python
# apps/predictions/services.py
def calculate_points(prediction, match) -> tuple[int, str] | None:
    ...
```

Reasons: easy to unit-test without DB fixtures, importable by both the sync service and management commands, keeps models thin.

Callers only call it, they never reimplement it. Today the single caller is `apps/matches/services.py::_calculate_points_for_match(match)`, used by the sync, the score API, the admin actions and the management commands. A thin model helper that calls it (for example a `Prediction.save_points()`) is allowed.

---

## Business Logic in `services.py`

Business calculations live in `apps/<app>/services.py`, so that a management command and an admin page share one implementation. Example: `campaign_report()` feeds both the `report_campaign` command and the admin campaign report page.

Exception: code that parses an HTTP request stays out of `services.py`. Sign-up attribution (UTM parameters, Referer, landing path) is centralised in `apps/accounts/signup_source.py`.

---

## Admin Views Pattern

Custom admin pages (not using standard `ModelAdmin`) must use `staff_member_required` and live in `apps/<app>/admin_views.py`.

```python
# apps/matches/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(staff_member_required, name='dispatch')
class CompetitionImportView(View):
    def get(self, request, competition_id): ...
    def post(self, request, competition_id): ...
```

Register these URLs in `ovalpronos/urls.py` under the `admin/` prefix, not in app `urls.py`, and **before** `path('admin/', admin.site.urls)`: its `<path:object_id>/` catch-all would otherwise swallow the route.

---

## HTMX Prediction Form Pattern

**Lock enforcement is always server-side.**

The prediction form auto-saves on `change`. Key rules:

1. The `<form>` wraps all inputs for a single match card.
2. `hx-swap="outerHTML"` — the entire match card is replaced on each response.
3. The server response must be a complete match card partial (same `partials/match_card.html`).
4. Lock enforcement is always server-side — never rely on the `disabled` attribute alone.
5. If only one of the two score fields is filled, the view must not save — return the partial unchanged. The `hx-trigger` filter also skips the request, but the server check is the one that counts.
6. Scores are bounded server-side (0 to 200).

```html
<form hx-post="{% url 'predictions:submit' match.pk %}"
      hx-trigger="change[this.querySelector('[name=score_h]').value !== '' && this.querySelector('[name=score_a]').value !== '']"
      hx-swap="outerHTML">
  {% csrf_token %}
  <input type="number" name="score_h" min="0"
         value="{{ prediction.predicted_home_score|default:'' }}">
  <input type="number" name="score_a" min="0"
         value="{{ prediction.predicted_away_score|default:'' }}">
</form>
```

---

## Unique Constraint Pattern

Use `UniqueConstraint` instead of `unique_together` when any of the constrained fields can be NULL (PostgreSQL treats each NULL as distinct, so `unique_together` with nullable FKs does not work as expected).

```python
# Good: partial constraints with condition= handle the nullable FKs
# (target shape for UserScore, which has no unique constraint yet)
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['user'],
            condition=Q(competition__isnull=True, league__isnull=True),
            name='unique_userscore_global'
        ),
        models.UniqueConstraint(
            fields=['user', 'competition'],
            condition=Q(league__isnull=True, competition__isnull=False),
            name='unique_userscore_competition'
        ),
        models.UniqueConstraint(
            fields=['user', 'league'],
            condition=Q(league__isnull=False),
            name='unique_userscore_league'
        ),
    ]

# OK — only when all fields are non-nullable (Prediction model)
class Meta:
    unique_together = ('user', 'match')
```

---

## App and File Naming

| What | Convention |
|---|---|
| App directory | `apps/<name>/` — lowercase, plural (`predictions` not `prediction`) |
| Model class | PascalCase, English, singular (`Prediction` not `Predictions`) |
| View class | PascalCase + `View` suffix (`PredictionsView`, `SubmitPredictionView`) |
| URL name | `<namespace>:<action>` — e.g. `predictions:submit`, `accounts:login` |
| Template | `templates/<app>/<name>.html`, partials in `templates/partials/<name>.html` |
| Management command | `apps/<app>/management/commands/<verb>_<noun>.py` |
| Service module | `apps/<app>/services.py` — business logic, no request or response objects, testable in isolation |
| Request parsing helper | dedicated module, e.g. `apps/accounts/signup_source.py` |
| Admin extension | `apps/<app>/admin_views.py` |

---

## Model `verbose_name`

Set `verbose_name` and `verbose_name_plural` on every model and field as `_("English")`, with the French translation in `locale/fr/LC_MESSAGES/django.po`. They are displayed in the Django admin, which follows the active language like the rest of the app.

```python
class Prediction(models.Model):
    class Meta:
        verbose_name = _("Prediction")
        verbose_name_plural = _("Predictions")
```

---

## Settings and Environment Variables

- All secrets via `python-decouple`'s `config()`
- Boolean flags: `config('DEBUG', default=False, cast=bool)`
- List values: `config('ALLOWED_HOSTS', cast=Csv())`
- Document every new env var in CLAUDE.md

---

## Anti-patterns — never do these

1. Hardcode colors (hex, `rgb()`/`rgba()`, `white`…) in templates, CSS or admin HTML — use `var(--color-*)` declared in the `:root` of `tokens.css`.
2. Use external URLs for team logos — `Team.logo` if uploaded, else the local PNG at `static/img/teams/<slug>.png`.
3. Reimplement scoring outside `apps/predictions/services.py` — the calculation logic lives only there; other code calls `calculate_points()`.
4. Enforce lock or odds validation client-side only — always re-check server-side in the view.
5. Use `element.innerHTML` with server-provided data in JS — use `textContent` or DOM methods.
6. Add a Competition row in prod without setting `is_active=True` — `sync_all_competitions()` only iterates DB rows with `is_active=True`.
7. Write `verbose_name` values as raw strings — use `_("English")` and translate them in `django.po`.
8. Use `unique_together` when any constrained field can be NULL — use `UniqueConstraint` with `condition=` instead (see §Unique Constraint Pattern).
9. Skip `{% trans %}` / `_()` on any user-visible string — all UI text must go through i18n (exceptions: §i18n Rules).
10. Render scoring or ranking logic in a template or view — it belongs in `apps/predictions/services.py`.
11. Declare a custom `admin/...` URL after `admin.site.urls` — the admin catch-all swallows it.
