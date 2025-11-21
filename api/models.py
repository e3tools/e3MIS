import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()

API_KEY_CONFIG = getattr(settings, "API_KEY_CONFIG", "")
COMPANY_PREFIX = API_KEY_CONFIG.get("COMPANY_PREFIX", "")


def _hash_secret(secret: str) -> str:
    pepper = API_KEY_CONFIG.get("TOKEN_PEPPER", "")
    return hashlib.sha256((secret + pepper).encode("utf-8")).hexdigest()


class ApiToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=120, blank=True, default="")
    prefix = models.CharField(max_length=20, default=COMPANY_PREFIX)
    public_id = models.CharField(max_length=12, unique=True, db_index=True)
    secret_hash = models.CharField(max_length=64)
    scopes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["public_id"]),
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self):
        who = getattr(self.user, "email", None) or getattr(self.user, "username", None) or self.user_id
        return f"{self.prefix}-{self.public_id} ({who})"

    @property
    def masked_token(self):
        return f"{self.prefix}-{self.public_id}.••••"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    @classmethod
    def mint(cls, *, user: User, name: str = "", scopes=None, ttl=None):
        if scopes is None:
            scopes = []
        public_id = uuid.uuid4().hex[:8]
        secret = secrets.token_urlsafe(32)
        token_str = f"{COMPANY_PREFIX}-{public_id}.{secret}"
        obj = cls(
            user=user,
            name=name,
            prefix=COMPANY_PREFIX,
            public_id=public_id,
            secret_hash=_hash_secret(secret),
            scopes=scopes,
        )
        if ttl:
            obj.expires_at = timezone.now() + ttl
        obj.save()
        return token_str, obj

    def verify(self, secret: str) -> bool:
        expected = self.secret_hash
        got = _hash_secret(secret)
        return hmac.compare_digest(expected, got)
