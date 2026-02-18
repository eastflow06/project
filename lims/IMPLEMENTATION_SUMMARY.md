# LIMS 모듈 재설계 완료

## 변경 사항 요약

### 1. 아키텍처 변경
- **기존**: Google Sheets를 직접 DB처럼 사용 (JSON 설정 파일 기반)
- **신규**: SQLAlchemy 기반 DB 모델 + Google Sheets 데이터 연동

### 2. 생성/수정된 파일

#### 핵심 파일
- `lims/models.py` - TestResult 모델 (새로 생성)
- `lims/utils.py` - Google Sheets 연동 유틸리티 (새로 생성)
- `lims/routes.py` - 완전히 재설계 (기존 825줄 → 새로운 구조)
- `lims/__init__.py` - models import 추가

#### 템플릿 파일
- `lims/templates/lims/dashboard.html` - 시험 목록 페이지 (재작성)
- `lims/templates/lims/edit.html` - 시험 설정 편집 페이지 (새로 생성)
- `lims/templates/lims/view.html` - 시험 결과 조회 페이지 (새로 생성)

#### 문서 및 스크립트
- `lims/README.md` - 상세 사용 설명서
- `init_lims_db.py` - DB 초기화 스크립트

### 3. 주요 기능

#### DB 모델 (TestResult)
```python
- id: 자동 증가 Primary Key
- test_title: 시험 제목 (필수)
- product_name: 제품명 (선택)
- gsheet_url: Google Sheets URL (필수)
- sheet_name: 워크시트 이름
- cell_range: 셀 범위 (예: A1:D100)
- main_title: 그래프 메인 제목
- sub_title: 그래프 서브 제목
- chart_settings: JSON 형식의 차트 설정
  - x_axis: 제목, 최솟값, 최댓값, 눈금 간격, 그리드 표시
  - y_axis: 제목, 최솟값, 최댓값, 눈금 간격, 그리드 표시
  - spec_line: 표시 여부, 기준값, 색상, 라벨
```

#### API 엔드포인트
```
페이지:
  GET  /lims/                    - 대시보드
  GET  /lims/edit/<test_id>      - 편집 (0=신규)
  GET  /lims/view/<test_id>      - 조회

CRUD:
  GET    /lims/api/tests          - 목록
  GET    /lims/api/tests/<id>     - 조회
  POST   /lims/api/tests          - 생성
  PUT    /lims/api/tests/<id>     - 수정
  DELETE /lims/api/tests/<id>     - 삭제

Google Sheets:
  GET  /lims/api/gsheet/data/<id>     - 데이터 조회
  POST /lims/api/gsheet/worksheets    - 워크시트 목록
```

#### UI 특징
- **다크 모드**: Tailwind CSS 기반 (#0f172a 배경)
- **반응형**: 모바일/태블릿/데스크톱 대응
- **섹션 구분**:
  - 기본 정보 (시험 제목, 제품명)
  - Google Sheets 연동 (URL, 시트, 범위)
  - 그래프 제목 설정
  - X축/Y축 설정 (2열 그리드)
  - 기준선 설정

### 4. 설치 및 실행

#### 필수 패키지
```bash
pip install gspread google-auth pandas
```

#### Google Service Account 설정
1. Google Cloud Console에서 Service Account 생성
2. Google Sheets API, Drive API 활성화
3. JSON 키 파일을 `/home/ubuntu/project/instance/google_key.json`에 저장
4. Service Account 이메일을 Google Sheets에 편집자 권한으로 공유

#### DB 초기화 (완료됨)
```bash
source venv/bin/activate
python init_lims_db.py
```

**결과**:
```
✅ LIMS 데이터베이스 테이블이 생성되었습니다.
✅ test_results 테이블이 확인되었습니다.
```

### 5. 사용 흐름

1. **시험 등록**
   - `/lims/` 접속 → "새 시험 등록" 클릭
   - Google Sheets URL 입력 → "워크시트 불러오기"
   - 시트 선택, 셀 범위 지정
   - 그래프 설정 (축, 기준선)
   - 저장

2. **시험 조회**
   - 대시보드에서 시험 선택 → "조회" 버튼
   - Chart.js 그래프 + 원본 데이터 테이블 표시
   - "데이터 새로고침"으로 최신 데이터 로드

3. **시험 수정/삭제**
   - "편집" 버튼으로 설정 변경
   - "삭제" 버튼으로 시험 제거

### 6. 기존 코드와의 차이점

| 항목 | 기존 | 신규 |
|------|------|------|
| 데이터 저장 | JSON 파일 (lims_config.json) | SQLite DB (test_results 테이블) |
| 시험 관리 | 수동 JSON 편집 | 웹 UI로 CRUD |
| Google Sheets | 직접 DB처럼 사용 | 데이터 소스로만 사용 |
| 차트 설정 | 하드코딩 | DB에 저장, 동적 적용 |
| UI | 기본 HTML | Tailwind CSS 다크 모드 |

### 7. 다음 단계

1. **Google API 키 설정 확인**
   ```bash
   ls -la /home/ubuntu/project/instance/google_key.json
   ```

2. **Flask 앱 재시작**
   ```bash
   # 개발 서버
   source venv/bin/activate
   flask run
   
   # 또는 프로덕션 서버 재시작
   sudo systemctl restart your-flask-app
   ```

3. **접속 테스트**
   - http://your-server/lims

### 8. 주의사항

- `google_key.json` 파일은 `.gitignore`에 추가 필요
- Google Sheets의 첫 번째 행은 헤더로 사용됨
- 셀 범위는 `A1:D100` 형식으로 입력
- Service Account 이메일에 Google Sheets 공유 권한 필수

### 9. 문제 해결

**"Google API 키 파일을 찾을 수 없습니다"**
→ `/home/ubuntu/project/instance/google_key.json` 경로 확인

**"워크시트를 찾을 수 없습니다"**
→ Service Account 이메일에 공유 권한 부여 확인

**"no such table: test_results"**
→ `python init_lims_db.py` 재실행

## 완료!

LIMS 모듈이 성공적으로 재설계되었습니다. 
모든 파일이 생성되었고 DB도 초기화되었습니다.
Google API 키만 설정하면 바로 사용 가능합니다.
