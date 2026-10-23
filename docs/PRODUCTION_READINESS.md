# Production readiness : Oval'Pronos

Audit Phase 0 du 2026-10-23, réalisé sur `main` @ `ecdb2e5`. Lecture seule : aucun code applicatif modifié.

Statuts : ✅ Fait · 🟡 Partiel · ❌ À faire · 👤 Action manuelle (VPS, DNS, dashboard) · ➖ Non applicable

Chaque statut s'appuie sur le code, pas sur la doc. Quand la doc et le code divergent, c'est le code qui fait foi (voir §3).

---

## 1. Résultats des vérifications automatiques

| Vérification | Résultat |
|---|---|
| `manage.py check --deploy` (DEBUG=False) | **4 warnings** : W004 `SECURE_HSTS_SECONDS` absent, W008 `SECURE_SSL_REDIRECT` absent, W012 `SESSION_COOKIE_SECURE` absent, W016 `CSRF_COOKIE_SECURE` absent |
| `makemigrations --check --dry-run` | **Échec** : migration manquante `predictions/0002` (Meta options + `verbose_name` de 5 champs). Sans effet sur le schéma SQL, mais une future CI le bloquera |
| Suite de tests (`manage.py test apps`, SQLite) | **85 tests, OK** une fois `polib` installé. Sans `polib` : 2 erreurs dans `apps/matches/tests_quality.py` (`polib` absent de `requirements.txt`) |
| Couverture (`coverage`, apps + ovalpronos) | **65 %** (2 848 lignes, 985 non couvertes) |
| `pip-audit -r requirements.txt` | **73 vulnérabilités connues dans 3 paquets** : Pillow 12.2.0 (60 avis, corrigés en 12.3.0 / 13.0.0), Django 6.0.6 (9 avis, corrigés en 6.0.8), requests 2.32.3 (4 avis, corrigés en 2.33.0) |
| Scan de secrets sur **tout l'historique** (151 commits, chaque blob) | **Aucun secret réel trouvé.** Uniquement des mots de passe de test (`'pass'`, `demo1234` dans `seed_ui_states.py`, protégé par `DEBUG`) et des placeholders. L'ancien `render.yaml` (supprimé) ne contenait que des `sync: false` / `generateValue: true`. Aucune chaîne Neon |
| `compilemessages` | Non exécuté : `msgfmt` (gettext) indisponible dans l'environnement d'audit. Les `.mo` sont versionnés |

**Note sur gitleaks** : le binaire n'a pas pu être téléchargé depuis l'environnement d'audit (réseau restreint). Le scan d'historique a été fait avec `detect-secrets` sur chaque blob + recherche ciblée (clés Google `AIza…`, Brevo `xkeysib-…`, Turnstile `0x4AAA…`, PostHog `phc_…`, URL Postgres avec mot de passe, clés privées SSH, `SECRET_KEY` en dur). gitleaks sera branché en CI en Phase 1 et confirmera.

---

## 2. Tableau des 40 items

La mission décrit les items par phase sans les numéroter. Ils sont regroupés ici en 40 lignes (ex. : CI et CD conditionné = 1 item, SEO + OG + favicon = 1 item).

