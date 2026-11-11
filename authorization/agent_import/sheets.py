"""Layout of the agent import file, shared by the template and the reader.

One sheet, one row per agent and unit: the agent's details on their first row, the cells left empty
on the rows of their other units (a new agent starts at the next row with details).

Headers are written in the user's language and read back in any language, so a template downloaded
in French can be uploaded from the English pages.
"""
from django.utils import translation
from django.utils.translation import gettext_lazy as _

# A file holds at most this many agents: every agent is checked with the page's form, and the
# whole file in one request.
MAX_AGENTS = 200
# Rows of the Agents sheet that carry the drop-down lists (about ten villages per agent).
MAX_ROWS = 4000

AGENTS_SHEET = _("Agents")
# The former second sheet (Nov 2026, agents and units apart): only to recognise an old template.
ASSIGNMENTS_SHEET = _("Assignments")
INSTRUCTIONS_SHEET = _("Instructions")
# Hidden sheet feeding the drop-down lists; never read back.
LISTS_SHEET = "Lists"

# (key, header, required). The order is the column order of the Agents sheet.
AGENT_COLUMNS = [
    ("first_name", _("First name"), True),
    ("last_name", _("Last name"), True),
    ("email", _("Email"), True),
    ("phone_number", _("Phone number"), False),
    ("role", _("Role"), False),
    ("group", _("Group"), False),
    ("supervisor", _("Supervisor"), False),
]

LANGUAGES = ("fr", "en")


def in_all_languages(text):
    """``text`` (a lazy translation) in every language of the site, casefolded."""
    names = set()
    for language in LANGUAGES:
        with translation.override(language):
            names.add(str(text).casefold())
    return names


def agent_header(key):
    return next(str(header) for k, header, _required in AGENT_COLUMNS if k == key)
