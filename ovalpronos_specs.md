# Oval'Pronos — Spécifications fonctionnelles complètes
*Version 3.0 — Migration Bubble.io → Django*
*Rédigé à partir de l'app Bubble originale — Mai 2026*

---

## 1. Vue d'ensemble

**Oval'Pronos** est une application web de pronostics rugby, ouverte au public, permettant à des utilisateurs de prédire les scores de matchs et de s'affronter dans un classement général ou au sein de ligues privées entre amis.

**Tagline :** *"Tu sais pas plaquer, viens pronostiquer"*
**Mascotte :** Un phacochère bleu (logo SVG disponible)
**Langue de l'interface :** Français par défaut, multilingue prévu (EN ensuite)
**Langue du code et des URLs :** Anglais exclusivement

---

## 2. Stack technique retenue

| Composant | Choix | Justification |
|---|---|---|
| Framework | Django 5.x | Auth, admin, ORM, forms natifs |
| BDD | PostgreSQL (prod) / SQLite (dev) | Robuste, contraintes natives |
| Frontend | Django Templates + Bootstrap 5 + HTMX | Pas de SPA, rendu serveur |
| Internationalisation | Django i18n (gettext) | Multilingue FR/EN natif |
| Scores sportifs | RapidAPI (cron V1) → Lambda AWS reconstruite (V2) | Simple à démarrer |
| Cotes | Saisie manuelle admin (V1) → API odds (V2) | |
| Email transactionnel | SMTP Ionos (inclus avec ovalpronos.com) | `noreply@ovalpronos.com`, 0€ |
| Déploiement | Render (V1) → Ionos VPS (V2) | Voir §16 |
| Assets statiques | WhiteNoise | Intégré Django |

---

## 3. Pages de l'application

| Page Bubble | URL Django (EN) | Accès | Description |
|---|---|---|---|
| `index` | `/` | Public | Landing page marketing |
| `login` | `/accounts/login/` | Non-auth | Connexion |
| `signup` | `/accounts/register/` | Non-auth | Inscription |
| `reset_pw` | `/accounts/password-reset/` | Non-auth | Reset mot de passe |
| `pronos` | `/predictions/` | Auth requis | Saisie des pronostics |
| `classement` | `/rankings/` | Auth requis | Classements |
| `profil` | `/accounts/profile/` | Auth requis | Profil + ligues |
| `rules` | `/rules/` | Public | Explication du barème |
| — | `/leagues/join/<code>/` | Auth requis* | Rejoindre une ligue via lien |
| `404` | Automatique Django | — | Page d'erreur 404 |

*Si non connecté → redirect `/accounts/login/?next=/leagues/join/<code>/` → auto-join après connexion (voir §10.4)

---

## 4. Internationalisation (i18n)

### 4.1 Configuration Django

```python
# settings.py
LANGUAGE_CODE = 'fr'

LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
]

MIDDLEWARE += ['django.middleware.locale.LocaleMiddleware']
USE_I18N = True
LOCALE_PATHS = [BASE_DIR / 'locale']
```

### 4.2 Règles d'implémentation

- Tout le **code Python** : en anglais (noms de variables, fonctions, modèles, commentaires)
- Toutes les **URLs** : en anglais
- Tout le **texte affiché** : via `{% trans "..." %}` ou `_("...")`
- `python manage.py makemessages -l fr` génère les fichiers `.po`
- Sélecteur de langue EN/FR dans le header (V2)

### 4.3 Exemple d'usage

```html
{% load i18n %}
<h1>{% trans "Predict upcoming matches" %}</h1>
```

```python
from django.utils.translation import gettext_lazy as _
error_msg = _("This match is already locked.")
```

---

## 5. Modèle de données

### 5.1 `CustomUser` (étend AbstractUser)

| Champ | Type | Contraintes | Notes |
|---|---|---|---|
| `email` | EmailField | unique, obligatoire | Identifiant de connexion |
| `first_name` | CharField | obligatoire | Prénom |
| `last_name` | CharField | obligatoire | Nom |
| `display_name` | CharField(50) | optionnel | Surnom affiché dans le classement |
| `favorite_team` | FK → Team | null, blank | Équipe favorite (dropdown) |
| `avatar` | ImageField | optionnel | Photo de profil |

**Note bootstrap :** `favorite_team` est nullable pour permettre l'inscription avant que les équipes soient importées via RapidAPI.

### 5.2 `Competition`

| Champ | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | ID RapidAPI, unique |
| `name` | CharField | "Top 14", "6 Nations", etc. |
| `code` | CharField | "TOP14", "SIX_NATIONS", etc. |
| `season` | CharField | "2024-2025" |
| `is_active` | BooleanField | Compétition de la saison en cours |
| `scoring_system` | CharField | COTES ou FIXED (voir §7) |
| `good_gap_pts` | IntegerField | Écart max pour bonus ×2 (défaut: 3) |

**Compétitions V1 :** Top 14, Champions Cup, 6 Nations
**Compétitions V2 :** Pro D2, Nationale

**Saison active :** les classements sont filtrés sur `is_active=True`. Une seule compétition par code peut être active à la fois.

### 5.3 `Team`

| Champ | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | ID RapidAPI, unique |
| `name` | CharField | "Clermont", "Stade Toulousain" |
| `short_name` | CharField | "ASM", "STA" |
| `slug` | SlugField | "clermont", "stade-toulousain" — clé pour le logo local |
| `country` | CharField | Pour équipes nationales |

