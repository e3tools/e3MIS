from datetime import timedelta
from django import forms
from django.utils import timezone
from .models import ApiToken


class ApiTokenAdminForm(forms.ModelForm):
    auto_generate_secret = forms.BooleanField(
        required=False, initial=True,
        help_text="If checked, a new secret will be generated on create and shown once."
    )
    ttl_hours = forms.IntegerField(
        required=False, min_value=1,
        help_text="Optional. Set expiry relative to now. Ignored if 'expires_at' is provided."
    )

    class Meta:
        model = ApiToken
        fields = [
            "user", "name", "prefix", "public_id", "scopes",
            "expires_at", "revoked_at", "last_used_at", "created_at", "secret_hash"
        ]
        widgets = {
            "scopes": forms.Textarea(attrs={"rows": 3}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "revoked_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "last_used_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "created_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        expires_at = cleaned.get("expires_at")
        ttl_hours = cleaned.get("ttl_hours")
        if self.instance.pk is None:
            if not cleaned.get("auto_generate_secret"):
                raise forms.ValidationError("For security, tokens must be auto-generated on create.")
        if not expires_at and ttl_hours:
            cleaned["expires_at"] = timezone.now() + timedelta(hours=ttl_hours)
        return cleaned
