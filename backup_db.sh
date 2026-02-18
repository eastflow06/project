#!/usr/bin/env bash
set -Eeuo pipefail

# -- DB 백업 설정 --
SRC_DB="$HOME/project/db/project.db"
DEST_DB_DIR="$HOME/gdrive/db"
TS="$(date '+%Y-%m-%d_%H%M')"
BAK_DB="$DEST_DB_DIR/project-$TS.db"

# -- 프로젝트 파일 백업 설정 --
SRC_PROJECT_FILES="$HOME/project/static/"
SRC_PDATA="$HOME/project/pdata/"
DEST_PROJECT_FILES="$HOME/gdrive/"

# 백업 폴더 생성
mkdir -p "$DEST_DB_DIR"
mkdir -p "$DEST_PROJECT_FILES"

# -- DB 파일 백업 --
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$SRC_DB" ".backup '$BAK_DB'"
  sqlite3 "$BAK_DB" "PRAGMA integrity_check;" | grep -q '^ok$'
else
  cp -a "$SRC_DB" "$BAK_DB"
fi

# -- rsync로 프로젝트 파일 백업 --
# 변경된 파일만 NAS로 동기화합니다.
rsync -az --progress "$SRC_PROJECT_FILES" "$DEST_PROJECT_FILES"
rsync -az --progress "$SRC_PDATA" "$DEST_PROJECT_FILES/pdata/"

# 최근 30개만 유지
ls -1t "$DEST_DB_DIR"/project-*.db 2>/dev/null | tail -n +31 | xargs -r rm -f

# 로그 기록
echo "$(date -Is) DB backup created: $BAK_DB" >> "$HOME/project/backup.log"
echo "$(date -Is) Project files synced to: $DEST_PROJECT_FILES" >> "$HOME/project/backup.log"
echo "$(date -Is) pdata synced to: $DEST_PROJECT_FILES/pdata/" >> "$HOME/project/backup.log"