**Logos :** fichiers SVG locaux stockés dans `static/img/teams/<slug>.svg`. Les logos sont personnalisés avec le phacochère intégré au blason de chaque équipe. Pas d'URL externe — la source de vérité est le fichier local.

```html
<!-- Dans les templates -->
<img src="{% static 'img/teams/'|add:match.home_team.slug|add:'.svg' %}"
     alt="{{ match.home_team.name }}" width="38" height="38">
```

### 5.4 `Match`

| Champ | Type | Notes |
|---|---|---|
| `external_id` | IntegerField | ID RapidAPI, unique |
| `competition` | FK → Competition | |
| `home_team` | FK → Team | |
| `away_team` | FK → Team | |
| `round` | CharField | En anglais : "Round 12", "Semi-final", "Final" |
| `datetime` | DateTimeField | Stocké en UTC, affiché en heure Paris |
| `venue` | CharField | Stade (optionnel) |
| `status` | CharField | SCHEDULED / IN_PLAY / FINISHED / POSTPONED / CANCELLED |
| `home_score` | IntegerField | null si pas joué |
| `away_score` | IntegerField | null si pas joué |
| `cote_home` | IntegerField | null si pas encore saisie |
| `cote_draw` | IntegerField | null si pas encore saisie |
| `cote_away` | IntegerField | null si pas encore saisie |

**Règle cotes nulles :** si l'une des 3 cotes est null, la carte de match affiche "Odds coming soon" et masque entièrement le formulaire de saisie. Le joueur ne peut pas pronostiquer tant que les cotes ne sont pas renseignées.

**Propriétés calculées :**
- `is_locked` → `now() >= datetime`
- `has_odds` → `cote_home is not None and cote_draw is not None and cote_away is not None`
- `result` → 'home' / 'away' / 'draw' / None
- `closes_soon` → `0 < (datetime - now()) < 24h`
- `time_until_kickoff` → "2h14", "3d", "45min" (string formatée)

```python
@property
def closes_soon(self):
    delta = self.datetime - timezone.now()
    return timedelta(0) < delta < timedelta(hours=24)

@property
def time_until_kickoff(self):
    delta = self.datetime - timezone.now()
    if delta.total_seconds() <= 0:
        return ""
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes}min"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours < 24:
        return f"{hours}h{minutes:02d}" if minutes else f"{hours}h"
    return f"{hours // 24}d"
```

**Cas CANCELLED :** si un match passe à CANCELLED après des pronostics soumis → `points_earned = 0`, `result_type = 'CANCELLED'` pour tous les `Prediction` associés. Les compteurs `UserScore` sont mis à jour (count_prediction++ mais 0 pts).

### 5.5 `Prediction`

| Champ | Type | Notes |
|---|---|---|
| `user` | FK → CustomUser | |
| `match` | FK → Match | |
| `predicted_home_score` | IntegerField | Score prédit domicile |
| `predicted_away_score` | IntegerField | Score prédit extérieur |
| `points_earned` | IntegerField | null = match pas terminé / 0 = MISS ou CANCELLED |
| `result_type` | CharField | EXACT / GAP / WIN / MISS / CANCELLED / null |

**Contrainte BDD :** `UNIQUE(user, match)` — un seul prono par joueur par match.

### 5.6 `League` (ligue privée)

| Champ | Type | Notes |
|---|---|---|
| `name` | CharField | Nom de la ligue |
| `code` | CharField(5) | Code unique auto-généré (ex: "X7K2P") |
| `creator` | FK → CustomUser | null si créateur supprimé |
| `members` | ManyToMany → CustomUser | Membres actifs |
| `competition` | FK → Competition | null = toutes compétitions actives |
| `is_active` | BooleanField | False = ligue archivée |
| `created_at` | DateTimeField | |

### 5.7 `UserScore` (cache classement)

| Champ | Type | Notes |
|---|---|---|
| `user` | FK → CustomUser | |
| `competition` | FK → Competition | null = classement global |
| `league` | FK → League | null = classement global ou par compétition |
| `season` | CharField | "2024-2025" — scope explicite |
| `count_exact` | IntegerField | Nb de scores exacts |
| `count_gap` | IntegerField | Nb de bons écarts |
| `count_win` | IntegerField | Nb de bons vainqueurs |
| `count_cancelled` | IntegerField | Nb de matchs annulés |
| `count_prediction` | IntegerField | Nb total de pronos joués |
| `points` | IntegerField | Total des points |
| `rank` | IntegerField | Rang calculé |

**Contrainte PostgreSQL :** utiliser `UniqueConstraint` avec des index partiels pour gérer les NULL :

```python
class Meta:
    constraints = [
        # Classement global (competition=null, league=null)
        models.UniqueConstraint(
            fields=['user', 'season'],
            condition=Q(competition__isnull=True, league__isnull=True),
            name='unique_userscore_global'
        ),
        # Classement par compétition (league=null)
        models.UniqueConstraint(
            fields=['user', 'competition', 'season'],
            condition=Q(league__isnull=True, competition__isnull=False),
            name='unique_userscore_competition'
        ),
        # Classement par ligue
        models.UniqueConstraint(
            fields=['user', 'league', 'season'],
            condition=Q(league__isnull=False),
            name='unique_userscore_league'
        ),
    ]
```

---

## 6. Page `predictions/` — Saisie des pronostics

### 6.1 Layout général

