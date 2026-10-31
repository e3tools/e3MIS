"""An example CDD cycle and the forms its tasks need, until COSO sends its own cycle.

Five phases: information and mobilisation → participatory diagnosis → planning → sub-project
implementation → follow-up and closing. Meetings use one minutes form ("Compte rendu de réunion");
the diagnosis, the priorities, the committee and the evaluation have their own forms; the
sub-project phase points at the COSO sub-project forms (seed_suivi_chantier, created if missing).

Idempotent: the template, phases and activities are matched by name, tasks by key, forms by name.
The template's version goes up only when the tree changes, so the app fetches it again.
Run with ``--group`` to give the forms to the agents who fill them, ``--enable`` to switch the
module on in the programme configuration.
"""
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from cdd.models import Activity, CycleTemplate, Phase, Task, TaskForm, TaskKind
from cdd.progress import template_specs
from fieldmonitoring.core.models import ProgrammeConfig
from trackableobjects.management.commands.seed_demo_forms import DEMO_GROUP
from trackableobjects.management.commands.seed_suivi_chantier import (
    F2, F3, RECORD, build, choice, day, multi, number, photo, text, textarea,
)
from trackableobjects.models import FollowUpEvent, TrackableObject

TEMPLATE = "Cycle CDD (exemple)"
MEETING = "Compte rendu de réunion (CDD)"
DIAGNOSIS = "Diagnostic participatif"
PRIORITIES = "Priorisation des besoins"
COMMITTEE = "Mise en place du comité de développement"
EVALUATION = "Évaluation participative"

PAST = {"max": "today"}


def attendance():
    return [
        ("hommes", number("Participants : hommes"), True),
        ("femmes", number("Participants : femmes"), True),
        ("jeunes", number("Dont jeunes (moins de 35 ans)"), False),
    ]


def meeting():
    return build([
        ("date", day("Date de la réunion", PAST), True),
        ("type", choice("Type de réunion", [
            "Rencontre avec les autorités", "Assemblée villageoise", "Restitution", "Réunion du comité",
            "Assemblée de redevabilité", "Autre",
        ]), True),
        ("lieu", text("Lieu"), True),
        *attendance(),
        ("ordre_du_jour", textarea("Ordre du jour"), True),
        ("decisions", textarea("Décisions prises"), True),
        ("liste_presence", photo("Liste de présence (photo)"), True),
        ("photo", photo("Photo de la réunion"), False),
    ])


def diagnosis():
    return build([
        ("date", day("Date du diagnostic", PAST), True),
        ("outils", multi("Outils utilisés", [
            "Carte sociale", "Profil historique", "Calendrier saisonnier", "Diagramme de Venn",
            "Classement par niveau de vie",
        ]), True),
        *attendance(),
        ("problemes", textarea("Principaux problèmes identifiés"), True),
        ("ressources", textarea("Ressources et atouts de la communauté"), False),
        ("photo", photo("Photo (carte, séance)"), False),
    ])


def priorities():
    return build([
        ("date", day("Date de la priorisation", PAST), True),
        ("mode", choice("Mode de décision", ["Vote", "Consensus"]), True),
        ("besoin_1", text("Besoin prioritaire n° 1"), True),
        ("besoin_2", text("Besoin prioritaire n° 2"), False),
        ("besoin_3", text("Besoin prioritaire n° 3"), False),
        *attendance(),
        ("pv", photo("Procès-verbal (photo)"), True),
    ])


def committee():
    return build([
        ("date", day("Date de mise en place", PAST), True),
        ("mode", choice("Mode de désignation", ["Élection en assemblée", "Désignation par consensus"]), True),
        ("membres", number("Nombre de membres", minimum=1), True),
        ("membres_femmes", number("Dont femmes"), True),
        ("president", text("Nom du président ou de la présidente"), True),
        ("pv", photo("Procès-verbal (photo)"), True),
    ])


def evaluation():
    return build([
        ("date", day("Date de l'évaluation", PAST), True),
        ("satisfaction", choice("Satisfaction de la communauté", [
            "Très satisfaite", "Satisfaite", "Peu satisfaite", "Pas satisfaite",
        ]), True),
        ("points_forts", textarea("Points forts"), True),
        ("difficultes", textarea("Difficultés"), True),
        ("recommandations", textarea("Recommandations"), False),
        *attendance(),
    ])


FORMS = [
    # name, description, schema
    (MEETING, "Compte rendu des réunions et assemblées du cycle CDD.", meeting),
    (DIAGNOSIS, "Diagnostic participatif de la communauté.", diagnosis),
    (PRIORITIES, "Besoins retenus par la communauté.", priorities),
    (COMMITTEE, "Mise en place du comité de développement du village.", committee),
    (EVALUATION, "Évaluation du cycle par la communauté.", evaluation),
]

