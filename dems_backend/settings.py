# dems_backend/settings.py - FIXED FOR POSTGRESQL & FRONTEND INTEGRATION
import sys
import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.db.backends.signals import connection_created

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'middleware'))

# ================================================================
# PRODUCTION / DEVELOPMENT TOGGLES
# ================================================================
# DEBUG is controlled via environment variable on Render (defaults to False in prod)
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dems-2024-secret-key-change-in-production')

# ================================================================
# ALLOWED_HOSTS & CORS CONFIGURATION
# ================================================================
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '.onrender.com,localhost,127.0.0.1,0.0.0.0').split(',')

# Frontend Integration
CORS_ALLOWED_ORIGINS = [
    'https://dems-frontend.onrender.com',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:5173',
]

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all only in local dev mode
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'content-disposition',
]

CSRF_TRUSTED_ORIGINS = [
    'https://dems-frontend.onrender.com',
    'https://*.onrender.com',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# ================================================================
# INSTALLED APPS & MIDDLEWARE
# ================================================================
INSTALLED_APPS = [
    'daphne', 
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',  # WebSocket support
    
    # Local apps
    'accounts',
    'courses',
    'exams',
    'payments',
    'proctoring',
    'notifications',
    'analytics',
    'chat',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files on Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'middleware.session_timeout.SessionTimeoutMiddleware',
    'middleware.comprehensive_security.ComprehensiveSecurityMiddleware',
    'analytics.middleware.StudentAccessMiddleware',
    'analytics.middleware.SystemLockMiddleware',
]

ROOT_URLCONF = 'dems_backend.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


WSGI_APPLICATION = 'dems_backend.wsgi.application'
ASGI_APPLICATION = 'dems_backend.asgi.application'

# ================================================================
# DATABASE CONFIGURATION (POSTGRESQL - NEON)
# ================================================================
# Uses dj_database_url to automatically connect to Render's DATABASE_URL (Neon PostgreSQL)
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

# ================================================================
# CHANNELS / WEBSOCKETS
# ================================================================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# ================================================================
# AUTH & PASSWORDS
# ================================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

# ================================================================
# REST FRAMEWORK & JWT
# ================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ================================================================
# STATIC & MEDIA FILES
# ================================================================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
os.makedirs(MEDIA_ROOT, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================================================
# EMAIL SETTINGS
# ================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = 'sntualex@gmail.com'
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'ozngfsecuztuoptr')
DEFAULT_FROM_EMAIL = 'DEMS <sntualex@gmail.com>'
EMAIL_TIMEOUT = 30

# ================================================================
# PAYMENT GATEWAYS (Chapa & Stripe)
# ================================================================
CHAPA_TEST_SECRET_KEY = 'CHASECK_TEST-7CKIWgCnj5vpIdPskLKOKOhX3JZgwshd'
CHAPA_TEST_PUBLISHABLE_KEY = 'CHAPUBK_TEST-ThDGeNx2LqhU85PU3l0fr00uw2u7zfhY'
CHAPA_ENVIRONMENT = 'test'
CHAPA_SECRET_KEY = os.environ.get('CHAPA_LIVE_SECRET_KEY', CHAPA_TEST_SECRET_KEY)
CHAPA_PUBLISHABLE_KEY = os.environ.get('CHAPA_LIVE_PUBLISHABLE_KEY', CHAPA_TEST_PUBLISHABLE_KEY)
CHAPA_BASE_URL = os.environ.get('CHAPA_BASE_URL', 'https://api.chapa.co/v1')

STRIPE_TEST_SECRET_KEY = 'sk_test_51U1xdxEEab9lbcMN3HQPDxyRqFaqcCq0M9GSQlgOaXS37sbKUYYc4anW2yV93VDM1XvpitJSrawzMoZ2EHJEpbQE00qttsEGEP'
STRIPE_TEST_PUBLISHABLE_KEY = 'pk_test_51U1xdxEEab9lbcMNppN8gCwp8IfiXtRBxcIJGxfmYIJMCG2tyF3VmRMkAFe3guztu9WlEhyxkoIR4DKaZvhjFUD900bVIgtYR0'
STRIPE_SECRET_KEY = os.environ.get('STRIPE_LIVE_SECRET_KEY', STRIPE_TEST_SECRET_KEY)
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_LIVE_PUBLISHABLE_KEY', STRIPE_TEST_PUBLISHABLE_KEY)
STRIPE_API_VERSION = '2023-10-16'
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

BASE_URL = os.environ.get('BASE_URL', 'https://dems-backend.onrender.com')

# ================================================================
# OPENAI & AI PROCTORING
# ================================================================
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
OPENAI_MAX_TOKENS = int(os.environ.get('OPENAI_MAX_TOKENS', 4096))
OPENAI_TEMPERATURE = float(os.environ.get('OPENAI_TEMPERATURE', 0.7))

AI_PROCTOR_SUSPICIOUS_THRESHOLD = int(os.environ.get('AI_PROCTOR_SUSPICIOUS_THRESHOLD', 3))
AI_PROCTOR_WARNING_THRESHOLD = int(os.environ.get('AI_PROCTOR_WARNING_THRESHOLD', 2))
AI_PROCTOR_AUTO_FLAG = os.environ.get('AI_PROCTOR_AUTO_FLAG', 'True') == 'True'

AI_RECOMMENDATIONS_USE_AI = os.environ.get('AI_RECOMMENDATIONS_USE_AI', 'True') == 'True'
AI_RECOMMENDATIONS_MAX_RESULTS = int(os.environ.get('AI_RECOMMENDATIONS_MAX_RESULTS', 10))

DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# ================================================================
# SECURITY & COOKIE HARDENING
# ================================================================
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'None' if not DEBUG else 'Lax'
CSRF_COOKIE_HTTPONLY = False  # Required by DRF / JS frontend
CSRF_COOKIE_SAMESITE = 'None' if not DEBUG else 'Lax'

SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# Security Middleware Configs
SEC_WHITELISTED_IPS = ['127.0.0.1', '::1']
SEC_RATE_LIMITS = {
    'admin':   {'requests': 30,  'window': 60},
    'api':     {'requests': 120, 'window': 60},
    'payment': {'requests': 10,  'window': 60},
    'exam':    {'requests': 300, 'window': 60},
    'upload':  {'requests': 20,  'window': 60},
    'search':  {'requests': 60,  'window': 60},
    'default': {'requests': 100, 'window': 60},
}