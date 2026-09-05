# backend/middleware/comprehensive_security.py
# ============================================================
# COMPLETE SECURITY MIDDLEWARE - ALL IN ONE FILE
# ============================================================
# FIXED: All methods included, handles empty CONTENT_LENGTH
# ============================================================

import re
import json
import time
import ipaddress
import logging
from collections import defaultdict

from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ComprehensiveSecurityMiddleware:
    """
    COMPREHENSIVE SECURITY MIDDLEWARE
    Combines ALL security mechanisms into one class.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # ============================================================
        # CONFIGURATION
        # ============================================================
        
        # 1. IP BLACKLIST CONFIG
        self.blacklisted_ips = []
        self.blacklisted_subnets = []
        
        # 2. USER AGENT CONFIG
        self.blocked_user_agents = [
            r'python-requests',
            r'curl',
            r'wget',
            r'sqlmap',
            r'nmap',
            r'nikto',
            r'nessus',
            r'httpx',
            r'masscan',
            r'recon-ng',
            r'whatweb',
            r'scrapy',
            r'phantomjs',
            r'selenium',
            r'puppeteer',
            r'headlesschrome',
            r'headless',
            r'python-urllib',
        ]
        
        # 3. SQL INJECTION PATTERNS
        self.sql_patterns = [
            r'(\b)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE|TRUNCATE|MERGE)\b',
            r'(\b)(OR|AND)\s+\d+\s*=\s*\d+',
            r'(\b)(SLEEP|DELAY|BENCHMARK|WAITFOR)\s*\(',
            r'(\b)(FROM|WHERE|HAVING|GROUP BY|ORDER BY)\s+',
            r'(\b)(INFORMATION_SCHEMA|sys\.|master\.|pg_|mysql\.)',
            r'(\b)(UNION\s+SELECT|UNION\s+ALL)',
            r'(\b)(\-\-|#|\/\*)',
            r'(\b)(xp_cmdshell|sp_executesql|sp_configure)',
            r'(\b)(LOAD_FILE|OUTFILE|DUMPFILE)\s*\(',
        ]
        
        # 4. XSS PATTERNS
        self.xss_patterns = [
            r'<script[^>]*>',
            r'</script>',
            r'javascript:',
            r'onerror\s*=',
            r'onload\s*=',
            r'onclick\s*=',
            r'onmouseover\s*=',
            r'onfocus\s*=',
            r'onblur\s*=',
            r'onchange\s*=',
            r'onsubmit\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
            r'<form[^>]*>',
            r'<svg[^>]*>',
            r'<math[^>]*>',
            r'expression\s*\(',
            r'vbscript:',
            r'data:text/html',
        ]
        
        # 5. COMMAND INJECTION PATTERNS
        self.command_patterns = [
            r';\s*(ls|cat|tail|head|rm|whoami|id|uname|ifconfig|netstat|ps|top|kill)\b',
            r'`[\s\S]*`',
            r'\$\s*\([\s\S]*\)',
            r'\|\s*(cat|grep|awk|sed|sort|wc)\b',
            r'&&\s*(rm|cp|mv|chmod|chown|kill)\b',
        ]
        
        # 6. PATH TRAVERSAL PATTERNS
        self.path_traversal_patterns = [
            r'\.\.\/',
            r'\.\.\\',
            r'%2e%2e%2f',
            r'%2e%2e%5c',
            r'%252e%252e%252f',
            r'..\\',
        ]
        
        # 7. UPLOAD SECURITY CONFIG
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.allowed_extensions = [
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.csv', '.txt', '.mp3', '.mp4', '.webm', '.mov', '.avi',
            '.mkv', '.zip', '.rar', '.7z'
        ]
        self.blocked_extensions = [
            '.exe', '.bat', '.cmd', '.sh', '.php', '.py', '.pl',
            '.cgi', '.asp', '.aspx', '.jsp', '.msi', '.dll',
            '.so', '.bin', '.apk', '.jar', '.class'
        ]
        
        # 8. RATE LIMITING CONFIG
        self.rate_limits = {
            'login': {'requests': 5, 'window': 60},
            'register': {'requests': 3, 'window': 3600},
            'otp': {'requests': 3, 'window': 3600},
            'admin': {'requests': 30, 'window': 60},
            'api': {'requests': 120, 'window': 60},
            'payment': {'requests': 10, 'window': 60},
            'default': {'requests': 100, 'window': 60},
        }
        
        # 9. ALLOWED HTTP METHODS
        self.allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
        
        # 10. ALLOWED CONTENT TYPES
        self.allowed_content_types = [
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
        ]
        
        # 11. BRUTE FORCE CONFIG
        self.brute_force_limit = 5
        self.brute_force_window = 300
        
        # 12. SESSION CONFIG
        self.session_cookie_secure = False
        self.session_cookie_httponly = True
        self.session_cookie_samesite = 'Lax'
        self.session_max_age = 3600
    
    # ============================================================
    # MAIN MIDDLEWARE ENTRY POINT
    # ============================================================
    
    def __call__(self, request):
        # 1. Check HTTP Method
        if request.method not in self.allowed_methods:
            return self._block_request(request, 'INVALID_METHOD', f'HTTP method {request.method} is not allowed.', status_code=405)
        
        # 2. Check IP Blacklist
        if self._is_blacklisted(request):
            return self._block_request(request, 'IP_BLACKLISTED', 'Your IP address has been blacklisted.', status_code=403)
        
        # 3. Check User Agent
        if self._is_blocked_user_agent(request):
            return self._block_request(request, 'USER_AGENT_BLOCKED', 'Automated tools are not allowed.', status_code=403)
        
        # 4. Rate Limiting - ONLY for non-login paths
        if not self._is_login_request(request):  # ✅ SKIP LOGIN
            if not self._check_rate_limit(request):
                return self._block_request(request, 'RATE_LIMIT', 'Too many requests. Please try again later.', status_code=429)
        
        # 5. Check Request Size - FIXED
        if not self._check_request_size(request):
            return self._block_request(request, 'REQUEST_TOO_LARGE', 'Request size exceeds limit.', status_code=413)
        
        # 6. Check Content Type
        if not self._check_content_type(request):
            return self._block_request(request, 'INVALID_CONTENT_TYPE', 'Content type not allowed.', status_code=415)
        
        # 7. Input Validation (GET, POST, JSON)
        validation_result = self._validate_inputs(request)
        if validation_result:
            return validation_result
        
        # 8. Upload Security
        if self._has_file_uploads(request):
            upload_result = self._validate_uploads(request)
            if upload_result:
                return upload_result
        
        # 9. Brute Force Protection - ✅ SKIP LOGIN - HANDLED IN LoginView
        # if self._is_brute_force_attempt(request):  # COMMENTED OUT
        #     return self._block_request(request, 'BRUTE_FORCE', 'Too many login attempts. Please try again later.', status_code=429)
        
        # 10. Session Security
        if self._is_login_request(request):
            self._secure_session(request)
        
        # Process the request
        response = self.get_response(request)
        
        # 11. Add Security Headers
        response = self._add_security_headers(response)
        
        # 12. Secure Cookies
        if response.cookies:
            self._secure_cookies(response)
        
        return response
    # ---------- 1. IP BLACKLIST ----------
    
    def _is_blacklisted(self, request):
        client_ip = self._get_client_ip(request)
        try:
            ip = ipaddress.ip_address(client_ip)
            for blacklisted in self.blacklisted_ips:
                if str(ip) == blacklisted:
                    return True
            for subnet in self.blacklisted_subnets:
                try:
                    network = ipaddress.ip_network(subnet, strict=False)
                    if ip in network:
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False
    
    # ---------- 2. USER AGENT FILTER ----------
    
    def _is_blocked_user_agent(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user_agent:
            return True
        for ua_pattern in self.blocked_user_agents:
            if re.search(ua_pattern, user_agent, re.IGNORECASE):
                return True
        return False
    
    # ---------- 3. RATE LIMITING ----------
    
    def _check_rate_limit(self, request):
        """Check if request exceeds rate limit"""
        # ✅ SKIP RATE LIMITING FOR LOGIN PATHS
        if self._is_login_request(request):
            return True
        
        client_ip = self._get_client_ip(request)
        path = request.path
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        limit_key = self._get_rate_limit_key(path)
        limit_config = self.rate_limits.get(limit_key, self.rate_limits['default'])
        cache_key = f'ratelimit:{limit_key}:{client_ip}:{user_id}'
        current_time = time.time()
        requests = cache.get(cache_key, [])
        requests = [t for t in requests if t > current_time - limit_config['window']]
        if len(requests) >= limit_config['requests']:
            logger.warning(f"RATE LIMIT EXCEEDED: {client_ip} - {path}")
            return False
        requests.append(current_time)
        cache.set(cache_key, requests, timeout=limit_config['window'])
        return True
    
           # backend/middleware/comprehensive_security.py
        # UPDATE _get_rate_limit_key to EXCLUDE login

    def _get_rate_limit_key(self, path):
        """Determine rate limit key from path"""
        # ✅ SKIP LOGIN PATHS - handled in LoginView
        if '/login' in path or '/register' in path:
            return 'default'
        elif '/send-reset-otp' in path or '/verify-otp' in path:
            return 'default'
        elif '/admin/' in path:
            return 'admin'
        elif '/payment' in path:
            return 'payment'
        else:
            return 'api'
    
    # ---------- 4. REQUEST SIZE LIMIT - FIXED ----------
    
    def _check_request_size(self, request):
        """Check if request size is within limits - FIXED"""
        try:
            content_length_str = request.META.get('CONTENT_LENGTH', '0')
            if not content_length_str or not content_length_str.strip():
                content_length = 0
            else:
                content_length = int(content_length_str)
            return content_length <= self.max_file_size
        except (ValueError, TypeError):
            return True
    
    # ---------- 5. CONTENT TYPE VALIDATION ----------
    
    def _check_content_type(self, request):
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return True
        content_type = request.META.get('CONTENT_TYPE', '')
        if not content_type:
            return True
        for allowed_type in self.allowed_content_types:
            if allowed_type in content_type:
                return True
        return False
    
    # ---------- 6. INPUT VALIDATION ----------
    
    def _validate_inputs(self, request):
        for key, value in request.GET.items():
            if self._contains_malicious_content(value):
                return self._block_request(request, 'INPUT_VALIDATION', f'Malicious content detected in parameter: {key}')
        
        if request.method == 'POST' and request.content_type == 'application/x-www-form-urlencoded':
            for key, value in request.POST.items():
                if self._contains_malicious_content(value):
                    return self._block_request(request, 'INPUT_VALIDATION', f'Malicious content detected in field: {key}')
        
        if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
            try:
                if request.body:
                    data = json.loads(request.body)
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, str) and self._contains_malicious_content(value):
                                return self._block_request(request, 'INPUT_VALIDATION', f'Malicious content detected in field: {key}')
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, str) and self._contains_malicious_content(item):
                                return self._block_request(request, 'INPUT_VALIDATION', 'Malicious content detected in JSON list')
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON',
                    'message': 'Request body contains invalid JSON.'
                }, status=400)
        
        return None
    
    def _contains_malicious_content(self, value):
        if not value or not isinstance(value, str):
            return False
        value_lower = value.lower()
        for pattern in self.sql_patterns + self.xss_patterns + self.command_patterns + self.path_traversal_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    # ---------- 7. UPLOAD SECURITY ----------
    
    def _has_file_uploads(self, request):
        return bool(request.FILES) and request.method in ['POST', 'PUT', 'PATCH']
    
    def _validate_uploads(self, request):
        for field_name, file in request.FILES.items():
            if file.size > self.max_file_size:
                return self._block_request(request, 'FILE_TOO_LARGE', f'File "{file.name}" exceeds the {self.max_file_size // (1024*1024)}MB limit.')
            file_extension = self._get_file_extension(file.name)
            if file_extension in self.blocked_extensions:
                return self._block_request(request, 'FILE_TYPE_BLOCKED', f'File type "{file_extension}" is not allowed.')
            if not self._validate_magic_bytes(file):
                return self._block_request(request, 'FILE_CONTENT_VALIDATION', f'File "{file.name}" contains potentially malicious content.')
        return None
    
    def _get_file_extension(self, filename):
        if '.' in filename:
            return filename.rsplit('.', 1)[1].lower()
        return ''
    
    def _validate_magic_bytes(self, file):
        try:
            header = file.read(4)
            file.seek(0)
            if header == b'MZ':
                return False
            if header in [b'<?ph', b'<?xm', b'<htm', b'<!DO', b'<ht']:
                return False
            if b'<?php' in header or b'<script' in header:
                return False
            return True
        except:
            return True
    
    # ---------- 8. BRUTE FORCE PROTECTION ----------
    
    def _is_brute_force_attempt(self, request):
        if request.path not in ['/api/auth/login/', '/api/admin-login/']:
            return False
        client_ip = self._get_client_ip(request)
        email = request.POST.get('email') or request.data.get('email') if hasattr(request, 'data') else None
        cache_key = f'bruteforce:{client_ip}:{email}' if email else f'bruteforce:{client_ip}'
        attempts = cache.get(cache_key, 0)
        if attempts >= self.brute_force_limit:
            logger.warning(f"BRUTE FORCE DETECTED: {client_ip} - {email}")
            return True
        if request.method == 'POST':
            cache.set(cache_key, attempts + 1, timeout=self.brute_force_window)
        return False
    
    # ---------- 9. SESSION SECURITY ----------
    
    def _is_login_request(self, request):
        return request.path in ['/api/auth/login/', '/api/admin-login/'] and request.method == 'POST'
    
    def _secure_session(self, request):
        if request.user.is_authenticated:
            try:
                request.session.cycle_key()
                request.session.set_expiry(self.session_max_age)
            except:
                pass
    
    # ---------- 10. SECURITY HEADERS ----------
    
    def _add_security_headers(self, response):
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-site'
        response['Cache-Control'] = 'no-store, max-age=0'
        if 'X-Powered-By' in response:
            del response['X-Powered-By']
        return response
    
    # ---------- 11. COOKIE SECURITY ----------
    
    def _secure_cookies(self, response):
        for key in response.cookies:
            response.cookies[key]['httponly'] = True
            response.cookies[key]['samesite'] = 'Lax'
            response.cookies[key]['secure'] = self.session_cookie_secure
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def _block_request(self, request, reason, message, status_code=403):
        """Block a request and log the event"""
        
        # Log the security event
        try:
            from analytics.models import SystemLog
            SystemLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=f'SECURITY_BLOCK: {reason}',
                details={
                    'reason': reason,
                    'message': message,
                    'ip': self._get_client_ip(request),
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                },
                log_level='WARNING'
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
        
        logger.warning(f"SECURITY BLOCK: {reason} - {self._get_client_ip(request)} - {request.path}")
        
        return JsonResponse({
            'error': 'Access Denied',
            'reason': reason,
            'message': message,
            'ip': self._get_client_ip(request),
            'timestamp': timezone.now().isoformat(),
        }, status=status_code)