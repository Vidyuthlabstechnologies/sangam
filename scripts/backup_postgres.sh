#!/bin/sh
# Dump the Sangam application database with pg_dump.
#
#   DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/sangam' ./scripts/backup_postgres.sh [outfile]
#
# The URL is read from the environment. This script does not contain
# credentials and does not connect unless you run it. Do not point it at
# a production database from CI, and do not commit the dump.
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "Set DATABASE_URL to a postgresql URL. This script does not embed credentials." >&2
  exit 1
fi

case "$DATABASE_URL" in
  postgres://*|postgresql://*|postgresql+*)
    ;;
  *)
    echo "DATABASE_URL must be a postgres URL." >&2
    exit 1
    ;;
esac

url=$(printf '%s\n' "$DATABASE_URL" | sed \
  -e 's/^postgresql+asyncpg:/postgresql:/' \
  -e 's/^postgresql+psycopg:/postgresql:/' \
  -e 's/^postgresql+psycopg2:/postgresql:/')

out="${1:-sangam-$(date -u +%Y%m%dT%H%M%SZ).dump}"
echo "Writing custom-format dump to $out" >&2
exec pg_dump --format=custom --no-password --file="$out" "$url"
