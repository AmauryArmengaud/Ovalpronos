# Audit Technique — Oval'Pronos
**Date :** 2026-05-22
**Stade :** Développement (pré-beta)
**Stack :** Django 5.1.4 · Bootstrap 5 · HTMX · PostgreSQL/SQLite · RapidAPI (rugby-live-data)

---

## Table des matières

1. [Vue d'ensemble du projet](#1-vue-densemble-du-projet)
2. [Architecture](#2-architecture)
3. [Modèles & schéma de base de données](#3-modèles--schéma-de-base-de-données)
4. [Vues & logique métier](#4-vues--logique-métier)
5. [Sécurité](#5-sécurité)
6. [Frontend & templates](#6-frontend--templates)
7. [Performance & scalabilité](#7-performance--scalabilité)
8. [Tests](#8-tests)
9. [Déploiement & CI/CD](#9-déploiement--cicd)
10. [Dépendances](#10-dépendances)
11. [Matrice de risques](#11-matrice-de-risques)
12. [Roadmap recommandée](#12-roadmap-recommandée)

---

## 1. Vue d'ensemble du projet

### 1.1 Description
Application web de pronostics rugby permettant aux utilisateurs de prédire les scores de matchs Top 14, Champions Cup et 6 Nations, puis de se comparer via un classement global ou des ligues privées.

### 1.2 Structure du projet

```
Ovalpronos/
├── ovalpronos/         # Config Django (settings, urls, wsgi)
├── apps/
│   ├── accounts/       # Auth & profils utilisateurs
│   ├── matches/        # Compétitions, équipes, matchs + sync API
│   ├── predictions/    # Saisie & scoring des pronostics
│   ├── rankings/       # Classements (vues uniquement, pas de modèle)
│   └── leagues/        # Ligues privées (V2 — non implémenté)
├── templates/          # 15 templates HTML
├── static/             # CSS, images (logos équipes, icônes)
├── locale/fr/          # Traductions françaises
└── .github/workflows/  # GitHub Actions (sync cron)
```

### 1.3 État actuel des apps

| App | Modèles | Vues | Admin | Tests | État |
|---|---|---|---|---|---|
| accounts | CustomUser | Register, Login, PwReset | ✅ | ❌ | Fonctionnel |
| matches | Competition, Team, Match | Home, Rules, Sync API | ✅ | ❌ | Fonctionnel |
| predictions | Prediction | Index, Submit (HTMX) | ✅ | ✅ (scoring) | Fonctionnel |
| rankings | — | Index (agrégation ORM) | — | ❌ | Fonctionnel |
| leagues | — | — | — | — | Non implémenté |

---

## 2. Architecture

### 2.1 Points forts

**Séparation claire des responsabilités**
- La logique de scoring est isolée dans `apps/predictions/services.py` (fonction pure `calculate_points`) — testable indépendamment et facilement modifiable.
- La sync API externe est dans `apps/matches/services.py`, complètement découplée des vues.

**Flux de données cohérent**
```
GitHub Actions (cron) → POST /api/sync-scores/ (Bearer token)
  → sync_all_competitions()
    → API rugby-live-data
    → upsert Competition/Team/Match (transaction atomique)
    → calculate_points() sur toutes les Prediction du match terminé
```

**Middleware stack correctement ordonné**
```python
SecurityMiddleware → WhiteNoiseMiddleware → SessionMiddleware →
LocaleMiddleware → CommonMiddleware → CsrfViewMiddleware →
AuthenticationMiddleware → MessageMiddleware → XFrameOptionsMiddleware
```

**HTMX sans JavaScript custom**
Le formulaire de pronostic auto-sauvegarde via `hx-post` + `hx-trigger="change"`. Zéro fichier `.js` custom dans le projet — maintenance simplifiée.

### 2.2 Problèmes d'architecture

**⚠️ Agrégation rankings en temps réel (non scalable)**
```python
# apps/rankings/views.py
queryset = (
    CustomUser.objects
    .annotate(
        total_points=Sum('predictions__points_earned'),
        count_predictions=Count('predictions'),
        ...
    )
    .order_by('-total_points')
)
```
À 100 utilisateurs avec 200 matchs chacun, cette requête scanne 20 000 lignes à chaque chargement de page. Pour la V1 c'est acceptable ; au-delà de ~500 users actifs il faudra un cache ou un modèle `UserScore` dénormalisé (prévu V2).

**⚠️ Pas d'index sur les champs de filtrage fréquents**
Les champs `Match.status`, `Match.datetime`, `Match.is_hidden`, `Prediction.result_type` n'ont pas d'index DB explicites. Les requêtes de filtrage sur ces colonnes feront des full-table scans dès que la table grossit.

**⚠️ URL de l'admin import déclarée hors `admin.site.urls`**
```python
# ovalpronos/urls.py
path('admin/matches/competition/<int:competition_id>/import/', CompetitionImportView.as_view()),
```
Protégée par `@staff_member_required`, donc sécurisée. Doit rester documenté.

**ℹ️ `rankings` n'a pas de modèle**
L'app rankings calcule tout on-the-fly via annotations ORM. Intentionnel pour la V1, documenté comme point de scalabilité.

### 2.3 Flux HTMX (predictions)

```
User change input (score)
  → hx-trigger vérifie que home ET away sont remplis
  → hx-post → /predictions/submit/<match_pk>/
    → SubmitPredictionView.post()
      → Validation : match existant, non locked, has_odds
      → update_or_create(user=request.user, match=match)
      → render partial match_card.html (success state)
    → hx-swap="outerHTML" remplace la carte
```

---

## 3. Modèles & schéma de base de données

### 3.1 Schéma actuel (5 tables + Django system tables)

```
accounts_customuser
  ├── Hérite AbstractUser (username, email unique, password...)
  ├── display_name: VARCHAR(50)
  ├── avatar: ImageField (upload_to='avatars/')
  └── favorite_team: FK → matches_team (SET_NULL)

matches_competition
  ├── external_id: INT
  ├── name, code, country, season: VARCHAR
  ├── scoring_system: VARCHAR(10) ['COTES'|'FIXED']
  ├── good_gap_pts: INT (default=3)
  ├── is_active: BOOL
  └── UNIQUE(external_id, season)

matches_team
  ├── external_id: INT (unique)
  ├── slug: SlugField (unique) → static/img/teams/<slug>.png
  ├── name, short_name, country: VARCHAR
  └── logo_url: URLField (backup)

matches_match
  ├── external_id: INT (unique)
  ├── competition: FK → matches_competition (CASCADE)
  ├── home_team, away_team: FK → matches_team (CASCADE)
  ├── round, venue: VARCHAR
  ├── datetime: DATETIME (UTC)
  ├── status: VARCHAR ['SCHEDULED'|'IN_PLAY'|'FINISHED'|'POSTPONED'|'CANCELLED']
  ├── is_hidden: BOOL (default=False)
  ├── home_score, away_score: INT (nullable)
  ├── cote_home, cote_draw, cote_away: INT (nullable, ×10)
  └── created_at, updated_at: DATETIME (auto)

predictions_prediction
  ├── user: FK → accounts_customuser (CASCADE)
  ├── match: FK → matches_match (CASCADE)
  ├── predicted_home_score, predicted_away_score: INT
  ├── points_earned: INT (nullable — calculé après match)
  ├── result_type: VARCHAR(20) ['EXACT'|'GAP'|'WIN'|'MISS'|'CANCELLED'] (nullable)
  ├── created_at, updated_at: DATETIME (auto)
  └── UNIQUE(user, match)
```

### 3.2 Propriétés calculées (pas en DB)

| Modèle | Propriété | Logique |
|---|---|---|
| Match | `is_locked` | `now() >= self.datetime` |
| Match | `result` | compare home_score vs away_score |
| Match | `has_odds` | cote_home AND cote_draw AND cote_away non nuls |
| Match | `closes_soon` | kickoff dans < 24h et pas encore locked |
| Match | `time_until_kickoff` | `datetime - now()` |
| Prediction | `predicted_result` | compare predicted scores |
| Prediction | `predicted_cote` | cote correspondant au vainqueur prédit |
| Prediction | `potential_points` | dict {exact, gap, win} |

### 3.3 Problèmes de modèles

**⚠️ Aucun index DB explicite**
```python
# Manquants dans les Meta :
# Match.Meta
indexes = [
    models.Index(fields=['status', 'datetime']),
    models.Index(fields=['is_hidden', 'status']),
]
# Prediction.Meta
indexes = [
    models.Index(fields=['user', 'match']),
    models.Index(fields=['result_type']),
    models.Index(fields=['points_earned']),
]
```

**⚠️ `Match.is_locked` calculé en Python, pas en SQL**
Le filtrage `match.is_locked` dans les templates est fait match par match en Python. Pour les listes de matchs, il serait plus efficace d'annoter avec `Case/When` :
```python
Match.objects.annotate(
    is_locked=Case(When(datetime__lte=Now(), then=True), default=False, output_field=BooleanField())
)
```

**ℹ️ `on_delete=CASCADE` sur CustomUser → Prediction**
Si un utilisateur est supprimé, toutes ses prédictions disparaissent. À discuter selon les règles métier (garder l'historique ? → `PROTECT`).

**ℹ️ `logo_url` encore présent sur Competition et Team**
Les logos d'équipes utilisent maintenant les fichiers locaux `static/img/teams/<slug>.png`. Le champ `logo_url` n'est probablement plus utilisé dans les templates — à nettoyer ultérieurement.

---

## 4. Vues & logique métier

### 4.1 Inventaire des vues

| View | Auth | Méthode | Description |
|---|---|---|---|
| `HomeView` | Non | GET | Landing page |
| `RulesView` | Non | GET | Règles de scoring |
| `RegisterView` | Non | GET/POST | Inscription |
| `LoginView` (Django) | Non | GET/POST | Connexion |
| `LogoutView` (Django) | Oui | POST | Déconnexion |
| `PasswordReset*` (Django) | Non | GET/POST | Reset password |
| `PredictionsView` | Oui | GET | Page pronostics (tab competitions) |
| `SubmitPredictionView` | Oui | POST | Soumission pronostic (HTMX) |
| `RankingsView` | Oui | GET | Classement global |
| `sync_scores_api` | Token | POST | Endpoint sync GitHub Actions |
| `CompetitionImportView` | Staff | POST | Import admin manuel |

### 4.2 Logique de scoring (`apps/predictions/services.py`)

**Système COTES (défaut) :**

| Résultat | Points |
|---|---|
| Score exact | `cote_winner × 3` |
| Bon écart (≤ `good_gap_pts`) | `cote_winner × 2` |
| Bon vainqueur | `cote_winner × 1` |
| Mauvais vainqueur | `0` |
| Match annulé | `0` (result_type=CANCELLED) |

**Système FIXED :** 5 / 3 / 1 / 0 points fixes.

**Points forts :**
- Fonction pure testable sans DB
- Gère les cas edge : pas de cotes, match annulé, nul
- `update_fields=['points_earned', 'result_type']` évite les mises à jour parasites

**Points à surveiller :**
- Le calcul est déclenché dans `sync_scores_api` après sync — si la sync échoue à mi-chemin (ex: timeout API), certains matchs FINISHED n'auront pas leurs points calculés jusqu'à la prochaine sync.
- Pas de mécanisme de recalcul forcé en cas d'erreur partielle.

### 4.3 Service de sync (`apps/matches/services.py`)

```python
with transaction.atomic():
    for game in games:
        home_team, _ = Team.objects.update_or_create(...)
        away_team, _ = Team.objects.update_or_create(...)
        match, created = Match.objects.update_or_create(...)
```

**Points forts :**
- Transaction atomique ✅
- Timeout sur les requêtes HTTP (15s) ✅
- Gestion gracieuse des erreurs API (log + return None) ✅
- Validation des données reçues (`.get()` défensif, try/except KeyError) ✅

**Problèmes :**
- **N+1 implicite** : `update_or_create` = SELECT + INSERT/UPDATE par équipe et par match. 200 matchs ≈ 600 requêtes. Optimisable avec `bulk_create(update_conflicts=True)`.
- **Pas de retry** sur échec HTTP : si l'API rugby est down, les scores restent manquants jusqu'au prochain cron (2h).
- **Slug d'équipe** : si deux équipes produisent le même slug, `IntegrityError` non gérée crashe la transaction atomique.

---

## 5. Sécurité

### 5.1 🔴 CRITIQUE — Secrets exposés dans le dépôt

Le fichier `.env` contient des clés réelles :

```
SECRET_KEY=116u+q+aile7%uj$*0+g7c5l#znk*n@(k^*x$af@lv!#o38#93
APISPORTS_KEY=50dac8901838383060f41d8f0fc5584c
RAPIDAPI_KEY=7655c3139amsha73a38d74dd396cp14dfedjsn197c47c04b4b
```

**Actions immédiates :**
1. Vérifier que `.env` est dans `.gitignore`
2. Si ce dépôt a jamais été public : révoquer et régénérer ces clés
3. `SYNC_SECRET_TOKEN` non défini dans `.env` → l'endpoint accepte actuellement **n'importe quelle requête**

### 5.2 🔴 CRITIQUE — Endpoint sync sans `@csrf_exempt`

```python
# apps/matches/views.py (actuel)
@require_POST
def sync_scores_api(request):
    auth_header = request.headers.get('Authorization', '')
    expected = f'Bearer {settings.SYNC_SECRET_TOKEN}'
    if not settings.SYNC_SECRET_TOKEN or auth_header != expected:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
```

**Problème :** `CsrfViewMiddleware` est actif globalement. GitHub Actions ne peut pas obtenir un CSRF token → toutes les requêtes de sync reçoivent **403 Forbidden**.

**Fix requis :**
```python
from django.views.decorators.csrf import csrf_exempt
import hmac

@csrf_exempt
@require_POST
def sync_scores_api(request):
    auth_header = request.headers.get('Authorization', '').strip()
    expected = f'Bearer {settings.SYNC_SECRET_TOKEN}'
    if not settings.SYNC_SECRET_TOKEN or not hmac.compare_digest(auth_header, expected):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    ...
```

### 5.3 🟡 IMPORTANT — Settings HTTPS manquants pour la production

```python
# À ajouter dans settings.py (conditionné à DEBUG=False)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

Render fournit HTTPS automatiquement mais Django doit forcer la redirection HTTP→HTTPS.

### 5.4 🟡 IMPORTANT — Pas de rate limiting

**Endpoints vulnérables :**
- `/accounts/register/` → inscription en masse
- `/accounts/password-reset/` → email bombing
- `/api/sync-scores/` → brute force token (même si protégé par token)

**Solution recommandée :** `django-ratelimit`
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def register(request): ...
```

### 5.5 ✅ Points de sécurité corrects

| Aspect | Statut | Détail |
|---|---|---|
| Authentification vues | ✅ | `LoginRequiredMixin` sur toutes les vues protégées |
| CSRF protection | ✅ | Middleware actif + `{% csrf_token %}` dans tous les forms |
| Injections SQL | ✅ | ORM exclusif, zéro requête raw |
| XSS | ✅ | Auto-escaping Django, zéro `\|safe` dans les templates |
| Password validation | ✅ | 4 validators Django activés |
| Object-level permissions | ✅ | `user=request.user` force l'ownership des pronostics |
| Admin protection | ✅ | `@staff_member_required` sur import view |
| Transaction atomique | ✅ | `transaction.atomic()` sur sync |
| Match locking côté serveur | ✅ | `is_locked` vérifié dans `SubmitPredictionView` |
| Validation inputs | ✅ | Type, positif, non vide — validé dans la vue |
| Comparaison token | ⚠️ | Utiliser `hmac.compare_digest` (timing attack) |

---

## 6. Frontend & templates

### 6.1 Architecture frontend

**Stack :**
- Bootstrap 5.3.3 (CDN)
- Tabler Icons (CDN)
- HTMX 2.0.4 (CDN)
- Barlow font (Google Fonts CDN)
- Zéro JavaScript custom

**CSS :** `static/css/main.css` utilise des variables CSS (`--primary-color`, etc.) — architecture white-label ready pour V4.

### 6.2 Pattern HTMX (match card)

```html
<form hx-post="{% url 'predictions:submit' match.pk %}"
      hx-trigger="change[this.querySelector('[name=home]').value !== ''
                         && this.querySelector('[name=away]').value !== '']"
      hx-swap="outerHTML"
      hx-target="#match-card-{{ match.pk }}">
  {% csrf_token %}
  ...
</form>
```

**Points forts :**
- CSRF token inclus ✅
- Validation serveur obligatoire ✅
- `hx-disabled-elt="this"` évite le double-submit ✅

**Problèmes :**
- **Pas d'indicateur de chargement** (spinner HTMX non configuré)
- **Pas de gestion d'erreur réseau** : si le POST échoue (500, timeout), HTMX ne montre rien. Ajouter `hx-on::response-error`.

### 6.3 CDN — dépendances externes

Tous les assets JS/CSS viennent de CDN publics. Risques :
1. **Disponibilité** : si unpkg/jsdelivr est down, l'app est inutilisable
2. **Intégrité** : aucun `integrity="sha384-..."` — un CDN compromis peut injecter du code

**Recommandation** : ajouter `integrity` + `crossorigin` sur chaque CDN link, ou vendor les assets dans `static/vendor/`.

### 6.4 Audit XSS — templates

| Template | Variables utilisateur | Escaping | Risque |
|---|---|---|---|
| base.html | `user.get_display_name` | Auto | ✅ Aucun |
| match_card.html | Tous champs modèle | Auto | ✅ Aucun |
| rankings/index.html | `entry.user.get_display_name` | Auto | ✅ Aucun |
| accounts/*.html | Formulaires Django | Auto | ✅ Aucun |
| email template | Aucune donnée user | `autoescape off` (plaintext) | ✅ Safe |

**Résultat : Zéro risque XSS détecté.**

---

## 7. Performance & scalabilité

### 7.1 Requêtes N+1 dans les templates

La page predictions accède à `match.home_team.name`, `match.away_team.name`, `match.competition.name`. Sans `select_related`, chaque accès génère une requête SQL séparée.

**Vérification à faire dans `PredictionsView.get_context_data()` :**
```python
# Requis :
matches = Match.objects.select_related(
    'home_team', 'away_team', 'competition'
).filter(...)
```

### 7.2 Requête rankings (agrégation à chaque page)

```python
queryset = CustomUser.objects.annotate(
    total_points=Sum('predictions__points_earned'),
    count_exact=Count('predictions', filter=Q(predictions__result_type='EXACT')),
    # ...
).order_by('-total_points')
```

**Complexité :** O(users × predictions) à chaque GET /rankings/.

| Volume | Impact estimé |
|---|---|
| < 100 users | Imperceptible |
| ~500 users × 100 matchs | ~50 000 rows — temps de réponse perceptible |
| > 1 000 users | Problématique |

**Solutions par stade :**
- **V1** : Cache Django 60s (`cache.get/set`)
- **V2** : Modèle `UserScore` dénormalisé mis à jour via signal `post_save` sur Prediction

### 7.3 Sync API — N+1 sur update_or_create

200 matchs = ~600 requêtes (SELECT + INSERT/UPDATE par équipe et par match).

**Optimisation possible :**
```python
Match.objects.bulk_create(
    new_matches,
    update_conflicts=True,
    update_fields=['home_score', 'away_score', 'status', 'updated_at']
)
```

### 7.4 Indexes DB manquants

| Table | Colonne(s) | Requête concernée | Impact |
|---|---|---|---|
| matches_match | `status`, `datetime` | Filtrage + tri principal | Élevé |
| matches_match | `is_hidden`, `status` | Exclusion UI | Moyen |
| predictions_prediction | `result_type` | Annotations rankings | Élevé |
| predictions_prediction | `points_earned` | SUM rankings | Élevé |

**À ajouter dans les Meta :**
```python
# Match.Meta
indexes = [
    models.Index(fields=['status', 'datetime']),
    models.Index(fields=['is_hidden', 'status']),
]

# Prediction.Meta
indexes = [
    models.Index(fields=['result_type']),
    models.Index(fields=['points_earned']),
]
```

### 7.5 Images équipes

26 PNG locaux dans `static/img/teams/`, servis par WhiteNoise avec compression. ✅

Amélioration optionnelle : conversion WebP (~70% de réduction), Pillow est déjà disponible.

### 7.6 Statiques en production

WhiteNoise sur Render (free tier) est acceptable pour la beta. Sur Hetzner V2, Cloudflare en reverse proxy gratuit apporte le cache CDN des statiques sans coût supplémentaire.

---

## 8. Tests

### 8.1 Couverture actuelle

**Fichier :** `apps/predictions/tests.py` — 11 tests `SimpleTestCase` + `MagicMock`

| Cas testé | Statut |
|---|---|
| Score exact | ✅ |
| Bon écart (dans le seuil `good_gap_pts`) | ✅ |
| Bon vainqueur (écart > seuil) | ✅ |
| Mauvais vainqueur | ✅ |
| Match annulé | ✅ |
| Pas de cotes | ✅ |
| Scénario nul | ✅ |

### 8.2 Tests manquants (obligatoires avant prod)

| Catégorie | Test manquant | Priorité |
|---|---|---|
| Intégration | `SubmitPredictionView` : POST valide, POST match locked, POST sans odds | 🔴 |
| Intégration | Ownership enforcement (user A ne peut pas écraser le prono de user B) | 🔴 |
| Intégration | `sync_scores_api` : token valide / invalide / manquant | 🔴 |
| Modèle | `Match.has_odds`, `is_locked`, `result` | 🟡 |
| Modèle | `Prediction.predicted_cote`, `potential_points` | 🟡 |
| Service | `sync_competition_matches()` avec fixture API mockée | 🟡 |
| E2E | register → predict → sync → classement | 🟢 |

### 8.3 Organisation recommandée

```
apps/predictions/tests/
  test_services.py     # calculate_points() (déplacer depuis tests.py)
  test_views.py        # SubmitPredictionView, PredictionsView
  test_models.py       # Propriétés Match et Prediction

apps/matches/tests/
  test_services.py     # sync_competition_matches() (API mockée)
  test_views.py        # sync_scores_api endpoint

apps/accounts/tests/
  test_views.py        # Register, login flow
```

---

## 9. Déploiement & CI/CD

### 9.1 render.yaml

**Points forts :**
- `SECRET_KEY: generateValue: true` → auto-généré par Render ✅
- `DEBUG: false` ✅
- Clés sensibles non dans le YAML (`sync: false`) ✅
- `gunicorn ovalpronos.wsgi:application` ✅

**Manques :**
- Pas de `conn_max_age` pour PostgreSQL (reconnexion à chaque requête sur Render free tier)
- Pas de health check endpoint

### 9.2 GitHub Actions — Sync cron

```yaml
schedule:
  - cron: '0 */2 * * *'      # Toutes les 2h
  - cron: '*/15 * * * 6,0'   # Toutes les 15min le week-end

steps:
  - run: |
      curl -X POST "${{ secrets.APP_URL }}/api/sync-scores/" \
        -H "Authorization: Bearer ${{ secrets.SYNC_SECRET_TOKEN }}" \
        --fail --silent --show-error
```

**Points forts :** `--fail` fait échouer le job sur 4xx/5xx ✅

**Problèmes :**
- **L'endpoint sync reçoit 403** à cause du bug CSRF (§5.2) — le cron ne fonctionne pas actuellement
- Pas de notification d'échec (email, Slack)
- Pas de retry automatique sur timeout API

### 9.3 Checklist avant déploiement

#### 🔴 Bloquants
- [ ] Fix `@csrf_exempt` + `hmac.compare_digest` sur `sync_scores_api`
- [ ] Définir `SYNC_SECRET_TOKEN` (≥ 32 chars aléatoires)
- [ ] Ajouter `.env` au `.gitignore`
- [ ] Vérifier l'historique git pour les secrets
- [ ] Ajouter les settings HTTPS (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, etc.)

#### 🟡 Importants
- [ ] Vérifier `select_related` dans `PredictionsView`
- [ ] Ajouter les indexes DB manquants
- [ ] Tester le flux sync manuellement : `python manage.py sync_matches`
- [ ] Vérifier que `compilemessages` tourne dans la build Render
- [ ] Activer les tests dans CI

#### 🟢 Améliorations V2
- [ ] Rate limiting (`django-ratelimit`)
- [ ] Cache rankings (Django cache framework)
- [ ] Modèle `UserScore` dénormalisé
- [ ] `integrity` sur les CDN links
- [ ] Monitoring / alertes sync failures

---

## 10. Dépendances

### 10.1 État actuel

| Package | Version | Statut |
|---|---|---|
| Django | 5.1.4 | ✅ À jour |
| psycopg2-binary | 2.9.10 | ✅ OK (binary acceptable pour Render) |
| dj-database-url | 2.3.0 | ✅ À jour |
| python-decouple | 3.8 | ✅ |
| gunicorn | 23.0.0 | ✅ |
| requests | 2.32.3 | ✅ |
| whitenoise | 6.8.2 | ✅ |
| django-crispy-forms | 2.3 | ✅ |
| crispy-bootstrap5 | 2024.10 | ✅ |
| Pillow | 12.2.0 | ✅ |
| pytz | 2024.2 | ⚠️ Redondant (Django 4+ gère les timezones nativement) |

### 10.2 À ajouter

| Package | Pourquoi | Priorité |
|---|---|---|
| `django-ratelimit` | Rate limiting endpoints sensibles | 🟡 V1 |
| `sentry-sdk` | Error tracking en production | 🟡 V1 |

---

## 11. Matrice de risques

| # | Risque | Probabilité | Impact | Priorité | Action |
|---|---|---|---|---|---|
| R1 | Secrets `.env` exposés dans git | Élevée | Critique | 🔴 | Révoquer clés, vérifier gitignore |
| R2 | Sync cron en 403 (bug CSRF) | Certaine | Élevé | 🔴 | `@csrf_exempt` + définir token |
| R3 | N+1 queries page predictions | Élevée | Moyen | 🟡 | `select_related` |
| R4 | Rankings lents à l'échelle | Moyenne | Moyen | 🟡 | Cache V1, UserScore V2 |
| R5 | Pas de rate limiting | Faible (beta) | Moyen | 🟡 | `django-ratelimit` avant ouverture |
| R6 | CDN down → app inutilisable | Faible | Élevé | 🟡 | Vendor les assets |
| R7 | Pas de tests intégration | Certaine | Moyen | 🟡 | Compléter avant prod |
| R8 | API rugby timeout sans retry | Moyenne | Faible | 🟢 | Retry + alerte cron |
| R9 | Slug collision équipes | Très faible | Moyen | 🟢 | Gérer IntegrityError dans sync |

---

## 12. Roadmap recommandée

### Sprint 0 — Sécurité (avant tout déploiement)
1. Vérifier `.gitignore` pour `.env`
2. Révoquer/régénérer les clés si le dépôt a été public
3. Fix `@csrf_exempt` + `hmac.compare_digest` sur `sync_scores_api`
4. Définir `SYNC_SECRET_TOKEN` (≥ 32 chars aléatoires)
5. Ajouter les settings HTTPS dans `settings.py`

### Sprint 1 — Stabilisation V1 beta
1. Vérifier et ajouter `select_related` dans `PredictionsView`
2. Ajouter les indexes DB manquants (via nouvelle migration)
3. Compléter la suite de tests (vues, endpoint, modèles)
4. Activer `python manage.py test` dans le pipeline CI
5. Ajouter `django-ratelimit` sur register / password-reset
6. Ajouter `sentry-sdk` pour le tracking d'erreurs prod

### Sprint 2 — Performance
1. Cache rankings (Django cache framework, TTL 60s)
2. Optimiser sync avec `bulk_create(update_conflicts=True)`
3. Modèle `UserScore` dénormalisé + signal `post_save`
4. Vendoriser les assets CDN dans `static/vendor/`

### V2 — Fonctionnalités
1. App `leagues` (ligues privées, invitations par code)
2. Classements par compétition et par ligue
3. Champions Cup & 6 Nations dans la sync
4. Profil utilisateur : historique, stats personnelles
5. Migration Render → Hetzner CX22 (~4€/mois)

---

*Audit réalisé le 2026-05-22 · Oval'Pronos stade développement actif*