```
[Logo]  Predict upcoming matches     [🏆 Rank #12 · 847 pts]

( ) Upcoming    ( ) Live    ( ) Past

┌─────────────────────────────────────────────────────────┐
│ Top 14 — Round 22              ⏱ Closes in 2h14        │ ← card-meta
├─────────────────────────────────────────────────────────┤
│ [Logo] Clermont   07/01 17:00   Perpignan [Logo]        │
│ [  5  ]  11    [  240  ]    63   [  20  ]               │
└─────────────────────────────────────────────────────────┘

▓▓▓▓▓▓▓▓░░░░  8 / 14 predictions submitted

[Faites un don aux marcassins]
```

### 6.2 Améliorations UI vs Bubble

- **Rang en header** : "🏆 Rank #12 · 847 pts" visible en permanence quand connecté
- **Groupement** par compétition et journée (pas une liste plate)
- **Countdown** dans la card-meta de chaque carte
- **Barre de progression** par journée : "8/14 predictions submitted"
- **Sauvegarde auto HTMX** — pas de bouton "Valider"
- **États vides** avec mascotte : "No upcoming matches — check back on Friday!"
- **Mobile-first** (Bubble était desktop uniquement)

### 6.3 Carte de match — comportement complet

#### État 1 : SCHEDULED, cotes disponibles, pas encore de prono

```
┌──────────────────────────────────────────────────────┐
│ Top 14 — Round 22              ⏱ Closes in 2h14     │
├──────────────────────────────────────────────────────┤
│ [Logo] Clermont   07/01 17:00   Perpignan  [Logo]    │
│ [    ]  11        [ 240 ]        63        [    ]    │
│  input  ↑cote_home ↑cote_draw  ↑cote_away  input     │
└──────────────────────────────────────────────────────┘
```
- Champs de saisie actifs
- Slot gauche = `cote_home`, badge central = `cote_draw`, slot droit = `cote_away`

#### État 2 : SCHEDULED, cotes disponibles, prono saisi

```
│ [  5  ]  11    [ 240 ]    63   [  20  ]   │
│  prédit  cote   draw      cote   prédit    │
```
- Champs pré-remplis avec les valeurs prédites, modifiables

#### État 3 : cotes non saisies (null)

```
┌──────────────────────────────────────────────────────┐
│ Top 14 — Round 22                         —         │
├──────────────────────────────────────────────────────┤
│ [Logo] Clermont   07/01 17:00   Perpignan  [Logo]    │
│         ⏳ Odds coming soon                          │
└──────────────────────────────────────────────────────┘
```
- Formulaire entièrement masqué
- Message "Odds coming soon" centré

#### État 4 : verrouillé (IN_PLAY ou datetime passée)

```
│ [  5  ]  11    [ 240 ]    63   [  20  ]   │
```
- Champs grisés, non modifiables (readonly côté serveur)
- Cotes affichées (pas encore de score réel)

#### État 5 : FINISHED

```
│ [  5  ]  17    [ 189 ]    22   [  20  ]   │
│  prédit  réel  👑 pts    réel    prédit   │
```
- Cotes remplacées par scores réels
- Badge central = points gagnés avec couleur selon result_type
- 🔴 MISS → 0, 🟢 WIN → cote×1, 🟣 GAP → cote×2, 👑 EXACT → cote×3

#### État 6 : CANCELLED

```
│ [  5  ]   —    [  ✗  ]    —    [  20  ]   │
```
- Badge gris avec ✗
- Tooltip : "Match cancelled — 0 points awarded"

### 6.4 Filtres

Radio buttons : **Upcoming** / **Live** / **Past** — "Upcoming" par défaut.

---

## 7. Système de scoring

### 7.1 Principe général

Les cotes sont stockées en base comme **entiers = cote Unibet × 10**.
Exemple : Perpignan à 6.3 chez Unibet → stocké `63`.
La cote applicable est celle du **vainqueur réel**.

### 7.2 Algorithme

```python
def calculate_points(prediction, match):
    """
    Returns (points: int, result_type: str) or None if not finished.
    result_type: 'EXACT' | 'GAP' | 'WIN' | 'MISS' | 'CANCELLED'
    """
    if match.status == 'CANCELLED':
        return 0, 'CANCELLED'

    if match.status != 'FINISHED':
        return None

    if not match.has_odds:
        return None  # Ne devrait pas arriver (prono bloqué sans cotes)

    real_home = match.home_score
    real_away = match.away_score
    pred_home = prediction.predicted_home_score
    pred_away = prediction.predicted_away_score

    def sign(n):
        return 1 if n > 0 else (-1 if n < 0 else 0)

    real_gap = real_home - real_away
    pred_gap = pred_home - pred_away

    # Cote du vainqueur réel
    if real_gap > 0:
        cote = match.cote_home
    elif real_gap < 0:
        cote = match.cote_away
    else:
        cote = match.cote_draw

    # Cas nul : prédit nul + résultat nul → bon écart minimum
    if real_gap == 0 and pred_gap == 0:
        if pred_home == real_home and pred_away == real_away:
            return cote * 3, 'EXACT'
        return cote * 2, 'GAP'

    # Mauvais vainqueur
    if sign(pred_gap) != sign(real_gap):
        return 0, 'MISS'

    # Score exact → ×3
    if pred_home == real_home and pred_away == real_away:
        return cote * 3, 'EXACT'

    # Bon écart de gap ≤ N pts → ×2
    if abs(pred_gap - real_gap) <= match.competition.good_gap_pts:
        return cote * 2, 'GAP'

    # Bon vainqueur → ×1
    return cote * 1, 'WIN'
```

