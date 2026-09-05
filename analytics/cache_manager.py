# backend/analytics/cache_manager.py
# AI CACHE MANAGER FOR PERFORMANCE

from django.core.cache import cache
from functools import wraps
import hashlib
import json

class AICacheManager:
    """Cache manager for AI responses to reduce API calls"""
    
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @staticmethod
    def cache_key(prefix, *args, **kwargs):
        """Generate a unique cache key"""
        key_data = json.dumps({
            'prefix': prefix,
            'args': args,
            'kwargs': kwargs
        }, sort_keys=True)
        return f"ai_{prefix}_{hashlib.md5(key_data.encode()).hexdigest()[:16]}"
    
    @staticmethod
    def get(key):
        """Get cached value"""
        return cache.get(key)
    
    @staticmethod
    def set(key, value, timeout=CACHE_TIMEOUT):
        """Set cached value"""
        cache.set(key, value, timeout)
    
    @staticmethod
    def clear(prefix):
        """Clear cache by prefix"""
        keys = cache.keys(f"ai_{prefix}_*")
        if keys:
            cache.delete_many(keys)

def cache_ai_response(prefix, timeout=3600):
    """Decorator to cache AI responses"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = AICacheManager.cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached = AICacheManager.get(key)
            if cached is not None:
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            if result and result.get('success'):
                AICacheManager.set(key, result, timeout)
            
            return result
        return wrapper
    return decorator

# ============================================================
# APPLY TO OPENAI SERVICE
# ============================================================

# backend/services/openai_service.py - ADD DECORATORS

from analytics.cache_manager import cache_ai_response

class OpenAIService:
    # ... existing code ...
    
    @cache_ai_response('essay_grading', timeout=7200)  # 2 hours
    def grade_essay(self, student_answer, model_answer, rubric="", max_marks=100):
        # ... existing code ...
        pass
    
    @cache_ai_response('plagiarism_check', timeout=3600)  # 1 hour
    def check_plagiarism_ai(self, text, context=""):
        # ... existing code ...
        pass