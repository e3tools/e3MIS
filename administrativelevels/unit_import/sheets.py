"""Layout of the unit import file, shared by the template and the reader.

One sheet, one column per administrative level (headers are the level names), then an optional
Zone column, one row per unit at the bottom of its branch: the layout of the files given to
``manage.py sync_administrative_levels``.
"""
from django.utils import translation
from django.utils.translation import gettext_lazy as _

MAX_ROWS = 10000

UNITS_SHEET = _("Units")
INSTRUCTIONS_SHEET = _("Instructions")
ZONE_HEADER = _("Zone")
URBAN_LABEL = _("Urban")
RURAL_LABEL = _("Rural")

LANGUAGES = ("fr", "en")


def in_all_languages(text):
    """``text`` (a lazy translation) in every language of the site, casefolded."""
    names = set()
    for language in LANGUAGES:
        with translation.override(language):
            names.add(str(text).casefold())
    return names


def same_name(name):
    """The form names are compared in: case and extra spaces do not count ("Kandi" is "KANDI")."""
    return " ".join(name.split()).casefold()
