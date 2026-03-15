#!/usr/bin/env bash
# =============================================================
# 05_mariadb-backup_full.sh  (sudo 필요)
# Mariabackup 전체 물리 백업 (최초 1회 또는 매월 1일 실행)
# 전체 백업은 증분 백업의 '기준점'이 됩니다.
# =============================================================
set -Eeuo pipefail

DB_USER="projectuser"
DB_PASS="ProjectDB2026!"
FULL_BACKUP_DIR="/home/ubuntu/backup/db/full"
LOG="/home/ubuntu/project/backup.log"
GDRIVE_PATH="gdrive:Backup_SIX/db/full"

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 이 스크립트는 sudo로 실행해야 합니다."
    exit 1
fi

echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [FULL] 전체 물리 백업 시작 — $(date)"  | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. 기존 전체 백업 보존 (날짜 폴더로 이동) ---
if [ -d "$FULL_BACKUP_DIR" ] && [ "$(ls -A $FULL_BACKUP_DIR 2>/dev/null)" ]; then
    OLD_FULL="${FULL_BACKUP_DIR}_old_$(date '+%Y%m%d_%H%M')"
    echo "[FULL] 기존 전체 백업 보존: $OLD_FULL" | tee -a "$LOG"
    mv "$FULL_BACKUP_DIR" "$OLD_FULL"
fi

mkdir -p "$FULL_BACKUP_DIR"

# --- 2. Mariabackup 전체 백업 실행 ---
echo "[FULL] Mariabackup 전체 백업 실행 중..." | tee -a "$LOG"
mariadb-backup --backup \
    --target-dir="$FULL_BACKUP_DIR" \
    --user="$DB_USER" \
    --password="$DB_PASS" \
    2>&1 | tee -a "$LOG"

# --- 3. 백업 Prepare (복원 가능한 상태로 만들기) ---
echo "[FULL] 백업 Prepare 중..." | tee -a "$LOG"
mariadb-backup --prepare \
    --target-dir="$FULL_BACKUP_DIR" \
    2>&1 | tee -a "$LOG"

# --- 4. 타임스탬프 기록 ---
TS="$(date '+%Y%m%d_%H%M%S')"
echo "$TS" > "$FULL_BACKUP_DIR/backup_timestamp.txt"
echo "[FULL] 타임스탬프: $TS" | tee -a "$LOG"

# --- 5. 크기 확인 ---
FULL_SIZE=$(du -sh "$FULL_BACKUP_DIR" | awk '{print $1}')
echo "[FULL] 전체 백업 크기: $FULL_SIZE (경로: $FULL_BACKUP_DIR)" | tee -a "$LOG"

# --- 6. GDrive 동기화 ---
echo "[FULL] GDrive 동기화 중..." | tee -a "$LOG"
/usr/bin/rclone sync "$FULL_BACKUP_DIR" "$GDRIVE_PATH" \
    --checksum \
    --log-level INFO \
    --log-file "$LOG" \
    2>&1 || echo "[WARN] GDrive 동기화 실패" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [FULL] 전체 백업 완료 — $(date)"      | tee -a "$LOG"
echo " 경로: $FULL_BACKUP_DIR"               | tee -a "$LOG"
echo " ★ 다음: 06_mariabackup_incremental.sh 로 증분 백업 시작" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
