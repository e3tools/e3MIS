# Déploiement de la branche `mis-monitoring-prod`

Cette branche = `prod_config` + `develop` (suivi terrain, API de l'app mobile, Django 5.2, PostGIS).
Fichiers de référence pour la VM : `deploy/docker-compose.yaml`, `deploy/nginx/nginx.conf`,
`deploy/env.example`.

---

## 1. En local

### 1.1 Mise en place (une seule fois)

```bash
git checkout mis-monitoring-prod
docker compose up -d --build        # PostGIS (localhost:5434) + Django (http://localhost:8000)
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Optionnel : un fichier `.env` à la racine peut contenir `MAPBOX_ACCESS_TOKEN=...` (il est ignoré par git).

### 1.2 Au quotidien

| Besoin | Commande |
|---|---|
| Démarrer / arrêter | `docker compose up -d` / `docker compose stop` |
| Voir les logs Django | `docker compose logs -f web` |
| Commande manage.py | `docker compose exec web python manage.py <commande>` |
| Tests | `docker compose exec web pytest -q` |
| Après modif de `requirements*.txt` ou du `Dockerfile` | `docker compose up -d --build` |

Le code est monté dans le conteneur : `runserver` recharge à chaque sauvegarde, pas besoin de down/up.

Sans Docker (`./manage.py runserver` depuis un venv) : il faut GDAL sur la machine
(`sudo apt install gdal-bin libgdal-dev`), la base PostGIS du compose (`docker compose up -d db`),
et décommenter les lignes `# local only` de `src/settings.py` (à recommenter avant commit).
SQLite n'est plus possible.

> Ne pas définir `PROGRAMME_TIMEZONE` en local : c'est la valeur par défaut d'un modèle,
> `makemigrations` croirait à un changement et créerait une fausse migration.

### 1.3 Tester la migration sur une copie de la base de prod (recommandé)

1. Sur la VM : `docker compose exec -T db pg_dump -U postgres -Fc smp > smp_copie.dump`, puis rapatrier
   le fichier en local.
2. En local :
   ```bash
   docker compose exec -T db createdb -U mis smp_copie
   docker compose exec -T db psql -U mis -d smp_copie -c "CREATE EXTENSION IF NOT EXISTS postgis;"
   docker compose exec -T db pg_restore -U mis -d smp_copie --no-owner --no-acl < smp_copie.dump
   docker compose run --rm -e DATABASE_URL=postgis://mis:mis@db:5432/smp_copie web python manage.py migrate
   ```
3. Si la migration passe, ouvrir l'app sur cette copie (`DATABASE_URL` idem avec `runserver 0.0.0.0:8001`
   et `-p 8001:8001`) et vérifier les écrans existants (sous-projets, objets suivis, utilisateurs).
4. Supprimer la copie et le dump ensuite (données de prod) : `docker compose exec -T db dropdb -U mis smp_copie`.

### 1.4 Construire et publier l'image

```bash
docker build -t cosobenin/smp-app:v2.0.2 .
docker push cosobenin/smp-app:v2.0.2
# image de la base (Postgres 17 bookworm + PostGIS), seulement si deploy/db/Dockerfile a changé
docker build -t cosobenin/smp-db:17-postgis3 deploy/db
docker push cosobenin/smp-db:17-postgis3
```

Garder l'ancien tag `v1.4.3` sur Docker Hub : c'est le retour arrière.

> Ne pas utiliser `postgis/postgis:17-*` pour la base : ces images sont sur Debian bullseye (glibc 2.31),
> alors que les données de prod ont été créées par `postgres:17.0` sur bookworm (glibc 2.36). Postgres
> affiche alors `collation version mismatch` et les index sur du texte peuvent devenir incohérents.

---

## 2. Sur la VM, avant le `up`

Toutes les commandes sont lancées dans le dossier du `docker-compose.yaml` actuel
(`/home/adminroot/docker-app`). Sur la VM, `docker` demande `sudo` : préfixer chaque commande
`docker compose ...` par `sudo`. Les fichiers de `deploy/` se collent dans la session SSH
(`cat > fichier <<'EOF' ... EOF`), le PAM ne permettant pas `scp` avec un compte Interactive.

