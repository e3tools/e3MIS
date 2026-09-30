# e3MIS — field monitoring MIS (Django 5.2 + PostGIS)

Management information system for a community-development programme (admin-unit data is Benin:
Department → Commune → Arrondissement). UI is French by default (`LANGUAGE_CODE='fr'`, `en` too).

Two kinds of user (`authorization.CustomUser`, logs in by **email**, no username):

- **Staff / admins** (`is_field_agent=False`): AdminLTE desktop UI. Design forms, manage
  administrative units, agents and groups, view, edit and export submissions.
- **Field agents / facilitators** (`is_field_agent=True`): mobile web views under `…/mobile/`.
  Register trackable objects and fill in follow-up events. Login redirects to
  `/trackable-objects/mobile`; non-agents are sent on to the subprojects list.

## Branches

`develop` is the integration branch (NestorBracho's work lands here). **`feature/field-monitoring`**
(from `develop`) is where the field monitoring tool is being merged in — plan and decisions in
`../MERGE_PLAN.md` in the local workspace. Merge `develop` into it regularly. `prod_config` = latest work + deployment
setup (Dockerfile, `run.sh`, gunicorn, `DATABASE_URL`/`SECRET_KEY`/`ALLOWED_HOSTS` from env); it
also comments out the `/api/v1/` router registrations, so do not merge it back into `develop`
blindly. `main` is stale (July 2025).

## Field monitoring (`fieldmonitoring/`)

Worksite visit verification, moved in from `suivi-terrain-backend` (Phase 1 of `../MERGE_PLAN.md`).
Apps: `core` (ProgrammeConfig, jobs, storage, geography), `registry` (worksites), `visits`
(check-in/out, photos, state machine), `review`, `compliance` (rules BR-1…BR-15), `warning`.
`fieldmonitoring/accounts/` is not an app: permissions, serializers and sign-in views for the API.
Tests in `tests/fieldmonitoring/`, named after rule IDs. The spec is `../spec/` in the workspace.

Its API is `/api/v1/…` **outside** the language prefix (docs `/api/docs/`), used by the Expo field
app and the React supervision dashboard. The MIS read-only API stays at `/fr/api/v1/…`.

Non-negotiables (from the spec; they govern visits, not MIS forms):
1. A failed check is never automatically `missed`: it is `unverified` and goes to a human. Every
   state change goes through `fieldmonitoring/visits/state_machine.py` (`apply()`), and a DB
   constraint enforces it.
2. Server time only; never store or compare device time.
3. The worksite is the unit; villages are labels.
4. Check-out is mandatory.
5. The tool warns, it does not enforce: no acknowledgement, escalation or action tracking.
6. Paused people are excluded from evaluation but always counted and shown.

How it maps onto the MIS:
- **Users:** `CustomUser.role` (ft, fc, sc, regional/national specialist, rdp, admin), `supervisor`,
  `commune`, `region`. Roles drive visit rules; groups still decide which forms a user sees. Saving
  a user with a visiting role sets `is_field_agent`. `authorization.models.User` is an alias.
- **Geography:** the AdministrativeUnit tree. `ProgrammeConfig.region_level/commune_level/
  village_level` say which levels play those roles; unset, the tree position is used
  (`fieldmonitoring/core/geography.py`). Worksites derive `commune`/`region` from `village`.
- **Sign-in:** `POST /api/v1/auth/token/` with `email` (or `username`, which old app builds send;
  exact match). User ids are **strings** in this API (clients compare them with URL params).
- DRF answers 401 (with WWW-Authenticate) when signed out or expired; the apps refresh only on 401.
- CSV exports read `?format=csv` themselves (`IgnoreFormatParamNegotiation`); DRF's global format
  override stays on for drf-yasg.
- Keep old app builds working: accept old field names until those builds are gone
  (`grievance_raised` is still accepted as `issue_reported`).

## Forms API for the field app (`trackableobjects/field_api/`)

Offline-first API the Expo app uses for MIS forms (Phase 2 of `../MERGE_PLAN.md`), at
`/api/v1/forms/` (field agents only):
- `GET sync/?since=<iso>`: templates, follow-up events (with `depends_on`, `standalone`,
  `can_create`/`can_fill`), administrative units for pickers, `trackable_object_options`, changed
  records/responses, and the full `record_ids`/`response_ids` so the phone drops what it can't see.
- `POST push/`: `{items: [...]}` (≤100), applied in order, one result each: `created`, `updated`,
  `duplicate` (replay), `conflict` (`stale` edit or one-off `already_answered`, with the server copy),
  `invalid` (per-field `errors`), `forbidden`, `not_found`. Creates carry `client_uuid`; updates carry
  `base_version`. A response can point at a record created in the same batch (`record_client_uuid`).
- `POST attachments/` (multipart, idempotent by `client_uuid`) after the answers carry the
  `"Attachment"` marker; `GET attachments/<id>/` streams it after a permission check.

Rules: `trackableobjects/visibility.py` is the single source of who sees and fills what; the MIS
mobile screens use it too. Answers are re-checked with the MIS parser
(`field_api/validation.py`): every page, fields hidden by display conditions dropped, files via the
marker. Unknown answer keys are dropped. `manage.py seed_demo_forms` adds sample forms (idempotent).

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
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements-dev.txt   # numpy 2.0 has no 3.13 wheels
cp .env.example .env                  # SECRET_KEY and DEBUG=True are required locally
docker compose up -d db               # PostGIS on localhost:5434 (5433 is the old field monitoring DB)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser          # asks for email
.venv/bin/python manage.py runserver
```

Settings come from the environment (`SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `MEDIA_ROOT`). Any `postgres://` URL runs on the PostGIS engine. The same
code serves production (government server) and the internal demo (Vercel + Neon).

