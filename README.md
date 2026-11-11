# e3MIS

The e3tools MIS (Django 5.2, PostGIS) and, since the October 2026 merge, the backend of the
Suivi Terrain field app and supervision dashboard (`fieldmonitoring/`).

- **MIS screens** (AdminLTE): form designer (trackable objects, follow-up events), users, groups,
  administrative units, submissions. Language prefix: `/fr/…`, `/en/…`.
- **APIs** (no language prefix): `/api/v1/` field monitoring (visits, review, compliance, warning,
  coordinates) and `/api/v1/forms/` (offline-first forms sync for the app).

```bash
docker compose up -d                        # PostGIS (localhost:5434) + Django (http://localhost:8000)
docker compose exec web python manage.py migrate
docker compose exec web pytest -q
```

Without Docker for Django (a venv): install GDAL first (`sudo apt install gdal-bin libgdal-dev`;
GeoDjango loads it at start-up, pip cannot provide it), `cp .env.example .env`, then
`docker compose up -d db` and `./manage.py runserver` from the activated venv. See `DEPLOYMENT.md` §1.

Demo data: `manage.py seed_demo`, `seed_demo_forms`, `seed_suivi_chantier` (COSO sub-project forms).
Read `CLAUDE.md` before changing code (architecture, rules, deployments, gotchas); the workspace
`../PROGRESS.md` has the current state and `../MERGE_PLAN.md` the merge decisions.
