from django.views.generic import ListView

from subprojects.models import Subproject


class SubprojectListView(ListView):
    model = Subproject
    template_name = 'subprojects/list.html'
    paginate_by = 100