### 7.3 Règle match nul

- Prédit nul + exact → ×3 👑
- Prédit nul + scores différents → ×2 🟣 (nul si rare, toujours récompensé)
- Prédit vainqueur → 0 🔴

### 7.4 Règle match annulé

`points_earned = 0`, `result_type = 'CANCELLED'`. Le prono est conservé mais ne compte pas. `count_cancelled` incrémenté dans `UserScore`.

### 7.5 Tableau récapitulatif

Match réel : Clermont 17 — Perpignan 22 (gap = -5, cote Perpignan = 63)

| Pronostic | Gap prédit | Écart de gaps | Résultat | Points |
|---|---|---|---|---|
| 17 - 22 | -5 | 0 | Score exact | 63 × 3 = **189** 👑 |
| 15 - 22 | -7 | 2 ≤ 3 | Bon écart | 63 × 2 = **126** 🟣 |
| 14 - 25 | -11 | 6 > 3 | Bon vainqueur | 63 × 1 = **63** 🟢 |
| 20 - 10 | +10 | — | Mauvais | **0** 🔴 |

### 7.6 Mode FIXED (alternatif)

```
Score exact   → 5 pts
Bon écart     → 3 pts
Bon vainqueur → 1 pt
Mauvais       → 0 pt
```
Sélectionnable via `Competition.scoring_system`.

### 7.7 Tests unitaires obligatoires (V1)

Le scoring est le cœur métier. Tous les cas du tableau §7.5 + cas nul + cas annulé + cas cotes null doivent être couverts avant mise en production.

```python
# apps/predictions/tests.py
class ScoringTests(TestCase):
    def test_exact_score(self): ...
    def test_good_gap(self): ...
    def test_good_gap_boundary(self): ...  # exactement 3 pts d'écart
    def test_good_gap_over(self): ...      # 4 pts d'écart → WIN seulement
    def test_win_only(self): ...
    def test_miss(self): ...
    def test_draw_exact(self): ...
    def test_draw_gap(self): ...
    def test_draw_miss(self): ...
    def test_cancelled(self): ...
    def test_no_odds(self): ...            # cotes null → None
```

---

## 8. Page `rankings/` — Classement

### 8.1 Layout

Deux colonnes :
- **Gauche :** "My leagues" → liste des ligues de l'utilisateur
- **Droite :** "Global ranking" → classement global saison active

### 8.2 Classement de proximité

Affichage prioritaire :
1. Top 3 global (toujours visible)
2. `---` séparateur si le joueur n'est pas dans le top 3
3. Les 3 joueurs juste au-dessus du joueur connecté
4. **Le joueur connecté** (surligné)
5. Les 3 joueurs juste en-dessous

### 8.3 Vues disponibles

1. **Global** — tous joueurs, saison active, trié par `points` DESC
2. **By competition** — filtre Top 14 / Champions Cup / 6 Nations
3. **League** — membres d'une ligue privée uniquement

### 8.4 Scope saison

Tous les classements sont filtrés sur la saison active (`Competition.is_active=True` ou `UserScore.season = current_season`). Les données des saisons passées sont conservées mais non affichées par défaut.

### 8.5 Colonnes

| Rang | Pseudo | Points | Pronos | Exacts | Bons écarts | Bons vainqueurs |

---

## 9. Ligues privées (`League`)

### 9.1 Création

- Accessible depuis `/accounts/profile/`
- Champs : nom de la ligue, compétition liée (optionnel)
- Code 5 caractères alphanumérique auto-généré (ex: `X7K2P`)
- Le créateur devient automatiquement membre

### 9.2 Rejoindre une ligue

**Via lien direct :** `/leagues/join/X7K2P/`
**Via formulaire :** champ "League code" sur la page profil

### 9.3 Flux non-authentifié

```
1. User clique sur /leagues/join/X7K2P/ sans être connecté
2. Redirect → /accounts/login/?next=/leagues/join/X7K2P/
3. User se connecte (ou s'inscrit)
4. Django redirige automatiquement vers /leagues/join/X7K2P/
5. La vue détecte que c'est un GET authentifié → auto-join → redirect profil
```

Le paramètre `next` est géré nativement par `LoginView` de Django.

### 9.4 Partage

Bouton "Copy invite link" → copie `https://ovalpronos.com/leagues/join/X7K2P/` dans le presse-papier.

### 9.5 Règles de gestion

- Un utilisateur peut créer plusieurs ligues et rejoindre plusieurs ligues
- Seul le créateur peut supprimer une ligue (soft-delete : `is_active=False`)
- Si le créateur supprime son compte, la ligue reste active (`creator=null`)
- Pas de limite de membres documentée pour l'instant

---

## 10. Page `accounts/profile/` — Profil

### 10.1 Informations affichées

- Prénom, Nom, Surnom, Équipe favorite, Avatar
- Stats saison active : points totaux, rang global, pronos joués
- Détail : nb exacts, bons écarts, bons vainqueurs, % de réussite, nb annulés

### 10.2 Résumé de journée

Après chaque journée, encart affiché pendant 48h :
*"This weekend you scored 189 pts 🔥 — you're up 3 places!"*

### 10.3 Actions disponibles

