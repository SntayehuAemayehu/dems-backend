# dems_backend/settings.py

import sys
import os
from pathlib import Path
from datetime import timedelta
from decouple import config
import dj_database_url

# ================================================================
# BASE DIRECTORY
# ================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'middleware'))

# ================================================================
# SECURITY WARNING: keep the secret key used in production secret!
# ================================================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dems-2024-secret-key-change-in-production')

# ================================================================
# SECURITY WARNING: don't run with debug turned on in production!
# ================================================================
DEBUG = os.environ.get('DEBUG', 'True') == 'True'  # Changed to default True for local

# ================================================================
# ALLOWED_HOSTS - Add your hosts here
# ================================================================
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ================================================================
# APPLICATION DEFINITION
# ================================================================
INSTALLED_APPS = [
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
    'channels',
    
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

# ================================================================
# MIDDLEWARE
# ================================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'middleware.session_timeout.SessionTimeoutMiddleware',
    'middleware.security_headers.SecurityHeadersMiddleware',
    'middleware.security_middleware.SQLInjectionMiddleware',
    'middleware.security_middleware.SecureCookieMiddleware',
    'analytics.middleware.StudentAccessMiddleware',
    'analytics.middleware.SystemLockMiddleware',
]

# ================================================================
# URL CONFIGURATION
# ================================================================
ROOT_URLCONF = 'dems_backend.urls'

# ================================================================
# TEMPLATES
# ================================================================
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

# ================================================================
# WSGI / ASGI
# ================================================================
WSGI_APPLICATION = 'dems_backend.wsgi.application'
ASGI_APPLICATION = 'dems_backend.asgi.application'

# ================================================================
# SECURE COOKIE SETTINGS
# ================================================================
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# ================================================================
# DATABASE - PostgreSQL (with fallback to SQLite for development)
# ================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Fix password with @ symbol - URL encode it
    # If your password has @, replace with %40
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG  # Only require SSL in production
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ================================================================
# CHANNEL LAYERS - WebSocket Support
# ================================================================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# ================================================================
# PASSWORD HASHING
# ================================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# ================================================================
# PASSWORD VALIDATION
# ================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ================================================================
# CUSTOM USER MODEL
# ================================================================
AUTH_USER_MODEL = 'accounts.User'

# ================================================================
# REST FRAMEWORK
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

# ================================================================
# JWT SETTINGS
# ================================================================
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
# CORS SETTINGS
# ================================================================
CORS_ALLOW_ALL_ORIGINS = True if DEBUG else False
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if not DEBUG else []
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

# ================================================================
# STATIC & MEDIA FILES
# ================================================================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
os.makedirs(MEDIA_ROOT, exist_ok=True)

if DEBUG:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================================================
# EMAIL SETTINGS
# ================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'sntualex@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'ozngfsecuztuoptr')
DEFAULT_FROM_EMAIL = f'DEMS <{EMAIL_HOST_USER}>'
EMAIL_TIMEOUT = 30

# ================================================================
# CHAPA PAYMENT GATEWAY
# ================================================================
CHAPA_TEST_SECRET_KEY = 'CHASECK_TEST-7CKIWgCnj5vpIdPskLKOKOhX3JZgwshd'
CHAPA_TEST_PUBLISHABLE_KEY = 'CHAPUBK_TEST-ThDGeNx2LqhU85PU3l0fr00uw2u7zfhY'
CHAPA_ENVIRONMENT = os.environ.get('CHAPA_ENVIRONMENT', 'test')

if CHAPA_ENVIRONMENT == 'live':
    CHAPA_SECRET_KEY = os.environ.get('CHAPA_LIVE_SECRET_KEY', '')
    CHAPA_PUBLISHABLE_KEY = os.environ.get('CHAPA_LIVE_PUBLISHABLE_KEY', '')
else:
    CHAPA_SECRET_KEY = CHAPA_TEST_SECRET_KEY
    CHAPA_PUBLISHABLE_KEY = CHAPA_TEST_PUBLISHABLE_KEY

CHAPA_BASE_URL = os.environ.get('CHAPA_BASE_URL', 'https://api.chapa.co/v1')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000')

# ================================================================
# STRIPE PAYMENT GATEWAY
# ================================================================
STRIPE_TEST_SECRET_KEY = 'sk_test_51U1xdxEEab9lbcMN3HQPDxyRqFaqcCq0M9GSQlgOaXS37sbKUYYc4anW2yV93VDM1XvpitJSrawzMoZ2EHJEpbQE00qttsEGEP'
STRIPE_TEST_PUBLISHABLE_KEY = 'pk_test_51U1xdxEEab9lbcMNppN8gCwp8IfiXtRBxcIJGxfmYIJMCG2tyF3VmRMkAFe3guztu9WlEhyxkoIR4DKaZvhjFUD900bVIgtYR0'
STRIPE_ENVIRONMENT = os.environ.get('STRIPE_ENVIRONMENT', 'test')

if STRIPE_ENVIRONMENT == 'live':
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_LIVE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_LIVE_PUBLISHABLE_KEY', '')
else:
    STRIPE_SECRET_KEY = STRIPE_TEST_SECRET_KEY
    STRIPE_PUBLISHABLE_KEY = STRIPE_TEST_PUBLISHABLE_KEY

STRIPE_API_VERSION = '2023-10-16'
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# ================================================================
# OPENAI CONFIGURATION
# ================================================================
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
OPENAI_MAX_TOKENS = int(os.environ.get('OPENAI_MAX_TOKENS', 4096))
OPENAI_TEMPERATURE = float(os.environ.get('OPENAI_TEMPERATURE', 0.7))
OPENAI_USE_GPT4_FOR_GRADING = os.environ.get('OPENAI_USE_GPT4_FOR_GRADING', 'True') == 'True'
OPENAI_USE_GPT4_FOR_PLAGIARISM = os.environ.get('OPENAI_USE_GPT4_FOR_PLAGIARISM', 'False') == 'True'
OPENAI_RATE_LIMIT = int(os.environ.get('OPENAI_RATE_LIMIT', 60))

# ================================================================
# AI PROCTORING CONFIGURATION
# ================================================================
AI_PROCTOR_SUSPICIOUS_THRESHOLD = int(os.environ.get('AI_PROCTOR_SUSPICIOUS_THRESHOLD', 3))
AI_PROCTOR_WARNING_THRESHOLD = int(os.environ.get('AI_PROCTOR_WARNING_THRESHOLD', 2))
AI_PROCTOR_AUTO_FLAG = os.environ.get('AI_PROCTOR_AUTO_FLAG', 'True') == 'True'

# ================================================================
# AI RECOMMENDATIONS CONFIGURATION
# ================================================================
AI_RECOMMENDATIONS_USE_AI = os.environ.get('AI_RECOMMENDATIONS_USE_AI', 'True') == 'True'
AI_RECOMMENDATIONS_MAX_RESULTS = int(os.environ.get('AI_RECOMMENDATIONS_MAX_RESULTS', 10))

# ================================================================
# FILE UPLOAD SIZE LIMITS
# ================================================================
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# ================================================================
# LOGGING CONFIGURATION
# ================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'exams': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}