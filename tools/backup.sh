#!/bin/sh
# Publish complete custom-format database archives via atomic rename.
set -eu
umask 077
database="postgresql:${DATABASE_URL#postgresql+asyncpg:}"
destination=${BACKUP_DIR:-/backups}
dump_once() {
    target="$destination/contest-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
    if pg_dump --dbname="$database" --format=custom --file="$target.partial"; then
        mv "$target.partial" "$target" || return 1
    else
        rm -f "$target.partial"
        return 1
    fi
    echo "Created $target"
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
