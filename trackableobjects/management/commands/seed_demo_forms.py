"""Sample MIS forms for the demo: a trackable object with follow-ups and a standalone form.

Idempotent (matched by name), so it can run on a demo database that already has data. Forms are
given to one demo group that every field agent joins: the MIS lets an agent fill a form only when
they are in *every* group the form has, so a form shared by the FT and FC groups could be filled
by nobody. Development and demo only.
"""
from django.contrib.auth.models import Group

from authorization.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from trackableobjects.models import (
    FollowUpEvent,
    FollowUpEventDependency,
    FollowUpEventTrackableObject,
    TrackableObject,
)

DEMO_GROUP = "Agents de terrain (démo)"


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


# --- Community infrastructure and groups (a CDD programme's usual record types) -------------------

YES = {"field": None, "operator": "equals", "value": "True"}


def when_yes(field):
    return {"conditions": [{**YES, "field": field}]}


def when(field, value):
    return {"conditions": [{"field": field, "operator": "equals", "value": value}]}


SCHOOL = form(
    [
        ("nom", {"type": "string"}, {"label": "Nom de l'école"}),
        ("type", {"type": "string", "enum": ["Publique", "Communautaire", "Confessionnelle"]}, {"label": "Type d'école"}),
        ("classes", {"type": "integer", "validators": {"min_value": 1}}, {"label": "Nombre de salles de classe"}),
        ("eleves", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Nombre d'élèves"}),
        ("latrines", {"type": "bool"}, {"label": "Latrines fonctionnelles ?"}),
        ("probleme_latrines", {"type": "string", "display": "textarea"},
         {"label": "Quel problème avec les latrines ?", "dependencies": when("latrines", "False")}),
        ("position", {"type": "geolocation"}, {"label": "Position"}),
        ("photo", {"type": "file"}, {"label": "Photo de l'école"}),
    ],
    required=("nom", "type", "classes", "latrines", "probleme_latrines"),
)

WORKS_PROGRESS = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de visite"}),
        ("avancement", {"type": "integer", "validators": {"min_value": 0, "max_value": 100}},
         {"label": "Avancement des travaux (%)"}),
        ("rythme", {"type": "string", "enum": ["Dans les délais", "Léger retard", "Arrêté"]}, {"label": "Rythme des travaux"}),
        ("cause_arret", {"type": "string", "enum": ["Manque de matériaux", "Problème de paiement", "Météo", "Conflit", "Autre"]},
         {"label": "Pourquoi les travaux sont-ils arrêtés ?", "dependencies": when("rythme", "Arrêté")}),
        ("probleme", {"type": "bool"}, {"label": "Un problème de qualité constaté ?"}),
        ("probleme_details", {"type": "string", "display": "textarea"},
         {"label": "Décrivez le problème", "dependencies": when_yes("probleme")}),
        ("photo", {"type": "file"}, {"label": "Photo des travaux"}),
    ],
    required=("date", "avancement", "rythme", "cause_arret", "probleme", "probleme_details"),
)

PROVISIONAL_HANDOVER = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de la réception"}),
        ("pv_signe", {"type": "bool"}, {"label": "Procès-verbal signé ?"}),
        ("reserves", {"type": "bool"}, {"label": "Des réserves ont été émises ?"}),
        ("reserves_details", {"type": "string", "display": "textarea"},
         {"label": "Lesquelles ?", "dependencies": when_yes("reserves")}),
        ("presents", {"type": "string", "multi": ["Mairie", "Comité de gestion", "Entreprise", "Bureau de contrôle", "Agent de terrain"]},
         {"label": "Présents à la réception"}),
        ("photo", {"type": "file"}, {"label": "Photo du procès-verbal"}),
    ],
    required=("date", "pv_signe", "reserves", "reserves_details"),
)

