from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'administrative_levels/list.html'
