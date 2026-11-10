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