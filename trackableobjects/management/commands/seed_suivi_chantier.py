"""The four worksite follow-up forms specified by the COSO team (Brice, 7 Oct 2026).

Source: ``BJ-GoG-COSO-Formulaires_Application_Suivi_Chantier_07102026.xlsx``. Field labels keep the
spreadsheet wording; question numbers are in the comments.

- F1 Identification is the *record* (trackable object "Sous-projet"): filled once, at the first
  visit. It creates the worksite visits attach to; its coordinates wait for a supervisor's
  confirmation (lifecycle.create_worksite).
- F2 Inspection, F3 Réception provisoire, F4 Suivi post-réception are follow-ups opened by the
  sub-project's stage (lifecycle.py):

      works ──F2 "Travaux achevés"──▶ acceptance ──F3 prononcée──▶ accepted (F4 only)
        │                               │  ▲
        │                               F3 ajournée → postponed (F2 and F3 stay open)
        └──F2 arrêt définitif──▶ terminated (no forms; a supervisor can reopen)

Check-in data (2.1, 3.1, 4.1) comes from the visit the form is linked to (visit_forms.py); the
village's zone (1.9) is shown by the app under the village. 1.17 ≥ 1.16 uses the ``min_field``
validator (field_api/validation.py). Not covered yet: warnings on a lower rate than last time
(2.9, 2.10) and on children on site (2.17), waiting for who should be alerted and how.

Idempotent: forms are matched by name and updated in place (their schema version goes up when the
questions change). Run with ``--group`` to give them to the group of agents who fill them.
"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from administrativelevels.models import AdministrativeLevel
from trackableobjects.models import FollowUpEvent, FollowUpEventTrackableObject, TrackableObject

from .seed_demo_forms import DEMO_GROUP, form

RECORD = "Sous-projet"
F2, F3, F4 = "Inspection du chantier", "Réception provisoire", "Suivi post-réception"

STAGES = [
    {"key": "works", "label": "Travaux en cours"},
    {"key": "acceptance", "label": "Réception à faire"},
    {"key": "postponed", "label": "Réception ajournée"},
    {"key": "accepted", "label": "Réceptionné provisoirement"},
    {"key": "terminated", "label": "Terminé (résilié)"},
]

# Réf. secteurs (codes kept in the comments for matching with the sub-project dashboard).
SECTORS = {
    "Agropastoralisme": [  # S01
        "Couloirs de passage", "Aires de pâturage", "Couloirs et aires de pâturage", "Hydraulique pastorale",
        "Mares", "Retenues d'eau", "Infrastructures d'élevage", "Formation",
    ],
    "Pistes rurales": ["Pistes", "Ouvrages de franchissement", "Pistes et ouvrages"],  # S02
    "Eau et assainissement": [  # S03
        "Eau potable", "Hygiène et assainissement", "Assainissement pluvial", "Déchets solides",
    ],
    "Économie locale": [  # S04
        "Transformation", "Maraîchage", "Marchés ruraux", "Petit élevage", "Stockage", "Artisanat",
        "Production agricole", "AGR", "Petits commerces", "Bas-fonds", "Pisciculture",
    ],
    "Éducation": ["Écoles", "Alphabétisation", "Cantines scolaires"],  # S05
    "Éclairage public": ["Lampadaires solaires"],  # S06
    "Jeunesse et sport": [  # S07
        "Infrastructures sportives", "Équipements sportifs", "Maisons des jeunes", "Espaces de loisirs",
        "Animation culturelle",
    ],
    "Santé": ["Centres de santé", "Équipements médicaux"],  # S08
}


def when(field, value, operator="equals"):
    return {"dependencies": {"conditions": [{"field": field, "operator": operator, "value": value}]}}


def yes(field):
    return when(field, "true")


def text(label, **extra):
    return {"type": "string"}, {"label": label, **extra}


def textarea(label, **extra):
    return {"type": "string", "display": "textarea"}, {"label": label, **extra}


def choice(label, values, **extra):
    return {"type": "string", "enum": list(values)}, {"label": label, **extra}


def multi(label, values, **extra):
    return {"type": "string", "multi": list(values)}, {"label": label, **extra}


def yes_no(label, **extra):
    return {"type": "bool"}, {"label": label, **extra}


def number(label, minimum=0, maximum=None, **extra):
    validators = {"min_value": minimum}
    if maximum is not None:
        validators["max_value"] = maximum
    return {"type": "integer", "validators": validators}, {"label": label, **extra}


def day(label, validators=None, **extra):
    return {"type": "string", "format": "date", **({"validators": validators} if validators else {})}, {
        "label": label, **extra,
    }


def photo(label, **extra):
    return {"type": "file"}, {"label": label, **extra}


def build(rows):
    """``[(name, (property, options), required), …]`` → a one-page MIS schema."""
    fields = [(name, prop, opts) for name, (prop, opts), _ in rows]
    return form(fields, required=[name for name, _, required in rows if required])


def identification(village_order):
    rows = [
        ("nom", text("Nom du sous-projet"), True),  # 1.1
        ("financement", choice("Financement", ["FI", "FA1", "FA2"]), True),  # 1.2
        ("secteur", choice("Secteur", SECTORS), True),  # 1.3
    ]
    for index, (sector, subsectors) in enumerate(SECTORS.items(), start=1):  # 1.4, filtered by 1.3
        rows.append((f"sous_secteur_s{index:02d}", choice("Sous-secteur", subsectors, **when("secteur", sector)), True))
    unit_validators = {"max_admin_level_order": str(village_order)} if village_order else {}
    rows += [
        # 1.5–1.8: one cascading choice, département → commune → arrondissement → village.
        ("village", ({"type": "administrative_level", "validators": unit_validators},
                     {"label": "Village", "help": "Département, commune, arrondissement puis village"}), True),
        ("site_physique", yes_no("Le sous-projet a-t-il un site physique ?"), True),  # 1.10
        # 1.11 (and 1.12, the accuracy, kept with it). Asked for every sub-project: without a
        # physical site, the agent stands at a public place in the village (Brice's answer).
        ("position", ({"type": "geolocation"}, {
            "label": "Coordonnées GPS du site (prises au centre)",
            "help": "Sans site physique : prenez la position d'un lieu public du village.",
        }), True),
        ("maitrise_ouvrage", choice("Mode de maîtrise d'ouvrage", ["MOC", "MODC"]), True),  # 1.13
        ("entreprise", text("Entreprise titulaire", **yes("site_physique")), True),  # 1.14
        ("montant", number("Montant du marché (FCFA)", minimum=1, **yes("site_physique")), True),  # 1.15
        ("date_demarrage", day("Date de l'ordre de service de démarrage", **yes("site_physique")), True),  # 1.16
        ("date_fin_prevue", day("Date prévue de fin des travaux", {"min_field": "date_demarrage"},
                                **yes("site_physique")), True),  # 1.17 ≥ 1.16
        ("photo_initiale_1", photo("Photo de l'état initial du site (1)", **yes("site_physique")), True),  # 1.18
        ("photo_initiale_2", photo("Photo de l'état initial du site (2)", **yes("site_physique")), True),
    ]
    return build(rows)


PHASES = [
    "Installation de chantier", "Terrassement-fondations", "Gros œuvre", "Second œuvre-finitions",
    "Constat d'achèvement", "Travaux achevés", "Travaux arrêtés",
]
STOPPED, DONE = "Travaux arrêtés", "Travaux achevés"
TEMPORARY, DEFINITIVE = "Temporaire (suspension)", "Définitif (résiliation)"
STOP_REASONS = [
    "Défaillance de l'entreprise", "Défaut de paiement", "Indisponibilité des matériaux", "Intempéries",
    "Litige foncier", "Opposition ou conflit communautaire", "Insécurité", "Problème technique ou de conception",
    "Décision du maître d'ouvrage", "Autre",
]
DELAY_CAUSES = [
    "Défaillance de l'entreprise", "Matériaux", "Paiement", "Intempéries", "Litige foncier", "Insécurité", "Autre",
]


def inspection():
    on_site = yes("entreprise_presente")
    return build([
        ("phase", choice("Phase des travaux", PHASES), True),  # 2.3
        ("arret_date", day("Date de l'arrêt des travaux", {"max": "today"}, **when("phase", STOPPED)), True),  # 2.4
        ("arret_nature", choice("Nature de l'arrêt", [TEMPORARY, DEFINITIVE], **when("phase", STOPPED)), True),  # 2.5
        ("arret_raisons", multi("Raisons de l'arrêt", STOP_REASONS, **when("phase", STOPPED)), True),  # 2.6
        ("arret_raison_autre", text("Préciser l'autre raison", **when("arret_raisons", "Autre", "contains")), True),
        ("reprise_date", day("Date probable de reprise des travaux", {"min": "today"},
                             **when("arret_nature", TEMPORARY)), True),  # 2.8
        ("taux_physique", number("Taux d'exécution physique (%)", maximum=100), True),  # 2.9
        ("taux_financier", number("Taux d'exécution financier (%)", maximum=100), True),  # 2.10
        ("entreprise_presente", yes_no("L'entreprise est-elle présente sur le chantier ?"), True),  # 2.11
        ("conducteur_present", yes_no("Le conducteur des travaux est-il présent ?", **on_site), True),  # 2.12
        ("ouvriers", number("Nombre d'ouvriers présents", **on_site), True),  # 2.13
        ("ouvriers_locaux", number("dont main-d'œuvre locale", **on_site), True),  # 2.14
        ("ouvriers_femmes", number("dont femmes", **on_site), True),  # 2.15
        ("ouvriers_jeunes", number("dont jeunes (moins de 35 ans)", **on_site), True),  # 2.16
        ("ouvriers_enfants", number("dont enfants (moins de 18 ans)", **on_site), True),  # 2.17
        ("heures_respectees", choice("Les heures réglementaires de travail sont-elles respectées ?",
                                     ["Oui", "Non", "Ne sait pas"], **on_site), True),  # 2.18
        ("responsable_hse", yes_no(
            "Le chantier dispose-t-il d'un responsable HSE ou d'une personne qui en fait office ?"), True),  # 2.19
        ("epi", choice("Port des EPI par les ouvriers", ["Tous", "Une partie", "Aucun"], **on_site), True),  # 2.20
        ("pharmacie", yes_no("Une boîte à pharmacie est-elle présente sur le chantier ?"), True),  # 2.21
        ("signalisation", yes_no("Des panneaux de signalisation temporaire sont-ils installés ?"), True),  # 2.22
        ("travaux_hauteur", yes_no("Des travaux en hauteur sont-ils réalisés ?"), True),  # 2.23
        ("antichute", multi("Dispositifs antichute utilisés", [
            "Ligne de vie", "Harnais de sécurité", "Nacelle", "Échafaudage avec garde-corps", "Aucun",
        ], **yes("travaux_hauteur")), True),  # 2.24
        ("dechets", choice("Gestion des déchets de chantier", ["Satisfaisante", "Insuffisante"]), True),  # 2.25
        ("incident", yes_no("Un incident ou accident est-il survenu depuis la dernière visite ?"), True),  # 2.26
        ("incident_description", textarea("Décrire l'incident ou l'accident", **yes("incident")), True),  # 2.27
        ("autre_probleme", yes_no("Un autre problème est-il survenu depuis la dernière visite ?"), True),  # 2.28
        ("probleme_description", textarea("Décrire le problème", **yes("autre_probleme")), True),  # 2.29
        ("retard", yes_no("Les travaux accusent-ils un retard ?"), True),  # 2.30
        ("retard_causes", multi("Causes du retard", DELAY_CAUSES, **yes("retard")), True),  # 2.31
        ("instructions", textarea("Instructions données à l'entreprise"), False),  # 2.32
        ("photo_1", photo("Photo du chantier (1)"), True),  # 2.33: two at least
        ("photo_2", photo("Photo du chantier (2)"), True),
    ])


WITHOUT_RESERVES, WITH_RESERVES, POSTPONED = (
    "Prononcée sans réserves", "Prononcée avec réserves", "Ajournée",
)


def handover():
    return build([
        ("date_reception", day("Date de la réception", {"max": "today"}), True),  # 3.3
        ("parties", multi("Parties présentes", [
            "Commune", "Entreprise", "Bureau de contrôle", "SETCO", "Comité ou bénéficiaires",
            "Services déconcentrés de l'État", "Autre",
        ]), True),  # 3.4
        ("decision", choice("Décision", [WITHOUT_RESERVES, WITH_RESERVES, POSTPONED]), True),  # 3.5
        ("reserves", textarea("Liste des réserves", **when("decision", WITH_RESERVES)), True),  # 3.6
        ("delai_reserves", number("Délai de levée des réserves (jours)", minimum=1,
                                  **when("decision", WITH_RESERVES)), True),  # 3.7
        ("motif_ajournement", textarea("Motif de l'ajournement", **when("decision", POSTPONED)), True),  # 3.8
        ("date_nouvelle_reception", day("Date prévue de la nouvelle réception",
                                        **when("decision", POSTPONED)), True),  # 3.9
        ("proces_verbal", photo("Procès-verbal signé", **when("decision", POSTPONED, "not_equals")), True),  # 3.10
        ("photo_1", photo("Photo de l'ouvrage achevé (1)"), True),  # 3.11: two at least
        ("photo_2", photo("Photo de l'ouvrage achevé (2)"), True),
    ])


def post_handover():
    return build([
        ("etat", choice("État de fonctionnement", [
            "Fonctionnel", "Partiellement fonctionnel", "Non fonctionnel",
        ]), True),  # 4.3
        ("causes", textarea("Causes du dysfonctionnement", **when("etat", "Fonctionnel", "not_equals")), True),  # 4.4
        ("degradations", yes_no("Des dégradations sont-elles constatées ?"), True),  # 4.5
        ("degradations_description", textarea("Décrire les dégradations", **yes("degradations")), True),  # 4.6
        ("comite", yes_no("Un comité de gestion est-il en place ?"), True),  # 4.7
        ("comite_fonctionnel", yes_no("Le comité de gestion est-il fonctionnel ?", **yes("comite")), True),  # 4.8
        ("entretien", yes_no("Un dispositif d'entretien est-il en place ?"), True),  # 4.9
        ("entretien_responsable", choice("Responsable de l'entretien", [
            "Comité de gestion", "Commune", "Prestataire privé", "Autre",
        ], **yes("entretien")), True),  # 4.10
        ("usagers", number("Nombre estimé d'usagers"), True),  # 4.11
        ("photo_1", photo("Photo de l'ouvrage (1)"), True),  # 4.12: two at least
        ("photo_2", photo("Photo de l'ouvrage (2)"), True),
    ])


EVENTS = [
    # name, description, schema builder, open in stages, stage rules (first match wins)
    (F2, "À chaque visite, après le pointage, jusqu'à la réception provisoire.", inspection,
     ["works", "acceptance", "postponed"], [
         {"field": "arret_nature", "operator": "equals", "value": DEFINITIVE, "to": "terminated"},
         {"field": "phase", "operator": "equals", "value": DONE, "to": "acceptance"},
     ]),
    (F3, "Une fois les travaux achevés. À reprendre si la réception est ajournée.", handover,
     ["acceptance", "postponed"], [
         {"field": "decision", "operator": "equals", "value": WITHOUT_RESERVES, "to": "accepted"},
         {"field": "decision", "operator": "equals", "value": WITH_RESERVES, "to": "accepted"},
         {"field": "decision", "operator": "equals", "value": POSTPONED, "to": "postponed"},
     ]),
    (F4, "À chaque visite après la réception provisoire, sans limite de durée.", post_handover,
     ["accepted"], []),
]


class Command(BaseCommand):
    help = "Create or update the sub-project forms (identification, inspection, handover, post-handover)."

    def add_arguments(self, parser):
        parser.add_argument("--group", default=DEMO_GROUP, help="Group of the agents who fill the forms.")
        parser.add_argument("--village-level-order", type=int,
                            help="Order of the village administrative level (default: the deepest level).")

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=options["group"])
        village_order = options["village_level_order"] or (
            AdministrativeLevel.objects.order_by("-order").values_list("order", flat=True).first()
        )
        record, created = TrackableObject.objects.get_or_create(name=RECORD, defaults={"description": ""})
        record.description = "Identification du sous-projet, renseignée une fois lors de la première visite."
        record.identifier_field = "nom"
        record.icon = "fa-hard-hat"
        record.color = "amber"
        record.stages = STAGES
        record.creates_worksite = True
        record.jsonForm = identification(village_order)
        record.save()
        record.groups.add(group)
        self.stdout.write(f"{'Created' if created else 'Updated'} {RECORD}")

        base = FollowUpEvent.objects.order_by("-order").values_list("order", flat=True).first() or 0
        for index, (name, description, schema, stages, rules) in enumerate(EVENTS, start=1):
            event, created = FollowUpEvent.objects.get_or_create(
                name=name, defaults={"description": description, "order": base + index}
            )
            event.description = description
            event.is_one_off = False
            event.is_active = True
            event.stages = stages
            event.stage_rules = rules
            event.jsonForm = schema()
            event.save()
            event.groups.add(group)
            FollowUpEventTrackableObject.objects.get_or_create(follow_up_event=event, trackable_object=record)
            self.stdout.write(f"{'Created' if created else 'Updated'} {name}")
