from django.contrib.auth.mixins import UserPassesTestMixin


class IsFieldAgentUserMixin(UserPassesTestMixin):
    permission_required = None
    groups_required = list()

    def test_func(self):
        if self.groups_required:
            return self.request.user.is_authenticated and self.request.user.is_field_agent and self.request.user.groups.filter(
                name__in=self.groups_required).exists()
        return self.request.user.is_authenticated and self.request.user.is_field_agent


class IsStaffMemberMixin(UserPassesTestMixin):
    permission_required = None
    groups_required = list()

    def test_func(self):
        if self.groups_required:
            return self.request.user.is_authenticated and not self.request.user.is_field_agent and self.request.user.groups.filter(
                name__in=self.groups_required).exists()
        return self.request.user.is_authenticated and not self.request.user.is_field_agent
