from rest_framework import permissions


class ReadOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        return bool(request.method in permissions.SAFE_METHODS)


class IsNotFieldAgent(permissions.BasePermission):
    """Desktop users and API-token integrations. Field agents get their own scoped endpoints."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_field_agent)
