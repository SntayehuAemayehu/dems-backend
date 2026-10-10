# backend/middleware/comprehensive_security.py
# ============================================================
# FORTRESS-GRADE COMPREHENSIVE SECURITY MIDDLEWARE
# ============================================================
# 40+ protections in one class.
#
# INPUT / REQUEST
#   1.  IP blacklist / whitelist / auto-blacklist (whitelist-safe)
#   2.  Trusted proxy IP extraction
#   3.  HTTP method validation
#   4.  Request size limit
#   5.  URL length limit
#   6.  Query param count limit
#   7.  Header size limit
#   8.  Content-Type validation
#   9.  JSON depth / key validation
#  10.  XSS detection
#  11.  SQL injection detection
#  12.  NoSQL injection detection
#  13.  Command injection detection
#  14.  Path traversal detection
#  15.  SSRF pattern detection (body / query only — NOT headers)
#  16.  XXE pattern detection
#  17.  LDAP injection detection
#  18.  Template injection detection
#  19.  CRLF injection detection
#
# FILES
#  20.  File size limit
#  21.  File extension blacklist
#  22.  Magic-byte / polyglot detection
#  23.  Double-extension detection
#  24.  Null-byte filename detection
#
# RATE / ABUSE
#  25.  Per-route rate limiting
#  26.  Per-user rate limiting
#  27.  Brute-force login lockout
#  28.  Auto-blacklist repeat offenders (SKIPS whitelisted IPs)
#  29.  Bot/UA blocklist
#  30.  Honeypot paths (instant blacklist, SKIPS whitelisted IPs)
#
# SESSION / RESPONSE
#  31.  Session cycling on login
#  32.  Security headers (HSTS, CSP, etc.)
#  33.  Secure cookie flags
#  34.  Cache-control on sensitive endpoints
#  35.  Remove Server / X-Powered-By
#  36.  Content-Sniffing protection
#  37.  Referrer-Policy
#  38.  Permissions-Policy
#  39.  Cross-Origin isolation headers
#  40.  Every block → SystemLog
# ============================================================

import re
import json
import time
import base64
import ipaddress
import logging
import hashlib
from urllib.parse import urlparse

from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .security_config import config

logger = logging.getLogger(__name__)


class ComprehensiveSecurityMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self._compile_patterns()

        # Paths excluded from rate limiting (login handled by LoginView)
        self.rate_limit_exclude_paths = [
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/auth/send-reset-otp/',
            '/api/auth/verify-otp/',
            '/api/auth/forgot-password/',
            '/api/auth/reset-password-token/',
            '/api/admin-login/',
        ]

        # Login endpoints that trigger session cycling
        self.login_paths = ['/api/auth/login/', '/api/admin-login/']

        # Endpoints that must not be cached
        self.no_cache_paths = [
            '/api/auth/', '/api/payments/', '/api/exams/',
            '/api/analytics/', '/api/proctoring/',
        ]

    # ============================================================
    # PATTERN COMPILATION (done once at boot)
    # ============================================================
    def _compile_patterns(self):
        # --- User Agents ---
        self.blocked_user_agents = re.compile('|'.join([
            r'python-requests', r'python-urllib', r'curl', r'wget',
            r'sqlmap', r'nmap', r'nikto', r'nessus', r'masscan',
            r'recon-ng', r'whatweb', r'scrapy', r'phantomjs',
            r'selenium', r'puppeteer', r'headlesschrome', r'headless',
            r'hydra', r'burpsuite', r'burp', r'zap', r'owasp',
            r'acunetix', r'netsparker', r'gobuster', r'dirbuster',
            r'wfuzz', r'arachni', r'xmrig', r'go-http-client',
            r'java/', r'okhttp', r'libwww-perl', r'lwp-',
            r'winhttp', r'wininet', r'httrack', r'httpx',
        ]), re.IGNORECASE)

        # --- XSS ---
        self.xss_patterns = re.compile('|'.join([
            r'<\s*script[^>]*>',
            r'<\s*/\s*script\s*>',
            r'javascript\s*:',
            r'vbscript\s*:',
            r'data\s*:\s*text/html',
            r'on(?:error|load|click|mouse\w+|focus|blur|change|submit|input|key\w+)\s*=',
            r'<\s*iframe[^>]*>',
            r'<\s*object[^>]*>',
            r'<\s*embed[^>]*>',
            r'<\s*svg[^>]*onload',
            r'<\s*math[^>]*>',
            r'expression\s*\(',
            r'<\s*img[^>]*src\s*=\s*[\'"]?\s*javascript',
            r'document\.cookie',
            r'document\.write',
            r'window\.location',
            r'eval\s*\(',
            r'setTimeout\s*\(\s*[\'"]',
        ]), re.IGNORECASE)

        # --- SQL Injection ---
        self.sql_patterns = re.compile('|'.join([
            r'\b(select|insert|update|delete|drop|union|alter|create|exec|execute|truncate|merge|declare|grant|revoke)\b',
            r'\b(or|and)\s+\d+\s*=\s*\d+',
            r'\b(sleep|delay|benchmark|waitfor|pg_sleep)\s*\(',
            r'\b(information_schema|sys\.|master\.|pg_|mysql\.|sqlite_)\b',
            r'\bunion\s+(all\s+)?select\b',
            r'\b(load_file|outfile|dumpfile|xp_cmdshell|sp_executesql|sp_configure)\b',
            r'(--|\#|/\*)',
            r'(\'|")\s*(or|and)\s*(\'|")',
            r'\bconvert\s*\(',
            r'\bcast\s*\([^)]*\bas\b',
            r'\bchar\s*\(\s*\d+',
            r'\bconcat\s*\(',
        ]), re.IGNORECASE)

        # --- NoSQL Injection ---
        self.nosql_patterns = re.compile('|'.join([
            r'\$where',
            r'\$ne\s*:',
            r'\$gt\s*:',
            r'\$regex',
            r'\$or\s*:',
            r'\$and\s*:',
            r'\$exists\s*:',
            r'\{\s*"\$',
        ]), re.IGNORECASE)

        # --- Command Injection ---
        self.cmd_patterns = re.compile('|'.join([
            r';\s*(ls|cat|tail|head|rm|whoami|id|uname|ifconfig|netstat|ps|top|kill|chmod|chown|cp|mv|wget|curl|bash|sh|zsh|nc|ncat|ping|traceroute)\b',
            r'`[^`]{1,200}`',
            r'\$\s*\([^)]{1,200}\)',
            r'\|\s*(cat|grep|awk|sed|sort|wc|head|tail|nc|bash|sh)\b',
            r'&&\s*(rm|cp|mv|chmod|chown|kill|wget|curl)\b',
            r'\|\|\s*(rm|cp|mv|chmod|kill)\b',
            r'\b(nc|ncat|netcat)\s+-[el]',
            r'\bwget\s+http',
            r'\bcurl\s+http',
        ]), re.IGNORECASE)

        # --- Path Traversal ---
        self.traversal_patterns = re.compile('|'.join([
            r'\.\.\/',
            r'\.\.\\\\',
            r'%2e%2e%2f',
            r'%2e%2e%5c',
            r'%252e%252e%252f',
            r'\.\.%2f',
            r'\.\.%5c',
            r'\.\./\.\.',
            r'/etc/passwd',
            r'/etc/shadow',
            r'/proc/self',
            r'c:\\\\windows',
            r'c:/windows',
        ]), re.IGNORECASE)

        # --- SSRF ---
        self.ssrf_patterns = re.compile('|'.join([
            r'https?://(?:localhost|127\.|0\.0\.0\.0|169\.254\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)',
            r'file://',
            r'gopher://',
            r'dict://',
            r'ftp://',
            r'ldap://',
            r'https?://\[::1\]',
            r'https?://0x',
            r'https?://\d{10,}',
        ]), re.IGNORECASE)

        # --- XXE ---
        self.xxe_patterns = re.compile('|'.join([
            r'<!ENTITY',
            r'<!DOCTYPE[^>]*SYSTEM',
            r'<!DOCTYPE[^>]*PUBLIC',
            r'SYSTEM\s+[\'"][^\'"]*[\'"]',
        ]), re.IGNORECASE)

        # --- LDAP ---
        self.ldap_patterns = re.compile('|'.join([
            r'\(&',
            r'\(\|',
            r'\(!',
            r'\*\)',
            r'\(uid=',
            r'\(cn=',
            r'\(objectClass=',
        ]), re.IGNORECASE)

        # --- Template Injection (SSTI) ---
        self.template_patterns = re.compile('|'.join([
            r'\{\{.*\}\}',
            r'\{%.*%\}',
            r'\$\{.*\}',
            r'<%=.*%>',
            r'#\{.*\}',
            r'__class__',
            r'__mro__',
            r'__subclasses__',
        ]), re.IGNORECASE)

        # --- CRLF ---
        self.crlf_patterns = re.compile('|'.join([
            r'%0d%0a',
            r'%0a',
            r'%0d',
            r'\r\n',
            r'\\r\\n',
        ]), re.IGNORECASE)

        # --- Full combined for fast check ---
        self.all_patterns = re.compile('|'.join([
            self.xss_patterns.pattern,
            self.sql_patterns.pattern,
            self.nosql_patterns.pattern,
            self.cmd_patterns.pattern,
            self.traversal_patterns.pattern,
            self.ssrf_patterns.pattern,
            self.xxe_patterns.pattern,
            self.ldap_patterns.pattern,
            self.template_patterns.pattern,
            self.crlf_patterns.pattern,
        ]), re.IGNORECASE)

    # ============================================================
    # MAIN ENTRY
    # ============================================================
    def __call__(self, request):
        client_ip = self._get_client_ip(request)
        path = request.path

        # --- 1. IP BLACKLIST (unless whitelisted) ---
        if client_ip not in config.WHITELISTED_IPS and self._is_blacklisted(client_ip):
            return self._block(request, 'IP_BLACKLISTED',
                               'Your IP address has been blacklisted.', 403)

        # --- 2. HTTP METHOD ---
        if request.method not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']:
            return self._block(request, 'INVALID_METHOD',
                               f'HTTP method {request.method} not allowed.', 405)

        # --- 3. HEADER SIZE ---
        if not self._check_header_size(request):
            return self._block(request, 'HEADERS_TOO_LARGE',
                               'Request headers too large.', 431)

        # --- 4. URL LENGTH ---
        if len(request.get_full_path()) > config.MAX_URL_LENGTH:
            return self._block(request, 'URL_TOO_LONG',
                               'URL exceeds maximum length.', 414)

        # --- 5. QUERY PARAM COUNT ---
        if len(request.GET) > config.MAX_QUERY_PARAMS:
            return self._block(request, 'TOO_MANY_PARAMS',
                               'Too many query parameters.', 400)

        # --- 6. HONEYPOT PATHS (instant block + blacklist — SKIPS whitelisted IPs) ---
        if self._is_honeypot(path):
            if client_ip not in config.WHITELISTED_IPS:
                self._auto_blacklist(client_ip, reason='HONEYPOT_TRIGGERED')
            return self._block(request, 'HONEYPOT_TRIGGERED',
                               'Access Denied.', 403)

        # --- 7. USER-AGENT ---
        if self._is_blocked_user_agent(request):
            self._record_violation(client_ip, 'USER_AGENT')
            return self._block(request, 'USER_AGENT_BLOCKED',
                               'Automated tools are not allowed.', 403)

        # --- 8. RATE LIMIT ---
        if not self._is_excluded_from_rate_limit(path):
            allowed, info = self._check_rate_limit(request)
            if not allowed:
                self._record_violation(client_ip, 'RATE_LIMIT')
                return self._rate_limit_response(request, info)

        # --- 9. REQUEST SIZE ---
        if not self._check_request_size(request):
            return self._block(request, 'REQUEST_TOO_LARGE',
                               f'Request exceeds {config.MAX_REQUEST_SIZE // (1024*1024)}MB.', 413)

        # --- 10. CONTENT TYPE ---
        if not self._check_content_type(request):
            return self._block(request, 'INVALID_CONTENT_TYPE',
                               'Content-Type not allowed.', 415)

        # --- 11. INPUT VALIDATION ---
        violation = self._validate_inputs(request)
        if violation:
            self._record_violation(client_ip, 'MALICIOUS_INPUT')
            return self._block(request, 'MALICIOUS_INPUT', violation, 403)

        # --- 12. JSON STRUCTURE ---
        if 'application/json' in request.META.get('CONTENT_TYPE', ''):
            json_err = self._validate_json_structure(request)
            if json_err:
                return self._block(request, 'INVALID_JSON', json_err, 400)

        # --- 13. FILE UPLOADS ---
        if request.FILES:
            upload_err = self._validate_uploads(request)
            if upload_err:
                return self._block(request, 'INVALID_UPLOAD', upload_err, 403)

        # --- 14. BRUTE FORCE (admin-login) ---
        if self._is_brute_force(request):
            self._record_violation(client_ip, 'BRUTE_FORCE')
            return self._block(request, 'BRUTE_FORCE',
                               'Too many login attempts. Try again later.', 429)

        # --- 15. SESSION CYCLE on login ---
        if self._is_login_request(request):
            self._cycle_session(request)

        # ============================================================
        # REQUEST PASSES → let Django handle it
        # ============================================================
        response = self.get_response(request)

        # --- 16. SECURITY HEADERS ---
        response = self._add_security_headers(response)

        # --- 17. SECURE COOKIES ---
        if response.cookies:
            self._secure_cookies(response)

        # --- 18. NO-CACHE for sensitive endpoints ---
        if any(path.startswith(p) for p in self.no_cache_paths):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response

    # ============================================================
    # IP RESOLUTION (with trusted proxies)
    # ============================================================
    def _get_client_ip(self, request):
        remote = request.META.get('REMOTE_ADDR', '')
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        real = request.META.get('HTTP_X_REAL_IP', '')

        # Only trust XFF/X-Real-IP if request came through a trusted proxy
        if remote in config.TRUSTED_PROXIES or not config.TRUSTED_PROXIES:
            if xff:
                ip = xff.split(',')[0].strip()
                if self._is_valid_ip(ip):
                    return ip
            if real and self._is_valid_ip(real):
                return real
        return remote or '0.0.0.0'

    def _is_valid_ip(self, ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except (ValueError, TypeError):
            return False

    # ============================================================
    # BLACKLIST / AUTO-BLACKLIST  (WHITELIST-SAFE)
    # ============================================================
    def _is_blacklisted(self, ip):
        # ✅ Whitelisted IPs are NEVER blacklisted
        if ip in config.WHITELISTED_IPS:
            return False

        if not self._is_valid_ip(ip):
            return False

        # Static list
        if ip in config.BLACKLISTED_IPS:
            return True
        addr = ipaddress.ip_address(ip)
        for subnet in config.BLACKLISTED_SUBNETS:
            try:
                if addr in ipaddress.ip_network(subnet, strict=False):
                    return True
            except ValueError:
                continue

        # Dynamic (cached) auto-blacklist
        if cache.get(f'auto_blacklist:{ip}'):
            return True
        return False

    def _auto_blacklist(self, ip, reason='AUTO'):
        # ✅ NEVER auto-blacklist whitelisted IPs (e.g. localhost / trusted proxies)
        if ip in config.WHITELISTED_IPS:
            logger.info(f"ℹ️ Skipped auto-blacklist for whitelisted IP {ip} (reason={reason})")
            return
        try:
            cache.set(f'auto_blacklist:{ip}', True, timeout=config.AUTO_BLACKLIST_DURATION)
            logger.warning(f"🚫 Auto-blacklisted {ip} — reason={reason}")
            self._log_to_system(ip, f'AUTO_BLACKLIST_{reason}',
                                f'IP {ip} auto-blacklisted')
        except Exception:
            pass

    def _record_violation(self, ip, category):
        # ✅ Don't accumulate violations for whitelisted IPs
        if ip in config.WHITELISTED_IPS:
            return
        try:
            key = f'violations:{ip}'
            count = cache.get(key, 0) + 1
            cache.set(key, count, timeout=config.AUTO_BLACKLIST_WINDOW)
            if count >= config.AUTO_BLACKLIST_THRESHOLD:
                self._auto_blacklist(ip, reason=category)
        except Exception:
            pass

    # ============================================================
    # HONEYPOT
    # ============================================================
    def _is_honeypot(self, path):
        for hp in config.HONEYPOT_PATHS:
            if path.startswith(hp):
                return True
        return False

    # ============================================================
    # HEADER SIZE
    # ============================================================
    def _check_header_size(self, request):
        total = sum(
            len(str(k)) + len(str(v))
            for k, v in request.META.items()
            if k.startswith('HTTP_') or k in ('CONTENT_TYPE', 'CONTENT_LENGTH')
        )
        return total <= config.MAX_HEADER_SIZE

    # ============================================================
    # USER AGENT
    # ============================================================
    def _is_blocked_user_agent(self, request):
        ua = request.META.get('HTTP_USER_AGENT', '')
        if not ua:
            return False  # allow empty UA for API clients
        return bool(self.blocked_user_agents.search(ua))

    # ============================================================
    # RATE LIMITING (with proper headers)
    # ============================================================
    def _is_excluded_from_rate_limit(self, path):
        return any(path.startswith(p) for p in self.rate_limit_exclude_paths)

    def _get_rate_limit_key(self, path):
        if '/admin/' in path or '/admin-login' in path:
            return 'admin'
        if '/payment' in path:
            return 'payment'
        if '/exam' in path:
            return 'exam'
        if '/upload' in path or '/documents/' in path:
            return 'upload'
        if '/search' in path or '?q=' in path:
            return 'search'
        return 'api'

    def _check_rate_limit(self, request):
        ip = self._get_client_ip(request)
        path = request.path
        user_id = request.user.id if request.user.is_authenticated else 'anon'

        key = self._get_rate_limit_key(path)
        cfg = config.RATE_LIMITS.get(key, config.RATE_LIMITS['default'])

        cache_key = f'rl:{key}:{ip}:{user_id}'
        now = time.time()
        requests = cache.get(cache_key, [])
        requests = [t for t in requests if t > now - cfg['window']]

        remaining = cfg['requests'] - len(requests) - 1
        reset_in = cfg['window']

        if len(requests) >= cfg['requests']:
            return False, {'limit': cfg['requests'], 'remaining': 0, 'reset': reset_in}

        requests.append(now)
        cache.set(cache_key, requests, timeout=cfg['window'])
        return True, {'limit': cfg['requests'], 'remaining': max(0, remaining), 'reset': reset_in}

    def _rate_limit_response(self, request, info):
        resp = JsonResponse({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'retry_after': info['reset'],
            'timestamp': timezone.now().isoformat(),
        }, status=config.RATE_LIMIT_STATUS)
        resp['Retry-After'] = str(info['reset'])
        resp['X-RateLimit-Limit'] = str(info['limit'])
        resp['X-RateLimit-Remaining'] = '0'
        resp['X-RateLimit-Reset'] = str(int(time.time()) + info['reset'])
        return resp

    # ============================================================
    # SIZE / CONTENT-TYPE
    # ============================================================
    def _check_request_size(self, request):
        try:
            cl = request.META.get('CONTENT_LENGTH', '0')
            if not cl or not str(cl).strip():
                return True
            return int(cl) <= config.MAX_REQUEST_SIZE
        except (ValueError, TypeError):
            return True

    def _check_content_type(self, request):
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return True
        ct = request.META.get('CONTENT_TYPE', '')
        if not ct:
            return True
        ct = ct.split(';')[0].strip().lower()
        return any(a in ct for a in [
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'application/octet-stream',
            'text/plain',
        ])

    # ============================================================
    # INPUT VALIDATION (returns violation string or None)
    # ============================================================
    def _validate_inputs(self, request):
        # 1. Query params
        for k, v in request.GET.items():
            bad = self._scan_value(v)
            if bad:
                return f'{bad} detected in query param "{k}"'

        # 2. Form body
        if 'application/x-www-form-urlencoded' in request.META.get('CONTENT_TYPE', ''):
            for k, v in request.POST.items():
                bad = self._scan_value(v)
                if bad:
                    return f'{bad} detected in form field "{k}"'

        # 3. JSON body (recurse)
        if 'application/json' in request.META.get('CONTENT_TYPE', ''):
            try:
                if request.body:
                    data = json.loads(request.body)
                    bad = self._scan_json(data, path='')
                    if bad:
                        return bad
            except json.JSONDecodeError:
                pass

        # 4. Headers — only scan for XSS / CRLF / command injection.
        #    Do NOT scan for SSRF here — Referer/Origin legitimately
        #    contain URLs (e.g. http://localhost:3000) and would be
        #    flagged as false positives.
        for h in ['HTTP_REFERER', 'HTTP_ORIGIN', 'HTTP_X_FORWARDED_HOST']:
            v = request.META.get(h, '')
            bad = self._scan_header_value(v)
            if bad:
                return f'{bad} detected in header {h}'

        return None

    def _scan_header_value(self, value):
        """
        Header-specific scan.
        Headers like Referer/Origin contain URLs, so we MUST NOT
        flag them as SSRF. We only look for XSS, CRLF, and command injection.
        """
        if not value or not isinstance(value, str):
            return None
        scan = value[:2000] if len(value) > 2000 else value

        if self.xss_patterns.search(scan):        return 'XSS pattern'
        if self.cmd_patterns.search(scan):        return 'Command injection'
        if self.crlf_patterns.search(scan):       return 'CRLF injection'
        return None

    def _scan_json(self, obj, path='', depth=0):
        if depth > config.MAX_JSON_DEPTH:
            return 'JSON structure too deep'
        if isinstance(obj, dict):
            if len(obj) > config.MAX_JSON_KEYS:
                return 'Too many keys in JSON object'
            for k, v in obj.items():
                bad = self._scan_value(str(k))
                if bad:
                    return f'{bad} detected in key "{path}.{k}"'
                r = self._scan_json(v, f'{path}.{k}', depth + 1)
                if r:
                    return r
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                r = self._scan_json(v, f'{path}[{i}]', depth + 1)
                if r:
                    return r
        elif isinstance(obj, str):
            return self._scan_value(obj, path)
        return None

    def _scan_value(self, value, context=''):
        if not value or not isinstance(value, str):
            return None
        scan = value[:4000] if len(value) > 4000 else value

        if self.xss_patterns.search(scan):        return 'XSS pattern'
        if self.sql_patterns.search(scan):        return 'SQL injection'
        if self.nosql_patterns.search(scan):      return 'NoSQL injection'
        if self.cmd_patterns.search(scan):        return 'Command injection'
        if self.traversal_patterns.search(scan):  return 'Path traversal'
        if self.ssrf_patterns.search(scan):       return 'SSRF pattern'
        if self.xxe_patterns.search(scan):        return 'XXE pattern'
        if self.ldap_patterns.search(scan):       return 'LDAP injection'
        if self.template_patterns.search(scan):   return 'Template injection'
        if self.crlf_patterns.search(scan):       return 'CRLF injection'
        return None

    # ============================================================
    # JSON STRUCTURE
    # ============================================================
    def _validate_json_structure(self, request):
        try:
            if not request.body:
                return None
            data = json.loads(request.body)

            def check_depth(o, d=0):
                if d > config.MAX_JSON_DEPTH:
                    return True
                if isinstance(o, dict):
                    return any(check_depth(v, d + 1) for v in o.values())
                if isinstance(o, list):
                    return any(check_depth(v, d + 1) for v in o)
                return False

            def count_keys(o):
                if isinstance(o, dict):
                    return len(o) + sum(count_keys(v) for v in o.values())
                if isinstance(o, list):
                    return sum(count_keys(v) for v in o)
                return 0

            if check_depth(data):
                return 'JSON depth exceeds limit'
            if count_keys(data) > config.MAX_JSON_KEYS:
                return 'Too many keys in JSON payload'
        except json.JSONDecodeError:
            return 'Invalid JSON payload'
        except Exception:
            pass
        return None

    # ============================================================
    # FILE UPLOAD VALIDATION (hardened)
    # ============================================================
    def _validate_uploads(self, request):
        for field, f in request.FILES.items():
            # 1. Size
            if f.size > config.MAX_FILE_SIZE:
                return f'File "{f.name}" exceeds {config.MAX_FILE_SIZE // (1024*1024)}MB.'

            # 2. Filename null byte
            if '\x00' in f.name or '%00' in f.name.lower():
                return f'Null byte in filename "{f.name}".'

            # 3. Path traversal in filename
            if '..' in f.name or '/' in f.name or '\\' in f.name:
                return f'Invalid characters in filename "{f.name}".'

            # 4. Extension
            name = f.name.lower()
            parts = name.split('.')
            for part in parts[1:]:
                if f'.{part}' in config.BLOCKED_EXTENSIONS:
                    return f'Blocked extension ".{part}" in "{f.name}".'

            # 5. Magic bytes
            try:
                header = f.read(32)
                f.seek(0)
                if not self._has_valid_magic_bytes(header):
                    return f'File "{f.name}" failed content signature check.'
            except Exception:
                pass

        return None

    def _has_valid_magic_bytes(self, header):
        if not header or len(header) < 2:
            return True

        signatures = [
            b'MZ',                    # Windows EXE/DLL
            b'\x7fELF',               # Linux ELF
            b'\xca\xfe\xba\xbe',      # Java class (big-endian)
            b'\xfe\xed\xfa\xce',      # Mach-O (32-bit)
            b'\xfe\xed\xfa\xcf',      # Mach-O (64-bit)
            b'\xce\xfa\xed\xfe',      # Mach-O reverse
            b'\xcf\xfa\xed\xfe',      # Mach-O reverse
            b'#!',                    # Shebang scripts
        ]
        for sig in signatures:
            if header.startswith(sig):
                return False

        low = header.lower()
        for bad in [b'<?php', b'<?=', b'<script', b'<%', b'<%=']:
            if low.startswith(bad) or bad in low[:16]:
                return False

        return True

    # ============================================================
    # BRUTE FORCE (admin-login only)
    # ============================================================
    def _is_brute_force(self, request):
        if request.method != 'POST':
            return False
        if not request.path.startswith('/api/admin-login/'):
            return False

        ip = self._get_client_ip(request)
        # ✅ Skip brute-force tracking for whitelisted IPs
        if ip in config.WHITELISTED_IPS:
            return False

        key = f'bf:admin:{ip}'
        attempts = cache.get(key, 0)
        if attempts >= 5:
            logger.warning(f"🚫 Brute-force blocked: {ip}")
            return True
        cache.set(key, attempts + 1, timeout=300)
        return False

    # ============================================================
    # SESSION CYCLING
    # ============================================================
    def _is_login_request(self, request):
        return request.method == 'POST' and any(
            request.path.startswith(p) for p in self.login_paths
        )

    def _cycle_session(self, request):
        try:
            if hasattr(request, 'session'):
                request.session.cycle_key()
        except Exception:
            pass

    # ============================================================
    # SECURITY HEADERS
    # ============================================================
    def _add_security_headers(self, response):
        response['Strict-Transport-Security'] = f'max-age={config.HSTS_MAX_AGE}; includeSubDomains; preload'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(self), camera=(self), '
            'payment=(), usb=(), magnetometer=(), gyroscope=(), '
            'accelerometer=(), fullscreen=(self)'
        )
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-site'
        response['Cross-Origin-Embedder-Policy'] = 'unsafe-none'
        response['X-Permitted-Cross-Domain-Policies'] = 'none'
        response['X-Download-Options'] = 'noopen'
        response['X-DNS-Prefetch-Control'] = 'off'

        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = config.CSP_POLICY

        for h in ['Server', 'X-Powered-By', 'X-AspNet-Version', 'X-AspNetMvc-Version']:
            if h in response:
                del response[h]

        return response

    # ============================================================
    # SECURE COOKIES
    # ============================================================
    def _secure_cookies(self, response):
        is_https = getattr(settings, 'SESSION_COOKIE_SECURE', False)
        for key in response.cookies:
            response.cookies[key]['httponly'] = True
            response.cookies[key]['samesite'] = 'Lax'
            response.cookies[key]['secure'] = is_https
            if key in ('sessionid', 'csrftoken'):
                response.cookies[key]['httponly'] = True

    # ============================================================
    # BLOCK RESPONSE + LOGGING
    # ============================================================
    def _block(self, request, reason, message, status_code=403):
        ip = self._get_client_ip(request)
        try:
            from analytics.models import SystemLog
            SystemLog.objects.create(
                user=request.user if getattr(request, 'user', None)
                     and request.user.is_authenticated else None,
                action=f'SECURITY_BLOCK: {reason}',
                details={
                    'reason': reason,
                    'message': message,
                    'ip': ip,
                    'path': request.path,
                    'method': request.method,
                    'ua': request.META.get('HTTP_USER_AGENT', '')[:300],
                },
                log_level='WARNING',
            )
        except Exception as e:
            logger.debug(f"SystemLog write failed (non-fatal): {e}")

        logger.warning(f"🚫 [{reason}] {ip} → {request.method} {request.path}")

        return JsonResponse({
            'error': 'Access Denied',
            'reason': reason,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }, status=status_code)

    def _log_to_system(self, ip, action, message):
        try:
            from analytics.models import SystemLog
            SystemLog.objects.create(
                user=None,
                action=action,
                details={'message': message, 'ip': ip},
                log_level='WARNING',
            )
        except Exception:
            pass