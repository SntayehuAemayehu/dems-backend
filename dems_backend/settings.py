# dems_backend/settings.py - COMPLETE FIXED WITH WEBSOCKET CONFIG
import sys
import os
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'middleware'))

# ================================================================
# ✅ CHANGE 1: PRODUCTION-READY DEBUG
# Reads from environment variable. Default False for production safety.
# ================================================================
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ================================================================
# ✅ CHANGE 2: PRODUCTION-READY ALLOWED_HOSTS
# Reads from environment. Includes .onrender.com for Render deployment.
# ================================================================
ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    '127.0.0.1,localhost,0.0.0.0'
).split(',')
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# ================================================================
# ✅ CHANGE 3: PRODUCTION-READY SECRET KEY
# Reads from environment. Falls back to dev key only if not set.
# ================================================================
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-dems-2024-secret-key-change-in-production'
)

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
    'channels',  # ✅ WebSocket support
   #'django_ratelimit'
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
# ✅ CHANGE 4: ADD WHITENOISE MIDDLEWARE FOR STATIC FILES
# WhiteNoise serves static files efficiently in production.
# Placed right after SecurityMiddleware as recommended.
# ================================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ NEW - Static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ✅ SESSION TIMEOUT MIDDLEWARE
    'middleware.session_timeout.SessionTimeoutMiddleware',
    # ✅ ONE comprehensive security middleware (ALL protections)
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

# ✅ ASGI_APPLICATION for WebSocket support
ASGI_APPLICATION = 'dems_backend.asgi.application'

# ================================================================
# ✅ CHANGE 5: PRODUCTION-READY DATABASE
# Uses PostgreSQL from DATABASE_URL on Render.
# Falls back to SQLite for local development.
# ================================================================
import dj_database_url

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
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
# ✅ CHANGE 6: PRODUCTION-READY CHANNEL LAYERS (WebSockets)
# Uses Redis on Render. Falls back to InMemory for local dev.
# ================================================================
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ✅ Use Argon2 for password hashing (most secure)
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

CORS_ALLOW_ALL_ORIGINS = True
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
# ✅ CHANGE 7: PRODUCTION-READY STATIC FILES + WHITENOISE
# Added WhiteNoise storage for compressed static files.
# ================================================================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
os.makedirs(MEDIA_ROOT, exist_ok=True)

# ✅ For development, serve media files
if DEBUG:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# ✅ WhiteNoise static files storage (production)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================================================
# EMAIL SETTINGS - REAL EMAIL SENDING (SMTP)
# ================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = 'sntualex@gmail.com'
EMAIL_HOST_PASSWORD = 'ozngfsecuztuoptr'
DEFAULT_FROM_EMAIL = 'DEMS <sntualex@gmail.com>'
EMAIL_TIMEOUT = 30

# ================================================================
# PAYMENT GATEWAY CONFIGURATIONS
# ================================================================

# Chapa
CHAPA_TEST_SECRET_KEY = 'CHASECK_TEST-7CKIWgCnj5vpIdPskLKOKOhX3JZgwshd'
CHAPA_TEST_PUBLISHABLE_KEY = 'CHAPUBK_TEST-ThDGeNx2LqhU85PU3l0fr00uw2u7zfhY'
CHAPA_ENVIRONMENT = 'test'
if CHAPA_ENVIRONMENT == 'live':
    CHAPA_SECRET_KEY = os.environ.get('CHAPA_LIVE_SECRET_KEY', '')
    CHAPA_PUBLISHABLE_KEY = os.environ.get('CHAPA_LIVE_PUBLISHABLE_KEY', '')
else:
    CHAPA_SECRET_KEY = CHAPA_TEST_SECRET_KEY
    CHAPA_PUBLISHABLE_KEY = CHAPA_TEST_PUBLISHABLE_KEY
CHAPA_BASE_URL = os.environ.get('CHAPA_BASE_URL', 'https://api.chapa.co/v1')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000')

