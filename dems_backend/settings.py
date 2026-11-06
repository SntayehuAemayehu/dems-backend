# dems_backend/settings.py - COMPLETE PRODUCTION READY
import sys
import os
from pathlib import Path
from datetime import timedelta
from decouple import config
import dj_database_url
import sqlite3
from django.db.backends.signals import connection_created
import mimetypes
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'middleware'))

# ================================================================
# ENVIRONMENT VARIABLES (Reads from .env locally, Render Env Vars in prod)
# ================================================================
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dems-2024-secret-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)

# Allow localhost and Render URLs
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', '.onrender.com', '*']

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
    'news',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # ✅ Added for Render static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'middleware.activity_log.ActivityLogMiddleware',
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
# DATABASE (Neon PostgreSQL on Render, SQLite Locally)
# ================================================================
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600
    )
}

# ================================================================
# CHANNEL LAYERS (Redis on Render, In-Memory Locally)
# ================================================================
if not DEBUG:
    # Production (Render) - We won't use Redis to save memory on Free Tier.
    # We will use InMemory, but note: this means WebSockets won't work across multiple instances.
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
else:
    # Local Development
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ================================================================
# AUTHENTICATION & REST FRAMEWORK
# ================================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
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

# ================================================================
# CORS & STATIC FILES
# ================================================================
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type', 'dnt',
    'origin', 'user-agent', 'x-csrftoken', 'x-requested-with', 'content-disposition',
]

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
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
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='sntualex@gmail.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='') # ✅ Must be in Render Env Vars
DEFAULT_FROM_EMAIL = 'DEMS <sntualex@gmail.com>'
EMAIL_TIMEOUT = 30

# ================================================================
# PAYMENT GATEWAYS
# ================================================================
CHAPA_TEST_SECRET_KEY = config('CHAPA_TEST_SECRET_KEY', default='CHASECK_TEST-xxxx')
CHAPA_TEST_PUBLISHABLE_KEY = config('CHAPA_TEST_PUBLISHABLE_KEY', default='CHAPUBK_TEST-xxxx')
CHAPA_BASE_URL = config('CHAPA_BASE_URL', default='https://api.chapa.co/v1')
BASE_URL = config('BASE_URL', default='http://localhost:8000')

STRIPE_TEST_SECRET_KEY = config('STRIPE_TEST_SECRET_KEY', default='sk_test_xxxx')
STRIPE_TEST_PUBLISHABLE_KEY = config('STRIPE_TEST_PUBLISHABLE_KEY', default='pk_test_xxxx')
STRIPE_API_VERSION = '2023-10-16'
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# ================================================================
# AI & PROCTORING CONFIGURATION
# ================================================================
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4')
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.8-flash')
AI_PROCTOR_SUSPICIOUS_THRESHOLD = 3
AI_PROCTOR_WARNING_THRESHOLD = 2
AI_PROCTOR_AUTO_FLAG = True

DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# ================================================================
# SECURITY HARDENING (Production vs Development)
# ================================================================
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000', 'http://127.0.0.1:3000',
    'http://localhost:8000', 'http://127.0.0.1:8000',
    'https://*.onrender.com', # ✅ Allow Render Domain
]

DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# ================================================================
# SECURITY MIDDLEWARE CONFIG
# ================================================================
SEC_WHITELISTED_IPS = ['127.0.0.1', '::1']
SEC_BLACKLISTED_IPS = []
SEC_BLACKLISTED_SUBNETS = []
SEC_TRUSTED_PROXIES = []

SEC_AUTO_BLACKLIST_THRESHOLD = 15
SEC_AUTO_BLACKLIST_WINDOW = 3600
SEC_AUTO_BLACKLIST_DURATION = 86400

SEC_MAX_REQUEST_SIZE = 50 * 1024 * 1024
SEC_MAX_URL_LENGTH = 2048
SEC_MAX_HEADER_SIZE = 16384
SEC_MAX_QUERY_PARAMS = 50
SEC_MAX_JSON_DEPTH = 10
SEC_MAX_JSON_KEYS = 500

SEC_MAX_FILE_SIZE = 50 * 1024 * 1024
SEC_BLOCKED_EXTENSIONS = [
    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
    '.jar', '.msi', '.dll', '.so', '.dylib', '.sh', '.bash',
    '.php', '.phtml', '.py', '.pl', '.rb', '.cgi', '.asp', '.aspx',
    '.jsp', '.jspx', '.class', '.bin', '.apk', '.app', '.deb', '.rpm',
    '.ps1', '.psm1', '.psd1', '.hta', '.wsf', '.wsh', '.lnk', '.reg',
]

SEC_RATE_LIMITS = {
    'admin':   {'requests': 30,  'window': 60},
    'api':     {'requests': 120, 'window': 60},
    'payment': {'requests': 10,  'window': 60},
    'exam':    {'requests': 300, 'window': 60},
    'upload':  {'requests': 20,  'window': 60},
    'search':  {'requests': 60,  'window': 60},
    'default': {'requests': 100, 'window': 60},
}

SEC_HONEYPOT_PATHS = [
    '/admin.php', '/wp-admin', '/wp-login.php', '/phpmyadmin',
    '/.env', '/.git/config', '/config.php', '/backup.sql',
    '/phpinfo.php', '/shell.php', '/xmlrpc.php',
]

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
# SQLITE WAL MODE (For Local Dev Only)
# ================================================================
def _sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=30000;')

connection_created.connect(_sqlite_pragmas)
DAPHNE_TIMEOUT = 120
#for news
mimetypes.add_type("video/mp4", ".mp4", True)
mimetypes.add_type("video/webm", ".webm", True)
mimetypes.add_type("video/quicktime", ".mov", True)
mimetypes.add_type("video/x-msvideo", ".avi", True)

