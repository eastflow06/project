"""
플로우차트 데모 데이터 추가 스크립트

실행 방법:
    python add_demo_data.py

주의: 프로젝트 루트 디렉토리(/home/ubuntu/project/)에서 실행하세요
"""

import sqlite3
import json
import os

# DB 경로 설정
DB_PATH = os.path.join('db', 'flowcharts.db')

# db 폴더가 없으면 생성
if not os.path.exists('db'):
    os.makedirs('db')
    print("✅ db 폴더를 생성했습니다.")

# 데이터베이스 연결
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 테이블 생성 (혹시 없을 경우 대비)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS flowcharts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        data TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 데모 플로우차트 데이터
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
        {
            "data": {
                "id": "node2",
                "label": "원료의약품 연구",
                "bgColor": "#FFFFFF",
                "textColor": "#000000",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "원료 안정성 및 제형 연구"
            },
            "position": {"x": 200, "y": 250}
        },
        {
            "data": {
                "id": "node3",
                "label": "과초산원료",
                "bgColor": "#FFFFFF",
                "textColor": "#000000",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "1.3ton 규모"
            },
            "position": {"x": 200, "y": 400}
        },
        {
            "data": {
                "id": "node4",
                "label": "동명오엠씨 안정성시험",
                "bgColor": "#4CAF50",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "진행 완료"
            },
            "position": {"x": 100, "y": 550}
        },
        {
            "data": {
                "id": "node5",
                "label": "자사합성 안정성시험",
                "bgColor": "#4CAF50",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "진행 완료"
            },
            "position": {"x": 300, "y": 550}
        },
        {
            "data": {
                "id": "node6",
                "label": "효력시험",
                "bgColor": "#FFFFFF",
                "textColor": "#000000",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "효력 검증 단계"
            },
            "position": {"x": 450, "y": 250}
        },
        {
            "data": {
                "id": "node7",
                "label": "스케일업",
                "bgColor": "#FFFFFF",
                "textColor": "#000000",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "생산 규모 확대"
            },
            "position": {"x": 600, "y": 250}
        },
        {
            "data": {
                "id": "node8",
                "label": "시판승인",
                "bgColor": "#FFFFFF",
                "textColor": "#000000",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "MFDS 승인 신청"
            },
            "position": {"x": 750, "y": 250}
        },
        {
            "data": {
                "id": "node9",
                "label": "품목허가신청",
                "bgColor": "#FF9800",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "9월 28일 신청 예정"
            },
            "position": {"x": 900, "y": 250}
        },
        {
            "data": {
                "id": "node10",
                "label": "제조업허가신청",
                "bgColor": "#FF9800",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "roundrectangle",
                "memo": "9월 8일 최종검토"
            },
            "position": {"x": 900, "y": 400}
        },
        {
            "data": {
                "id": "node11",
                "label": "스트립 개발",
                "bgColor": "#F44336",
                "textColor": "#FFFFFF",
                "borderStyle": "solid",
                "shape": "ellipse",
                "memo": "추가 개발 필요"
            },
            "position": {"x": 1050, "y": 100}
        }
    ],
    "edges": [
        {"data": {"id": "edge1", "source": "node1", "target": "node2", "lineStyle": "solid"}},
        {"data": {"id": "edge2", "source": "node2", "target": "node3", "lineStyle": "solid"}},
        {"data": {"id": "edge3", "source": "node3", "target": "node4", "lineStyle": "solid"}},
        {"data": {"id": "edge4", "source": "node3", "target": "node5", "lineStyle": "solid"}},
        {"data": {"id": "edge5", "source": "node2", "target": "node6", "lineStyle": "solid"}},
        {"data": {"id": "edge6", "source": "node6", "target": "node7", "lineStyle": "solid"}},
        {"data": {"id": "edge7", "source": "node7", "target": "node8", "lineStyle": "solid"}},
        {"data": {"id": "edge8", "source": "node8", "target": "node9", "lineStyle": "solid"}},
        {"data": {"id": "edge9", "source": "node8", "target": "node10", "lineStyle": "solid"}},
        {"data": {"id": "edge10", "source": "node9", "target": "node11", "lineStyle": "dotted"}}
    ]
}

# 데모 데이터 삽입
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

print("=" * 60)
print("✅ 데모 데이터가 추가되었습니다!")
print("=" * 60)
print(f"DB 경로: {os.path.abspath(DB_PATH)}")
print()
print("다음 단계:")
print("1. python app.py 실행")
print("2. 브라우저에서 http://localhost:5000/flowchart/ 접속")
print("=" * 60)
