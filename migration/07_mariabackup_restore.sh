#!/usr/bin/env bash
# =============================================================
# 07_mariabackup_restore.sh  (sudo 필요)
# 전체 백업 + 증분 백업을 조합하여 DB 복원
#
# 사용법:
#   --dry-run   : 실제 복원 없이 절차만 출력
#   --inc DIRNAME : 복원할 증분 백업 디렉토리 이름 (예: inc_20260305_0300)
#                   미지정 시 최신 증분 백업까지 자동 적용
#
# 예) sudo bash 07_mariabackup_restore.sh --dry-run
#     sudo bash 07_mariabackup_restore.sh --inc inc_20260305_0300
# =============================================================
set -euo pipefail

BACKUP_BASE="/home/ubuntu/backup/db"
FULL_DIR="$BACKUP_BASE/full"
RESTORE_STAGING="$BACKUP_BASE/restore_staging"
LOG="/home/ubuntu/project/backup.log"
DRY_RUN=false
TARGET_INC=""

# 옵션 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --inc)     TARGET_INC="$2"; shift 2 ;;
        *) echo "알 수 없는 옵션: $1"; exit 1 ;;
    esac
done

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] sudo로 실행해야 합니다."
    exit 1
fi

run() {
    if $DRY_RUN; then
        echo "[DRY-RUN] $*"
    else
        eval "$*"
    fi
}

echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [RESTORE] 복원 시작 — $(date)"         | tee -a "$LOG"
if $DRY_RUN; then echo " ★ DRY-RUN 모드 (실제 복원 없음)"; fi | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. 전체 백업 확인 ---
if [ ! -d "$FULL_DIR" ]; then
    echo "[ERROR] 전체 백업 디렉토리 없음: $FULL_DIR" | tee -a "$LOG"
    exit 1
fi
FULL_TS=$(cat "$FULL_DIR/backup_timestamp.txt" 2>/dev/null || echo "unknown")
echo "[RESTORE] 전체 백업 타임스탬프: $FULL_TS" | tee -a "$LOG"

# --- 2. 적용할 증분 백업 목록 결정 ---
if [ -n "$TARGET_INC" ]; then
    # 특정 증분까지만 적용
    mapfile -t INC_LIST < <(ls -1dt "$BACKUP_BASE"/inc_* 2>/dev/null | \
        awk -v tgt="$BACKUP_BASE/$TARGET_INC" 'p==0{print; if($0==tgt)p=1}' | sort)
else
    # 모든 증분 적용 (시간순)
    mapfile -t INC_LIST < <(ls -1dt "$BACKUP_BASE"/inc_* 2>/dev/null | sort)
fi

echo "[RESTORE] 적용할 증분 백업 수: ${#INC_LIST[@]}" | tee -a "$LOG"
for d in "${INC_LIST[@]}"; do echo "  → $d" | tee -a "$LOG"; done

# --- 3. 스테이징 디렉토리에 전체 백업 복사 ---
echo "[RESTORE] 스테이징 디렉토리 준비 중..." | tee -a "$LOG"
run "rm -rf '$RESTORE_STAGING'"
run "cp -ar '$FULL_DIR' '$RESTORE_STAGING'"

# --- 4. 전체 백업 prepare (apply-log-only) ---
echo "[RESTORE] 전체 백업 prepare 중..." | tee -a "$LOG"
run "mariabackup --prepare --target-dir='$RESTORE_STAGING' 2>&1 | tee -a '$LOG'"

# --- 5. 증분 백업 순서대로 apply ---
for INC_DIR in "${INC_LIST[@]}"; do
    echo "[RESTORE] 증분 적용: $INC_DIR" | tee -a "$LOG"
    if [ "$INC_DIR" = "${INC_LIST[-1]}" ]; then
        # 마지막 증분은 --apply-log-only 없이 (최종 prepare)
        run "mariabackup --prepare --target-dir='$RESTORE_STAGING' --incremental-dir='$INC_DIR' 2>&1 | tee -a '$LOG'"
    else
        run "mariabackup --prepare --target-dir='$RESTORE_STAGING' --incremental-dir='$INC_DIR' 2>&1 | tee -a '$LOG'"
    fi
done

# 증분이 없으면 최종 prepare
if [ ${#INC_LIST[@]} -eq 0 ]; then
    echo "[RESTORE] 증분 없음 — 최종 prepare 실행" | tee -a "$LOG"
    run "mariabackup --prepare --target-dir='$RESTORE_STAGING' 2>&1 | tee -a '$LOG'"
fi

# --- 6. MariaDB 중지 → 데이터 복사 → 권한 복구 → 시작 ---
echo "[RESTORE] MariaDB 중지 중..." | tee -a "$LOG"
run "systemctl stop mariadb"
run "systemctl stop gunicorn || true"

echo "[RESTORE] 기존 데이터 디렉토리 백업 중..." | tee -a "$LOG"
run "mv /var/lib/mysql /var/lib/mysql_old_$(date '+%Y%m%d_%H%M') || true"
run "mkdir -p /var/lib/mysql"

echo "[RESTORE] 데이터 복사 중 (copy-back)..." | tee -a "$LOG"
run "mariabackup --copy-back --target-dir='$RESTORE_STAGING' 2>&1 | tee -a '$LOG'"

echo "[RESTORE] 권한 복구 중..." | tee -a "$LOG"
run "chown -R mysql:mysql /var/lib/mysql"

echo "[RESTORE] MariaDB 시작 중..." | tee -a "$LOG"
run "systemctl start mariadb"
sleep 5
run "systemctl start gunicorn || true"

echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [RESTORE] 복원 완료 — $(date)"         | tee -a "$LOG"
if ! $DRY_RUN; then
    echo " MariaDB 상태 확인:"
    systemctl status mariadb --no-pager | head -5
fi
echo "======================================" | tee -a "$LOG"
