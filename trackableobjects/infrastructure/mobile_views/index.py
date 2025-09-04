from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, F, Count, Sum, Subquery
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy

from administrativelevels.models import AdministrativeUnit
from trackableobjects.models import TrackableObjectInstance


class IndexTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'trackable_objects/mobile/index.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_field_agent:
            return HttpResponseRedirect(reverse_lazy('subprojects:subproject_list'))
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        administrative_units_qs = AdministrativeUnit.objects.filter(
            id__in=self.get_descendants(self.request.user.administrative_unit)
        ).values_list('id')

        qs = TrackableObjectInstance.objects.filter(
            administrative_units__in=Subquery(administrative_units_qs)
        ).annotate(
            total_one_off_events=Count(
                'trackable_object__follow_up_events',
                filter=Q(trackable_object__follow_up_events__is_one_off=True),
                distinct=True
            ),
            total_one_off_responses=Count(
                'follow_up_responses',
                filter=Q(follow_up_responses__follow_up_event__is_one_off=True),
                distinct=True
            ),
        ).annotate(pending_one_off=F('total_one_off_events') - F('total_one_off_responses'))

        kwargs.update({
            'pending_activities': qs.aggregate(pending_total=Sum('pending_one_off'))['pending_total'] or ''
        })
        return super().get_context_data(**kwargs)

    def get_descendants(self, administrative_unit):
        descendants = list()

        def recurse(node):
            if node.children.exists():
                for child in node.children.all():
                    recurse(child)
            else:
                descendants.append(node.id)

        recurse(administrative_unit)
        return descendants