- Modifier surnom, équipe favorite, avatar
- Voir ses ligues (code + lien de partage)
- Créer une nouvelle ligue
- Rejoindre une ligue (saisie du code)
- Quitter une ligue

---

## 11. Page `rules/` — Règles du jeu

### 11.1 Titre : "Flexion, liez, jeu"

### 11.2 Contenu

1. Explication du formulaire de saisie
2. Explication des cotes (cote forte = résultat improbable = plus de points à gagner)
3. Les 4 niveaux illustrés avec des vraies cartes match :
   - 🟢 Bon vainqueur → cote × 1
   - 🟣 Bon écart de gap (≤ 3 pts) → cote × 2
   - 👑 Score exact → cote × 3
   - 🔴 Mauvais → 0
4. Compétitions disponibles : Top 14, 6 Nations, Champions Cup, Pro D2 (V2), Nationale (V2)
5. Lien de contact

---

## 12. Page `index` — Landing page

### 12.1 Sections

1. **Hero** : Logo + "Se connecter" + "S'inscrire" (CTA `--color-accent`)
   - Titre : "Tu sais pas plaquer, viens pronostiquer"

2. **Section 2** : "Oval'Pronos, c'est simple et c'est drôle"
   - Image gauche + texte droit

3. **Section 3** : "Garde tout pour la daronne"
   - Mise en avant des ligues privées

### 12.2 Design system

#### Palette de couleurs

| Variable CSS | Hex | Usage |
|---|---|---|
| `--color-primary` | `#2B3467` | Bleu marine — titres, header, footer, boutons |
| `--color-light` | `#BAD7E9` | Bleu clair — fonds, hover, accents secondaires |
| `--color-background` | `#FCFFF9` | Fond général (blanc cassé légèrement vert) |
| `--color-accent` | `#EB455F` | Rouge/rose — CTAs, alertes |
| `--color-badge-exact` | `#F5C542` | Or — badge score exact + couronne 👑 |
| `--color-badge-gap` | `#9334B6` | Violet — badge bon écart |
| `--color-badge-win` | `#A8E063` | Vert — badge bon vainqueur |
| `--color-badge-miss` | `#FF2E2E` | Rouge vif — badge mauvais pronostic |
| `--color-text-on-primary` | `#FCFFF9` | Texte sur fond sombre |
| `--color-text` | `#2B3467` | Texte standard |

```css
:root {
  --color-primary:       #2B3467;
  --color-light:         #BAD7E9;
  --color-background:    #FCFFF9;
  --color-accent:        #EB455F;
  --color-badge-exact:   #F5C542;
  --color-badge-gap:     #9334B6;
  --color-badge-win:     #A8E063;
  --color-badge-miss:    #FF2E2E;
  --color-text-on-primary: #FCFFF9;
  --color-text:          #2B3467;
}
```

**Règle White Label :** zéro valeur hex en dur dans les templates. Tout passe par ces variables pour permettre la personnalisation par tenant en V4.

#### Typographie

- **Police :** Barlow (Google Fonts)
- **Titres :** Barlow 600/700, couleur `--color-primary`
- **Corps :** Barlow 400
- **Boutons :** Barlow 600
- **Scores / badges :** Barlow 700

```html
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### 12.3 Composant : carte de match

#### Structure HTML complète

```html
<div class="match-card">

  <!-- Bande de contexte -->
  <div class="card-meta">
    <span class="card-meta-label">
      {{ match.competition.name }} — {{ match.round }}
    </span>
    {% if match.status == 'FINISHED' %}
      <span class="card-meta-status finished">{% trans "Finished" %}</span>
    {% elif match.status == 'CANCELLED' %}
      <span class="card-meta-status cancelled">{% trans "Cancelled" %}</span>
    {% elif match.status == 'IN_PLAY' %}
      <span class="card-meta-status live">{% trans "Live" %}</span>
    {% elif match.is_locked %}
      <span class="card-meta-status locked">{% trans "Locked" %}</span>
    {% else %}
      <span class="card-meta-status {% if match.closes_soon %}urgent{% endif %}">
        <i class="ti ti-clock" aria-hidden="true"></i>
        {% trans "Closes in" %} {{ match.time_until_kickoff }}
      </span>
    {% endif %}
  </div>

  <!-- Corps de la carte -->
  <div class="card-body">

    <!-- Ligne équipes -->
    <div class="match-header">
      <div class="team-block">
        <img src="{% static 'img/teams/'|add:match.home_team.slug|add:'.svg' %}"
             alt="{{ match.home_team.name }}" width="38" height="38">
        <span class="team-name">{{ match.home_team.name }}</span>
      </div>
      <div class="match-datetime">
        {{ match.datetime|date:"d/m/y" }}<br>{{ match.datetime|date:"H:i" }}
      </div>
      <div class="team-block away">
        <img src="{% static 'img/teams/'|add:match.away_team.slug|add:'.svg' %}"
             alt="{{ match.away_team.name }}" width="38" height="38">
        <span class="team-name">{{ match.away_team.name }}</span>
      </div>
    </div>

    <!-- Ligne scores / cotes -->
    {% if not match.has_odds %}
      <div class="odds-pending">⏳ {% trans "Odds coming soon" %}</div>

    {% elif match.status == 'FINISHED' and prediction %}
      <!-- Résultat : scores réels + badge points -->
      <div class="match-scores">
        <div class="score-box readonly">{{ prediction.predicted_home_score }}</div>
        <span class="real-score">{{ match.home_score }}</span>
        <div class="badge-wrapper">
          {% if prediction.result_type == 'EXACT' %}<span class="crown">👑</span>{% endif %}
          <div class="badge badge-{{ prediction.result_type|lower }}">
            {{ prediction.points_earned }}
          </div>
        </div>
        <span class="real-score">{{ match.away_score }}</span>
        <div class="score-box readonly">{{ prediction.predicted_away_score }}</div>
      </div>

    {% elif match.is_locked %}
      <!-- Verrouillé : cotes affichées, saisie désactivée -->
      <div class="match-scores">
        <div class="score-box {% if prediction %}filled{% endif %}" disabled>
          {{ prediction.predicted_home_score|default:"" }}
        </div>
        <span class="real-score cote">{{ match.cote_home }}</span>
        <div class="badge-wrapper">
          <div class="badge badge-pending">{{ match.cote_draw }}</div>
        </div>
        <span class="real-score cote">{{ match.cote_away }}</span>
        <div class="score-box {% if prediction %}filled{% endif %}" disabled>
          {{ prediction.predicted_away_score|default:"" }}
        </div>
      </div>

    {% else %}
      <!-- Saisie ouverte -->
      <form hx-post="{% url 'predictions:submit' match.pk %}"
            hx-trigger="change"
            hx-swap="outerHTML">
        {% csrf_token %}
        <div class="match-scores">
          <input class="score-box" type="number" name="home" min="0" max="200"
                 value="{{ prediction.predicted_home_score|default:'' }}">
          <span class="real-score cote">{{ match.cote_home }}</span>
          <div class="badge-wrapper">
            <div class="badge badge-pending">{{ match.cote_draw }}</div>
          </div>
          <span class="real-score cote">{{ match.cote_away }}</span>
          <input class="score-box" type="number" name="away" min="0" max="200"
                 value="{{ prediction.predicted_away_score|default:'' }}">
        </div>
      </form>
    {% endif %}

  </div>
