# Déploiement du tableau de bord de supervision

Le tableau de bord de supervision (dépôt `leonardogutierrezh/suivi-terrain-web`) est servi par le
nginx de la VM à l'adresse **https://mis.coso.gouv.bj/supervision/**. Il s'adresse aux SC, aux
spécialistes régionaux et nationaux, au RdP et aux admins. Les FT et FC utilisent l'app mobile.

Pour le déploiement du MIS lui-même, voir `DEPLOYMENT.md`.

## Principe

- C'est une application React compilée par Vite en **fichiers statiques** (`index.html` et `assets/`).
  Elle n'a ni conteneur qui tourne, ni base de données, ni domaine à elle.
- `VITE_BASE_PATH=/supervision/` (au moment du build) fixe le préfixe des fichiers et des pages.
- Elle appelle l'API en relatif (`/api/v1/…`), donc le Django du MIS sur la même adresse. Il n'y a
  rien à configurer pour CORS, les cookies ou Django. Le jeton de connexion est gardé dans le
  `sessionStorage` du navigateur.
- nginx sert `data/supervision/` sous `/supervision/`. Une adresse inconnue renvoie `index.html`,
  pour qu'un rafraîchissement sur une page interne fonctionne. Les fichiers de `assets/` ont un hash
  dans leur nom et sont mis en cache un an ; `index.html` ne l'est jamais.
- **Transport :** `scp` est bloqué sur la VM, mais elle sait récupérer des images sur Docker Hub.
  Le build est donc livré dans une petite image `cosobenin/smp-supervision:<commit>`
  (`deploy/supervision/Dockerfile`, busybox + le contenu de `dist/`). Cette image n'est jamais lancée : on en
  copie seulement les fichiers.

## 1. Build et publication (en local)

Il faut Node ≥ 20.19 (Vite 8). Avec nvm : `nvm install 22` (une seule fois), puis `nvm use 22`.

```bash
cd ../suivi-terrain-web            # cloné à côté de e3MIS
git pull
nvm use 22
npm ci
VITE_BASE_PATH=/supervision/ npm run build
C=$(git rev-parse --short HEAD)
docker build -f ../e3MIS/deploy/supervision/Dockerfile -t cosobenin/smp-supervision:$C dist
docker push cosobenin/smp-supervision:$C
```

- Ne **pas** définir `VITE_ENVIRONMENT`. Cette variable sert à la démo et ajoute le bandeau orange DÉMO.
- Vérifier que `dist/index.html` référence bien `/supervision/assets/…`.

## 2. Mise en place sur la VM (une seule fois)

Dans `/home/adminroot/docker-app`, avec `sudo` devant chaque `docker`.

1. `docker-compose.yaml`, service `nginx`, volumes : ajouter
   `- ./data/supervision:/var/www/supervision:ro` (déjà présent dans `deploy/docker-compose.yaml`).
2. `data/nginx/nginx.conf`, dans le bloc `server`, avant `location /` : ajouter les blocs
   `location = /supervision`, `location /supervision/` et `location /supervision/assets/` (déjà
   présents dans `deploy/nginx/nginx.conf`).
3. Copier les fichiers (section 3), **puis** `docker compose up -d nginx`. Le volume doit exister
   avant le démarrage de nginx, sinon Docker crée un dossier vide.
4. `docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload`

## 3. Copier une version sur la VM (à chaque mise à jour)

```bash
docker pull cosobenin/smp-supervision:<commit>
rm -rf data/supervision && mkdir -p data/supervision
id=$(docker create cosobenin/smp-supervision:<commit>)
docker cp $id:/supervision/. data/supervision/
docker rm $id
ls data/supervision                # index.html et assets/
```

Pour une mise à jour, nginx n'a besoin ni de modification ni de rechargement.

## 4. Vérifier

- https://mis.coso.gouv.bj/supervision/ affiche la page de connexion (« Tableau de bord de supervision »).
- Se connecter avec un compte SC (email et mot de passe du MIS). Un SC voit son équipe, la file de
  revue et la page « Coordonnées » (positions à confirmer).
- Rafraîchir sur une page interne (par exemple `/supervision/coordonnees`) : le tableau de bord doit
  s'afficher de nouveau.
- Une page blanche indique en général un build fait sans `VITE_BASE_PATH=/supervision/`. Les
  fichiers sont alors demandés sous `/assets/…` (onglet Réseau du navigateur).

## Comptes

Les comptes se créent sur la page agents de terrain du MIS : un rôle (sc, rdp, admin…) et des unités
administratives. Pour un SC, la commune décide des sites et des agents qu'il voit.

## Retour arrière

- Version précédente : refaire la section 3 avec l'ancien tag.
- Retirer le tableau de bord : supprimer les blocs `/supervision` de `nginx.conf`, puis
  `nginx -t && nginx -s reload`.

Ces deux opérations ne touchent ni au MIS ni à sa base.
