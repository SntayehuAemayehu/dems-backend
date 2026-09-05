# backend/middleware/security_middleware.py
# COMPLETE SECURITY MIDDLEWARE

from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
import re
import json
from collections import defaultdict
import time

class SecurityHeadersMiddleware:
    """Add security headers to all responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # ✅ HSTS - Force HTTPS
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # ✅ Prevent XSS attacks
        response['X-XSS-Protection'] = '1; mode=block'
        
        # ✅ Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # ✅ Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # ✅ Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://*; "
            "connect-src 'self' https://*;"
        )
        
        # ✅ Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # ✅ Permissions Policy
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response


class RateLimitMiddleware:
    """Rate limiting for all requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            'login': {'requests': 5, 'window': 60},      # 5 per minute
            'register': {'requests': 3, 'window': 3600},  # 3 per hour
            'otp': {'requests': 3, 'window': 3600},       # 3 per hour
            'api': {'requests': 100, 'window': 60},       # 100 per minute
            'payment': {'requests': 10, 'window': 60},    # 10 per minute
            'admin': {'requests': 30, 'window': 60},      # 30 per minute
        }
    
    def __call__(self, request):
        # ✅ Determine rate limit key
        key = self._get_rate_limit_key(request)
        if key:
            limit = self._get_limit(request)
            if limit and not self._check_rate_limit(key, limit['requests'], limit['window']):
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Please try again later.',
                    'retry_after': limit['window'],
                }, status=429)
        
        return self.get_response(request)
    
    def _get_rate_limit_key(self, request):
        """Generate a unique key for rate limiting"""
        ip = self._get_client_ip(request)
        path = request.path
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        
        # ✅ Different limits for different endpoints
        if '/api/auth/login' in path:
            return f'ratelimit:login:{ip}'
        elif '/api/auth/register' in path:
            return f'ratelimit:register:{ip}'
        elif '/api/auth/send-reset-otp' in path:
            return f'ratelimit:otp:{ip}'
        elif '/api/admin/' in path:
            return f'ratelimit:admin:{user_id}:{ip}'
        elif '/api/payments/' in path:
            return f'ratelimit:payment:{user_id}'
        else:
            return f'ratelimit:api:{user_id}:{ip}'
    
    def _get_limit(self, request):
        """Get rate limit for the request"""
        path = request.path
        if '/api/auth/login' in path:
            return self.rate_limits['login']
        elif '/api/auth/register' in path:
            return self.rate_limits['register']
        elif '/api/auth/send-reset-otp' in path:
            return self.rate_limits['otp']
        elif '/api/admin/' in path:
            return self.rate_limits['admin']
        elif '/api/payments/' in path:
            return self.rate_limits['payment']
        else:
            return self.rate_limits['api']
    
    def _check_rate_limit(self, key, limit, window):
        """Check if rate limit is exceeded"""
        current = time.time()
        requests = cache.get(key, [])
        
        # ✅ Clean old requests
        requests = [t for t in requests if t > current - window]
        
        if len(requests) >= limit:
            return False
        
        requests.append(current)
        cache.set(key, requests, timeout=window)
        return True
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class SQLInjectionMiddleware:
    """Detect and block SQL injection attempts"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.sql_patterns = [
            r'(\b)(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE)\b',
            r'(\b)(OR|AND)\s+\d+\s*=\s*\d+',
            r'(\b)(SLEEP|DELAY|BENCHMARK|WAITFOR)\s*\(',
            r'(\b)(FROM|WHERE|HAVING|GROUP BY|ORDER BY)\s+',
            r'(\b)(INFORMATION_SCHEMA|sys\.|master\.|pg_|mysql\.)',
            r'(\b)(UNION\s+SELECT|UNION\s+ALL)',
            r'(\b)(\-\-|#|\/\*)',
            r'(\b)(xp_cmdshell|sp_executesql|sp_configure)',
        ]
    
    def __call__(self, request):
        # ✅ Check query parameters
        for key, value in request.GET.items():
            if self._check_sql_injection(value):
                return self._block_request(request, f'SQL Injection detected in parameter: {key}')
        
        # ✅ Check POST data
        if request.method == 'POST':
            for key, value in request.POST.items():
                if self._check_sql_injection(value):
                    return self._block_request(request, f'SQL Injection detected in field: {key}')
            
            # ✅ Check JSON body
            if request.content_type == 'application/json':
                try:
                    body = json.loads(request.body)
                    for key, value in body.items():
                        if isinstance(value, str) and self._check_sql_injection(value):
                            return self._block_request(request, f'SQL Injection detected in JSON field: {key}')
                except:
                    pass
        
        return self.get_response(request)
    
    def _check_sql_injection(self, value):
        """Check if value contains SQL injection patterns"""
        if not value or not isinstance(value, str):
            return False
        
        value = value.lower()
        for pattern in self.sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    def _block_request(self, request, reason):
        """Block malicious request"""
        # ✅ Log the attack
        from analytics.models import SystemLog
        SystemLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action='SECURITY_BLOCK',
            details={
                'reason': reason,
                'ip': self._get_client_ip(request),
                'path': request.path,
                'method': request.method,
            },
            log_level='WARNING'
        )
        
        return JsonResponse({
            'error': 'Access Denied',
            'message': 'Your request was blocked for security reasons.',
            'timestamp': timezone.now().isoformat(),
        }, status=403)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class SecureCookieMiddleware:
    """Secure cookie handling"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # ✅ Verify session cookie
        if request.session.get('_session_cookie_verified') != True:
            # ✅ Check if session is valid
            if request.session.session_key:
                # ✅ Validate session data
                if not self._validate_session(request):
                    request.session.flush()
                    request.session['_session_cookie_verified'] = True
                    return JsonResponse({
                        'error': 'Invalid Session',
                        'message': 'Please login again.',
                    }, status=401)
            request.session['_session_cookie_verified'] = True
        
        response = self.get_response(request)
        
        # ✅ Secure cookies
        response.set_cookie(
            'sessionid',
            request.session.session_key,
            secure=True,
            httponly=True,
            samesite='Lax',
        )
        
        return response
    
    def _validate_session(self, request):
        """Validate session data"""
        # ✅ Check session age
        if request.session.get('_session_init_time'):
            session_age = timezone.now().timestamp() - request.session['_session_init_time']
            if session_age > 86400:  # 24 hours
                return False
        
        # ✅ Check user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if request.session.get('_user_agent_hash'):
            current_hash = hashlib.md5(user_agent.encode()).hexdigest()
            if current_hash != request.session['_user_agent_hash']:
                return False
        
        return True