</div>
```

#### CSS clé

```css
/* Ligne de scores — hauteur fixe, tout centré */
.match-scores {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 52px;
}

/* Couronne positionnée au-dessus sans décaler la ligne */
.badge-wrapper {
  position: relative;
  width: 52px; height: 52px;
  display: flex; align-items: center; justify-content: center;
}
.crown {
  position: absolute;
  top: -26px; left: 50%;
  transform: translateX(-50%);
  font-size: 22px; line-height: 1;
}

.card-meta { background: var(--color-primary); padding: 8px 1.25rem; display: flex; justify-content: space-between; }
.card-meta-label { font-size: 12px; font-weight: 600; color: var(--color-light); }
.card-meta-status { font-size: 12px; font-weight: 600; }
.card-meta-status.urgent { color: var(--color-accent); }
.card-meta-status.live { color: var(--color-badge-win); }
.card-meta-status.finished, .card-meta-status.locked { color: #888; }

.badge-exact { background: var(--color-badge-exact); color: var(--color-primary); }
.badge-gap   { background: var(--color-badge-gap);   color: #fff; }
.badge-win   { background: var(--color-badge-win);   color: var(--color-primary); }
.badge-miss  { background: var(--color-badge-miss);  color: #fff; }
.badge-pending { background: #dde3e0; color: var(--color-primary); }
.badge-cancelled { background: #888; color: #fff; }
```

---

## 13. Authentification

### 13.1 Inscription (`/accounts/register/`)

Champs :
- Email (unique, obligatoire)
- Password + confirmation
- Last name / First name
- Display name (surnom affiché dans le classement)
- Favorite team (dropdown FK → Team, nullable)

### 13.2 Connexion (`/accounts/login/`)

- Email + mot de passe
- Support du paramètre `?next=` pour redirect post-login (utilisé pour les invitations de ligue)
- Lien "Forgot password?"

### 13.3 Reset mot de passe

- Django natif : `PasswordResetView` → email → `PasswordResetConfirmView`
- Envoi via SMTP Ionos (voir §15)

---

## 14. Admin Django

### 14.1 Accès

`/admin/` — réservé aux `is_staff=True`. Protégé par le système d'auth Django natif.

### 14.2 Modèles exposés dans l'admin

| Modèle | Actions disponibles | Filtres |
|---|---|---|
| `Competition` | CRUD + import RapidAPI | `is_active`, `season` |
| `Team` | CRUD | `country` |
| `Match` | CRUD + saisie cotes inline | `status`, `competition`, `datetime` |
| `CustomUser` | Lecture + modification rôle | `is_active`, `is_staff` |
| `League` | Lecture + désactivation | `is_active` |
| `Prediction` | Lecture seule | `match`, `user`, `result_type` |
| `UserScore` | Lecture + recalcul | `competition`, `season` |

### 14.3 Import de compétition via RapidAPI

Une action admin personnalisée permet d'importer ou de mettre à jour les matchs d'une compétition depuis RapidAPI en renseignant uniquement le **code compétition** et la **saison** :

**Interface admin :** page dédiée à `/admin/matches/competition/<id>/import/`

```
┌─────────────────────────────────────────────────────┐
│  Import matches from RapidAPI                       │
│                                                     │
│  Competition : [Top 14          ▼]                  │
│  Season      : [2024-2025         ]                 │
│                                                     │
│  [  Import matches  ]                               │
│                                                     │
│  ✓ 87 matches imported, 12 updated                  │
└─────────────────────────────────────────────────────┘
```

**Vue Django (`AdminImportView`) :**

```python
# apps/matches/admin_views.py
class CompetitionImportView(StaffRequiredMixin, View):
    def get(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        return render(request, 'admin/matches/import.html', {'competition': competition})

    def post(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        created, updated = sync_competition_matches(competition.code)
        messages.success(request, f"{created} matches imported, {updated} updated.")
        return redirect('admin:matches_competition_change', competition_id)
```

**Ce que fait `sync_competition_matches(code)` :**
1. Appel `GET /games?league=<external_id>&season=<season>` sur RapidAPI
2. `update_or_create` sur `external_id` pour chaque match
3. Création auto des `Team` si elles n'existent pas encore
4. Si un match passe à FINISHED → déclenche `calculate_points()` pour tous les `Prediction` associés
5. Recalcule les `UserScore` concernés

### 14.4 Saisie manuelle des cotes

Inline sur chaque `Match` dans l'admin :
- `cote_home`, `cote_draw`, `cote_away` (entiers, cote Unibet × 10)
- Action bulk "Set odds from Unibet" (V2 — automatisation via The Odds API)

---

## 15. Email transactionnel

### 15.1 Fournisseur : SMTP Ionos (inclus avec ovalpronos.com)

Le domaine `ovalpronos.com` est déjà enregistré chez Ionos. L'accès SMTP est inclus dans l'abonnement — pas besoin de Brevo ou d'un service tiers. On utilise directement `noreply@ovalpronos.com` dès la V1.

```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.ionos.fr')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')       # noreply@ovalpronos.com
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD') # mot de passe boîte Ionos
DEFAULT_FROM_EMAIL = "Oval'Pronos <noreply@ovalpronos.com>"
```

**Variables `.env` et Render :**
```
EMAIL_HOST=smtp.ionos.fr
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@ovalpronos.com
EMAIL_HOST_PASSWORD=<mot-de-passe-boite-ionos>
```

**En développement :** `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` — les emails s'affichent dans le terminal, aucune config SMTP requise.

### 15.2 Emails envoyés (V1)

| Déclencheur | Objet | Contenu |
|---|---|---|
| Reset mot de passe | "Reset your Oval'Pronos password" | Lien sécurisé Django natif |

### 15.3 Emails prévus (V2)

| Déclencheur | Objet |
|---|---|
| J-24h avant deadline pronos | "⏱ Last chance to predict Round 22!" |
| Résultats de journée | "Your Round 22 results are in 🏉" |
| Invitation ligue | "You've been invited to join [Ligue Name]" |

---

## 16. Synchronisation des scores

### 16.1 Contexte

La Lambda AWS originale est **perdue** et doit être reconstruite.

### 16.2 Cron — GitHub Actions (gratuit, remplace le cron payant Render)

Au lieu de payer ~2$/mois pour le cron Render, on utilise **GitHub Actions** gratuitement. Le workflow appelle un endpoint Django sécurisé.

```yaml
# .github/workflows/sync_matches.yml
name: Sync matches

on:
  schedule:
    - cron: '0 */2 * * *'      # toutes les 2h
    - cron: '*/15 * * * 6,0'   # toutes les 15min sam/dim (fenêtres de matchs)
  workflow_dispatch:              # déclenchement manuel possible

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Django sync endpoint
        run: |
          curl -X POST ${{ secrets.APP_URL }}/api/sync-scores/ \
            -H "Authorization: Bearer ${{ secrets.SYNC_SECRET_TOKEN }}" \
            --fail --silent --show-error
```

**Secrets GitHub à configurer :**
- `APP_URL` → `https://ovalpronos.onrender.com` (ou domaine custom)
- `SYNC_SECRET_TOKEN` → token aléatoire partagé avec Django

**Endpoint Django sécurisé :**
```python
# apps/matches/views.py
@require_POST
def sync_scores_api(request):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token != settings.SYNC_SECRET_TOKEN:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from apps.matches.services import sync_all_competitions
    created, updated = sync_all_competitions()
    return JsonResponse({'created': created, 'updated': updated})
```

### 16.3 Architecture V2 — Lambda AWS reconstruite (~30 lignes)

```
EventBridge (toutes les 5 min pendant fenêtres de matchs)
→ Lambda Python : GET scores RapidAPI
→ POST https://ovalpronos.com/api/sync-scores/
   Authorization: Bearer <SYNC_SECRET_TOKEN>
   Body: [{external_id, home_score, away_score, status}, ...]
→ Django : update + calculate_points + UserScore
→ Retourne 200 OK
```

### 16.4 Saisie manuelle des cotes (V1)

Via Django Admin — champs `cote_home / cote_draw / cote_away` sur chaque Match.
Automatisation via The Odds API prévue en V2.

---

## 17. Déploiement & coûts

### 17.1 Stratégie : 2 phases, 0 migration intermédiaire

```
Phase 1 — Render free   →  0€/mois   (dev + beta)
                ↓ migration unique quand l'app est en prod et les users arrivent
Phase 2 — Hetzner CX22  →  3.79€/mois (toujours actif)
```

Pas de Render payant, pas d'étape intermédiaire. On reste sur Render free jusqu'au moment où le cold start commence à gêner de vrais utilisateurs — puis migration directe vers Hetzner en une soirée.

### 17.2 Phase 1 — Gratuit (dev + beta)

| Service | Fournisseur | Coût | Notes |
|---|---|---|---|
| Serveur Django | Render free | 0€ | Cold start 30s après 15min inactivité |
| PostgreSQL | **Neon** (serverless, 3 Go) | 0€ | Toujours actif, pas de cold start |
| Cron sync | **GitHub Actions** | 0€ | Public repo |
| Email | **Ionos SMTP** (inclus avec ovalpronos.com) | 0€ | noreply@ovalpronos.com |
| Domaine | Ionos (déjà payé) | ~10€/an | DNS géré chez Ionos |
| **Total** | | **0€/mois** | |

**Limitation acceptable en beta :** cold start ~30s si inactif depuis 15 min. Les utilisateurs de la beta le tolèrent.

### 17.3 Phase 2 — Always-on (production)

Quand l'app est stable et que le cold start gêne → migration directe sur **Hetzner**.
Le domaine et l'email restent chez Ionos, seul le serveur change.

| Service | Config | Coût |
|---|---|---|
| VPS CX22 Hetzner | 2 vCPU AMD, 4 Go RAM, 40 Go SSD | **3.79€/mois** |
| PostgreSQL | Auto-hébergé sur la VM | inclus |
| Nginx + Gunicorn + systemd | Config manuelle (script fourni) | inclus |
| SSL | Let's Encrypt / Certbot | gratuit |
| Email | Ionos SMTP (déjà en place) | 0€ |
| Cron | GitHub Actions (déjà en place) | 0€ |
| **Total** | | **~4€/mois** |

### 17.4 Migration Phase 1 → Phase 2 (une soirée)

```bash
# Étape 1 — Exporter la base Neon (5 min)
pg_dump $NEON_DATABASE_URL > backup.sql

# Étape 2 — Créer et configurer le VPS Hetzner
# (script bash complet fourni au moment de la migration)

# Étape 3 — Importer la base (5 min)
psql $HETZNER_DATABASE_URL < backup.sql

# Étape 4 — Mettre à jour les DNS chez Ionos (2 min)
# A ovalpronos.com → IP du serveur Hetzner
# Propagation DNS : jusqu'à 24h

# Étape 5 — Mettre à jour les variables d'env (2 min)
# DATABASE_URL → nouvelle URL PostgreSQL Hetzner
```

Le code Django ne change pas. Seules les variables d'environnement bougent.

### 17.5 Phase 3 — White Label & SaaS

Infrastructure à définir selon le volume au moment de la V4.
Options : Hetzner CX32, cluster Kubernetes, ou instances dédiées par tenant.

---

## 18. Roadmap

### V1 — MVP (objectif : 2-3 week-ends) — 0€/mois
- [ ] Setup projet Django + i18n + URLs anglaises
- [ ] Inscription / Connexion / Reset MDP (SMTP Ionos)
- [ ] Landing page index
- [ ] Import compétitions via admin + RapidAPI
- [ ] Saisie manuelle des cotes dans l'admin
- [ ] Page predictions : cartes de match avec tous les états
- [ ] Sauvegarde auto HTMX des pronostics
- [ ] Calcul des points (scoring cotes)
- [ ] Tests unitaires scoring (obligatoires)
- [ ] Classement global saison active
- [ ] Page rules
- [ ] Endpoint `/api/sync-scores/` sécurisé par token
- [ ] GitHub Actions cron (2h + 15min week-end)
- [ ] Déploiement **Render free + Neon** → 0€/mois

### V2 — Engagement + Migration infra — ~4€/mois
- [ ] Ligues privées (League + codes + flux non-auth)
- [ ] Classement par ligue + classement de proximité
- [ ] Page profil complète avec stats + résumé de journée
- [ ] Barre de progression des pronos par journée
- [ ] Reconstruction Lambda AWS (scores quasi temps réel)
- [ ] Notifications email deadline + résultats
- [ ] Automatisation cotes via The Odds API
- [ ] Sélecteur de langue EN/FR
- [ ] **Migration Hetzner CX22** (script fourni) → ~4€/mois

### V3 — Growth
- [ ] Pro D2, Nationale
- [ ] Badges et achievements
- [ ] Bouton don "aux marcassins"

### V4 — White Label & SaaS

Transformation en solution vendable (clubs, médias, fédérations, entreprises).

#### Prérequis à anticiper dès V2

- **Thème configurable** : modèle `TenantConfig` (logo, couleurs, nom) — variables CSS déjà prêtes
- **Textes i18n** : surchargeables par tenant sans toucher au code
- **Sous-domaines** : `clientA.ovalpronos.com` ou domaines personnalisés

#### Fonctionnalités V4

- [ ] Multi-tenant via `django-tenants` (schémas PostgreSQL séparés)
- [ ] Customisation par tenant : logo, couleurs, nom, favicon, domaine
- [ ] Admin tenant : espace limité par client
- [ ] Compétitions privées (tournois internes sans RapidAPI)
- [ ] Scoring personnalisable par tenant
- [ ] Export CSV classement et pronostics
- [ ] Dashboard analytique (engagement, utilisateurs actifs)

#### Modèle commercial

| Offre | Cible | Prix indicatif |
|---|---|---|
| Starter | PME, animation interne < 50 users | ~50€/mois |
| Club | Clubs sportifs, médias < 500 users | ~150€/mois |
| Pro | Fédérations, grands groupes | sur devis |
| Instance dédiée | Clients premium hébergement propre | setup + mensuel |
