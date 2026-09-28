# e3MIS — field monitoring MIS (Django 4.2)

Management information system for a community-development programme (admin-unit data is Benin:
Department → Commune → Arrondissement). UI is French by default (`LANGUAGE_CODE='fr'`, `en` too).

Two kinds of user (`authorization.CustomUser`, logs in by **email**, no username):

- **Staff / admins** (`is_field_agent=False`): AdminLTE desktop UI. Design forms, manage
  administrative units, agents and groups, view, edit and export submissions.
- **Field agents / facilitators** (`is_field_agent=True`): mobile web views under `…/mobile/`.
  Register trackable objects and fill in follow-up events. Login redirects to
  `/trackable-objects/mobile`; non-agents are sent on to the subprojects list.

## Branches

`develop` is the integration branch and holds all current work; feature branches are cut from it
and merged back (`trackable_objects` is the active one). `prod_config` = latest work + deployment
setup (Dockerfile, `run.sh`, gunicorn, `DATABASE_URL`/`SECRET_KEY`/`ALLOWED_HOSTS` from env); it
also comments out the `/api/v1/` router registrations, so do not merge it back into `develop`
blindly. `main` is stale (July 2025).

## Domain model

| App | Models |
|---|---|
| `authorization` | `CustomUser` (`is_field_agent`, `phone_number`, M2M `administrative_units`), `AppSettings` singleton (`AppSettings.load()`) |
| `administrativelevels` | `AdministrativeLevel` (unique `order`, required), `AdministrativeUnit` tree (`parent`, `hierarchy_name` set in `save()`, `get_descendant_ids()`) |
| `trackableobjects` | `TrackableObject` (form template), `FollowUpEvent` (form linked to objects via `FollowUpEventTrackableObject`; linked to none = standalone form), `FollowUpEventDependency` (child hidden until parent answered for that instance), `TrackableObjectInstance` and `FollowUpEventResponse` (the answers) |
| `subprojects` | Older hard-coded module: `Subproject`, `Contractor`, `SiteVisit`, `ProgressUpdate`, … plus `SubprojectCustomField` forms. **`Attachment` stores files for all response types.** |
| `api` | `ApiToken` and the read-only `/api/v1/` ViewSets |

Access is by Django **groups**: objects, events and instances carry M2M `groups`, and an agent sees
an event only if they share a group and its dependencies are met. Instances with
`restrict_by_administrative_units=True` are visible only to agents assigned to an overlapping unit
(ancestors and descendants included). `display_id` gives the UI prefixes `TO-` / `FE-`.

## Dynamic forms (the core of the system)

Every `jsonForm` / `config_schema` **template** has this shape (a dict, not a list):

```json
{"form": [{"page": {"properties": {"name": {"type": "string"}}, "required": ["name"]},
           "options": {"fields": {"name": {"label": "Name", "order": 1, "dependencies": {…}}}}}]}
```

**Answers** (`TrackableObjectInstance.jsonForm`, `FollowUpEventResponse.jsonForm`) are a flat dict:
`{"name": "École B", "ok": true}`. Files are stored as the string `"Attachment"` plus a
`subprojects.Attachment(field_name=…)` row.

- Builder UI: `static/js/custom/schema_form.js` (jQuery; writes into `#config_schema`).
- Parser: `utils/json_form_parser.py`, `parse_custom_jsonschema()` builds a Django `Form`. Types
  include string/enum/multi/date, number, integer, boolean, file, geolocation, `trackable_object`,
  `administrative_level` (cascading select; `administrative_level_restriction` limits to the
  user's units).
- Display conditions: `dependencies.conditions` (equals, not_equals, contains, greater_than,
  less_than, between; AND/OR). Parent-form conditions (`is_parent_form`) are evaluated on the
  server, the rest in `static/js/custom/dynamic_form_runtime.js` (config from
  `templates/trackable_objects/_dynamic_form_config.html`).
- Saving answers: `utils/dynamic_form_io.py` (`build_json_form`). Tables and CSV/XLSX export:
  `utils/submission_table.py`, `utils/submission_export.py`.
- `identifier_field` names the answer key used as a record's label.

## Code layout conventions

- One class-based view per file: `<app>/infrastructure/views/` (desktop) and
  `<app>/infrastructure/mobile_views/` (agents). Forms in `<app>/infrastructure/forms/`, DRF in
  `<app>/api/`. Each `urls.py` imports views one by one.
- URL namespaces: `trackableobjects`, `subprojects`, `authorization`, `administrativelevels`, with
  nested `…:mobile:` and `…:api:`. All URLs are inside `i18n_patterns` (paths start `/fr/` or `/en/`).
- Templates in the root `templates/` by area, with `mobile/` and `partials/` subfolders.
- Permission mixins in `src/permissions.py`: `IsStaffMemberMixin`, `IsFieldAgentUserMixin`
  (optional `groups_required`). Put one on every new view.
- Strings go through `gettext`; translations in `locale/fr/LC_MESSAGES/django.po`.
- Pre-commit: black + isort + flake8, line length 120; commitizen commit messages.

## Running locally

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt   # numpy 2.0 has no 3.13 wheels
echo "MAPBOX_ACCESS_TOKEN=dummy" > .env    # required, no default; DB defaults to ./db.sqlite3
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser          # asks for email
.venv/bin/python manage.py runserver
```

Setup data: create `AdministrativeLevel`s first (`order` is required), then load units with
`manage.py sync_administrative_levels <excel>`. `create_administrative_levels_users` creates one
agent per unit and **prints passwords** — do not run it where output is logged.

API: JWT at `/api/login/`, docs at `/api/v1/swagger/`; `/api/v1/` also accepts `MIS-…` API tokens.

## Testing

There are **no tests** (every `tests.py` is a stub). Until there are, verify changes with:

- `manage.py check` and `manage.py makemigrations --check --dry-run` (currently reports one
  pre-existing drift in `api` — the `ApiToken.prefix` default — which is not yours to fix unless asked)
- a Django test-client smoke run that logs in as a superuser and as a field agent (in a group, with
  an administrative unit) and requests every page, then POSTs a trackable-object instance and a
  follow-up response. Seed forms in the dict shape above; a list makes the mobile views crash.

## Known issues (do not "discover" these again)

- `src/settings.py` hardcodes `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]` (production uses
  `prod_config`). `SECRET_KEY` is also the API-token pepper. `MEDIA_ROOT` is undefined.
- `TrackableObjectDeleteView` and `FollowUpEventDeleteView` have no permission mixin.
- `trackable-objects/api/trackable-object-instance` trusts an `HTTP_USER` header and 500s without
  it; `subprojects/api/custom-fields` 500s without its parameters.
- `/api/v1/user/` 500s (`UserSerializer` lists `username`, `administrative_unit`); check
  `FollowUpEventSerializer` field names too. `TokenViewSet` exists but is not routed.
- No view sets `TrackableObjectInstance.administrative_units` (admin only).
- Several packages lack `__init__.py` (work as namespace packages). `identifier.sqlite` is a stray file.
