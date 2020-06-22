#!/usr/bin/env bash

hostport="0.0.0.0:8000"

if [[ -n "$@" ]]; then
   hostport="$@"
fi
python3 manage.py migrate
python3 manage.py runserver $hostport
