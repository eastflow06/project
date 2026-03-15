#!/usr/bin/env bash
# =============================================================
# 01_mysql_full_dump.sh
# 마이그레이션 전 MySQL 전체 덤프 백업 + GDrive 업로드
# 이 파일만 잘 보관하면 언제든 롤백 가능합니다.
# =============================================================
set -Eeuo pipefail

MYSQL_USER="projectuser"
MYSQL_PASS="ProjectDB2026!"
MYSQL_DB="project_db"

BACKUP_DIR="/home/ubuntu/backup/migration"
TS="$(date '+%Y%m%d_%H%M%S')"
DUMP_FILE="$BACKUP_DIR/mysql_full_before_migration_${TS}.sql.gz"
MD5_FILE="$DUMP_FILE.md5"
LOG="/home/ubuntu/project/migration/migration.log"
GDRIVE_PATH="gdrive:redapril/backup/migration"

mkdir -p "$BACKUP_DIR"
echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [01] MySQL 전체 백업 시작 — $(date)"  | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. mysqldump 실행 ---
echo "[01] mysqldump 실행 중..." | tee -a "$LOG"
MYSQL_PWD="$MYSQL_PASS" mysqldump \
    -u "$MYSQL_USER" \
    --all-databases \
    --single-transaction \
    --no-tablespaces \
    --routines \
    --triggers \
    --events \
    | gzip > "$DUMP_FILE"

if [ ! -s "$DUMP_FILE" ]; then
    echo "[ERROR] 덤프 파일 생성 실패!" | tee -a "$LOG"
    exit 1
fi

DUMP_SIZE=$(du -h "$DUMP_FILE" | awk '{print $1}')
echo "[01] 덤프 완료: $DUMP_FILE ($DUMP_SIZE)" | tee -a "$LOG"

# --- 2. MD5 체크섬 생성 ---
md5sum "$DUMP_FILE" > "$MD5_FILE"
echo "[01] MD5 체크섬 생성: $(cat $MD5_FILE)" | tee -a "$LOG"

# --- 3. GDrive 업로드 ---
echo "[01] GDrive 업로드 중... ($GDRIVE_PATH)" | tee -a "$LOG"
/usr/bin/rclone copy "$BACKUP_DIR" "$GDRIVE_PATH" \
    --include "mysql_full_before_migration_${TS}.*" \
    --checksum \
    --log-level INFO \
    --log-file "$LOG"

echo "[01] GDrive 업로드 완료" | tee -a "$LOG"

# --- 4. GDrive 파일 확인 ---
echo "[01] GDrive 파일 확인:" | tee -a "$LOG"
/usr/bin/rclone ls "$GDRIVE_PATH/" 2>/dev/null | tail -5 | tee -a "$LOG"

# --- 5. 복원 명령 안내 ---
echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [01] 백업 완료 요약" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " 로컬 파일: $DUMP_FILE" | tee -a "$LOG"
echo " GDrive:   $GDRIVE_PATH/$(basename $DUMP_FILE)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " [롤백 방법]" | tee -a "$LOG"
echo " sudo systemctl stop mariadb || sudo systemctl stop mysql" | tee -a "$LOG"
echo " sudo apt reinstall mysql-server" | tee -a "$LOG"
echo " zcat $DUMP_FILE | mysql -u root -p" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " ★ 다음 단계: sudo bash 02_install_mariadb.sh" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
