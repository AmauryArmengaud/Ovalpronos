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
    'crispy_forms',
    'crispy_bootstrap5',

    # Nos apps métier (dans apps/)
    'apps.accounts',
    'apps.matches',
    'apps.predictions',
    'apps.rankings',
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
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Dossier créé par collectstatic pour Render
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Formulaires ─────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# ─── API Rugby (rugby-live-data via RapidAPI) ────────────────────────────────
RAPIDAPI_KEY = config('RAPIDAPI_KEY', default='')
SYNC_SECRET_TOKEN = config('SYNC_SECRET_TOKEN', default='')

# Compétitions à synchroniser (IDs rugby-live-data sur RapidAPI)
RUGBY_COMPETITIONS = {
    'TOP14': {'id': 1230, 'name': 'Top 14', 'country': 'France', 'season': 2026},
    #'CHAMPIONS_CUP': {'id': 1236, 'name': 'Champions Cup', 'country': 'Europe', 'season': 2025},
    #'SIX_NATIONS': {'id': 180, 'name': '6 Nations', 'country': 'World', 'season': 2025},
}
# Fallback season used if a competition config has no 'season' key.
RUGBY_SEASON = config('RUGBY_SEASON', default='2025')


# ─── Email ────────────────────────────────────────────────────────────────────
# Dev: print emails to terminal. Prod: Ionos SMTP.
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

