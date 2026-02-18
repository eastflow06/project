# 플로우차트 시스템 - 기존 프로젝트 통합 가이드

## 📁 현재 프로젝트 구조

```
/home/ubuntu/project/           # 프로젝트 루트
├── app.py                      # 메인 Flask 애플리케이션
├── db/
│   └── project.db             # 기존 데이터베이스
└── (기타 파일들...)
```

## 🎯 통합 후 구조

```
/home/ubuntu/project/
├── app.py                      # 메인 Flask 앱
├── db/
│   ├── project.db             # 기존 DB
│   └── flowcharts.db          # 플로우차트 DB (자동 생성)
└── flowchart/                  # ✨ 새로 추가
    ├── __init__.py            # Blueprint 정의
    └── templates/             # 플로우차트 전용 템플릿
        ├── flowchart_list.html
        ├── flowchart_editor.html
        └── flowchart_view.html
```

## 🚀 통합 단계

### 1단계: flowchart 폴더 배치

```bash
cd /home/ubuntu/project
# flowchart 폴더를 프로젝트 루트에 복사
```

### 2단계: app.py 수정

기존 `app.py`에 다음 코드를 추가하세요:

```python
# 파일 상단에 import 추가
from flowchart import flowchart_bp, init_db

# Flask app 생성 후 Blueprint 등록
app = Flask(__name__)

# 플로우차트 Blueprint 등록
app.register_blueprint(flowchart_bp)

# 앱 시작 시 DB 초기화 (if __name__ == '__main__': 위에)
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### 3단계: 완료!

서버를 실행하고 접속하세요:

```bash
python app.py
# 또는
python3 app.py
```

브라우저에서:
```
http://your-server:5000/flowchart/
```

## 📋 전체 app.py 예시

```python
from flask import Flask, render_template
from flowchart import flowchart_bp, init_db

app = Flask(__name__)

# 플로우차트 Blueprint 등록
app.register_blueprint(flowchart_bp)

# 기존 라우트들...
@app.route('/')
def index():
    return render_template('index.html')

# ... 기타 라우트들 ...

# 앱 시작 시 DB 초기화
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

## 🔗 URL 경로

통합 후 사용 가능한 URL:

- `http://your-server:5000/flowchart/` - 플로우차트 목록
- `http://your-server:5000/flowchart/create` - 새로 만들기
- `http://your-server:5000/flowchart/edit/<id>` - 수정
- `http://your-server:5000/flowchart/view/<id>` - 보기 (공유용)

## 💾 데이터베이스

- **위치**: `/home/ubuntu/project/db/flowcharts.db`
- **자동 생성**: 처음 실행 시 자동으로 생성됩니다
- **기존 DB와 분리**: `project.db`와 완전히 독립적입니다

### 기존 project.db를 사용하고 싶다면

`flowchart/__init__.py` 파일을 수정:

```python
# DB 경로를 project.db로 변경
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'project.db')

# init_db() 함수에서 테이블만 추가
def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('''
        CREATE TABLE IF NOT EXISTS flowcharts (
            ...
        )
    ''')
    db.commit()
    db.close()
```

## 🎨 기존 템플릿 스타일 적용

### base.html 상속

`flowchart/templates/flowchart_list.html`을 수정:

```html
{% extends "base.html" %}

{% block title %}플로우차트 관리{% endblock %}

{% block content %}
    <!-- 기존 플로우차트 내용 -->
{% endblock %}
```

### 네비게이션 메뉴에 추가

기존 템플릿 (예: `base.html` 또는 `navbar.html`)에 링크 추가:

```html
<nav>
    <a href="/">홈</a>
    <a href="/flowchart/">플로우차트</a>
    <!-- 기타 메뉴 -->
</nav>
```

## 🔐 인증 추가 (선택사항)

Flask-Login을 사용 중이라면:

```python
# flowchart/__init__.py에 추가
from flask_login import login_required

@flowchart_bp.route('/')
@login_required
def index():
    ...

@flowchart_bp.route('/create')
@login_required
def create():
    ...
```

