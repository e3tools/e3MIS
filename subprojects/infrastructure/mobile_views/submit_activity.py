from django.views.generic import TemplateView
from subprojects.models import SubprojectCustomField


class SubmitActivityView(TemplateView):
    template_name = 'subprojects/mobile/submit_activity.html'

    def get_context_data(self, **kwargs):
        kwargs['custom_fields'] = SubprojectCustomField.objects.all()
        return super().get_context_data(**kwargs)
