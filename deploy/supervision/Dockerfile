# Transport image for the supervision dashboard (suivi-terrain-web): it only carries the static
# build to the VM through Docker Hub (scp is blocked there). It is never run; see
# DEPLOY_SUPERVISION.md. Build context = the dist/ folder (not the repo: node_modules is huge):
#   docker build -f ../e3MIS/deploy/supervision/Dockerfile -t cosobenin/smp-supervision:<commit> dist
FROM busybox:1.36
COPY . /supervision/