### Phase 1 : sécurité et intégrité des données

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 1 | Secrets hors du repo + rotation | 🟡 | `.gitignore` couvre `.env*`, `db.sqlite3`, `media/`. Scan historique propre (§1) | `.gitignore` ne couvre pas `*.sql`, `*.dump`, `*.pem`, `*.key`. Pas de pre-commit gitleaks, pas de procédure de rotation écrite. Aucune clé à faire tourner en urgence | 1 |
| 2 | Authentification sur chaque endpoint (dont `/api/*`) | 🟡 | `apps/matches/views.py::_check_bearer` utilise `hmac.compare_digest`, `@require_POST/GET`, 401 sans détail. Vues app en `LoginRequiredMixin` | Pas de test qui parcourt le resolver. 3 endpoints non documentés : `/api/live-matches/`, `/api/update-scores/`, `/api/has-live-matches/` (voir item 24). `LeaguePublicInviteView` **ajoute le membre sur un simple GET** : un `<img src=".../leagues/invite/CODE/">` sur un site tiers fait rejoindre une ligue à un joueur connecté | 1 |
| 3 | IDOR / contrôle d'accès objet | 🟡 | `LeagueDetailView._get_league` lève `PermissionDenied` pour un non-membre. `LeagueLeaveView` vérifie l'appartenance. `SubmitPredictionView` vérifie `is_locked` et `has_odds` | `SubmitPredictionView` ne vérifie **ni `is_hidden`** ni que le joueur a accès à la compétition. **`is_hidden` n'est respecté nulle part côté joueur** : seulement dans 2 endpoints API (`matches/views.py:118,212`). L'action admin "masquer" n'a donc aucun effet sur la page pronostics ni sur les rappels email. Aucun test pour un POST sur match verrouillé | 1 |
| 4 | 2FA admin / URL admin | ❌ | `ovalpronos/urls.py` : `path('admin/', ...)` | Pas de 2FA, URL standard. Décision n°9 | 1 |
| 5 | Rate limiting | ❌ | Aucune occurrence de `ratelimit` ; `CACHES` = `LocMemCache` par défaut (non partagé entre workers) | Login, register, reset, join league (code 5 caractères, 36⁵ ≈ 60 M), submit et `/api/*` sans limite. Turnstile protège login/register mais pas reset ni join. Présence de nginx à confirmer sur le VPS | 1 |
| 6 | Audit des dépendances | ❌ | `pip-audit` : 73 vulnérabilités (§1). `requirements.txt` : `posthog` et `google-genai>=1.0.0` non épinglés. `base.html:20` charge `@tabler/icons-webfont@latest` | Pas de Dependabot, pas de SRI sur les 4 CDN (Bootstrap CSS/JS, Tabler, HTMX), Tabler en `@latest`. `pytz` et `crispy-forms` probablement inutilisés (à confirmer). `polib` manquant pour les tests | 1 |
| 7 | Sauvegardes de la base | 👤 ❌ | Rien dans le repo (`scripts/` ne contient que des scripts Gemini) | Aucune preuve de sauvegarde. À vérifier sur le VPS (Hetzner Backups activé ?). `media/` non sauvegardé non plus | 1 |
| 8 | Test de restauration | ❌ | Aucun script | Jamais testé à notre connaissance | 1 |
| 9 | Plan de rollback | ❌ | `deploy.sh` non versionné (décrit dans `CLAUDE.md` : `git pull`, `migrate`, `restart`) | Pas de SHA précédent mémorisé, pas de dump pré-migration, pas de smoke test, pas de retour arrière | 1 |

### Phase 2 : tests et CI/CD

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 10 | Tests unitaires | 🟡 | 85 tests (accounts 8, emails 12, leagues 14, matches 14, quality 4, predictions 18, rankings 15). Couverture 65 % | Pas de tests des propriétés `Match` avec heure figée ni passage heure d'été, pas de fixtures JSON RapidAPI, mode FIXED partiel | 2 |
| 11 | Tests de régression + N+1 | 🟡 | `apps/matches/tests.py` couvre la correction de score après FINISHED prématuré | Aucun `assertNumQueries`. Pas de convention `test_regression_*` | 2 |
| 12 | Smoke tests et `/healthz/` | ❌ | Aucun endpoint health, aucun script | | 2 |
| 13 | Tests end-to-end | ❌ | Pas de Playwright | | 2 |
| 14 | CI + CD conditionné | ❌ | `.github/workflows/deploy.yml` : push sur `main` → SSH direct, sans job de test | Un commit qui casse les tests part en prod. Pas de concurrency group | 2 |
| 15 | Environnement de staging | ❌ | Aucun. Pas de variable `ENVIRONMENT` | Décision n°4 | 2 |

