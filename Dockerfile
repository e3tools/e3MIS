FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# GeoDjango (django.contrib.gis, used for visit GPS positions) needs GDAL/GEOS/PROJ.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# create app directory.
RUN mkdir -p /usr/appserver
WORKDIR /usr/appserver

# install requirement
# DEV=true also installs the test tools (pytest); only the local docker-compose.yml sets it.
ARG DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt \
    && if [ "$DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

# copy all the code
COPY . .

EXPOSE 9000

ENTRYPOINT [ "./run.sh" ]

CMD [ "serve" ]
