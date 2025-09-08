#!/bin/bash

show_help() {
    echo """
    Commands
    ---------------------------------------------------------
    bash          : run bash
    eval          : eval shell command
    django        : invoke django commands
    serve         : run web server as wsgi app
    test          : run all tests
  """
}

case "$1" in
  
    bash )
        bash
    ;;

    eval )
        eval "${@:2}"
    ;;

    django )
        python ./manage.py "${@:2}"
    ;;

    serve )
        python ./manage.py migrate
        gunicorn src.wsgi:application \
        --bind 0.0.0.0:9000 \
        --workers 4
    ;;

    test )
        pytest --cov=app --cov-report=xml
    ;;

    * )
        show_help
    ;;

esac
