from django.contrib.auth.mixins import UserPassesTestMixin


class IsFieldAgentUserMixin(UserPassesTestMixin):
    permission_required = None
    groups_required = list()

    def test_func(self):
        if self.groups_required:
            return self.request.user.is_authenticated and self.request.user.is_field_agent and self.request.user.groups.filter(
                name__in=self.groups_required).exists()
        return self.request.user.is_authenticated and self.request.user.is_field_agent


class IsAdminMemberMixin(UserPassesTestMixin):
    """Desktop users allowed to delete: superusers and the Admin group (matches the delete buttons)."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and not user.is_field_agent and (
            user.is_superuser or user.groups.filter(name='Admin').exists())


class IsStaffMemberMixin(UserPassesTestMixin):
    permission_required = None
    groups_required = list()

    def test_func(self):
        if self.groups_required:
            return self.request.user.is_authenticated and not self.request.user.is_field_agent and self.request.user.groups.filter(
                name__in=self.groups_required).exists()
        return self.request.user.is_authenticated and not self.request.user.is_field_agent