Setup data: create `AdministrativeLevel`s first (`order` is required), then load units with
`manage.py sync_administrative_levels <excel>`. `create_administrative_levels_users` creates one
agent per unit and **prints passwords** — do not run it where output is logged.

APIs: field monitoring at `/api/v1/` (JWT from `/api/v1/auth/token/`, docs `/api/docs/`); MIS
read-only at `/fr/api/v1/` (JWT from `/fr/api/login/` or `MIS-…` API tokens, docs `/fr/api/v1/swagger/`).
`manage.py seed_demo` loads field monitoring demo data (its own small tree; empty databases only).
`manage.py run_jobs` runs the 20:00 auto-close and Monday warning (cron on a server).

## Deployments

- **Production:** government server (`mis.coso.gouv.bj`), Docker image from Florentin's `prod_config`.
- **Internal demo:** https://e3mis-demo.vercel.app — Vercel project `e3mis-demo`, container runtime
  (`Dockerfile.vercel`, `vercel.json`), Neon (PostGIS) and a private Vercel Blob store, Vercel Cron.
  Deploy with `vercel deploy --prod`. Migrate Neon right after a schema change, from this Mac:
  `vercel env pull <scratch file> --environment production`, run `manage.py migrate` with
  `DATABASE_URL` set to its `DATABASE_URL_UNPOOLED`, delete the file. Demo users are
  `<name>@example.org`; signing in on the deployed site is for the user, not for agents.

## Testing

```bash
.venv/bin/pytest                      # tests/ — needs the db container
.venv/bin/python manage.py makemigrations --check --dry-run
```

`tests/conftest.py` has the fixtures (desktop user, field agent in a group with a unit, a form, a
record, a follow-up). Tests cover every page for both roles, the field agent flows, the API and the
access rules. Seed forms in the dict shape above; a list makes the mobile views crash.

Adding a field with `auto_now_add` to an existing model makes `makemigrations` prompt (and hang
under a non-interactive shell): write that migration by hand with `preserve_default=False`.

## Access rules

- Pages: `src/permissions.py` — `IsStaffMemberMixin` (desktop), `IsFieldAgentUserMixin` (mobile),
  `IsAdminMemberMixin` (delete: superuser or `Admin` group). Every view needs one.
- `/api/v1/` is read-only for signed-in desktop users or API tokens (`MIS-…`); field agents are
  refused. DRF accepts API token, JWT and session (the MIS pages call their JSON endpoints with the
  session cookie). Never take the user's identity from a request parameter or header.

## Offline sync fields

Records, follow-up responses and attachments have `client_uuid` (phone-generated, unique),
records/follow-ups have `version` (bumped when answers change) and `schema_version` (the form's
version when filled). Trackable objects and follow-up events have `schema_version`, bumped when their
`jsonForm` changes (`VersionedSchemaMixin`, `SyncedAnswerMixin` in `trackableobjects/models.py`).

## Known issues (do not "discover" these again)

- `SECRET_KEY` is also the API-token pepper: changing it invalidates every API token.
- `TokenViewSet` (create/list/revoke API tokens) exists but is not routed.
- No view sets `TrackableObjectInstance.administrative_units` (admin only).
- `/api/v1/` sits inside `i18n_patterns`, so paths are `/fr/api/v1/…`.
- Several packages lack `__init__.py` (work as namespace packages). `identifier.sqlite` is a stray file.
- The production Docker image (`prod_config`) needs GDAL/GEOS installed for PostGIS.

## Working rules

- Stage files explicitly; do not `git add -A` (local-only files: `.env.local`, `.agents/`, `.claude/`).
- Finished phases merge directly into `develop` (Leonardo is lead developer).
- End commit messages with the `Co-Authored-By` line the session provides.
