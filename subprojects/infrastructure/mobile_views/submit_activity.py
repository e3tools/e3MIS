from django.views.generic import TemplateView


class SubmitActivityView(TemplateView):
    template_name = 'subprojects/mobile/submit_activity.html'

    def get_context_data(self, **kwargs):
        kwargs.update({'subprojects': self.get_descendants(self.request.user.administrative_unit)})
        return super().get_context_data(**kwargs)

    def get_descendants(self, subproject):
        descendants = [subproject]

        def recurse(node):
            for child in node.children.all():
                descendants.append(child)
                recurse(child)

        recurse(subproject)
        return descendants