SCHOOL_IN_USE = form(
    [
        ("eleves_filles", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Élèves filles inscrites"}),
        ("eleves_garcons", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Élèves garçons inscrits"}),
        ("enseignants", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Enseignants présents"}),
        ("utilisee", {"type": "bool"}, {"label": "Les salles sont-elles utilisées ?"}),
        ("pourquoi", {"type": "string", "display": "textarea"},
         {"label": "Pourquoi ne sont-elles pas utilisées ?", "dependencies": when("utilisee", "False")}),
    ],
    required=("eleves_filles", "eleves_garcons", "utilisee", "pourquoi"),
)

HEALTH_CENTRE = form(
    [
        ("nom", {"type": "string"}, {"label": "Nom du centre de santé"}),
        ("niveau", {"type": "string", "enum": ["Unité villageoise", "Centre de santé", "Maternité"]}, {"label": "Niveau"}),
        ("personnel", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Personnel soignant"}),
        ("electricite", {"type": "bool"}, {"label": "Accès à l'électricité ?"}),
        ("eau", {"type": "bool"}, {"label": "Accès à l'eau potable ?"}),
        ("position", {"type": "geolocation"}, {"label": "Position"}),
    ],
    required=("nom", "niveau", "electricite", "eau"),
)

HEALTH_SUPERVISION = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de visite"}),
        ("consultations", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Consultations ce mois-ci"}),
        ("rupture", {"type": "bool"}, {"label": "Rupture de médicaments essentiels ?"}),
        ("medicaments", {"type": "string", "display": "textarea"},
         {"label": "Quels médicaments manquent ?", "dependencies": when_yes("rupture")}),
        ("proprete", {"type": "string", "enum": ["Bonne", "Moyenne", "Mauvaise"]}, {"label": "Propreté des locaux"}),
        ("photo", {"type": "file"}, {"label": "Photo"}),
    ],
    required=("date", "rupture", "medicaments", "proprete"),
)

EQUIPMENT_INVENTORY = form(
    [
        ("lits", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Lits"}),
        ("refrigerateur", {"type": "bool"}, {"label": "Réfrigérateur pour vaccins fonctionnel ?"}),
        ("panneaux", {"type": "bool"}, {"label": "Panneaux solaires installés ?"}),
        ("manquants", {"type": "string", "display": "textarea"}, {"label": "Équipements manquants"}),
    ],
    required=("lits", "refrigerateur", "panneaux"),
)

GROUP = form(
    [
        ("nom", {"type": "string"}, {"label": "Nom du groupement"}),
        ("activite", {"type": "string", "enum": ["Agriculture", "Élevage", "Transformation", "Commerce", "Artisanat"]},
         {"label": "Activité principale"}),
        ("membres", {"type": "integer", "validators": {"min_value": 1}}, {"label": "Nombre de membres"}),
        ("femmes", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Dont femmes"}),
        ("presidente", {"type": "string"}, {"label": "Nom du/de la président(e)"}),
        ("telephone", {"type": "string"}, {"label": "Téléphone du/de la président(e)"}),
    ],
    required=("nom", "activite", "membres"),
)

GROUP_MEETING = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de la réunion"}),
        ("presents", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Membres présents"}),
        ("epargne", {"type": "number", "validators": {"min_value": 0}}, {"label": "Épargne collectée (FCFA)"}),
        ("difficulte", {"type": "bool"}, {"label": "Une difficulté signalée ?"}),
        ("difficulte_details", {"type": "string", "display": "textarea"},
         {"label": "Laquelle ?", "dependencies": when_yes("difficulte")}),
    ],
    required=("date", "presents", "difficulte", "difficulte_details"),
)

GRANT = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de réception"}),
        ("montant", {"type": "number", "validators": {"min_value": 0}}, {"label": "Montant reçu (FCFA)"}),
        ("usage", {"type": "string", "multi": ["Équipement", "Intrants", "Formation", "Fonds de roulement"]},
         {"label": "Utilisation prévue"}),
        ("photo", {"type": "file"}, {"label": "Photo du reçu"}),
    ],
    required=("date", "montant"),
)

RURAL_ROAD = form(
    [
        ("nom", {"type": "string"}, {"label": "Nom de la piste"}),
        ("longueur", {"type": "number", "validators": {"min_value": 0}}, {"label": "Longueur (km)"}),
        ("villages", {"type": "string"}, {"label": "Villages reliés"}),
        ("ouvrages", {"type": "integer", "validators": {"min_value": 0}}, {"label": "Ouvrages (ponts, dalots)"}),
        ("position", {"type": "geolocation"}, {"label": "Position du départ de la piste"}),
    ],
    required=("nom", "longueur"),
)

ROAD_CONDITION = form(
    [
        ("date", {"type": "string", "format": "date", "validators": {"max": "today"}}, {"label": "Date de visite"}),
        ("praticable", {"type": "string", "enum": ["Toute l'année", "Saison sèche seulement", "Impraticable"]},
         {"label": "La piste est-elle praticable ?"}),
        ("degradations", {"type": "string", "multi": ["Nids-de-poule", "Érosion", "Ouvrage endommagé", "Végétation"]},
         {"label": "Dégradations constatées"}),
        ("entretien", {"type": "bool"}, {"label": "Entretien communautaire réalisé ?"}),
        ("photo", {"type": "file"}, {"label": "Photo"}),
    ],
    required=("date", "praticable", "entretien"),
)


class Command(BaseCommand):
    help = "Create sample trackable objects and follow-up events for the demo (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        group = Group.objects.get_or_create(name=DEMO_GROUP)[0]
        group.user_set.add(*User.objects.filter(is_field_agent=True))
        groups = [group]

        def template(model, name, schema, **extra):
            obj, created = model.objects.get_or_create(
                name=name, defaults={"description": extra.pop("description", ""), "jsonForm": schema, **extra}
            )
            obj.groups.set(groups)
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

        # Record types with their follow-ups: (name, schema, identifier, icon, colour, description,
        # [(follow-up name, schema, one-off, description, depends on)]).
        catalogue = [
            ("École (salles de classe)", SCHOOL, "nom", "fa-school", "amber", "Écoles construites ou réhabilitées", [
                ("Suivi des travaux de l'école", WORKS_PROGRESS, False, "À chaque visite de chantier", None),
                ("Réception provisoire de l'école", PROVISIONAL_HANDOVER, True, "Une seule fois, après un suivi des travaux",
                 "Suivi des travaux de l'école"),
                ("Fonctionnement de l'école", SCHOOL_IN_USE, False, "Après la réception", "Réception provisoire de l'école"),
            ]),
            ("Centre de santé", HEALTH_CENTRE, "nom", "fa-hospital", "coral", "Centres et unités de santé appuyés", [
                ("Visite de supervision du centre", HEALTH_SUPERVISION, False, "Visite mensuelle", None),
                ("Inventaire des équipements", EQUIPMENT_INVENTORY, True, "Une seule fois", None),
            ]),
            ("Groupement communautaire", GROUP, "nom", "fa-users", "green", "Groupements et AGR appuyés", [
                ("Réunion du groupement", GROUP_MEETING, False, "À chaque réunion", None),
                ("Réception de la subvention", GRANT, True, "Une seule fois", None),
            ]),
            ("Piste rurale", RURAL_ROAD, "nom", "fa-road", "brown", "Pistes construites ou réhabilitées", [
                ("Suivi des travaux de la piste", WORKS_PROGRESS, False, "Pendant les travaux", None),
                ("État de la piste", ROAD_CONDITION, False, "Après les travaux, à chaque passage", None),
            ]),
        ]
        order = 10
        for name, schema, identifier, icon, color, description, follow_ups in catalogue:
            record = template(TrackableObject, name, schema, identifier_field=identifier, icon=icon, color=color,
                              description=description)
            by_name = {}
            for fu_name, fu_schema, one_off, fu_description, parent in follow_ups:
                event = template(FollowUpEvent, fu_name, fu_schema, is_one_off=one_off, order=order,
                                 description=fu_description)
                order += 1
                FollowUpEventTrackableObject.objects.get_or_create(follow_up_event=event, trackable_object=record)
                if parent:
                    FollowUpEventDependency.objects.get_or_create(parent=by_name[parent], child=event)
                by_name[fu_name] = event
        self.stdout.write(self.style.SUCCESS("Demo forms ready."))
