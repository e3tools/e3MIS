from django.views.generic import TemplateView
from src.permissions import IsFieldAgentUserMixin


class RegisterMenuTemplateView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/register_menu.html'