1. **Sauvegarder** (l'ancienne stack tourne encore) :
   ```bash
   docker compose exec -T db pg_dump -U postgres -Fc smp > ~/smp_$(date +%F).dump
   cp docker-compose.yaml docker-compose.yaml.v1.4.3
   cp data/nginx/nginx.conf ~/nginx.conf.v1.4.3
   cp .env ~/.env.v1.4.3
   ```
   Vérifier que le dump n'est pas vide (`ls -lh ~/smp_*.dump`).
2. **Compléter le `.env`** (voir `deploy/env.example`) :
   - ajouter `DEBUG=False`
   - ajouter `PROGRAMME_TIMEZONE=Africa/Porto-Novo` (**avant le premier démarrage**, sinon il faudra la corriger en base)
   - **ne pas changer `SECRET_KEY`** (sinon les tokens API MIS existants deviennent invalides)
   - `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` : inchangés
   - `CORS_ALLOWED_ORIGINS` : seulement si le tableau de bord est servi depuis un autre domaine
3. **Remplacer les fichiers de config** par ceux de `deploy/` :
   - `deploy/docker-compose.yaml` → `docker-compose.yaml` (vérifier le tag de l'image, 2 occurrences)
   - `deploy/nginx/nginx.conf` → `data/nginx/nginx.conf`
4. **Récupérer l'image** : `docker compose pull`
5. **Passer la base sur PostGIS** (image `cosobenin/smp-db:17-postgis3` : même Postgres 17 et même
   Debian que `postgres:17.0`, le volume `pg_data` est réutilisé) :
   ```bash
   docker compose up -d db
   docker compose exec db psql -U postgres -d smp -c "CREATE EXTENSION IF NOT EXISTS postgis;"
   docker compose exec db psql -U postgres -d smp -c "ALTER EXTENSION postgis UPDATE;"
   docker compose exec db psql -U postgres -d smp -c "REINDEX DATABASE smp;"
   ```
   Aucun `WARNING: ... collation version mismatch` ne doit s'afficher. Le `REINDEX` reconstruit les
   index avec la collation de l'image (rapide sur cette base, sans risque).
6. **Démarrer le reste** : `docker compose up -d`
   (`run.sh serve` lance `migrate` et `collectstatic` tout seul.)

## 3. Sur la VM, juste après le `up`

1. `docker compose ps` : `django-app`, `scheduler`, `db`, `nginx` sont `Up`.
2. `docker compose logs django-app --tail 50` : migrations OK, `Listening at: http://0.0.0.0:9000`.
3. `docker compose logs scheduler --tail 20` : pas d'erreur.
4. `docker compose exec nginx nginx -t` puis ouvrir https://mis.coso.gouv.bj et se connecter.
5. `curl -s -o /dev/null -w "%{http_code}\n" https://mis.coso.gouv.bj/api/v1/forms/sync/` → `401` attendu
   (l'API répond, sans préfixe `/fr/`).
6. Données initiales :
   ```bash
   docker compose exec django-app python manage.py seed_suivi_chantier --group "<groupe des agents terrain>"
   # quand le fichier urbain/rural arrive :
   docker compose exec django-app python manage.py import_village_zones /chemin/fichier.xlsx \
       --village-column <colonne> --zone-column <colonne> --dry-run
   ```
   (Le fichier xlsx doit être copié dans le conteneur : `docker compose cp fichier.xlsx django-app:/tmp/`.)
7. Dans `/admin` : pour chaque utilisateur, rôle, superviseur et commune.
8. Prévenir le collègue que le serveur est prêt (nouvelles versions de l'app, tableau de bord, test avec Brice).

## 4. Retour arrière

La base garde l'image `cosobenin/smp-db:17-postgis3` (une base qui a eu l'extension ne se relit pas
proprement avec `postgres:17.0`) ; on la recrée depuis le dump d'avant la mise à jour.

```bash
docker compose down
cp docker-compose.yaml.v1.4.3 docker-compose.yaml
cp ~/nginx.conf.v1.4.3 data/nginx/nginx.conf
cp ~/.env.v1.4.3 .env
# dans docker-compose.yaml, service db : image: cosobenin/smp-db:17-postgis3
docker compose up -d db
docker compose exec -T db dropdb -U postgres smp
docker compose exec -T db createdb -U postgres smp
docker compose exec -T db pg_restore -U postgres -d smp < ~/smp_<date>.dump
docker compose up -d
```
