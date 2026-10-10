# backend/middleware/security_config.py
"""
Central security configuration.
Loads from SystemConfig DB if available, falls back to safe defaults.
"""

from django.conf import settings


def _env(key, default=None):
    return getattr(settings, key, default)


class SecurityConfig:
    # ---------- IP ----------
    BLACKLISTED_IPS = _env('SEC_BLACKLISTED_IPS', [])
    BLACKLISTED_SUBNETS = _env('SEC_BLACKLISTED_SUBNETS', [])
    WHITELISTED_IPS = _env('SEC_WHITELISTED_IPS', ['127.0.0.1', '::1'])
    TRUSTED_PROXIES = _env('SEC_TRUSTED_PROXIES', [])
    AUTO_BLACKLIST_THRESHOLD = _env('SEC_AUTO_BLACKLIST_THRESHOLD', 15)
    AUTO_BLACKLIST_WINDOW = _env('SEC_AUTO_BLACKLIST_WINDOW', 3600)
    AUTO_BLACKLIST_DURATION = _env('SEC_AUTO_BLACKLIST_DURATION', 86400)

    # ---------- GEO ----------
    ALLOWED_COUNTRIES = _env('SEC_ALLOWED_COUNTRIES', [])  # empty = allow all
    BLOCKED_COUNTRIES = _env('SEC_BLOCKED_COUNTRIES', [])

    # ---------- RATE LIMITS ----------
    RATE_LIMITS = _env('SEC_RATE_LIMITS', {
        'admin':       {'requests': 30,   'window': 60},
        'api':         {'requests': 120,  'window': 60},
        'payment':     {'requests': 10,   'window': 60},
        'exam':        {'requests': 300,  'window': 60},
        'upload':      {'requests': 20,   'window': 60},
        'search':      {'requests': 60,   'window': 60},
        'default':     {'requests': 100,  'window': 60},
    })

    # ---------- REQUEST ----------
    MAX_REQUEST_SIZE = _env('SEC_MAX_REQUEST_SIZE', 50 * 1024 * 1024)
    MAX_JSON_DEPTH = _env('SEC_MAX_JSON_DEPTH', 10)
    MAX_JSON_KEYS = _env('SEC_MAX_JSON_KEYS', 500)
    MAX_HEADER_SIZE = _env('SEC_MAX_HEADER_SIZE', 16 * 1024)
    MAX_URL_LENGTH = _env('SEC_MAX_URL_LENGTH', 2048)
    MAX_QUERY_PARAMS = _env('SEC_MAX_QUERY_PARAMS', 50)

    # ---------- UPLOAD ----------
    MAX_FILE_SIZE = _env('SEC_MAX_FILE_SIZE', 50 * 1024 * 1024)
    BLOCKED_EXTENSIONS = _env('SEC_BLOCKED_EXTENSIONS', [
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
        '.jar', '.msi', '.dll', '.so', '.dylib', '.sh', '.bash',
        '.php', '.phtml', '.py', '.pl', '.rb', '.cgi', '.asp', '.aspx',
        '.jsp', '.jspx', '.class', '.bin', '.apk', '.app', '.deb', '.rpm',
        '.ps1', '.psm1', '.psd1', '.hta', '.wsf', '.wsh', '.lnk', '.reg',
    ])

    # ---------- BLOCK RESPONSES ----------
    BLOCK_STATUS = 403
    RATE_LIMIT_STATUS = 429
    SIZE_LIMIT_STATUS = 413
    CONTENT_TYPE_STATUS = 415

    # ---------- HEADERS ----------
    HSTS_MAX_AGE = _env('SEC_HSTS_MAX_AGE', 31536000)
    CSP_POLICY = _env('SEC_CSP_POLICY', (
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
    ))

    # ---------- HONEYPOT ----------
    HONEYPOT_PATHS = _env('SEC_HONEYPOT_PATHS', [
        '/admin.php', '/wp-admin', '/wp-login.php', '/phpmyadmin',
        '/.env', '/.git/config', '/config.php', '/backup.sql',
        '/phpinfo.php', '/shell.php', '/xmlrpc.php',
    ])


config = SecurityConfig()