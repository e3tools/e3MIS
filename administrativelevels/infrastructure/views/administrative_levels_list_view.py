from django.views.generic import TemplateView


class AdministrativeLevelsListView(TemplateView):
    template_name = 'administrative_levels/list.html'
