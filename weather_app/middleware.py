from datetime import datetime
from django.core.cache import cache
from django.http import JsonResponse


class RateLimitMiddleware:
    RATE_LIMIT = 30
    WINDOW = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            ip = self.get_client_ip(request)
            cache_key = f"rate_limit_{ip}"
            data = cache.get(cache_key, {"count": 0, "start": datetime.now()})
            elapsed = (datetime.now() - data["start"]).total_seconds()

            if elapsed > self.WINDOW:
                data = {"count": 1, "start": datetime.now()}
            else:
                if data["count"] >= self.RATE_LIMIT:
                    return JsonResponse(
                        {"error": "Слишком много запросов. Попробуйте через минуту."},
                        status=429
                    )
                data["count"] += 1

            cache.set(cache_key, data, timeout=self.WINDOW)

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
