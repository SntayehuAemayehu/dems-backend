from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class ActivityLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # A simple placeholder that logs activity
        user = request.user if request.user.is_authenticated else "Anonymous"
        logger.info(f"Activity: {user} accessed {request.path}")