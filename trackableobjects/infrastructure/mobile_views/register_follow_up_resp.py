import datetime
import json
from django.views.generic.edit import CreateView
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext as _
from subprojects.models import Attachment
from trackableobjects.models import FollowUpEvent, FollowUpEventResponse, TrackableObjectInstance
from src.permissions import IsFieldAgentUserMixin
from utils.json_form_parser import parse_custom_jsonschema


def serialize_for_json(data):
    """
    Recursively converts all datetime.date and datetime.datetime objects to ISO strings.
    """
    if isinstance(data, dict):
        return {k: serialize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data


class FollowUpEventResponseCreateView(IsFieldAgentUserMixin, CreateView):
    model = FollowUpEventResponse
    queryset = FollowUpEvent.objects.all()
    fields = '__all__'
    template_name = "trackable_objects/mobile/register_follow_up_event_resp.html"
    pk_url_kwarg = 'follow_up_event'
    instance = None

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        self.object = self.get_object()
        if not self.has_object_permission_groups():
            return self.handle_no_permission()
        form = self.get_custom_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.has_object_permission_groups():
            return self.handle_no_permission()
        return self.render_to_response(self.get_context_data())

    def form_valid(self, form):
        self.instance = self.model.objects.filter(id=self.kwargs['response']).first() if 'response' in self.kwargs else None

        if self.instance is not None:
            trackable_object_instance = self.instance.trackable_object_instance
        else:
            trackable_instance_id = self.kwargs.get('trackable_instance')
            trackable_object_instance = TrackableObjectInstance.objects.filter(
                id=trackable_instance_id).first() if trackable_instance_id else None

        cleaned_data = serialize_for_json(form.cleaned_data)

        for key in cleaned_data.keys():
            if key in form.files.keys():
                cleaned_data[key] = 'Attachment'

            if hasattr(cleaned_data[key], 'id') and hasattr(cleaned_data[key], '_meta'):
                cleaned_data[key] = cleaned_data[key].id

        if self.instance is None:
            self.instance = self.model(
                follow_up_event=self.object,
                created_by=self.request.user,
                jsonForm=cleaned_data,
                trackable_object_instance=trackable_object_instance,
            )
        else:
            self.instance.filled_by = self.request.user
            self.instance.jsonForm = cleaned_data
            self.instance.trackable_object_instance = trackable_object_instance
        self.instance.save()

        if form.files is not None:
            for key, value in form.files.items():
                Attachment.objects.create(
                    follow_up_event_response=self.instance,
                    field_name=key,
                    file=value,
                )

        messages.success(self.request, _('Your Follow Up Event was successfully created or updated.'))

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return TemplateResponse(self.request, self.template_name, {
            'form': form,
            'custom_form': self.get_custom_form(),
            'object': self.object,
            'parent_form_data_json': self.get_parent_form_data_json(),
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['custom_form'] = self.get_custom_form()
        follow_up_event = FollowUpEvent.objects.filter(id=self.kwargs['follow_up_event']).first()
        context['follow_up_event'] = follow_up_event

        trackable_instance_id = self.kwargs.get('trackable_instance')
        if trackable_instance_id:
            context['trackable_object_instance'] = TrackableObjectInstance.objects.filter(
                id=trackable_instance_id).first()
        elif 'response' in self.kwargs:
            response = FollowUpEventResponse.objects.filter(id=self.kwargs['response']).first()
            context['trackable_object_instance'] = response.trackable_object_instance if response else None
        else:
            context['trackable_object_instance'] = None

        toi = context['trackable_object_instance']
        if toi:
            if follow_up_event.is_one_off:
                context['back_url'] = reverse_lazy(
                    'trackableobjects:mobile:follow_up_event_list', args=[toi.id]
                )
            else:
                context['back_url'] = reverse_lazy(
                    'trackableobjects:mobile:follow_up_event_detail',
                    args=[toi.id, follow_up_event.id]
                )
        else:
            if follow_up_event.is_one_off:
                context['back_url'] = reverse_lazy(
                    'trackableobjects:mobile:standalone_follow_up_event_list', args=[follow_up_event.id]
                )
            else:
                context['back_url'] = reverse_lazy(
                    'trackableobjects:mobile:standalone_follow_up_event_detail',
                    args=[follow_up_event.id]
                )

        context['parent_form_data_json'] = self.get_parent_form_data_json()

        return context

    def get_parent_form_data(self):
        """
        Collect parent form data from:
        1. TrackableObjectInstance (parent form)
        2. Parent FollowUpEvent responses (if any dependencies exist)

        Returns a dictionary of field_name: value pairs
        """
        parent_form_data = {}

        # Get the trackable object instance
        trackable_instance_id = self.kwargs.get('trackable_instance')
        if trackable_instance_id:
            trackable_object_instance = TrackableObjectInstance.objects.filter(
                id=trackable_instance_id
            ).first()
        elif 'response' in self.kwargs:
            response = FollowUpEventResponse.objects.filter(id=self.kwargs['response']).first()
            trackable_object_instance = response.trackable_object_instance if response else None
        else:
            trackable_object_instance = None

        # Collect data from TrackableObjectInstance
        if trackable_object_instance and trackable_object_instance.jsonForm:
            parent_form_data.update(trackable_object_instance.jsonForm)

        # Collect data from parent FollowUpEvent responses
        follow_up_event = self.object
        if follow_up_event:
            # Get parent dependencies (events this event depends on)
            parent_dependencies = follow_up_event.dependencies_children.all()

            for dependency in parent_dependencies:
                parent_event = dependency.parent

                # Get the most recent response for this parent event
                if trackable_object_instance:
                    parent_response = FollowUpEventResponse.objects.filter(
                        follow_up_event=parent_event,
                        trackable_object_instance=trackable_object_instance
                    ).order_by('-created_at').first()

                    if parent_response and parent_response.jsonForm:
                        # Merge parent response data
                        parent_form_data.update(parent_response.jsonForm)

        return parent_form_data

    def get_parent_form_data_json(self):
        """
        Get parent form data as JSON string for template
        """
        parent_data = self.get_parent_form_data()
        return json.dumps(serialize_for_json(parent_data))

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        follow_up_event_response = FollowUpEventResponse.objects.filter(
            id=self.kwargs.get('response', None),
            follow_up_event=self.object
        ).first()

        if follow_up_event_response is not None:
            initial = follow_up_event_response.jsonForm
            # attachment_initial = Attachment.objects.filter(subproject_form_response=form_response).all()
            # for attachment in attachment_initial:
            #     initial.update({attachment.field_name: attachment.file})
            return initial
        return self.initial.copy()

    def get_custom_form(self):
        try:
            follow_up_event = self.object
            schema_json = follow_up_event.jsonForm if follow_up_event else {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        except FollowUpEvent.DoesNotExist:
            schema_json = {
                "form": [
                    {
                        "page": {
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }

        # NEW: Pass parent form data to the parser
        parent_form_data = self.get_parent_form_data()

        form_class = parse_custom_jsonschema(
            schema_json,
            page_index=0,
            administrative_level_ids=[id for unit in self.request.user.administrative_units.all() for id in self.get_descendants(unit)],
            parent_form_data=parent_form_data  # NEW: Pass parent data
        )

        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": self.request.POST,
                    "files": self.request.FILES,
                }
            )
        return kwargs

    def get_custom_field_names(self):
        try:
            follow_up_event = FollowUpEvent.objects.last()
            schema_json = follow_up_event.jsonForm if follow_up_event else {}
            return list(schema_json['form'][0]['page']['properties'].keys())
        except Exception:
            return []

    def has_object_permission_groups(self):
        groups = self.object.groups.all()
        for group in groups:
            if not self.request.user.groups.filter(id=group.id).exists():
                return False
        return True

    def get_success_url(self):
        toi = self.instance.trackable_object_instance
        fe = self.instance.follow_up_event
        if toi:
            if fe.is_one_off:
                return reverse_lazy(
                    'trackableobjects:mobile:follow_up_event_list', args=[toi.id]
                )
            return reverse_lazy(
                'trackableobjects:mobile:follow_up_event_detail', args=[toi.id, fe.id]
            )
        else:
            if fe.is_one_off:
                return reverse_lazy(
                    'trackableobjects:mobile:standalone_follow_up_event_list', args=[fe.id]
                )
            return reverse_lazy(
                'trackableobjects:mobile:standalone_follow_up_event_detail', args=[fe.id]
            )

    def get_descendants(self, administrative_unit):
        descendants = []

        def recurse(node):
            descendants.append(node.id)
            for child in node.children.all():
                recurse(child)

        recurse(administrative_unit)
        return descendants
