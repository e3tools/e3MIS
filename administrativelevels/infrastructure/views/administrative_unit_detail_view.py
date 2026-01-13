from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from administrativelevels.models import AdministrativeUnit, AdministrativeLevel
from administrativelevels.forms import AdministrativeUnitForm, AdministrativeUnitEditForm


class AdministrativeUnitDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'administrative_units/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            # Showing specific unit detail
            unit = get_object_or_404(AdministrativeUnit, pk=pk)
            context['administrative_unit'] = unit

            # Get all children of this unit
            context['children'] = unit.children.all().order_by('name')

            # Form for editing the unit name
            context['edit_form'] = AdministrativeUnitEditForm(instance=unit)

            # Form for adding a new child
            context['add_child_form'] = AdministrativeUnitForm(parent_unit=unit)

            # Check if this unit can have children (if there's a next level)
            next_level_exists = AdministrativeLevel.objects.filter(order=unit.level.order + 1).exists()
            context['can_add_children'] = next_level_exists
        else:
            # No pk provided - showing root level units
            context['administrative_unit'] = None
            context['children'] = AdministrativeUnit.objects.filter(parent__isnull=True).order_by('name')
            context['edit_form'] = None
            context['add_child_form'] = None
            context['can_add_children'] = False
            context['is_root_view'] = True

        return context

    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')

        if not pk:
            messages.error(request, 'Cannot perform this action on root view.')
            return redirect('administrativelevels:administrative_unit_root')

        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        action = request.POST.get('action')

        if action == 'edit':
            # Edit unit name
            form = AdministrativeUnitEditForm(request.POST, instance=unit)
            if form.is_valid():
                form.save()
                messages.success(request, f'Administrative unit "{unit.name}" updated successfully.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        elif action == 'add_child':
            # Add new child unit
            form = AdministrativeUnitForm(request.POST, parent_unit=unit)
            if form.is_valid():
                child = form.save(commit=False)
                child.parent = unit
                child.save()
                messages.success(request, f'Child unit "{child.name}" added successfully.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        return redirect('administrativelevels:administrative_unit_detail', pk=unit.pk)