# LIMS 모듈 - 시험결과 관리 시스템

Flask Blueprint 기반의 LIMS(Laboratory Information Management System) 모듈입니다.
Google Sheets와 연동하여 시험 데이터를 관리하고 시각화합니다.

## 주요 기능

1. **시험 관리**
   - 시험 제목, 제품명, Google Sheets 연동 정보 관리
   - 그래프 제목 및 차트 설정 저장

2. **Google Sheets 연동**
   - gspread 라이브러리를 사용한 Google Sheets 데이터 읽기
   - 워크시트 목록 자동 조회
   - 셀 범위 지정 지원

3. **데이터 시각화**
   - Chart.js를 사용한 그래프 렌더링
   - X축/Y축 설정 (제목, 최솟값, 최댓값, 눈금 간격, 그리드 표시)
   - 기준선(Spec Line) 표시 기능

4. **다크 모드 UI**
   - Tailwind CSS 기반의 현대적인 다크 모드 인터페이스
   - 반응형 디자인

## 파일 구조

```
/home/ubuntu/project/lims/
├── __init__.py          # Blueprint 정의
├── models.py            # SQLAlchemy 모델 (TestResult)
├── routes.py            # API 및 페이지 라우트
├── utils.py             # Google Sheets 연동 유틸리티
├── README.md            # 이 파일
└── templates/
    └── lims/
        ├── dashboard.html   # 시험 목록 페이지
        ├── edit.html        # 시험 설정 편집 페이지
        └── view.html        # 시험 결과 조회 페이지
```

## 데이터베이스 스키마

### TestResult 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| id | Integer | Primary Key (자동 증가) |
| test_title | String(200) | 시험 제목 (필수) |
| product_name | String(200) | 제품명 (선택) |
| gsheet_url | String(500) | Google Sheets URL (필수) |
| sheet_name | String(100) | 워크시트 이름 (기본값: Sheet1) |
| cell_range | String(50) | 셀 범위 (기본값: A1:Z100) |
| main_title | String(200) | 그래프 메인 제목 |
| sub_title | String(200) | 그래프 서브 제목 |
| chart_settings | Text | 차트 설정 (JSON) |
| created_at | DateTime | 생성일시 |
| updated_at | DateTime | 수정일시 |

### chart_settings JSON 구조

```json
{
  "x_axis": {
    "title": "경과일 (일)",
    "min": 0,
    "max": 100,
    "interval": 10,
    "show_grid": true
  },
  "y_axis": {
    "title": "함량 (%)",
    "min": 0,
    "max": 100,
    "interval": 10,
    "show_grid": true
  },
  "spec_line": {
    "show": true,
    "value": 90,
    "color": "#ff0000",
    "label": "기준선"
  }
}
```

## 설치 및 설정

### 1. 필요한 패키지 설치

```bash
pip install gspread google-auth pandas
```

### 2. Google Service Account 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 및 Google Drive API 활성화
3. Service Account 생성 및 JSON 키 파일 다운로드
4. 키 파일을 `/home/ubuntu/project/instance/google_key.json`에 저장

### 3. Google Sheets 권한 설정

Service Account 이메일 주소를 Google Sheets에 편집자 권한으로 공유

### 4. 데이터베이스 초기화

메인 Flask 앱에서 다음 코드를 추가하여 DB 초기화:

```python
from lims.models import db

with app.app_context():
    db.create_all()
```

또는 Flask-Migrate 사용:

```bash
flask db init
flask db migrate -m "Add LIMS tables"
flask db upgrade
```

## API 엔드포인트

### 페이지 라우트

- `GET /lims/` - 대시보드 (시험 목록)
- `GET /lims/edit/<test_id>` - 시험 설정 편집 (0이면 신규 생성)
- `GET /lims/view/<test_id>` - 시험 결과 조회

### CRUD API

- `GET /lims/api/tests` - 시험 목록 조회
- `GET /lims/api/tests/<test_id>` - 특정 시험 조회
- `POST /lims/api/tests` - 시험 생성
- `PUT /lims/api/tests/<test_id>` - 시험 수정
- `DELETE /lims/api/tests/<test_id>` - 시험 삭제

### Google Sheets 연동 API

- `GET /lims/api/gsheet/data/<test_id>` - Google Sheets 데이터 조회
- `POST /lims/api/gsheet/worksheets` - 워크시트 목록 조회

### 유틸리티 API

- `GET /lims/api/chart-settings/default` - 기본 차트 설정 조회

## 사용 예시

### 1. 새 시험 등록

1. `/lims/` 접속
2. "새 시험 등록" 버튼 클릭
3. 시험 정보 입력:
   - 시험 제목: "페라스타AG의 안정성시험"
   - 제품명: "페라스타AG"
   - Google Sheets URL 입력
   - "워크시트 불러오기" 클릭하여 시트 선택
   - 셀 범위 지정 (예: A1:D100)
4. 그래프 설정:
   - 메인 제목, 서브 제목 입력
   - X축/Y축 설정 (제목, 범위, 간격)
   - 기준선 설정 (표시 여부, 값, 색상)
5. "저장" 클릭

### 2. 시험 결과 조회

1. 대시보드에서 시험 선택
2. "조회" 버튼 클릭
3. 그래프 및 원본 데이터 테이블 확인
4. "데이터 새로고침" 버튼으로 최신 데이터 로드

### 3. 프로그래밍 방식으로 데이터 조회

```python
from lims.utils import fetch_gsheet_data

# Google Sheets 데이터 가져오기
df = fetch_gsheet_data(
    gsheet_url='https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit',
    sheet_name='Sheet1',
    cell_range='A1:D100'
)

print(df.head())
```

## 주의사항

1. **Google API 키 파일 보안**
   - `google_key.json` 파일은 절대 Git에 커밋하지 마세요
   - `.gitignore`에 추가 권장

2. **셀 범위 형식**
   - 올바른 형식: `A1:D100`, `B2:F50`
   - 잘못된 형식: `A1-D100`, `invalid`

3. **데이터 형식**
   - Google Sheets의 첫 번째 행은 헤더로 사용됩니다
   - 숫자 데이터는 그래프에 자동으로 표시됩니다

## 문제 해결

### Google Sheets 연동 오류

**증상**: "Google API 키 파일을 찾을 수 없습니다"

**해결**:
```bash
# 키 파일 경로 확인
ls -la /home/ubuntu/project/instance/google_key.json

# 없으면 instance 폴더 생성
mkdir -p /home/ubuntu/project/instance

# 키 파일 복사
cp /path/to/your/google_key.json /home/ubuntu/project/instance/
```

### 워크시트를 찾을 수 없음

**증상**: "워크시트 'Sheet1'를 찾을 수 없습니다"

**해결**:
1. Google Sheets에서 워크시트 이름 확인
2. Service Account 이메일에 공유 권한 부여 확인
3. "워크시트 불러오기" 버튼으로 실제 워크시트 목록 확인

### 데이터베이스 오류

**증상**: "no such table: test_results"

**해결**:
```python
# Flask shell에서 실행
from app import app, db
from lims.models import TestResult

with app.app_context():
    db.create_all()
    print("Tables created successfully!")
```

## 향후 개선 사항

- [ ] 다중 그래프 지원 (한 페이지에 여러 차트)
- [ ] 데이터 필터링 기능
- [ ] Excel 파일 업로드 지원
- [ ] 시험 결과 PDF 내보내기
- [ ] 사용자별 권한 관리
- [ ] 시험 템플릿 기능

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

## 문의

문제가 발생하거나 기능 요청이 있으면 프로젝트 관리자에게 문의하세요.
