#!/bin/sh
# Publish complete custom-format database archives via atomic rename.
set -eu
umask 077

case "${DATABASE_URL:-}" in
    postgresql+asyncpg://*) database="postgresql://${DATABASE_URL#postgresql+asyncpg://}" ;;
    postgresql+psycopg://*) database="postgresql://${DATABASE_URL#postgresql+psycopg://}" ;;
    postgresql://*|postgres://*) database="${DATABASE_URL}" ;;
    *)
        echo "Unsupported DATABASE_URL: expected postgresql[+driver]://..." >&2
        exit 1
        ;;
esac

destination=${BACKUP_DIR:-/backups}
retention=${BACKUP_RETENTION_DAYS:-14}
case "$retention" in
    ''|*[!0-9]*)
        echo "BACKUP_RETENTION_DAYS must be a positive integer" >&2
        exit 1
        ;;
esac
if [ "$retention" -lt 1 ]; then
    echo "BACKUP_RETENTION_DAYS must be a positive integer" >&2
    exit 1
fi

prune() {
    find "$destination" -maxdepth 1 -type f -name 'contest-*.dump' -mtime +"$retention" -exec rm -f {} \;
}

dump_once() {
    target="$destination/contest-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
    if pg_dump --dbname="$database" --format=custom --file="$target.partial"; then
        mv "$target.partial" "$target" || return 1
    else
        rm -f "$target.partial"
        return 1
    fi
    echo "Created $target"
    prune || echo "Could not prune old backups" >&2
}

if [ "${1:-}" = "--once" ]; then
    dump_once
    exit
fi
while true; do
    if dump_once; then
        sleep 86400
    else
        echo "Database backup failed, retrying in five minutes" >&2
        sleep 300
    fi
done
