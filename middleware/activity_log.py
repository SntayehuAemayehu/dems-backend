<<<<<<< HEAD
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class ActivityLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # A simple placeholder that logs activity
        user = request.user if request.user.is_authenticated else "Anonymous"
        logger.info(f"Activity: {user} accessed {request.path}")
=======
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("activity_log")


class ActivityLogMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        try:
            user = request.user

            username = (
                user.username
                if user.is_authenticated
                else "Anonymous"
            )

            logger.info(
                "User: %s | Method: %s | Path: %s | Status: %s",
                username,
                request.method,
                request.path,
                response.status_code
            )

        except Exception:
            pass

        return response
>>>>>>> fef26a3404fa12aab798e3115f08987e95af10f7
