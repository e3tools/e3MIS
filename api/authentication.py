import re
from django.utils import timezone
from rest_framework import exceptions, authentication

from .models import ApiToken

TOKEN_RE = re.compile(r"^(?P<prefix>[A-Za-z0-9_-]+)-(?P<public_id>[a-f0-9]{8})\.(?P<secret>[\w\-_.~]+)$")


class BearerApiTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).decode("utf-8")
        if not auth or not auth.startswith(self.keyword + " "):
            return None

        token_str = auth[len(self.keyword) + 1:].strip()
        m = TOKEN_RE.match(token_str)
        if not m:
            raise exceptions.AuthenticationFailed("Invalid token format.")

        public_id = m.group("public_id")
        secret = m.group("secret")

        try:
            api_token = ApiToken.objects.select_related("user").get(public_id=public_id)
        except ApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not api_token.is_active:
            raise exceptions.AuthenticationFailed("Token is inactive.")

        if not api_token.verify(secret):
            raise exceptions.AuthenticationFailed("Invalid token.")

        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=["last_used_at"])

        return api_token.user, api_token
