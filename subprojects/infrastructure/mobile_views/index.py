from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy


class IndexTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'subprojects/mobile/index.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_field_agent:
            return HttpResponseRedirect(reverse_lazy('subprojects:subproject_list'))
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
