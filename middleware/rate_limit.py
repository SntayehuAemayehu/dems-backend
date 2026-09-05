# backend/middleware/rate_limit.py - COMPLETE FIXED
import time
from django.http import JsonResponse
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    """Rate limiting - EXCLUDES login/register to allow per-user brute force tracking"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            'admin': {'requests': 30, 'window': 60},
            'api': {'requests': 120, 'window': 60},
            'payment': {'requests': 10, 'window': 60},
            'default': {'requests': 100, 'window': 60},
        }
        
        # EXCLUDE PATHS FROM RATE LIMITING
        self.exclude_paths = [
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/send-reset-otp',
            '/api/auth/verify-otp',
            '/api/auth/forgot-password',
            '/api/admin-login',
        ]
    
    def __call__(self, request):
        # Skip excluded paths
        for path in self.exclude_paths:
            if request.path.startswith(path):
                return self.get_response(request)
        
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
            return JsonResponse({
                'error': 'Too Many Requests',
                'message': 'Please wait a moment and try again.',
                'retry_after': limit_config['window']
            }, status=429)
        
        requests.append(current_time)
        cache.set(cache_key, requests, timeout=limit_config['window'])
        
        response = self.get_response(request)
        
        # Add rate limit headers
        response['X-RateLimit-Limit'] = str(limit_config['requests'])
        response['X-RateLimit-Remaining'] = str(limit_config['requests'] - len(requests))
        response['X-RateLimit-Reset'] = str(limit_config['window'])
        
        return response
    
    def _get_rate_limit_key(self, path):
        if '/admin/' in path:
            return 'admin'
        elif '/payment' in path:
            return 'payment'
        else:
            return 'api'
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')