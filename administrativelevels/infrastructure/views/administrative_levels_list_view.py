from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Count
from administrativelevels.models import AdministrativeLevel
from administrativelevels.forms import AdministrativeLevelForm


class AdministrativeLevelsListView(LoginRequiredMixin, TemplateView):
    template_name = 'administrative_levels/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['administrative_levels'] = AdministrativeLevel.objects.annotate(
            units_count=Count('units')
        ).order_by('order')
        context['form'] = AdministrativeLevelForm()
        return context

    def post(self, request, *args, **kwargs):
        level_id = request.POST.get('administrative_level_id')

        if level_id:
            # Update existing level
            try:
                level = AdministrativeLevel.objects.get(pk=level_id)
                form = AdministrativeLevelForm(request.POST, instance=level)
            except AdministrativeLevel.DoesNotExist:
                messages.error(request, 'Administrative level not found.')
                return redirect('administrativelevels:administrative_levels_list')
        else:
            # Create new level
            form = AdministrativeLevelForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Administrative level saved successfully.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')

        return redirect('administrativelevels:administrative_levels_list')
