#!/usr/bin/env bash
# =============================================================
# 02_install_mariadb.sh  (sudo 필요)
# MySQL 서비스 중지 → MySQL 제거 → MariaDB 설치
# → project_db / projectuser 재생성
#
# ★ 반드시 01_mysql_full_dump.sh 완료 후 실행하세요!
# =============================================================
set -Eeuo pipefail

DB_NAME="project_db"
DB_USER="projectuser"
DB_PASS="ProjectDB2026!"
LOG="/home/ubuntu/project/migration/migration.log"

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 이 스크립트는 sudo로 실행해야 합니다."
    echo "  sudo bash $(basename $0)"
    exit 1
fi

echo "" >> "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [02] MariaDB 설치 시작 — $(date)"     | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# --- 1. Gunicorn 중지 ---
echo "[02] Gunicorn 중지..." | tee -a "$LOG"
systemctl stop gunicorn 2>/dev/null || true

# --- 2. MySQL 중지 ---
echo "[02] MySQL 서비스 중지..." | tee -a "$LOG"
systemctl stop mysql 2>/dev/null || true

# --- 3. MySQL 제거 (데이터 보존) ---
echo "[02] MySQL 패키지 제거 중... (데이터 디렉토리는 유지)" | tee -a "$LOG"
DEBIAN_FRONTEND=noninteractive apt-get remove -y mysql-server mysql-client mysql-common 2>&1 | tee -a "$LOG"
apt-get autoremove -y 2>&1 | tee -a "$LOG"
# 데이터 디렉토리 보존 확인
echo "[02] /var/lib/mysql 존재 여부: $(ls /var/lib/mysql 2>/dev/null | wc -l) 개 파일" | tee -a "$LOG"

# --- 4. MariaDB 공식 저장소 추가 ---
echo "[02] MariaDB 공식 저장소 추가..." | tee -a "$LOG"
curl -LsS https://downloads.mariadb.com/MariaDB/mariadb_repo_setup | bash 2>&1 | tee -a "$LOG"

# --- 5. MariaDB 설치 ---
echo "[02] MariaDB 패키지 설치..." | tee -a "$LOG"
apt-get update -q 2>&1 | tee -a "$LOG"
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    mariadb-server \
    mariadb-client \
    mariadb-backup 2>&1 | tee -a "$LOG"

# --- 6. MariaDB 서비스 시작 ---
echo "[02] MariaDB 서비스 시작..." | tee -a "$LOG"
systemctl start mariadb
systemctl enable mariadb

VER=$(mariadb --version 2>/dev/null | head -1)
echo "[02] MariaDB 버전: $VER" | tee -a "$LOG"

# --- 7. DB 및 유저 재생성 ---
echo "[02] DB/유저 생성 중..." | tee -a "$LOG"
mariadb -u root <<SQL
-- 기존 DB 있으면 제거 후 재생성
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 유저 재생성
DROP USER IF EXISTS '${DB_USER}'@'localhost';
CREATE USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';

-- 외부 AI 서버 접속 허용 (기존 원격 접속 유지)
DROP USER IF EXISTS '${DB_USER}'@'%';
CREATE USER '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'%';

FLUSH PRIVILEGES;
SHOW DATABASES;
SQL

echo "" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
echo " [02] MariaDB 설치 완료 — $(date)"     | tee -a "$LOG"
echo " ★ 다음 단계: sudo bash 03_restore_to_mariadb.sh" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"
