"""
Oval'Pronos — Configuration Django
-----------------------------------
Utilise python-decouple pour gérer les variables d'environnement.
En développement : créer un fichier .env à la racine du projet.
En production (Render) : renseigner les variables dans le dashboard.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Sécurité ────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Tell Django to trust the X-Forwarded-Proto header from the proxy (Gunicorn/nginx)
# so that request.scheme returns 'https' in production for correct OG image URLs.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HTTPS-only cookies and HSTS in prod; dev runs on plain http://localhost
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# 1 day while validating, then raise; no includeSubDomains until every subdomain has TLS
SECURE_HSTS_SECONDS = 0 if DEBUG else 86400
# SECURE_SSL_REDIRECT left off: the http→https redirect belongs to nginx (certbot), and
# enabling it here without X-Forwarded-Proto set by nginx would cause a redirect loop


# ─── Applications installées ─────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',  # Pour les filtres de template (pluralize, etc.)

    # Packages tiers
    'anymail',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_ratelimit',

    # Nos apps métier (dans apps/)
    'apps.accounts',
    'apps.matches',
    'apps.predictions',
    'apps.rankings',
    'apps.leagues',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Sert les fichiers statiques en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
]

ROOT_URLCONF = 'ovalpronos.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Dossier templates global
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ovalpronos.context_processors.analytics',
                'ovalpronos.context_processors.static_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'ovalpronos.wsgi.application'


# ─── Base de données ─────────────────────────────────────────────────────────
# En développement : SQLite (zéro config)
# En production : DATABASE_URL est injectée automatiquement par Render
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Si DATABASE_URL est définie (Render / prod), on bascule sur PostgreSQL
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)


# ─── Authentification ────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.CustomUser'  # Notre modèle User personnalisé
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmailOrUsernameBackend']
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'matches:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── Internationalisation ────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True  # IMPORTANT : stocke les dates en UTC, affiche en heure locale

LANGUAGES = [('fr', 'Français'), ('en', 'English')]
LOCALE_PATHS = [BASE_DIR / 'locale']


# ─── Fichiers statiques ───────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_STORAGE was removed in Django 5.1 and is silently ignored; STORAGES replaces it.
# No Manifest variant: templates build logo paths from team.slug and a missing PNG would raise
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
# Cache-busting query string for locally-hosted CSS/JS. Increment after any
# deploy that modifies static assets until ManifestStaticFilesStorage is set up.
STATIC_VERSION = '5'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Cache & rate limiting ───────────────────────────────────────────────────
# DatabaseCache is shared by all Gunicorn workers (LocMemCache is per process,
# so limits would not hold). Table created by accounts migration 0004.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}
RATELIMIT_VIEW = 'apps.accounts.views.ratelimited'
# A cache failure must not lock every player out of login
RATELIMIT_FAIL_OPEN = True
# DatabaseCache increments are not atomic: concurrent requests may slip a few extra
# attempts past a limit. Accepted for this traffic instead of running Redis on the VPS
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003', 'django_ratelimit.W001']


# ─── Formulaires ─────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# ─── Cloudflare Turnstile (CAPTCHA anti-bot) ────────────────────────────────
# Générer des clés sur https://dash.cloudflare.com/ → Turnstile
# Les clés de test ci-dessous fonctionnent en dev (toujours valides).
TURNSTILE_SITE_KEY = config('TURNSTILE_SITE_KEY', default='1x00000000000000000000AA')
TURNSTILE_SECRET_KEY = config('TURNSTILE_SECRET_KEY', default='1x0000000000000000000000000000000AA')


# ─── Media (uploaded files) ──────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─── API Rugby (rugby-live-data via RapidAPI) ────────────────────────────────
RAPIDAPI_KEY = config('RAPIDAPI_KEY', default='')
SYNC_SECRET_TOKEN = config('SYNC_SECRET_TOKEN', default='')



# ─── Email ────────────────────────────────────────────────────────────────────
# Dev: console backend (EMAIL_BACKEND env var unset) — never set BREVO_API_KEY
#      locally so that no real email is sent from a dev machine.
# Prod: set EMAIL_BACKEND=anymail.backends.brevo.EmailBackend + BREVO_API_KEY.
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.ionos.fr')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@ovalpronos.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default="Oval'Pronos <noreply@ovalpronos.com>")

# Password reset link validity — 24 h.
PASSWORD_RESET_TIMEOUT = 86400

ANYMAIL = {
    'BREVO_API_KEY': config('BREVO_API_KEY', default=''),
}


# ─── Analytics (PostHog EU) ───────────────────────────────────────────────────
POSTHOG_API_KEY = config('POSTHOG_API_KEY', default='')
POSTHOG_ENABLED = config('POSTHOG_ENABLED', default=False, cast=bool)

