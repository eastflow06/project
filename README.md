# 플로우차트 관리 시스템

기존 Flask 프로젝트에 플로우차트 기능을 추가하는 모듈입니다.

## 📁 현재 프로젝트 구조

```
/home/ubuntu/project/           # 프로젝트 루트
├── app.py                      # 메인 Flask 애플리케이션
└── db/
    └── project.db             # 기존 데이터베이스
```

## 🎯 설치 후 구조

```
/home/ubuntu/project/
├── app.py                      # 메인 Flask 앱
├── db/
│   ├── project.db             # 기존 DB
│   └── flowcharts.db          # 플로우차트 DB (자동 생성)
├── flowchart/                  # ✨ 새로 추가
│   ├── __init__.py            # Blueprint
│   └── templates/
│       ├── flowchart_list.html
│       ├── flowchart_editor.html
│       └── flowchart_view.html
└── add_demo_data.py           # 데모 데이터 스크립트 (선택)
```

## 🚀 설치 방법

### 1단계: 파일 배치

```bash
# 프로젝트 루트로 이동
cd /home/ubuntu/project

# flowchart 폴더를 프로젝트 루트에 복사
# (압축 해제하거나 직접 복사)
```

### 2단계: app.py 수정

기존 `app.py`에 다음 코드를 추가:

```python
# 파일 상단에 import 추가
from flowchart import flowchart_bp, init_db

# Flask app 생성 후
app = Flask(__name__)

# Blueprint 등록
app.register_blueprint(flowchart_bp)

# 기존 라우트들...
@app.route('/')
def index():
    ...

# 앱 시작 시 DB 초기화 추가 (if __name__ == '__main__': 위에)
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

전체 예시는 `app_example.py`를 참고하세요.

### 3단계: 서버 실행

```bash
python app.py
```

### 4단계: 접속

```
http://localhost:5000/flowchart/
```

또는 서버 IP:
```
http://your-server-ip:5000/flowchart/
```

## ✨ 주요 기능

- **인터랙티브 편집기**: 드래그로 노드 배치
- **노드 스타일**: 색상, 모양, 테두리 변경
- **연결선**: 노드 간 화살표 연결
- **메모**: 각 노드에 상세 정보 추가
- **공유**: 링크로 읽기 전용 뷰어 공유
- **내보내기**: PNG 이미지로 다운로드

## 🔗 URL 구조

- `/flowchart/` - 플로우차트 목록
- `/flowchart/create` - 새로 만들기
- `/flowchart/edit/<id>` - 수정
- `/flowchart/view/<id>` - 보기 (공유용)

## 💾 데이터베이스

- **위치**: `/home/ubuntu/project/db/flowcharts.db`
- **자동 생성**: 첫 실행 시 자동 생성
- **기존 DB와 분리**: project.db와 독립적

## 🎨 사용 예시

### 의약품 개발 프로젝트
- 연구 → 시험 → 허가 신청 과정 시각화
- 진행 상황을 색상으로 구분
- 각 단계별 메모 추가

### 노드 색상 의미 (권장)
- 🔵 파란색: 시작/기획
- 🟢 초록색: 완료
- 🟠 주황색: 진행 중
- 🔴 빨간색: 지연/문제
- ⚪ 흰색: 예정

## 📝 데모 데이터 추가 (선택)

```bash
python add_demo_data.py
```

페라스텔릴티상액 프로젝트 예시가 추가됩니다.

## 🛠️ 고급 설정

### URL 경로 변경

`flowchart/__init__.py` 수정:

```python
flowchart_bp = Blueprint('flowchart', __name__, 
                        url_prefix='/my-custom-path')
```

### 기존 템플릿 스타일 적용

`flowchart/templates/flowchart_list.html`:

```html
{% extends "base.html" %}
{% block content %}
    <!-- 내용 -->
{% endblock %}
```

### 인증 추가 (Flask-Login)

`flowchart/__init__.py`:

```python
from flask_login import login_required

@flowchart_bp.route('/')
@login_required
def index():
    ...
```

### 기존 project.db 사용

`flowchart/__init__.py`에서 DB 경로 변경:

```python
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'project.db')
```

## 🌐 프로덕션 배포

### systemd 서비스

`/etc/systemd/system/project.service`:

```ini
[Unit]
Description=Flask Project
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/project
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start project
sudo systemctl enable project
```

### Nginx 설정

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
    }

    location /flowchart/ {
        proxy_pass http://127.0.0.1:5000/flowchart/;
    }
}
```

## 🐛 문제 해결

### Import 에러
```bash
# flowchart 폴더 위치 확인
ls -la /home/ubuntu/project/flowchart/
```

### 템플릿 에러
```bash
# templates 폴더 확인
ls -la /home/ubuntu/project/flowchart/templates/
```

### DB 권한 에러
```bash
chmod 755 /home/ubuntu/project/db
chmod 644 /home/ubuntu/project/db/flowcharts.db
```

## 📚 문서

- `SETUP_GUIDE.md` - 상세한 설치 가이드
- `app_example.py` - 전체 app.py 예시

## 💡 팁

### 네비게이션 메뉴 추가

기존 템플릿에:

```html
<nav>
    <a href="/">홈</a>
    <a href="/flowchart/">플로우차트</a>
</nav>
```

### 백업

```bash
# 정기 백업
cp db/flowcharts.db db/flowcharts_backup_$(date +%Y%m%d).db
```

### 키보드 단축키

- 마우스 휠: 줌 인/아웃
- 드래그: 캔버스 이동
- Ctrl + 클릭: 여러 노드 선택

## 📦 의존성

- Flask (이미 설치되어 있음)
- SQLite3 (Python 내장)
- Cytoscape.js (CDN)

추가 패키지 설치 불필요!

## ✅ 설치 체크리스트

- [ ] flowchart 폴더를 /home/ubuntu/project/에 복사
- [ ] app.py에 Blueprint 코드 추가
- [ ] 서버 실행: python app.py
- [ ] 브라우저에서 /flowchart/ 접속 테스트
- [ ] (선택) 데모 데이터 추가
- [ ] (선택) 메뉴에 링크 추가

---

**Made for /home/ubuntu/project/** ❤️
