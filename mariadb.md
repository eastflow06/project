## MariaDB 설치 및 MySQL → MariaDB 마이그레이션

### 1단계: 현재 MySQL 백업 (필수)

```bash
# 전체 덤프 백업
mysqldump -u projectuser -p'Project2026' --all-databases --single-transaction \
  > /home/ubuntu/backup_before_migration_$(date +%Y%m%d).sql

# 압축
gzip /home/ubuntu/backup_before_migration_$(date +%Y%m%d).sql

# GDrive에도 업로드
rclone copy /home/ubuntu/backup_before_migration_*.sql.gz gdrive:redapril/backup/db/
```

---

### 2단계: MySQL 서비스 중지 및 제거

```bash
# 서비스 중지
sudo systemctl stop mysql
sudo systemctl stop gunicorn

# MySQL 제거 (데이터는 보존)
sudo apt remove mysql-server mysql-client
sudo apt autoremove

# 데이터 디렉토리 확인 (삭제 금지)
ls /var/lib/mysql
```

---

### 3단계: MariaDB 설치

```bash
# 최신 MariaDB 저장소 추가 (Ubuntu 기준)
curl -LsS https://downloads.mariadb.com/MariaDB/mariadb_repo_setup | sudo bash

# 설치
sudo apt update
sudo apt install mariadb-server mariadb-client

# 서비스 시작
sudo systemctl start mariadb
sudo systemctl enable mariadb

# 버전 확인
mariadb --version
```

---

### 4단계: MariaDB 초기 보안 설정

```bash
sudo mariadb-secure-installation
# 질문 응답 가이드:
# Enter current password for root: (엔터)
# Switch to unix_socket authentication: n
# Change the root password: y → 새 비밀번호 입력
# Remove anonymous users: y
# Disallow root login remotely: y
# Remove test database: y
# Reload privilege tables: y
```

---

### 5단계: DB 및 유저 재생성

```bash
sudo mariadb -u root -p

-- DB 생성
CREATE DATABASE project_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 유저 생성 (기존과 동일하게)
CREATE USER 'projectuser'@'localhost' IDENTIFIED BY 'Project2026';
GRANT ALL PRIVILEGES ON project_db.* TO 'projectuser'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

### 6단계: 백업 데이터 복원

```bash
# 압축 해제 후 복원
zcat /home/ubuntu/backup_before_migration_$(date +%Y%m%d).sql.gz \
  | mariadb -u projectuser -p'Project2026' project_db

# 복원 확인
mariadb -u projectuser -p'Project2026' project_db -e "SHOW TABLES;"
```

---

### 7단계: Flask 앱 설정 확인

```python
# config.py 또는 .env — 변경 불필요 (드라이버 호환)
# mysql+pymysql 그대로 사용 가능
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://projectuser:Project2026@localhost/project_db"

# 단, mysqlclient 사용 중이라면 mariadb 드라이버로 교체 권장
# pip install mariadb
# SQLALCHEMY_DATABASE_URI = "mariadb+mariadbconnector://projectuser:Project2026@localhost/project_db"
```

---

### 8단계: 서비스 재시작 및 검증

```bash
# Gunicorn 재시작
sudo systemctl restart gunicorn

# 로그 확인
sudo journalctl -u gunicorn -f

# MariaDB 상태 확인
sudo systemctl status mariadb
```

---

### 9단계: Mariabackup 설정 (증분 백업)

```bash
# 설치
sudo apt install mariadb-backup

# 전체 백업 (최초 1회)
sudo mariabackup --backup \
  --target-dir=/home/ubuntu/backup/db/full \
  --user=projectuser --password='Project2026'

# 증분 백업 스크립트 (cron 등록)
mariabackup --backup \
  --target-dir=/home/ubuntu/backup/db/inc_$(date +%Y%m%d_%H%M) \
  --incremental-basedir=/home/ubuntu/backup/db/full \
  --user=projectuser --password='Project2026'
```

---

### 주의사항 요약

| 항목 | 내용 |
|------|------|
| 코드 변경 | pymysql 사용 시 **변경 없음** |
| 포트 | 3306 동일 |
| 데이터 타입 | 완전 호환 |
| 리스크 구간 | 2단계~6단계 (MySQL 제거 후 복원 전) |
| 롤백 방법 | 1단계 백업으로 MySQL 재설치 후 복원 |

**1단계 백업만 잘 해두면 언제든 롤백 가능**하니 부담 없이 진행할 수 있습니다.