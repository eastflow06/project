#!/usr/bin/env bash
set -Eeuo pipefail

# =============================================================
# backup_db.sh — MariaDB 증분 백업 + 프로젝트 파일 동기화
# MariaDB 마이그레이션 후 mysqldump → Mariabackup 증분 방식으로 변경
# =============================================================

# -- 프로젝트 파일 백업 설정 --
SRC_PROJECT_FILES="$HOME/project/static/"
SRC_PDATA="$HOME/project/pdata/"
DEST_PROJECT_FILES="$HOME/gdrive/"

# 백업 폴더 생성
mkdir -p "$DEST_PROJECT_FILES"

# -- MariaDB 증분 백업 (Mariabackup) --
# 전체 백업(full)이 없으면 먼저 05_mariabackup_full.sh를 실행하세요.
# 전체 백업이 있으면 변경분(증분)만 빠르게 백업합니다.
INCREMENTAL_SCRIPT="$HOME/project/migration/06_mariabackup_incremental.sh"
if [ -f "$INCREMENTAL_SCRIPT" ]; then
    sudo bash "$INCREMENTAL_SCRIPT"
else
    echo "$(date -Is) [WARN] 증분 백업 스크립트 없음: $INCREMENTAL_SCRIPT" >> "$HOME/project/backup.log"
fi

# -- rsync로 프로젝트 파일 백업 --
# 변경된 파일만 NAS로 동기화합니다.
rsync -az --progress "$SRC_PROJECT_FILES" "$DEST_PROJECT_FILES"
rsync -az --progress "$SRC_PDATA" "$DEST_PROJECT_FILES/pdata/"

# 로그 기록
echo "$(date -Is) MariaDB 증분 백업 완료" >> "$HOME/project/backup.log"
echo "$(date -Is) Project files synced to: $DEST_PROJECT_FILES" >> "$HOME/project/backup.log"
echo "$(date -Is) pdata synced to: $DEST_PROJECT_FILES/pdata/" >> "$HOME/project/backup.log"
