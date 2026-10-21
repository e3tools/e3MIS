# Database image for production: the official Postgres 17 on Debian bookworm plus PostGIS.
# Not postgis/postgis:17-*: those are built on Debian bullseye (glibc 2.31), while the production
# data was created by postgres:17.0 on bookworm (glibc 2.36). A different glibc changes text
# collation and can silently corrupt text indexes. Same base => same glibc => same collation.
FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-postgis-3 postgresql-17-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*
