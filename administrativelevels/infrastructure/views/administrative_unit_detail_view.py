from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from administrativelevels.models import AdministrativeUnit, AdministrativeLevel
from administrativelevels.forms import AdministrativeUnitEditForm, AdministrativeUnitForm


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

            # Form for adding a new child (only name, parent and level set automatically)
            context['add_child_form'] = AdministrativeUnitForm()

            # Check if this unit can have children (if there's a next level)
            next_level_exists = AdministrativeLevel.objects.filter(order=unit.level.order + 1).exists()
            context['can_add_children'] = next_level_exists
        else:
            # No pk provided - showing root level units
            context['administrative_unit'] = None
            context['children'] = AdministrativeUnit.objects.filter(parent__isnull=True).order_by('name')
            context['edit_form'] = None
            context['is_root_view'] = True

            # Check if root level (order=1) exists to allow adding root units
            root_level_exists = AdministrativeLevel.objects.filter(order=1).exists()
            context['can_add_root'] = root_level_exists
            context['add_root_form'] = AdministrativeUnitForm() if root_level_exists else None

        return context

    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        action = request.POST.get('action')

        if not pk:
            # Root view
            if action == 'add_root':
                form = AdministrativeUnitForm(request.POST)
                if form.is_valid():
                    root_level = AdministrativeLevel.objects.filter(order=1).first()
                    if root_level:
                        unit = form.save(commit=False)
                        unit.level = root_level
                        unit.parent = None
                        unit.save()
                        messages.success(request, f'Root unit "{unit.name}" added successfully.')
                    else:
                        messages.error(request, 'No root level defined. Please create an administrative level with order 1.')
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
            elif action == 'delete_child':
                child_pk = request.POST.get('child_pk')
                if child_pk:
                    child = get_object_or_404(AdministrativeUnit, pk=child_pk)
                    name = child.name
                    self._delete_unit_recursive(child)
                    messages.success(request, f'Unit "{name}" and all its descendants deleted successfully.')
            return redirect('administrativelevels:administrative_unit_root')

        unit = get_object_or_404(AdministrativeUnit, pk=pk)

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
            form = AdministrativeUnitForm(request.POST)
            if form.is_valid():
                child_level = AdministrativeLevel.objects.filter(order=unit.level.order + 1).first()
                if child_level:
                    child = form.save(commit=False)
                    child.parent = unit
                    child.level = child_level
                    child.save()
                    messages.success(request, f'Child unit "{child.name}" added successfully.')
                else:
                    messages.error(request, 'No child level defined for this unit.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        elif action == 'delete_child':
            child_pk = request.POST.get('child_pk')
            if child_pk:
                child = get_object_or_404(AdministrativeUnit, pk=child_pk)
                name = child.name
                self._delete_unit_recursive(child)
                messages.success(request, f'Unit "{name}" and all its descendants deleted successfully.')

        elif action == 'delete_self':
            parent_pk = unit.parent.pk if unit.parent else None
            name = unit.name
            self._delete_unit_recursive(unit)
            messages.success(request, f'Unit "{name}" and all its descendants deleted successfully.')
            if parent_pk:
                return redirect('administrativelevels:administrative_unit_detail', pk=parent_pk)
            return redirect('administrativelevels:administrative_unit_root')

        return redirect('administrativelevels:administrative_unit_detail', pk=unit.pk)

    def _delete_unit_recursive(self, unit):
        for child in unit.children.all():
            self._delete_unit_recursive(child)
        unit.delete()