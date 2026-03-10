#!/bin/sh
set -eu

MONGO_URI="${MONGO_URI:-mongodb://mongo:27017}"
INTERVAL_SEC="${MONGO_BACKUP_INTERVAL_SEC:-86400}"
TARGET_DIR="${MONGO_BACKUP_TARGET_DIR:-/backups}"
FILE_PREFIX="${MONGO_BACKUP_FILE_PREFIX:-mongo}"
KEEP_LAST="${MONGO_BACKUP_KEEP_LAST:-14}"

case "$INTERVAL_SEC" in
  ''|*[!0-9]*)
    echo "Invalid MONGO_BACKUP_INTERVAL_SEC: $INTERVAL_SEC" >&2
    exit 1
    ;;
esac

case "$KEEP_LAST" in
  ''|*[!0-9]*)
    echo "Invalid MONGO_BACKUP_KEEP_LAST: $KEEP_LAST" >&2
    exit 1
    ;;
esac

if [ "$INTERVAL_SEC" -le 0 ]; then
  echo "MONGO_BACKUP_INTERVAL_SEC must be greater than 0" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

backup_once() {
  TS="$(date -u +"%Y%m%dT%H%M%SZ")"
  TMP_FILE="$TARGET_DIR/.${FILE_PREFIX}-${TS}.archive.gz.tmp"
  OUT_FILE="$TARGET_DIR/${FILE_PREFIX}-${TS}.archive.gz"

  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting backup to $OUT_FILE"
  if mongodump --uri="$MONGO_URI" --archive="$TMP_FILE" --gzip; then
    mv "$TMP_FILE" "$OUT_FILE"
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Backup finished: $OUT_FILE"
  else
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Backup failed" >&2
    rm -f "$TMP_FILE"
    return 1
  fi

  if [ "$KEEP_LAST" -gt 0 ]; then
    # Keep only the most recent files that match the configured prefix.
    ls -1t "$TARGET_DIR/${FILE_PREFIX}-"*.archive.gz 2>/dev/null | sed -e "1,${KEEP_LAST}d" | while IFS= read -r OLD_FILE; do
      [ -n "$OLD_FILE" ] && rm -f "$OLD_FILE"
    done
  fi
}

echo "Backup loop started (interval=${INTERVAL_SEC}s, target=${TARGET_DIR}, keep_last=${KEEP_LAST})"

while true; do
  backup_once || true
  sleep "$INTERVAL_SEC"
done
