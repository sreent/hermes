#!/bin/sh
# shellcheck shell=sh
# /opt/hermes/bin/tuos: tuos is this distribution's name for hermes (FORK.md). It starts the hermes
# shim beside it, which drops a root caller to the hermes user, so `docker exec <c> tuos ...` behaves
# exactly like `docker exec <c> hermes ...` and the process is still recognised as hermes.
exec /opt/hermes/bin/hermes "$@"
