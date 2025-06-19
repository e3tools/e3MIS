from django.views.generic import TemplateView
from src.permissions import IsFieldAgentUserMixin


class IndexTemplateView(IsFieldAgentUserMixin, TemplateView):
    template_name = 'subprojects/mobile/index.html'
