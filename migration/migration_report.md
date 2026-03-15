# MySQL → MariaDB 마이그레이션 보고서

**일시**: 2026-03-05  
**대상**: `project_db` (Ubuntu 24.04, Flask/Gunicorn 환경)  
**결과**: ✅ 성공 완료

---

## 1. 마이그레이션 개요

| 항목 | 이전 | 이후 |
|------|------|------|
| DB 엔진 | MySQL 8.0.45 | MariaDB 12.2.2 |
| 백업 방식 | mysqldump 전체 덤프 (매일) | Mariabackup 증분 백업 (매일) + 전체 (매월) |
| 백업 속도 | DB 전체 크기에 비례 | 변경분만 → 수 초~분 |
| 코드 변경 | — | 없음 (mysql+pymysql 드라이버 동일) |
| 복원 레코드 | memo 1,405건 (마이그레이션 전 기준) | **1,545건** (동일 데이터 + 중간 추가분) |

---

## 2. 마이그레이션 단계별 이력

### Phase 1 — 사전 준비
- `00_preflight_check.sh` 실행 → **PASS 9 / FAIL 0** 전 항목 통과
- MySQL, rclone, GDrive 연결, 디스크 여유(32GB) 모두 정상

### Phase 2 — MySQL 전체 덤프 (01번 스크립트)
- `mysqldump --all-databases` 실행 → **⚠️ 덤프 파일 4KB (사실상 빈 파일)** [→ 이슈 #1]
- GDrive 업로드 완료 (`gdrive:redapril/backup/migration/`)

### Phase 3 — MariaDB 설치 (02번 스크립트)
- Gunicorn, MySQL 순서대로 중지
- MariaDB 공식 저장소 추가, 패키지 35개 설치 (36MB)
- 기존 `/var/lib/mysql` → `/var/lib/mysql-8.0`으로 자동 이동 (정상 동작)
- `project_db` + `projectuser` 재생성 완료

### Phase 4 — 데이터 복원 (03번 스크립트)
- 01번 덤프 파일(4KB)로 복원 시도 → **데이터 0건** [→ 이슈 #1 재발]
- 별도 방법으로 MySQL 8 데이터 추출 필요

### Phase 5 — MySQL 8 임시 재기동 및 실제 덤프
- **⚠️ MySQL 서비스 재설치 후 기동 실패** [→ 이슈 #2]
- MySQL 8 기동 후 실제 덤프 추출 (378KB, INSERT 16개 이상) 성공
- MariaDB로 전환 후 `zcat dump | mariadb project_db` 복원 → **1,545건 확인**

### Phase 6 — Flask 앱 재起動
- Gunicorn 재시작 후 HTTP 응답 확인
- **⚠️ 포트 5000으로 확인 시 0 응답** → 포트 8000으로 재확인 후 **200 OK** [→ 이슈 #3 단순 착오]

### Phase 7 — 전체 물리 백업 (05번 스크립트)
- `mariabackup --backup` 실행 → `project_db` 17개 `.ibd` 파일 포함 **completed OK**
- **⚠️ prepare 단계 실패** (`--apply-log-only` 옵션 지원 안 됨) [→ 이슈 #4]
- **⚠️ `mariabackup` 명령 미발견** (이름 변경됨) [→ 이슈 #5]
- **⚠️ RELOAD, PROCESS 권한 오류** [→ 이슈 #6]

---

## 3. 트러블슈팅 상세

### 이슈 #1 — 최초 덤프 파일이 4KB로 비어있음

**원인**  
`mysqldump --all-databases` 명령이 정상 실행됐으나 파일 크기가 4KB(헤더만 존재).  
MySQL 8.0에서 `PROCESS` 권한 없이 `--all-databases` 실행 시 시스템 DB를 건너뛰고, `project_db`도 내용 없이 종료되는 현상. `projectuser`가 `project_db.*`만 접근 가능하여  `--all-databases` 옵션이 실질적으로 빈 덤프를 생성함.

**해결**  
MariaDB 설치 과정에서 `/var/lib/mysql-8.0`으로 이동된 MySQL 8 물리 데이터 디렉토리가 존재함을 확인.  
MySQL 8을 임시로 재기동하여 `mysqldump -u projectuser project_db`(특정 DB 지정)로 **378KB** 덤프 추출 성공.

**예방책**  
`01_mysql_full_dump.sh`를 `--all-databases` 대신 `-u projectuser project_db` 단일 DB 덤프로 개선 필요.

---

### 이슈 #2 — MySQL 8 임시 재기동 실패 (`feedback=OFF` 오류)

**원인**  
MariaDB 설치 시 `/etc/mysql/mariadb.conf.d/feedback.cnf`가 자동 생성되며 내용:
```
[server]
feedback=OFF
```
MySQL 8은 `feedback` 변수를 지원하지 않아 기동 즉시 오류 발생:
```
[ERROR] unknown variable 'feedback=OFF'
```

**해결**  
```bash
mv /etc/mysql/mariadb.conf.d/feedback.cnf /tmp/feedback.cnf.bak
systemctl restart mysql   # MySQL 8 정상 기동
# ... 덤프 완료 후
mv /tmp/feedback.cnf.bak /etc/mysql/mariadb.conf.d/feedback.cnf
```

**팁**  
MySQL과 MariaDB가 동일 서버에서 공존할 경우 `/etc/mysql/` 설정 파일 충돌에 주의.

---

### 이슈 #3 — Flask 앱 HTTP 응답 포트 5000 → 8000

**원인 및 해결**  
확인 명령에서 포트 5000을 사용했으나 실제 Gunicorn은 **8000번 포트**로 바인딩 중.  
`curl http://localhost:8000/` → **200 OK** 정상 확인.

---

### 이슈 #4 — `--apply-log-only` 옵션 지원 안 됨

**원인**  
MariaDB 12.x에서 WAL(Write-Ahead Log) 아키텍처 변경으로 `--apply-log-only` 옵션 폐기.  
기존 문서(MariaDB 10.x 기준)에는 증분 백업 적용 시 `--apply-log-only` 사용이 권고됐으나 12.x에서는 단순 `--prepare`로 통합됨.

**해결**  
05/06/07번 스크립트에서 `--apply-log-only` 제거:
```bash
# 변경 전
mariadb-backup --prepare --apply-log-only --target-dir=...
# 변경 후
mariadb-backup --prepare --target-dir=...
```

---

### 이슈 #5 — `mariabackup` 명령 미발견

**원인**  
MariaDB 12.x에서 바이너리 이름이 변경됨:
- 기존: `mariabackup`
- 신규: `mariadb-backup`

**해결**  
05/06/07번 스크립트 전체에서 `mariabackup` → `mariadb-backup` 교체.  
실행 시에도 deprecated 경고 메시지 출력됨:
```
mariabackup: Deprecated program name. Use '/usr/bin/mariadb-backup' instead
```

---

### 이슈 #6 — Mariabackup 실행 시 RELOAD, PROCESS 권한 오류

**원인**  
`mariadb-backup`은 물리 백업을 위해 DB 전역 권한이 필요:
- `RELOAD` — 로그 플러시
- `PROCESS` — 프로세스 목록 조회

`projectuser`는 `project_db.*`에 대한 ALL 권한만 보유, 전역 권한 미부여.

**해결**  
```sql
GRANT RELOAD, PROCESS, LOCK TABLES ON *.* TO 'projectuser'@'localhost';
GRANT RELOAD, PROCESS, LOCK TABLES ON *.* TO 'projectuser'@'%';
FLUSH PRIVILEGES;
```

---

## 4. 현재 운영 환경

### 서비스 상태
```
● mariadb.service   — active (running)   MariaDB 12.2.2
● gunicorn.service  — active (running)   Flask 앱 포트 8000
```

### 백업 스케줄 (crontab)
```
0 3 * * *       backup_to_gdrive.sh   → 증분 백업 + GDrive 업로드 (매일)
0 1 1 * *       05_mariabackup_full.sh → 전체 물리 백업 갱신 (매월 1일)
```

### 데이터 보존 현황
| 경로 | 내용 |
|------|------|
| `/var/lib/mysql` | MariaDB 운영 데이터 (현재 사용 중) |
| `/var/lib/mysql-8.0-data` | MySQL 8.0 백업 데이터 (안전 확인 후 삭제 가능) |
| `/home/ubuntu/backup/db/full/` | Mariabackup 전체 물리 백업 (43MB) |
| `/home/ubuntu/backup/migration/` | 마이그레이션용 덤프 파일 보관 |

---

## 5. 스크립트 수정사항 요약

| 파일 | 수정 내용 |
|------|----------|
| `05_mariabackup_full.sh` | `mariabackup` → `mariadb-backup`, `--apply-log-only` 제거 |
| `06_mariabackup_incremental.sh` | `mariabackup` → `mariadb-backup` |
| `07_mariabackup_restore.sh` | `mariabackup` → `mariadb-backup`, `--apply-log-only` 제거 |
| `backup_db.sh` | `mysqldump` → `06_mariabackup_incremental.sh` 호출로 대체 |
| `backup_to_gdrive.sh` | GDrive sync 경로 `~/gdrive/db/` → `~/backup/db/` |

---

*보고서 작성일: 2026-03-05*