# Stripe
STRIPE_TEST_SECRET_KEY = 'sk_test_51U1xdxEEab9lbcMN3HQPDxyRqFaqcCq0M9GSQlgOaXS37sbKUYYc4anW2yV93VDM1XvpitJSrawzMoZ2EHJEpbQE00qttsEGEP'
STRIPE_TEST_PUBLISHABLE_KEY = 'pk_test_51U1xdxEEab9lbcMNppN8gCwp8IfiXtRBxcIJGxfmYIJMCG2tyF3VmRMkAFe3guztu9WlEhyxkoIR4DKaZvhjFUD900bVIgtYR0'
STRIPE_ENVIRONMENT = 'test'
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

# File upload size limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024   # 50MB

# ================================================================
# ✅ NEW SECURITY HARDENING SECTION
# ================================================================

# --- HTTPS / Transport Security ---
SECURE_SSL_REDIRECT = False          # Set True in production (HTTPS)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# --- Session / Cookie Hardening ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800            # 30 minutes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# ================================================================
# ✅ CHANGE 8: PRODUCTION-READY CSRF TRUSTED ORIGINS
# Includes Render domain for frontend CORS.
# ================================================================
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.onrender.com',              # ✅ Render backend
    'https://dems-frontend.onrender.com',  # ✅ Render frontend
]

# --- Uploads Limits (extra) ---
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# ================================================================
# SECURITY MIDDLEWARE CONFIG (used by comprehensive_security.py)
# ================================================================

# --- IP Whitelist / Blacklist ---
SEC_WHITELISTED_IPS = ['127.0.0.1', '::1']
SEC_BLACKLISTED_IPS = []
SEC_BLACKLISTED_SUBNETS = []
SEC_TRUSTED_PROXIES = []

# --- Auto-Blacklist Repeat Offenders ---
SEC_AUTO_BLACKLIST_THRESHOLD = 15
SEC_AUTO_BLACKLIST_WINDOW = 3600
SEC_AUTO_BLACKLIST_DURATION = 86400

# --- Request Limits ---
SEC_MAX_REQUEST_SIZE = 50 * 1024 * 1024
SEC_MAX_URL_LENGTH = 2048
SEC_MAX_HEADER_SIZE = 16384
SEC_MAX_QUERY_PARAMS = 50
SEC_MAX_JSON_DEPTH = 10
SEC_MAX_JSON_KEYS = 500

# --- File Upload ---
SEC_MAX_FILE_SIZE = 50 * 1024 * 1024
SEC_BLOCKED_EXTENSIONS = [
    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
    '.jar', '.msi', '.dll', '.so', '.dylib', '.sh', '.bash',
    '.php', '.phtml', '.py', '.pl', '.rb', '.cgi', '.asp', '.aspx',
    '.jsp', '.jspx', '.class', '.bin', '.apk', '.app', '.deb', '.rpm',
    '.ps1', '.psm1', '.psd1', '.hta', '.wsf', '.wsh', '.lnk', '.reg',
]

# --- Rate Limits (per route key) ---
SEC_RATE_LIMITS = {
    'admin':   {'requests': 30,  'window': 60},
    'api':     {'requests': 120, 'window': 60},
    'payment': {'requests': 10,  'window': 60},
    'exam':    {'requests': 300, 'window': 60},
    'upload':  {'requests': 20,  'window': 60},
    'search':  {'requests': 60,  'window': 60},
    'default': {'requests': 100, 'window': 60},
}

# --- Honeypot Paths (instant blacklist) ---
SEC_HONEYPOT_PATHS = [
    '/admin.php', '/wp-admin', '/wp-login.php', '/phpmyadmin',
    '/.env', '/.git/config', '/config.php', '/backup.sql',
    '/phpinfo.php', '/shell.php', '/xmlrpc.php',
]

# --- HSTS / CSP ---
SEC_HSTS_MAX_AGE = 31536000
SEC_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https://*; "
    "media-src 'self' blob: https://*; "
    "connect-src 'self' https://* wss://* ws://*; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

# ================================================================
# ✅ CHANGE 9: PRODUCTION SSL/HTTPS ENFORCEMENT
# Enables SSL cookies and HTTPS redirect only in production.
# ================================================================
if not DEBUG:
    # HTTPS enforcement
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    # Development settings
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ================================================================
# END OF PRODUCTION-READY SETTINGS
# ================================================================