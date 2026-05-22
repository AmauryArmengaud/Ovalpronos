# CONVENTIONS.md

Coding conventions for Oval'Pronos. Follow these consistently — they exist to make the codebase predictable and to prepare for V4 white-label.

---

## Language Rules

| Context | Language |
|---|---|
| Python code (variables, functions, classes, arguments) | English |
| URL patterns | English |
| Django model field names | English |
| Code comments | English |
| Git commit messages | English |
| Displayed UI text (templates, form labels, error messages) | French via i18n |
| `verbose_name` in models | French string (displayed in Django admin) |

```python
# Good
class Prediction(models.Model):
    points_earned = models.IntegerField(verbose_name="Points gagnés")

# Bad — French variable name
class Pronostic(models.Model):
    points_gagnes = models.IntegerField()
```

---

## i18n Rules

Every string that appears in a rendered page must go through the translation system.

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
        verbose_name = "Match"
        verbose_name_plural = "Matchs"

# View messages and form errors
messages.error(request, _("This match is already locked."))
```

Use `gettext_lazy` (`_()`) everywhere except inside view functions where `gettext` is also fine.

After adding new translatable strings:
```bash
python manage.py makemessages -l fr   # scan for new strings
# Edit locale/fr/LC_MESSAGES/django.po
python manage.py compilemessages      # compile .po → .mo
```

---

## Team Logo Pattern

Team logos are local SVG files. Never use external URLs or `Team.logo_url` in templates.

```html
{% load static %}
<img src="{% static 'img/teams/'|add:team.slug|add:'.svg' %}"
     alt="{{ team.name }}"
     width="38" height="38">
```

File naming: `static/img/teams/<team.slug>.svg`. The `slug` field on `Team` is the single source of truth. When a team is imported via api-sports.io sync, its `slug` must be set manually before a logo displays. If the SVG file is missing, the browser shows a broken image — add a CSS fallback via `onerror` if needed.

---

## CSS Variables — No Hardcoded Hex Values

All colors must use CSS custom properties defined in `static/css/main.css`. This is mandatory for V4 white-label theming where per-tenant colors override these variables.

```css
/* Good */
.btn-primary { background: var(--color-accent); }
.team-name   { color: var(--color-text); }

/* Bad — breaks white-label */
.btn-primary { background: #EB455F; }
```

Available variables:

| Variable | Hex | Usage |
|---|---|---|
| `--color-primary` | `#2B3467` | Navy — headers, buttons, footer |
| `--color-light` | `#BAD7E9` | Light blue — hover, secondary accents |
| `--color-background` | `#FCFFF9` | Off-white page background |
| `--color-accent` | `#EB455F` | Red/pink — CTAs, alerts |
| `--color-badge-exact` | `#F5C542` | Gold — exact score badge (👑) |
| `--color-badge-gap` | `#9334B6` | Purple — good gap badge |
| `--color-badge-win` | `#A8E063` | Green — correct winner badge |
| `--color-badge-miss` | `#FF2E2E` | Red — wrong prediction badge |
| `--color-text-on-primary` | `#FCFFF9` | Text on dark backgrounds |
| `--color-text` | `#2B3467` | Standard body text |

---

## Scoring Calculation Location

The scoring function lives in `apps/predictions/services.py` as a standalone function, not as a model method.

```python
# apps/predictions/services.py
def calculate_points(prediction, match) -> tuple[int, str] | None:
    ...
```

Reasons: easy to unit-test without DB fixtures, importable by both the sync service and management commands, keeps models thin.

The model calls it via a helper:
```python
# apps/predictions/models.py
def save_points(self):
    result = calculate_points(self, self.match)
    if result is not None:
        self.points_earned, self.result_type = result
        self.save(update_fields=['points_earned', 'result_type'])
```

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

Register these URLs in `ovalpronos/urls.py` under the `admin/` prefix, not in app `urls.py`.

---

## HTMX Prediction Form Pattern

The prediction form uses auto-save via `hx-trigger="change"`. Key rules:

1. The `<form>` wraps all inputs for a single match card.
2. `hx-swap="outerHTML"` — the entire match card is replaced on each response.
3. The server response must be a complete match card partial (same `partials/match_card.html`).
4. Lock enforcement is always server-side — never rely on the `disabled` attribute alone.
5. If only one of the two score fields is filled, the view must not save — return the partial unchanged.

```html
<form hx-post="{% url 'predictions:submit' match.pk %}"
      hx-trigger="change"
      hx-swap="outerHTML">
  {% csrf_token %}
  <input type="number" name="home" min="0" max="200"
         value="{{ prediction.predicted_home_score|default:'' }}">
  <input type="number" name="away" min="0" max="200"
         value="{{ prediction.predicted_away_score|default:'' }}">
</form>
```

---

## Unique Constraint Pattern

Use `UniqueConstraint` instead of `unique_together` when any of the constrained fields can be NULL (PostgreSQL treats each NULL as distinct, so `unique_together` with nullable FKs does not work as expected).

```python
# Good — handles nullable FKs correctly (UserScore model)
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['user', 'season'],
            condition=Q(competition__isnull=True, league__isnull=True),
            name='unique_userscore_global'
        ),
        models.UniqueConstraint(
            fields=['user', 'competition', 'season'],
            condition=Q(league__isnull=True, competition__isnull=False),
            name='unique_userscore_competition'
        ),
        models.UniqueConstraint(
            fields=['user', 'league', 'season'],
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
| App directory | `apps/<name>/` — lowercase, singular (`predictions` not `prediction`) |
| Model class | PascalCase, English, singular (`Prediction` not `Predictions`) |
| View class | PascalCase + `View` suffix (`PredictionsView`, `SubmitPredictionView`) |
| URL name | `<namespace>:<action>` — e.g. `predictions:submit`, `accounts:login` |
| Template | `templates/<app>/<name>.html`, partials in `templates/partials/<name>.html` |
| Management command | `apps/<app>/management/commands/<verb>_<noun>.py` |
| Service module | `apps/<app>/services.py` — pure functions, no HTTP, testable in isolation |
| Admin extension | `apps/<app>/admin_views.py` |

---

## Model `verbose_name`

Set `verbose_name` and `verbose_name_plural` in French on every model (displayed in Django admin). This is the one place where French strings appear directly in Python without `_()`.

```python
class Prediction(models.Model):
    class Meta:
        verbose_name = "Pronostic"
        verbose_name_plural = "Pronostics"
```

---

## Settings and Environment Variables

- All secrets via `python-decouple`'s `config()`
- Boolean flags: `config('DEBUG', default=False, cast=bool)`
- List values: `config('ALLOWED_HOSTS', cast=Csv())`
- Document every new env var in CLAUDE.md and in `render.yaml`
