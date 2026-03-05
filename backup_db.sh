#!/usr/bin/env bash
set -Eeuo pipefail

# -- DB 백업 설정 (MySQL) --
MYSQL_USER="projectuser"
MYSQL_PASS="ProjectDB2026!"
MYSQL_DB="project_db"
DEST_DB_DIR="$HOME/gdrive/db"
TS="$(date '+%Y-%m-%d_%H%M')"
BAK_DB="$DEST_DB_DIR/project-$TS.sql.gz"

# -- 프로젝트 파일 백업 설정 --
SRC_PROJECT_FILES="$HOME/project/static/"
SRC_PDATA="$HOME/project/pdata/"
DEST_PROJECT_FILES="$HOME/gdrive/"

# 백업 폴더 생성
mkdir -p "$DEST_DB_DIR"
mkdir -p "$DEST_PROJECT_FILES"

# -- MySQL DB 백업 (mysqldump + gzip) --
# --no-tablespaces: PROCESS 권한 부족 경고 무시
# --single-transaction: InnoDB 테이블의 일관된 백업 보장
MYSQL_PWD="$MYSQL_PASS" mysqldump -u "$MYSQL_USER" --no-tablespaces --single-transaction "$MYSQL_DB" | gzip > "$BAK_DB"

# -- rsync로 프로젝트 파일 백업 --
# 변경된 파일만 NAS로 동기화합니다.
rsync -az --progress "$SRC_PROJECT_FILES" "$DEST_PROJECT_FILES"
rsync -az --progress "$SRC_PDATA" "$DEST_PROJECT_FILES/pdata/"

# 최근 30개만 유지
ls -1t "$DEST_DB_DIR"/project-*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm -f

# 로그 기록
echo "$(date -Is) MySQL backup created: $BAK_DB" >> "$HOME/project/backup.log"
echo "$(date -Is) Project files synced to: $DEST_PROJECT_FILES" >> "$HOME/project/backup.log"
echo "$(date -Is) pdata synced to: $DEST_PROJECT_FILES/pdata/" >> "$HOME/project/backup.log"