# Phases → activities → tasks: (key, name, kind, forms, due after N days, depends on, required, instructions).
# Forms are names: MIS follow-up events, or the "Sous-projet" record type.
CYCLE = [
    ("Information et mobilisation", 30, [
        ("Information des autorités et de la communauté", [
            ("info-autorites", "Rencontre avec les autorités locales", TaskKind.MEETING, [MEETING], 14, [], True,
             "Présenter le programme au chef de village et aux autorités ; remplir le compte rendu."),
            ("assemblee-information", "Assemblée villageoise d'information", TaskKind.MEETING, [MEETING], 30,
             ["info-autorites"], True,
             "Informer toute la communauté (femmes et jeunes compris) du cycle et de ses étapes."),
        ]),
    ]),
    ("Diagnostic participatif", 45, [
        ("Diagnostic", [
            ("diagnostic", "Diagnostic participatif", TaskKind.FORM, [DIAGNOSIS], 60, ["assemblee-information"],
             True, "Animer les outils du diagnostic avec des groupes d'hommes, de femmes et de jeunes."),
            ("restitution", "Restitution du diagnostic", TaskKind.MEETING, [MEETING], 75, ["diagnostic"], True,
             "Présenter les résultats du diagnostic en assemblée."),
        ]),
    ]),
    ("Planification", 45, [
        ("Priorités et comité", [
            ("priorisation", "Priorisation des besoins", TaskKind.FORM, [PRIORITIES], 90, ["restitution"], True,
             "La communauté classe ses besoins ; noter le mode de décision."),
            ("comite", "Mise en place du comité de développement", TaskKind.FORM, [COMMITTEE], 100, [], True,
             "Élection ou désignation du comité en assemblée."),
            ("validation-plan", "Validation du plan en assemblée", TaskKind.MEETING, [MEETING], 120,
             ["priorisation", "comite"], True, "Le plan et le sous-projet retenu sont validés en assemblée."),
        ]),
    ]),
    ("Mise en œuvre du sous-projet", 180, [
        ("Sous-projet", [
            ("identification-sous-projet", "Identification du sous-projet (fiche 1)", TaskKind.FORM, [RECORD], 150,
             ["validation-plan"], True, "Remplir la fiche 1 lors de la première visite du chantier."),
            ("suivi-travaux", "Suivi des travaux", TaskKind.FORM, [F2], 270, ["identification-sous-projet"], True,
             "Une fiche d'inspection à chaque visite du chantier."),
            ("reception-provisoire", "Réception provisoire", TaskKind.FORM, [F3], 300, ["suivi-travaux"], True,
             "Après la fin des travaux."),
        ]),
    ]),
    ("Suivi et clôture", 60, [
        ("Redevabilité et évaluation", [
            ("assemblee-redevabilite", "Assemblée de redevabilité", TaskKind.MEETING, [MEETING], 330,
             ["reception-provisoire"], True, "Rendre compte de l'utilisation des fonds à la communauté."),
            ("evaluation", "Évaluation participative", TaskKind.FORM, [EVALUATION], 345, [], True, ""),
            ("visite-echange", "Visite d'échange avec une autre communauté", TaskKind.MANUAL, [], None, [], False,
             "Facultative."),
            ("cloture", "Clôture du cycle", TaskKind.MANUAL, [], 365, ["evaluation", "assemblee-redevabilite"], True,
             "Vérifier que toutes les tâches sont faites, puis marquer comme faite."),
        ]),
    ]),
]


class Command(BaseCommand):
    help = "Create or update the example CDD cycle and its forms."

    def add_arguments(self, parser):
        parser.add_argument("--group", default=DEMO_GROUP, help="Group of the agents who fill the forms.")
        parser.add_argument("--enable", action="store_true", help="Switch the CDD module on.")

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=options["group"])
        if not TrackableObject.objects.filter(name=RECORD).exists():
            call_command("seed_suivi_chantier", group=options["group"], stdout=self.stdout)
        forms = {RECORD: TrackableObject.objects.get(name=RECORD)}
        for name in (F2, F3):
            forms[name] = FollowUpEvent.objects.get(name=name)
        base = FollowUpEvent.objects.order_by("-order").values_list("order", flat=True).first() or 0
        for index, (name, description, schema) in enumerate(FORMS, start=1):
            event, created = FollowUpEvent.objects.get_or_create(
                name=name, defaults={"description": description, "order": base + index}
            )
            event.description = description
            event.is_active = True
            event.jsonForm = schema()
            event.save()
            event.groups.add(group)
            forms[name] = event
            self.stdout.write(f"{'Created' if created else 'Updated'} {name}")

        template, created = CycleTemplate.objects.get_or_create(name=TEMPLATE)
        before = None if created else template_specs(template)
        template.description = "Cycle d'exemple, à remplacer par le cycle CDD du programme."
        template.save()
        self._tree(template, forms)
        if before is not None and before != template_specs(template):
            template.bump_version()
        self.stdout.write(f"{'Created' if created else 'Updated'} {TEMPLATE} (version {template.version})")

        if options["enable"]:
            config = ProgrammeConfig.get()
            config.cdd_enabled = True
            config.save(update_fields=["cdd_enabled", "updated_at"])
            self.stdout.write("CDD module switched on")

    def _tree(self, template, forms):
        tasks, depends = {}, {}
        for phase_order, (phase_name, planned_days, activities) in enumerate(CYCLE, start=1):
            phase, _ = Phase.objects.update_or_create(
                template=template, name=phase_name, defaults={"order": phase_order, "planned_days": planned_days}
            )
            for activity_order, (activity_name, rows) in enumerate(activities, start=1):
                activity, _ = Activity.objects.update_or_create(
                    phase=phase, name=activity_name, defaults={"order": activity_order}
                )
                for order, (key, name, kind, form_names, due, after, required, instructions) in enumerate(rows, 1):
                    task = Task.objects.filter(activity__phase__template=template, key=key).first() or Task(key=key)
                    task.activity, task.order, task.name, task.kind = activity, order, name, kind
                    task.planned_offset_days, task.required, task.instructions = due, required, instructions
                    task.save()
                    task.forms.all().delete()
                    for form_name in form_names:
                        target = forms[form_name]
                        field = "trackable_object" if isinstance(target, TrackableObject) else "follow_up_event"
                        TaskForm.objects.create(task=task, **{field: target})
                    tasks[key], depends[key] = task, after
        for key, after in depends.items():
            tasks[key].depends_on.set([tasks[k] for k in after])