### Phase 3 : observabilité

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 16 | Logging | ❌ | `settings.LOGGING` = `{}`. Les crons écrivent sur stdout redirigé vers `/home/amaury/logs/` | **PII dans les logs** : `apps/predictions/tasks.py:132,241` loggent `user.email` en cas d'échec d'envoi. Pas de request id, pas de format structuré | 3 |
| 17 | Suivi d'erreurs | ❌ | Pas de Sentry/GlitchTip. `templates/500.html` est bien statique | `ADMINS` non défini : aucune erreur 500 n'est remontée. Décision n°2 | 3 |
| 18 | Monitoring de performance | ❌ | Rien | | 3 |
| 19 | Uptime + heartbeats des crons | 👤 ❌ | Rien dans le repo | Un cron qui ne tourne plus (sync, cotes, rappels) passe inaperçu | 3 |
| 20 | Alerting (technique + métier) | 🟡 | `/api/notify/missing-odds/` envoie un email aux superusers | Seule alerte existante. Son texte dit "14 prochains jours" alors que la requête porte sur 7 jours (`matches/views.py:204`) | 3 |
| 21 | Analytics | 🟡 | `ovalpronos/analytics.py` (exceptions avalées), identification `user_{{ user.pk }}`, 5 événements serveur | Événements funnel manquants, pas de suppression PostHog à la suppression de compte, pas de `docs/analytics.md`. Dépend de la décision n°7 | 3 |

### Phase 4 : pipeline LLM des cotes

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 22 | Evals | ❌ | Rien | | 4 |
| 23 | Prompt injection / validation serveur | 🟡 | `update_odds_api` : plage `[10, 1000]`, rejet des matchs commencés | **Aucune allowlist de `match_id`** : le modèle peut renvoyer n'importe quel id de match futur, le serveur l'accepte. Pas de contrôle d'overround, pas de garde-fou sur une variation forte. Une entrée qui n'est pas un objet (`"foo"`) ou un `match_id` non numérique provoque une **500** (`entry.get` / `Match.objects.get`) au lieu d'un rejet propre | 4 |
| 24 | Fallback quand le modèle tombe | 🟡 | `scripts/update_odds.py::_call_gemini` : 3 essais, backoff 30/60 s | **Point le plus sensible** : quand Google Search ne trouve pas une cote, le script demande au modèle de **l'estimer sans recherche** (`estimate_config`) et l'écrit en base comme une vraie cote. Les joueurs voient une cote inventée, sans le savoir, qui pèse directement sur les points. Pas de modèle de repli configurable, pas de `--dry-run`, pas de timeout par appel. Par ailleurs `scripts/sync_live_scores.py` (non référencé dans les crons documentés) et l'endpoint `/api/update-scores/` permettent à un LLM d'écrire des **scores finaux et de déclencher le calcul des points** | 4 |
| 25 | Limites de tokens | ❌ | Un seul appel pour tous les matchs, pas de `max_output_tokens`, pas de détection de troncature | Avec beaucoup de matchs (6 Nations + Top 14 + coupes), risque de réponse tronquée silencieuse | 4 |

