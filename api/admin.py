from django.contrib import admin, messages
from django.utils import timezone
from django.http import HttpResponse
from django.db import models
import csv

from .models import ApiToken
from .admin_forms import ApiTokenAdminForm


# --------- List filters ---------

class ActiveFilter(admin.SimpleListFilter):
    title = "active"
    parameter_name = "active"

    def lookups(self, request, model_admin):
        return [("yes", "Active"), ("no", "Inactive")]

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "yes":
            return qs.filter(revoked_at__isnull=True).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
            )
        if self.value() == "no":
            return qs.exclude(
                models.Q(revoked_at__isnull=True) &
                (models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
            )
        return qs


class RevokedFilter(admin.SimpleListFilter):
    title = "revoked"
    parameter_name = "revoked"

    def lookups(self, request, model_admin):
        return [("yes", "Revoked"), ("no", "Not revoked")]

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.filter(revoked_at__isnull=False)
        if self.value() == "no":
            return qs.filter(revoked_at__isnull=True)
        return qs


class ExpiredFilter(admin.SimpleListFilter):
    title = "expired"
    parameter_name = "expired"

    def lookups(self, request, model_admin):
        return [("yes", "Expired"), ("no", "Not expired")]

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "yes":
            return qs.filter(expires_at__isnull=False, expires_at__lte=now)
        if self.value() == "no":
            return qs.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        return qs


# --------- Actions ---------

@admin.action(description="Revoke selected tokens")
def revoke_selected(modeladmin, request, queryset):
    updated = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    messages.success(request, f"Revoked {updated} token(s).")


@admin.action(description="Restore selected tokens")
def restore_selected(modeladmin, request, queryset):
    updated = queryset.filter(revoked_at__isnull=False).update(revoked_at=None)
    messages.success(request, f"Restored {updated} token(s).")


@admin.action(description="Export selected tokens (no secrets) as CSV")
def export_csv(modeladmin, request, queryset):
    # Export safe details only
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="api_tokens.csv"'
    writer = csv.writer(response)
    writer.writerow(["prefix", "public_id", "user_id", "user", "name", "scopes", "created_at", "last_used_at", "expires_at", "revoked_at"])
    for t in queryset.select_related("user"):
        user_display = getattr(t.user, "email", None) or getattr(t.user, "username", None) or t.user_id
        writer.writerow([
            t.prefix, t.public_id, t.user_id, user_display, t.name,
            t.scopes, t.created_at, t.last_used_at, t.expires_at, t.revoked_at
        ])
    return response


# --------- ModelAdmin ---------

@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    form = ApiTokenAdminForm

    list_display = (
        "masked_token", "user_display", "name",
        "is_active_display", "expires_at", "revoked_at", "last_used_at", "created_at"
    )
    list_filter = (ActiveFilter, ExpiredFilter, RevokedFilter, "prefix", "created_at")
    search_fields = ("public_id", "name", "user__username", "user__email")
    ordering = ("-created_at",)
    actions = (revoke_selected, restore_selected, export_csv)

    readonly_fields = (
        "public_id", "secret_hash", "created_at", "last_used_at",
        "masked_token", "is_active_display",
    )

    fieldsets = (
        ("Identity", {
            "fields": ("user", "name", "prefix", "public_id", "masked_token")
        }),
        ("Status & Visibility", {
            "fields": ("is_active_display", "expires_at", "revoked_at", "last_used_at", "created_at")
        }),
        ("Security (server-side only)", {
            "classes": ("collapse",),
            "fields": ("secret_hash",),
            "description": "Hashed secret. Never reveals raw secret."
        }),
        ("Admin helpers", {
            "fields": ("auto_generate_secret", "ttl_hours"),
            "description": "On creation, the raw token will be generated and shown once."
        }),
        ("Scopes", {
            "fields": ("scopes",),
        }),
    )

    def user_display(self, obj):
        return getattr(obj.user, "email", None) or getattr(obj.user, "username", None) or obj.user_id
    user_display.short_description = "User"

    def is_active_display(self, obj):
        if obj.revoked_at:
            return "Inactive (revoked)"
        if obj.is_expired:
            return "Inactive (expired)"
        return "Active"
    is_active_display.short_description = "State"

    # Prevent manual creation of raw secret through admin
    def save_model(self, request, obj, form, change):
        """
        On create:
          - Force auto generation of secret via ApiToken.mint()
          - Show the raw token once in a success message
        On change:
          - Save normally (no secret changes)
        """
        from .models import ApiToken  # local import to avoid cycles

        if change:
            # Edits: never touch secret, just save allowed fields
            super().save_model(request, obj, form, change)
            return

        # Create flow: mint instead of naive save
        cleaned = form.cleaned_data
        ttl = None
        if cleaned.get("expires_at"):
            # Already set by clean(), nothing to do
            pass
        # We need user, name, scopes, expires_at handled by mint + update
        user = cleaned["user"]
        name = cleaned.get("name", "")
        scopes = cleaned.get("scopes") or []

        # Use model's classmethod mint to create row and get raw token
        raw, created_obj = ApiToken.mint(
            user=user,
            name=name,
            scopes=scopes,
            ttl=None  # expires_at was already set by form if ttl provided
        )

        # If the form computed expires_at, persist it
        if cleaned.get("expires_at"):
            created_obj.expires_at = cleaned["expires_at"]
            created_obj.save(update_fields=["expires_at"])

        # Optional: prefix override from api
        if cleaned.get("prefix") and created_obj.prefix != cleaned["prefix"]:
            created_obj.prefix = cleaned["prefix"]
            created_obj.save(update_fields=["prefix"])

        # Give admin the one-time token
        self.message_user(
            request,
            f"Token created. Copy it now, it won't be shown again: {raw}",
            level=messages.SUCCESS,
        )

    # No inline add using the green plus to avoid bypassing our mint flow
    def has_add_permission(self, request):
        return request.user.has_perm("api.add_apitoken")

    # Hardening: disallow deleting through admin action unless you insist; revocation is safer.
    def has_delete_permission(self, request, obj=None):
        return False
