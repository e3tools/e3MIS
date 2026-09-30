"""Sample MIS forms for the demo: a trackable object with follow-ups and a standalone form.

Idempotent (matched by name), so it can run on a demo database that already has data. Forms are
given to the Technical and Community facilitator groups. Development and demo only.
"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventDependency,
    FollowUpEventTrackableObject,
    TrackableObject,
)

GROUPS = ("Technical facilitator", "Community facilitator")


def form(fields, required=()):
    """Build a one-page schema from ``[(name, property, options), …]``."""
    properties, options = {}, {}
    for order, (name, prop, opts) in enumerate(fields, start=1):
        properties[name] = prop
        options[name] = {"order": order, **opts}
    return {"form": [{"page": {"type": "object", "properties": properties, "required": list(required)},
                      "options": {"fields": options}}]}


WATER_POINT = form(
    [
        ("nom", {"type": "string"}, {"label": "Nom du point d'eau"}),
        ("type", {"type": "string", "enum": ["Forage", "Puits", "Source aménagée"]}, {"label": "Type"}),
        ("fonctionnel", {"type": "bool"}, {"label": "Fonctionnel ?"}),
        ("menages", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Ménages desservis"}),
        ("position", {"type": "geolocation"}, {"label": "Position"}),
        ("photo", {"type": "file"}, {"label": "Photo"}),
    ],
    required=("nom", "type", "fonctionnel"),
)

INSPECTION = form(
    [
        ("etat", {"type": "string", "enum": ["Bon", "Moyen", "Mauvais"]}, {"label": "État général"}),
        ("reparation", {"type": "bool"}, {"label": "Réparation nécessaire ?"}),
        ("details", {"type": "string", "display": "textarea"}, {
            "label": "Quelle réparation ?",
            "dependencies": {"conditions": [{"field": "reparation", "operator": "equals", "value": "True"}]},
        }),
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de visite"}),
        ("photo", {"type": "file"}, {"label": "Photo"}),
    ],
    required=("etat", "reparation", "details", "date"),
)

HANDOVER = form(
    [
        ("pv_signe", {"type": "bool"}, {"label": "Procès-verbal signé ?"}),
        ("observations", {"type": "string", "display": "textarea"}, {"label": "Observations"}),
    ],
    required=("pv_signe",),
)

MEETING = form(
    [
        ("date", {"type": "string", "format": "date"}, {"label": "Date"}),
        ("participants", {"type": "integer", "validators": {"min_value": 1}}, {"label": "Participants"}),
        ("femmes", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Dont femmes"}),
        ("themes", {"type": "string", "multi": ["Eau", "Assainissement", "Hygiène", "Gestion"]},
         {"label": "Thèmes abordés"}),
        ("compte_rendu", {"type": "string", "display": "textarea"}, {"label": "Compte rendu"}),
    ],
    required=("date", "participants"),
)


class Command(BaseCommand):
    help = "Create sample trackable objects and follow-up events for the demo (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        groups = [Group.objects.get_or_create(name=name)[0] for name in GROUPS]

        def template(model, name, schema, **extra):
            obj, created = model.objects.get_or_create(
                name=name, defaults={"description": extra.pop("description", ""), "jsonForm": schema, **extra}
            )
            obj.groups.add(*groups)
            return obj

        water = template(TrackableObject, "Point d'eau", WATER_POINT, identifier_field="nom",
                         icon="fa-tint", color="blue", description="Forages, puits et sources suivis")
        inspection = template(FollowUpEvent, "Inspection du point d'eau", INSPECTION, order=1,
                              description="Visite de contrôle, à répéter")
        handover = template(FollowUpEvent, "Réception des travaux", HANDOVER, is_one_off=True, order=2,
                            description="Une seule fois, après une inspection")
        template(FollowUpEvent, "Réunion communautaire", MEETING, order=3,
                 description="Formulaire indépendant, sans point d'eau")
        for event in (inspection, handover):
            FollowUpEventTrackableObject.objects.get_or_create(follow_up_event=event, trackable_object=water)
        FollowUpEventDependency.objects.get_or_create(parent=inspection, child=handover)
        self.stdout.write(self.style.SUCCESS("Demo forms ready."))
