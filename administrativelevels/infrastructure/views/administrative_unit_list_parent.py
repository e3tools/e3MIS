from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from administrativelevels.models import AdministrativeUnit


class AdministrativeUnitListParentView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        parent_id = kwargs.get('parent')
        print(parent_id)
        if parent_id:
            levels = AdministrativeUnit.objects.filter(parent_id=parent_id)
        else:
            levels = AdministrativeUnit.objects.filter(parent__isnull=True)

        data = [
            {
                'id': level.id,
                'name': level.name,  # Replace with actual model fields
                'parent_id': level.parent_id,
            }
            for level in levels
        ]

        return JsonResponse({'administrative_levels': data}, safe=False)