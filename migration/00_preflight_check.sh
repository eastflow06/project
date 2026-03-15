#!/usr/bin/env bash
# =============================================================
# 00_preflight_check.sh
# MariaDB 마이그레이션 전 환경 사전 점검 스크립트
# =============================================================
set -uo pipefail

MYSQL_USER="projectuser"
MYSQL_PASS="ProjectDB2026!"
MYSQL_DB="project_db"
REQUIRED_DISK_GB=2
LOG="/home/ubuntu/project/migration/preflight.log"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0

log() { echo -e "$1" | tee -a "$LOG"; }
ok()   { log "${GREEN}[PASS]${NC} $1"; PASS=$((PASS+1)); }
fail() { log "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); }
warn() { log "${YELLOW}[WARN]${NC} $1"; }

echo "" > "$LOG"
log "============================================="
log " MariaDB 마이그레이션 사전 점검 — $(date)"
log "============================================="

# 1. MySQL 서비스 상태
log "\n[1] MySQL 서비스 상태 확인"
if systemctl is-active --quiet mysql; then
    ok "MySQL 서비스 실행 중"
else
    fail "MySQL 서비스가 실행 중이 아닙니다. sudo systemctl start mysql"
fi

# 2. MySQL 연결 확인
log "\n[2] MySQL 연결 확인"
if MYSQL_PWD="$MYSQL_PASS" mysql -u "$MYSQL_USER" "$MYSQL_DB" -e "SELECT 1;" &>/dev/null; then
    ok "MySQL 접속 성공 (user: $MYSQL_USER, db: $MYSQL_DB)"
else
    fail "MySQL 접속 실패 — 사용자/비밀번호/DB명 확인 필요"
fi

# 3. DB 버전
log "\n[3] MySQL 버전 확인"
VER=$(MYSQL_PWD="$MYSQL_PASS" mysql -u "$MYSQL_USER" "$MYSQL_DB" -se "SELECT VERSION();" 2>/dev/null || echo "unknown")
ok "MySQL 버전: $VER"

# 4. 테이블 수 및 총 데이터 크기
log "\n[4] DB 크기 확인"
SIZE_MB=$(MYSQL_PWD="$MYSQL_PASS" mysql -u "$MYSQL_USER" -e \
    "SELECT ROUND(SUM(DATA_LENGTH+INDEX_LENGTH)/1024/1024,2) FROM information_schema.TABLES WHERE TABLE_SCHEMA='$MYSQL_DB';" \
    -se 2>/dev/null || echo "0")
ok "project_db 크기: ${SIZE_MB} MB"

# 5. 디스크 여유 공간
log "\n[5] 디스크 여유 공간 확인 (최소 ${REQUIRED_DISK_GB}GB 필요)"
AVAIL_GB=$(df -BG /home/ubuntu | awk 'NR==2{gsub("G","",$4); print $4}')
if [ "$AVAIL_GB" -ge "$REQUIRED_DISK_GB" ]; then
    ok "디스크 여유: ${AVAIL_GB}GB"
else
    fail "디스크 여유 공간 부족: ${AVAIL_GB}GB (최소 ${REQUIRED_DISK_GB}GB 필요)"
fi

# 6. rclone 설치 및 gdrive 설정 확인
log "\n[6] rclone + GDrive 설정 확인"
if command -v rclone &>/dev/null; then
    ok "rclone 설치됨: $(rclone --version | head -1)"
    if rclone lsd gdrive: &>/dev/null; then
        ok "GDrive (gdrive:) 연결 정상"
    else
        warn "GDrive 연결 실패 — rclone config로 재설정 필요할 수 있음"
    fi
else
    fail "rclone 미설치"
fi

# 7. gunicorn 상태
log "\n[7] Gunicorn 서비스 상태"
if systemctl is-active --quiet gunicorn; then
    ok "Gunicorn 실행 중 (마이그레이션 중 일시 중단 예정)"
else
    warn "Gunicorn이 실행 중이 아닙니다"
fi

# 8. mariadb 패키지 충돌 여부
log "\n[8] MariaDB 관련 패키지 사전 설치 여부"
if dpkg -l | grep -q "mariadb-server"; then
    warn "mariadb-server가 이미 설치되어 있습니다 — 02번 스크립트를 건너뛸 수 있음"
else
    ok "MariaDB 미설치 — 설치 준비 완료"
fi

# 최종 결과
log "\n============================================="
log " 점검 결과: PASS=${PASS}, FAIL=${FAIL}"
log "============================================="

if [ "$FAIL" -gt 0 ]; then
    log "${RED}★ FAIL 항목을 해결한 후 마이그레이션을 진행하세요.${NC}"
    exit 1
else
    log "${GREEN}★ 모든 점검 통과! 01_mysql_full_dump.sh 를 실행하세요.${NC}"
    exit 0
fi