### Phase 5 : comptes, emails, conformité

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 26 | Reset de mot de passe | 🟡 | `accounts/urls.py` : vues Django natives (pas d'énumération), `PASSWORD_RESET_TIMEOUT = 86400`, lien construit sur `SITE_URL`, tracking Brevo désactivé. 2 tests sur le lien | Pas de rate limit, pas de test d'expiration ni d'usage unique | 5 |
| 27 | Vérification d'email | ❌ | Aucun champ `email_verified` | Les rappels partent à toutes les adresses (`tasks.py:88`). `email` unique mais sensible à la casse : `Foo@x.fr` et `foo@x.fr` peuvent coexister (le backend d'authentification prévoit d'ailleurs le cas `MultipleObjectsReturned`). Décision n°6 | 5 |
| 28 | Suppression du compte + export | ❌ | Aucune vue | `League.creator` en `CASCADE` : supprimer un créateur supprime la ligue de tous ses membres. Décision n°5 | 5 |
| 29 | Confidentialité, CGU, mentions légales | ❌ | Aucune route `/legal/` | Mentions légales obligatoires en France | 5 |
| 30 | Consentement cookies / traceurs | ❌ | `base.html:40-50` charge PostHog sans consentement ; `ARCHITECTURE.md §11` justifie par "localStorage = pas de consentement" | **Hypothèse juridiquement fausse** : l'article 82 de la loi Informatique et Libertés vise tout accès au terminal, `localStorage` compris. Décision n°7 | 5 |
| 31 | SPF / DKIM / DMARC | 👤 | Hors repo (DNS Ionos) | À vérifier avec `dig`. Pas de lien de désinscription ni d'en-tête `List-Unsubscribe` sur les rappels | 5 |

### Phase 6 : expérience, front, performance

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 32 | Pages d'erreur, états vides, chargement | 🟡 | `404.html`, `500.html` (statique). `hx-disabled-elt` sur les inputs | Pas de `403`, `400`, `429`, ni vue d'échec CSRF. Un match verrouillé renvoie un texte brut "Match is locked." (403) qui n'est pas une carte HTMX. Pas de gestion `htmx:sendError`. `500.html` contient des hex en dur (acceptable pour une page statique, à documenter comme exception) | 6 |
| 33 | Accessibilité | 🟡 | `aria-label` sur les inputs de score, lien d'évitement, `lang="{{ CURRENT_LANG }}"`, badges avec icône + texte, variantes `--color-badge-*-text` à contraste vérifié | Blanc cassé sur `--color-accent` = **3,75:1** (sous 4,5:1 pour du texte normal). Pas de zone `aria-live` pour l'enregistrement. Pas de tests axe | 6 |
| 34 | Multi-appareils et réseaux lents | 🟡 | `inputmode="numeric"`, `interactive-widget=resizes-content` | Pas de tests Playwright ni de throttling. Pas de `maxlength` sur les inputs et pas de borne haute côté serveur : `score_h=99999999999` dépasse un `integer` PostgreSQL et provoque une **500** | 6 |
| 35 | Images | 🟡 | Logos PNG locaux, favicon complet | Avatars : pas de limite de taille, pas de redimensionnement, **EXIF (GPS) conservé**, nom de fichier d'origine. `media/` servi uniquement en DEBUG (`urls.py`) : comment les avatars sont-ils servis en prod ? (nginx à vérifier) | 6 |
| 36 | Cache | ❌ | `settings.STATICFILES_STORAGE` est **ignoré par Django 6** (supprimé en 5.1) : le stockage effectif est `StaticFilesStorage`. Pas de compression WhiteNoise, pas de hash, d'où le `STATIC_VERSION` manuel | Pas de cache partagé. Décision n°1 | 6 |
| 37 | SEO, AEO, OG, favicon | 🟡 | OG complet et surchargeable dans `base.html:29-37`, favicon ico/png/apple-touch | Pas de `sitemap.xml`, `robots.txt`, `canonical`, JSON-LD, `llms.txt`, `site.webmanifest`, ni meta description | 6 |

### Phase 7 et 8 : infrastructure, coûts, documentation

| # | Item | Statut | Preuve | Écart constaté | Phase |
|---|---|---|---|---|---|
| 38 | Domaine, SSL, en-têtes, CSP | 🟡 | `SECURE_PROXY_SSL_HEADER` défini, certbot en place (doc) | Les 4 warnings de `check --deploy` (§1), pas de CSP, pas de `SECURE_REFERRER_POLICY` explicite. CAA et renouvellement à vérifier | 7 |
| 39 | Plafonds de dépenses | 👤 ❌ | Rien | La sync live appelle `/match/{id}` pour **chaque** match passé non terminé (`services.py`, boucle `live_matches`), y compris les `POSTPONED` anciens, toutes les 10 min pendant un match : consommation RapidAPI qui grandit avec la saison | 7 |
| 40 | Documentation | 🟡 | `CLAUDE.md`, `ARCHITECTURE.md`, `ROLLOUT.md`, `README.md`, `docs/REDESIGN.md` | Nombreuses incohérences (§3). `CONVENTIONS.md` **n'est pas versionné** : `.gitignore` exclut `*.md` sauf une liste, il n'existe que dans le projet claude.ai. Même piège pour les futurs `docs/ops/*.md` (`!docs/*.md` ne couvre pas les sous-dossiers) | 8 |

**Bilan** : 0 ✅, 18 🟡, 18 ❌, 4 👤 (dont 3 également ❌).

---

## 3. Incohérences de documentation

| Doc | Affirmation | Réalité dans le code |
|---|---|---|
| `CLAUDE.md`, `README.md` (admin), `requirements.txt`, `.env.example`, `Competition` docstring, aide de `sync_matches` | Source api-sports.io, `APISPORTS_KEY` | Source unique : rugby-live-data (RapidAPI). `APISPORTS_KEY` n'est lu nulle part |
| `ROLLOUT.md` §10.5.3 | `sync_all_competitions()` itère `settings.RUGBY_COMPETITIONS` | Itère la base (`is_active=True`), conforme à l'entrée du 2026-10-15. §10.5.3 est obsolète |
| `ARCHITECTURE.md` §11 | "Why UserScore is V2, not V1… will be introduced when…" | `UserScore` est utilisé par `RankingsView` et rafraîchi à chaque calcul de points |
| `ROLLOUT.md` "On hold" | `UserScore` parqué | Seul le champ `rank` est inutilisé, le modèle est en service |
| `ROLLOUT.md` §9.1, `CONVENTIONS.md` | `UserScore` a des `UniqueConstraint` partielles | Le modèle n'a **aucune** contrainte d'unicité, seulement un index. Des doublons sont possibles en cas d'exécutions concurrentes (sync live + action admin) |
| `ROLLOUT.md` §3.4 | "Local SVG logo pattern" | Logos PNG |
| `README.md`, `CLAUDE.md`, `ARCHITECTURE.md` §10 | Scripts dans `.github/scripts/`, cron `python .github/scripts/update_odds.py` | Les scripts sont dans `scripts/`. **À vérifier sur le VPS** : si la crontab suit la doc, la mise à jour des cotes échoue chaque mardi |
| `CLAUDE.md`, `ROLLOUT.md` | Gemini 3.6 Flash | `update_odds.py` utilise `gemini-3.8-flash`, `sync_live_scores.py` `gemini-3.6-flash` |
| `ARCHITECTURE.md`, `README.md` | "cote Unibet × 10" | Cotes multi-bookmakers trouvées par recherche, ou **estimées par le modèle** sans source |
| `CLAUDE.md` | `/api/upcoming-matches/` sur 14 jours | 7 jours |
| `CLAUDE.md` | "Django 5", email Ionos SMTP | Django 6.0.6, Brevo via anymail |
| `README.md` | Tests "11/11" | 85 tests, commande `manage.py test apps` |
| `ARCHITECTURE.md` §9, `README.md` | Vue d'import `/admin/matches/competition/<id>/import/` | **Inaccessible** : l'URL est résolue par le catch-all de l'admin (`RedirectView`), le bouton "Sync" de la liste utilise une autre route. `CompetitionImportView` est du code mort |
| `ARCHITECTURE.md` §3 | Étape 1 : CANCELLED avant tout | `calculate_points` teste `has_odds` d'abord. Sans effet en pratique car `_calculate_points_for_match` traite CANCELLED en amont |
| `CONVENTIONS.md` | `admin.css` ne redéfinit jamais les variables | `admin.css` redéfinit `:root` (copie de `main.css`) et contient 12 hex |
| `CONVENTIONS.md` | Table des couleurs | Valeurs obsolètes (`--color-text` = `#404771`, `--color-badge-gap` = `#8B35A8`, `--color-badge-miss` en rgba, nouvelles variables `*-text`) |
| `CONVENTIONS.md` | `verbose_name` en français sans `_()` | Tous les modèles utilisent `_("English")`. Le code est cohérent, c'est la convention qui ne l'est plus |
| `CONVENTIONS.md` | Inputs `home`/`away`, `max="200"` | `score_h`/`score_a`, aucune borne |
| `ARCHITECTURE.md` §11 | `localStorage` dispense de consentement | Faux en droit français (voir item 30) |
| `ROLLOUT.md` | `CompressedStaticFilesStorage` | Réglage ignoré par Django 6 (item 36) |
| `settings.py` | Commentaires "Render" | Hetzner |
| Aucune doc | `/api/live-matches/`, `/api/update-scores/`, `/api/has-live-matches/`, `scripts/sync_live_scores.py` | Présents et actifs côté serveur |

---

## 4. Les 5 risques les plus urgents

1. **Aucune sauvegarde prouvée.** Rien dans le repo, rien de documenté. Un disque Hetzner perdu ou un `migrate` raté efface la saison de tous les joueurs. Action : vérifier aujourd'hui si Hetzner Backups est actif, puis Phase 1.5.
2. **Dépendances vulnérables exposées.** Pillow 12.2.0 (60 avis) traite les avatars uploadés par n'importe quel inscrit ; Django 6.0.6 a 9 avis corrigés en 6.0.8. Montée de version patch, faible risque, à faire en premier.
3. **Équité du jeu : cotes inventées.** Le fallback "estimate" écrit des cotes produites par le modèle sans source comme si c'étaient de vraies cotes, et le serveur accepte n'importe quel `match_id`. Comme les points sont proportionnels aux cotes, une cote fausse fausse le classement. S'y ajoute l'endpoint `/api/update-scores/` qui permet d'écrire un score final.
4. **Sessions et comptes peu protégés.** Cookies session/CSRF sans `Secure`, pas de HSTS, aucun rate limiting (login, reset, code de ligue), et adhésion à une ligue déclenchable par un simple GET depuis un site tiers.
5. **Déploiement sans filet et sans visibilité.** Push sur `main` = prod sans tests, sans rollback ; `LOGGING` vide, pas de suivi d'erreurs, pas de heartbeats. Plusieurs 500 évitables existent déjà (score géant, payload API malformé) et personne n'en est averti.

Bugs fonctionnels trouvés en route (à corriger en Phase 1, avec test de régression) :

- `Match.is_hidden` ignoré sur la page pronostics, la soumission et les rappels email.
- 500 sur un score hors plage `integer` (pas de borne haute).
- 500 sur `/api/update-odds/` et `/api/update-scores/` avec une entrée malformée.
- Rappels de deadline envoyés pour **toutes** les compétitions, y compris celles où le joueur n'a aucune ligue (la page pronostics, elle, filtre par ligue).
- `Competition.code` n'est pas unique alors que la sync fait `Competition.objects.get(code=…)` : deux saisons actives d'une même compétition feraient planter la sync.
- La sync tourne dans une seule transaction : une `IntegrityError` (ex. deux équipes au même slug) annule toute la compétition et bloque les jeux suivants.
- Migration `predictions/0002` manquante.

---

## 5. Décisions qui bloquent la suite

Les 10 décisions de la section 10 de la mission, avec ma recommandation. Trois décisions supplémentaires apparues pendant l'audit sont ajoutées à la fin.

| # | Décision | Options | Recommandation |
|---|---|---|---|
| 1 | Cache partagé | (a) Redis local, ~30 Mo RAM ; (b) `DatabaseCache` PostgreSQL, 0 € et 0 RAM | **(b)** : trafic faible, une dépendance de moins, suffisant pour le rate limiting. Redis si les mesures montrent un besoin |
| 2 | Suivi d'erreurs | (a) Sentry UE gratuit (5 k erreurs/mois) ; (b) GlitchTip auto-hébergé (~300-500 Mo RAM sur un CX22 de 4 Go) | **(a)**, avec `send_default_pii=False` et `before_send` qui retire emails et cookies |
| 3 | Sauvegardes | (a) Hetzner Storage Box BX11 environ 4 €/mois ; (b) Backblaze B2 (UE), quelques centimes pour < 1 Go ; outil `restic` ou `pg_dump` + `age` | **(b) + restic** (chiffrement, déduplication, rétention intégrés). Hors Hetzner, coût quasi nul. **Dépense nouvelle à valider** |
| 4 | Staging | (a) même CX22 ; (b) second serveur ~4 €/mois | **(a)** avec les garde-fous listés dans la mission |
| 5 | Suppression d'un créateur de ligue | (a) transfert au membre le plus ancien ; (b) suppression si seul membre ; (c) blocage | **(a) + (b)** : transfert automatique, suppression seulement s'il est seul. Passer `creator` en `SET_NULL` dans une migration expand |
| 6 | Comptes non vérifiés | pronostiquer ? classement ? ligue ? purge ? | Peuvent pronostiquer et rejoindre une ligue, **n'apparaissent pas** au classement global et ne reçoivent pas d'emails, purge à 30 jours. Comptes existants marqués vérifiés |
| 7 | Consentement | (a) exemption CNIL configurée sur PostHog ; (b) bandeau maison | **(a)** si PostHog accepte la configuration requise (pas d'identification `user_pk` côté JS, rétention limitée, opt-out). Sinon (b). Implique de retirer `posthog.identify` |
| 8 | Échec total des cotes | (a) alerte + saisie manuelle ; (b) bascule FIXED à H-X | **(a)** : la bascule change les règles d'un match pour tout le monde, mauvais pour l'équité |
| 9 | 2FA admin | oui / non | **Oui** pour les superusers (`django-otp`, TOTP), un seul compte concerné |
| 10 | Dépenses récurrentes | | Seule nouvelle dépense proposée : stockage de sauvegarde (< 1 €/mois sur B2). Tout le reste en offres gratuites |
| 11 | **Fallback "estimate" des cotes** (nouveau) | (a) le supprimer, le match reste "Cotes à venir" ; (b) le garder mais marquer la cote comme estimée et l'afficher aux joueurs ; (c) garder tel quel | **(a)** : une cote inventée n'a pas de place dans un jeu où elle fixe les points. Changement visible par les joueurs, donc ton accord est requis |
| 12 | **`/api/update-scores/` et `sync_live_scores.py`** (nouveau) | (a) supprimer ; (b) garder derrière un flag désactivé | **(a)** si le script n'est plus planifié sur le VPS (à vérifier dans la crontab). Un score final écrit par un LLM déclenche le calcul des points |
| 13 | **Correction de `is_hidden`** (nouveau) | appliquer le filtre partout | **Oui**, mais c'est visible par les joueurs : des matchs aujourd'hui affichés disparaîtront s'ils ont été masqués dans l'admin. À vérifier d'abord : combien de matchs sont `is_hidden=True` en prod ? |

---

## 6. Prochaine étape proposée

Après tes réponses aux décisions 1, 3, 11, 12 et 13 :

**Phase 1a (petite PR, faible risque)** : montée de version Django 6.0.8 / Pillow 12.3+ / requests 2.33, migration manquante, `polib` en dépendance de test, réglages `check --deploy` (cookies Secure, redirection SSL, HSTS à 1 jour), `STORAGES` WhiteNoise, correction du `.gitignore` (`docs/**/*.md`, dumps, clés).

**Phase 1b** : test de permissions par parcours du resolver, corrections IDOR et 500 listées en §4 avec tests de régression, rate limiting, invitation de ligue en POST.

**Phase 1c** : scripts de sauvegarde, restauration et `deploy.sh` versionné avec rollback, plus `docs/ops/MANUAL_ACTIONS.md`.

Actions manuelles à faire dès maintenant (lecture seule sur le VPS) :

```bash
crontab -l                                   # chemin réel de update_odds.py, sync_live_scores.py planifié ?
ls /etc/nginx/sites-enabled/ && sudo nginx -T | grep -E "server_name|location /media|limit_req"
free -h && df -h /                           # RAM et disque disponibles (décisions 1, 2, 4)
sudo -u postgres psql ovalpronos -c "select count(*) from matches_match where is_hidden;"
```

Et dans la console Hetzner : le service "Backups" est-il activé sur le CX22 ?
