#!/usr/bin/env python3
"""
플로우차트 데모 데이터 추가 스크립트
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'flowcharts.db')

# 데모 플로우차트 데이터 - 의약품 개발 프로세스
# 새 에디터 형식: bgColor, borderColor, shadowColor, textColor, shape
demo_flowchart = {
    "title": "의약품 개발 프로세스",
    "description": "신약 개발부터 시판까지의 전체 프로세스를 보여주는 플로우차트입니다.",
    "data": {
        "nodes": [
            {
                "data": {
                    "id": "node1",
                    "label": "시작",
                    "memo": "신약 개발 프로젝트 시작",
                    "bgColor": "#4CAF50",
                    "borderColor": "#2E7D32",
                    "shadowColor": "#4CAF50",
                    "textColor": "#FFFFFF",
                    "shape": "ellipse"
                },
                "position": {"x": 150, "y": 80}
            },
            {
                "data": {
                    "id": "node2",
                    "label": "기초 연구",
                    "memo": "타겟 물질 발굴 및 기초 연구 단계\n- 질병 메커니즘 연구\n- 후보 물질 탐색",
                    "bgColor": "#2196F3",
                    "borderColor": "#1565C0",
                    "shadowColor": "#2196F3",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 150, "y": 180}
            },
            {
                "data": {
                    "id": "node3",
                    "label": "전임상 시험",
                    "memo": "동물실험을 통한 안전성/유효성 평가\n- 독성 시험\n- 약효 평가",
                    "bgColor": "#2196F3",
                    "borderColor": "#1565C0",
                    "shadowColor": "#2196F3",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 350, "y": 180}
            },
            {
                "data": {
                    "id": "node4",
                    "label": "IND 승인?",
                    "memo": "임상시험계획 승인 신청\n- 식약처 제출\n- 심사 기간: 30일",
                    "bgColor": "#FF9800",
                    "borderColor": "#E65100",
                    "shadowColor": "#FF9800",
                    "textColor": "#FFFFFF",
                    "shape": "diamond"
                },
                "position": {"x": 550, "y": 180}
            },
            {
                "data": {
                    "id": "node5",
                    "label": "임상 1상",
                    "memo": "소수 건강인 대상 안전성 평가\n- 대상: 20-80명\n- 기간: 수개월",
                    "bgColor": "#2196F3",
                    "borderColor": "#1565C0",
                    "shadowColor": "#2196F3",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 550, "y": 300}
            },
            {
                "data": {
                    "id": "node6",
                    "label": "임상 2상",
                    "memo": "환자 대상 유효성/안전성 평가\n- 대상: 100-300명\n- 용량 결정",
                    "bgColor": "#2196F3",
                    "borderColor": "#1565C0",
                    "shadowColor": "#2196F3",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 350, "y": 300}
            },
            {
                "data": {
                    "id": "node7",
                    "label": "임상 3상",
                    "memo": "대규모 환자 대상 확증 시험\n- 대상: 1000-3000명\n- 다기관 시험",
                    "bgColor": "#2196F3",
                    "borderColor": "#1565C0",
                    "shadowColor": "#2196F3",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 150, "y": 300}
            },
            {
                "data": {
                    "id": "node8",
                    "label": "NDA 승인?",
                    "memo": "신약 허가 신청\n- 전체 임상 데이터 제출\n- 심사 기간: 1년 내외",
                    "bgColor": "#FF9800",
                    "borderColor": "#E65100",
                    "shadowColor": "#FF9800",
                    "textColor": "#FFFFFF",
                    "shape": "diamond"
                },
                "position": {"x": 150, "y": 420}
            },
            {
                "data": {
                    "id": "node9",
                    "label": "제품 출시",
                    "memo": "제품 출시 및 판매\n- 시판 후 조사(PMS)\n- 이상반응 모니터링",
                    "bgColor": "#4CAF50",
                    "borderColor": "#2E7D32",
                    "shadowColor": "#4CAF50",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 350, "y": 420}
            },
            {
                "data": {
                    "id": "node10",
                    "label": "종료",
                    "memo": "프로젝트 완료",
                    "bgColor": "#E91E63",
                    "borderColor": "#AD1457",
                    "shadowColor": "#E91E63",
                    "textColor": "#FFFFFF",
                    "shape": "ellipse"
                },
                "position": {"x": 550, "y": 420}
            },
            {
                "data": {
                    "id": "node11",
                    "label": "재검토",
                    "memo": "승인 거부 시 데이터 보완 또는 프로젝트 재검토",
                    "bgColor": "#f44336",
                    "borderColor": "#c62828",
                    "shadowColor": "#f44336",
                    "textColor": "#FFFFFF",
                    "shape": "roundrectangle"
                },
                "position": {"x": 700, "y": 180}
            }
        ],
        "edges": [
            {"data": {"id": "e1", "source": "node1", "target": "node2", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e2", "source": "node2", "target": "node3", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e3", "source": "node3", "target": "node4", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e4", "source": "node4", "target": "node5", "label": "승인", "lineColor": "#4CAF50", "lineStyle": "solid"}},
            {"data": {"id": "e5", "source": "node4", "target": "node11", "label": "거부", "lineColor": "#f44336", "lineStyle": "dashed"}},
            {"data": {"id": "e6", "source": "node5", "target": "node6", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e7", "source": "node6", "target": "node7", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e8", "source": "node7", "target": "node8", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e9", "source": "node8", "target": "node9", "label": "승인", "lineColor": "#4CAF50", "lineStyle": "solid"}},
            {"data": {"id": "e10", "source": "node8", "target": "node11", "label": "거부", "lineColor": "#f44336", "lineStyle": "dashed"}},
            {"data": {"id": "e11", "source": "node9", "target": "node10", "label": "", "lineColor": "#90A4AE", "lineStyle": "solid"}},
            {"data": {"id": "e12", "source": "node11", "target": "node2", "label": "재시작", "lineColor": "#FF9800", "lineStyle": "dotted"}}
        ]
    }
}

def add_demo_data():
    # DB 폴더 확인
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # 테이블 생성 (없으면)
    db = sqlite3.connect(DB_PATH)
    db.execute('''
        CREATE TABLE IF NOT EXISTS flowcharts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 기존 데모 데이터 삭제 후 새로 추가
    db.execute('DELETE FROM flowcharts WHERE title = ?', (demo_flowchart['title'],))

    # 데이터 삽입
    cursor = db.execute('''
        INSERT INTO flowcharts (title, description, data)
        VALUES (?, ?, ?)
    ''', (
        demo_flowchart['title'],
        demo_flowchart['description'],
        json.dumps(demo_flowchart['data'])
    ))
    db.commit()
    print(f"데모 플로우차트가 추가되었습니다! (ID: {cursor.lastrowid})")
    print(f"확인: http://localhost:5000/flowchart/")

    db.close()

if __name__ == '__main__':
    add_demo_data()