## 🌐 Nginx 설정 (프로덕션 배포)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /flowchart/ {
        proxy_pass http://127.0.0.1:5000/flowchart/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔧 systemd 서비스 (자동 시작)

`/etc/systemd/system/project.service` 파일:

```ini
[Unit]
Description=Project Flask Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/project
Environment="PATH=/home/ubuntu/project/venv/bin"
ExecStart=/home/ubuntu/project/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

서비스 시작:
```bash
sudo systemctl daemon-reload
sudo systemctl start project
sudo systemctl enable project
sudo systemctl status project
```

## 📝 데모 데이터 추가 (선택사항)

프로젝트 루트에서 실행:

```python
# add_demo_data.py
import sqlite3
import json
import os

DB_PATH = 'db/flowcharts.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

demo_data = {
    "nodes": [
        {
            "data": {
                "id": "node1",
                "label": "페라스텔릴티상액",
                "bgColor": "#2196F3",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "과산화아세트산 4% 함유 의료기기 소독제"
            },
            "position": {"x": 200, "y": 100}
        },
        # ... 더 많은 노드들
    ],
    "edges": [
        {"data": {"id": "edge1", "source": "node1", "target": "node2", "lineStyle": "solid"}},
        # ... 더 많은 엣지들
    ]
}

cursor.execute('''
    INSERT INTO flowcharts (title, description, data)
    VALUES (?, ?, ?)
''', (
    '페라스텔릴티상액 개발 프로젝트',
    '의료기기 소독제 개발 및 허가 진행 상황',
    json.dumps(demo_data)
))

conn.commit()
conn.close()
print("✅ 데모 데이터가 추가되었습니다!")
```

실행:
```bash
python add_demo_data.py
```

## 🐛 문제 해결

### Import 에러: No module named 'flowchart'

```bash
# flowchart 폴더가 프로젝트 루트에 있는지 확인
ls -la /home/ubuntu/project/flowchart/

# __init__.py 파일이 있는지 확인
ls -la /home/ubuntu/project/flowchart/__init__.py
```

### 템플릿을 찾을 수 없음

```bash
# templates 폴더와 파일들이 있는지 확인
ls -la /home/ubuntu/project/flowchart/templates/
```

### DB 권한 오류

```bash
# db 폴더 권한 확인
ls -la /home/ubuntu/project/db/

# 권한 부여
chmod 755 /home/ubuntu/project/db
chmod 644 /home/ubuntu/project/db/flowcharts.db
```

### 포트가 이미 사용 중

```python
# app.py에서 다른 포트 사용
app.run(port=5001)
```

## 💡 사용 팁

### 1. 메인 페이지에서 링크 추가

```html
<!-- templates/index.html -->
<div class="menu">
    <a href="/flowchart/">📊 플로우차트 관리</a>
</div>
```

### 2. 진행 상황 색상 코드

- 🔵 파란색: 기획/시작
- 🟢 초록색: 완료
- 🟠 주황색: 진행 중
- 🔴 빨간색: 지연/문제
- ⚪ 흰색: 예정

### 3. 백업

```bash
# 정기 백업 스크립트
cp /home/ubuntu/project/db/flowcharts.db \
   /home/ubuntu/project/db/flowcharts_backup_$(date +%Y%m%d).db
```

## 📚 추가 문서

- Flask Blueprint: https://flask.palletsprojects.com/blueprints/
- Cytoscape.js: https://js.cytoscape.org/

## ✅ 체크리스트

- [ ] flowchart 폴더를 /home/ubuntu/project/에 복사
- [ ] app.py에 Blueprint 등록 코드 추가
- [ ] 서버 실행하여 /flowchart/ 접속 테스트
- [ ] 새 플로우차트 만들기 테스트
- [ ] (선택) 네비게이션 메뉴에 링크 추가
- [ ] (선택) 데모 데이터 추가
- [ ] (선택) systemd 서비스 등록

통합 완료! 🎉
