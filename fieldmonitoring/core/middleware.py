"""API answers must never be stored by a proxy or a browser.

Field test, 10 Nov: the proxy in front of the production server kept GET answers of `/api/` for
minutes. Supervisors saw positions they had just confirmed, and the app could receive an old
clock anchor from `/health/`. A view that sets its own `Cache-Control` (the photo) keeps it.
"""


class ApiNoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and not response.has_header("Cache-Control"):
            response["Cache-Control"] = "no-store, private"
        return response
