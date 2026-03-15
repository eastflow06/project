#!/usr/bin/env bash
# =============================================================
# 03_restore_to_mariadb.sh  (sudo 필요)
# 01번 덤프 파일을 MariaDB에 복원 + 검증 + Flask 재시작
# =============================================================
set -Eeuo pipefail

DB_NAME="project_db"
DB_USER="projectuser"
DB_PASS="ProjectDB2026!"
BACKUP_DIR="/home/ubuntu/backup/migration"
LOG="/home/ubuntu/project/migration/migration.log"
EXPECTED_MEMO_COUNT=1400  # 마이그레이션 전 확인된 약 1405건 (기준값)

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 이 스크립트는 sudo로 실행해야 합니다."
    exit 1
fi

echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [03] MariaDB 복원 시작 — $(date)"     | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. 덤프 파일 자동 탐색 (최신 파일 선택) ---
DUMP_FILE=$(ls -1t "$BACKUP_DIR"/mysql_full_before_migration_*.sql.gz 2>/dev/null | head -1)
if [ -z "$DUMP_FILE" ]; then
    echo "[ERROR] 덤프 파일을 찾을 수 없습니다: $BACKUP_DIR" | tee -a "$LOG"
    echo "  01_mysql_full_dump.sh 를 먼저 실행하세요." | tee -a "$LOG"
    exit 1
fi
echo "[03] 복원할 덤프 파일: $DUMP_FILE" | tee -a "$LOG"

# --- 2. MD5 무결성 검증 ---
if [ -f "${DUMP_FILE}.md5" ]; then
    echo "[03] MD5 체크섬 검증 중..." | tee -a "$LOG"
    if md5sum -c "${DUMP_FILE}.md5" --quiet; then
        echo "[03] MD5 검증 통과" | tee -a "$LOG"
    else
        echo "[ERROR] MD5 불일치! 파일이 손상되었습니다." | tee -a "$LOG"
        exit 1
    fi
else
    echo "[WARN] MD5 파일 없음 — 검증 건너뜀" | tee -a "$LOG"
fi

# --- 3. MariaDB에 복원 ---
echo "[03] project_db 복원 중..." | tee -a "$LOG"

# 기존 DB 초기화 후 복원
mariadb -u root <<SQL
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'%';
FLUSH PRIVILEGES;
SQL

zcat "$DUMP_FILE" | mariadb -u root 2>&1 | tee -a "$LOG"
echo "[03] 복원 완료" | tee -a "$LOG"

# --- 4. 데이터 검증 ---
echo "[03] 데이터 검증 중..." | tee -a "$LOG"

TABLE_COUNT=$(MYSQL_PWD="$DB_PASS" mariadb -u "$DB_USER" "$DB_NAME" \
    -se "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='$DB_NAME';" 2>/dev/null)
MEMO_COUNT=$(MYSQL_PWD="$DB_PASS" mariadb -u "$DB_USER" "$DB_NAME" \
    -se "SELECT COUNT(*) FROM memo;" 2>/dev/null || echo "0")

echo "[03] 테이블 수: $TABLE_COUNT" | tee -a "$LOG"
echo "[03] memo 레코드 수: $MEMO_COUNT (기대값: ~$EXPECTED_MEMO_COUNT)" | tee -a "$LOG"

if [ "$MEMO_COUNT" -ge "$EXPECTED_MEMO_COUNT" ]; then
    echo "[03] ✓ 데이터 검증 통과" | tee -a "$LOG"
else
    echo "[WARN] memo 레코드 수가 기대치보다 적습니다. 데이터를 직접 확인하세요." | tee -a "$LOG"
fi

# --- 5. Gunicorn 재시작 ---
echo "[03] Gunicorn 재시작 중..." | tee -a "$LOG"
systemctl restart gunicorn 2>/dev/null || true
sleep 3

# --- 6. HTTP 응답 확인 ---
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:5000/ 2>/dev/null || echo "0")
echo "[03] Flask 앱 HTTP 응답 코드: $HTTP_CODE" | tee -a "$LOG"
if [[ "$HTTP_CODE" =~ ^(200|301|302)$ ]]; then
    echo "[03] ✓ Flask 앱 정상 응답" | tee -a "$LOG"
else
    echo "[WARN] Flask 앱 응답 이상 (code: $HTTP_CODE) — 로그 확인: journalctl -u gunicorn -n 30" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [03] 복원 완료 — $(date)"             | tee -a "$LOG"
echo " ★ 다음 단계: sudo bash 05_mariabackup_full.sh" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
