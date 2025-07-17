from django.contrib.auth.mixins import UserPassesTestMixin


class IsFieldAgentUserMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_field_agent


class IsStaffMemberMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return self.request.user.is_authenticated and not self.request.user.is_field_agent
