# backend/middleware/session_timeout.py - COMPLETE
import time
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings

class SessionTimeoutMiddleware:
    """Enforce session timeout"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'SESSION_COOKIE_AGE', 1800)  # Default 30 min
    
    def __call__(self, request):
        # Only check for authenticated users
        if request.user.is_authenticated:
            session_key = request.session.session_key
            
            # Track last activity
            last_activity = request.session.get('last_activity', time.time())
            
            # Update last activity
            request.session['last_activity'] = time.time()
            
            # Check if session has expired
            if time.time() - last_activity > self.timeout:
                # Clear session
                request.session.flush()
                
                # For API requests
                if request.path.startswith('/api/'):
                    return JsonResponse({
                        'error': 'Session Expired',
                        'message': 'Your session has expired. Please login again.',
                        'login_required': True
                    }, status=401)
        
        return self.get_response(request)