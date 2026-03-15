#!/usr/bin/env bash
# =============================================================
# 06_mariadb-backup_incremental.sh  (sudo 필요)
# Mariabackup 증분 백업 스크립트 (cron 등록용)
# 전체 백업(full)을 기준으로 변경분만 백업합니다.
# cron 예: 0 3 * * * sudo bash /home/ubuntu/project/migration/06_mariadb-backup_incremental.sh
# =============================================================
set -Eeuo pipefail

DB_USER="projectuser"
DB_PASS="ProjectDB2026!"
BACKUP_BASE="/home/ubuntu/backup/db"
FULL_DIR="$BACKUP_BASE/full"
TS="$(date '+%Y%m%d_%H%M')"
INC_DIR="$BACKUP_BASE/inc_${TS}"
LOG="/home/ubuntu/project/backup.log"
GDRIVE_BASE="gdrive:Backup_SIX/db"
KEEP_DAYS=7   # 로컬 증분 백업 보존 기간 (일)

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 이 스크립트는 sudo로 실행해야 합니다."
    exit 1
fi

echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [INC] 증분 백업 시작 — $(date)"       | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. 전체 백업 존재 여부 확인 ---
if [ ! -d "$FULL_DIR" ] || [ ! -f "$FULL_DIR/backup_timestamp.txt" ]; then
    echo "[ERROR] 전체 백업이 없습니다: $FULL_DIR" | tee -a "$LOG"
    echo "  먼저 05_mariadb-backup_full.sh 를 실행하세요." | tee -a "$LOG"
    exit 1
fi

# --- 2. 가장 최신 기반 디렉토리 탐색 (full → 최신 inc 순) ---
LATEST_INC=$(ls -1dt "$BACKUP_BASE"/inc_* 2>/dev/null | head -1 || true)
if [ -n "$LATEST_INC" ]; then
    BASE_DIR="$LATEST_INC"
    echo "[INC] 증분 기반: 최신 증분 백업 → $BASE_DIR" | tee -a "$LOG"
else
    BASE_DIR="$FULL_DIR"
    echo "[INC] 증분 기반: 전체 백업 → $BASE_DIR" | tee -a "$LOG"
fi

# --- 3. 증분 백업 실행 ---
mkdir -p "$INC_DIR"
echo "[INC] 증분 백업 실행 중 → $INC_DIR" | tee -a "$LOG"
mariadb-backup --backup \
    --target-dir="$INC_DIR" \
    --incremental-basedir="$BASE_DIR" \
    --user="$DB_USER" \
    --password="$DB_PASS" \
    2>&1 | tee -a "$LOG"

# --- 4. 크기 확인 ---
INC_SIZE=$(du -sh "$INC_DIR" | awk '{print $1}')
echo "[INC] 증분 백업 크기: $INC_SIZE (경로: $INC_DIR)" | tee -a "$LOG"

# --- 5. GDrive 동기화 ---
echo "[INC] GDrive 동기화 중..." | tee -a "$LOG"
/usr/bin/rclone sync "$BACKUP_BASE" "$GDRIVE_BASE" \
    --include "inc_${TS}/**" \
    --checksum \
    --log-level INFO \
    --log-file "$LOG" \
    2>&1 || echo "[WARN] GDrive 동기화 실패" | tee -a "$LOG"

# --- 6. 오래된 로컬 증분 백업 정리 (KEEP_DAYS일 초과분 삭제) ---
echo "[INC] 오래된 로컬 증분 백업 정리 중 (${KEEP_DAYS}일 초과)..." | tee -a "$LOG"
find "$BACKUP_BASE" -maxdepth 1 -type d -name "inc_*" \
    -mtime +$KEEP_DAYS -exec rm -rf {} + 2>/dev/null \
    && echo "[INC] 정리 완료" | tee -a "$LOG" || true

# --- 7. 현재 백업 목록 출력 ---
echo "[INC] 현재 로컬 백업 목록:" | tee -a "$LOG"
ls -1dt "$BACKUP_BASE"/inc_* 2>/dev/null | head -10 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [INC] 증분 백업 완료 — $(date)"       | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
