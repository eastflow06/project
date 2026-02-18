# Flowchart Service Documentation

## 개요

Flask 기반의 웹 플로우차트 에디터 서비스입니다. Cytoscape.js 라이브러리를 사용하여 브라우저에서 인터랙티브한 플로우차트를 생성, 편집, 공유할 수 있습니다.

## 프로젝트 구조

```
flowchart/
├── __init__.py              # Flask Blueprint, 라우트, DB 로직
├── templates/
│   ├── flowchart_list.html   # 플로우차트 목록 페이지
│   ├── flowchart_editor.html # 편집기 (Cytoscape.js 기반)
│   ├── flowchart_view.html   # 읽기 전용 뷰어
│   └── flowchart_share.html  # 공유용 전체 화면 뷰어
└── README.md                 # 이 문서
```

## 데이터베이스

### 테이블 스키마

```sql
CREATE TABLE flowcharts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    data TEXT NOT NULL,          -- Cytoscape.js JSON 데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 데이터 저장 형식

`data` 필드에는 Cytoscape.js의 elements 객체가 JSON 문자열로 저장됩니다:

```json
{
  "nodes": [
    {
      "data": {
        "id": "node1",
        "label": "시작",
        "nodeType": "start",
        "memo": "",
        "bgColor": "#ACE7AE",
        "borderColor": "#52CE60",
        "borderWidth": 1.5,
        "textColor": "#333333",
        "fontSize": "14px",
        "fontWeight": "normal",
        "fontStyle": "normal",
        "textAlign": "center"
      },
      "position": { "x": 200, "y": 100 }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "edge1",
        "source": "node1",
        "target": "node2",
        "label": "다음",
        "lineColor": "#404040",
        "lineStyle": "solid",
        "curveStyle": "taxi",
        "controlPoint1": { "x": 250, "y": 150 },
        "controlPoint2": { "x": 300, "y": 200 }
      }
    }
  ]
}
```

## API 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/flowchart/` | 플로우차트 목록 페이지 |
| GET | `/flowchart/create` | 새 플로우차트 편집기 |
| GET | `/flowchart/edit/<id>` | 기존 플로우차트 편집 |
| GET | `/flowchart/view/<id>` | 플로우차트 뷰어 (사이드바 포함) |
| GET | `/flowchart/share/<id>` | 공유용 전체 화면 뷰어 |
| POST | `/flowchart/api/save` | 플로우차트 저장/업데이트 |
| DELETE | `/flowchart/api/delete/<id>` | 플로우차트 삭제 |

### 저장 API 요청 형식

```javascript
fetch('/flowchart/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        id: 1,                    // null이면 새로 생성
        title: "플로우차트 제목",
        description: "설명",
        flowchart_data: {         // Cytoscape elements
            nodes: [...],
            edges: [...]
        }
    })
});
```

## 노드 타입 (nodeType)

| 타입 | 설명 | 기본 모양 | 기본 색상 |
|------|------|----------|----------|
| `start` | 시작 노드 | 타원 (ellipse) | 연두색 (#ACE7AE) |
| `end` | 종료 노드 | 타원 (ellipse) | 핑크색 (#F8CECC) |
| `state` | 상태/프로세스 노드 | 둥근 사각형 (round-rectangle) | 투명 (#f5f5f0) |
| `decision` | 조건/결정 노드 | 다이아몬드 (diamond) | 노란색 (#FFF2CC) |
| `text` | 텍스트 박스 (주석) | 투명 사각형 | 투명 |

## 노드 데이터 속성

### 공통 속성

| 속성 | 타입 | 설명 |
|------|------|------|
| `id` | string | 노드 고유 ID |
| `label` | string | 노드에 표시되는 텍스트 |
| `nodeType` | string | 노드 타입 (start, end, state, decision, text) |
| `memo` | string | 메모/상세 설명 |

### 스타일 속성

| 속성 | 타입 | 설명 | 기본값 |
|------|------|------|--------|
| `bgColor` | string | 배경색 (hex) | 타입별 기본색 |
| `borderColor` | string | 테두리색 (hex) | `#333333` |
| `borderWidth` | number | 테두리 두께 (px) | `1.5` |
| `textColor` | string | 텍스트 색상 (hex) | `#333333` |

### 텍스트 노드 전용 속성

| 속성 | 타입 | 설명 | 기본값 |
|------|------|------|--------|
| `fontSize` | string | 글꼴 크기 | `14px` |
| `fontWeight` | string | 굵기 (normal, bold) | `normal` |
| `fontStyle` | string | 스타일 (normal, italic) | `normal` |
| `textAlign` | string | 정렬 (left, center, right) | `center` |

**참고**: 텍스트 노드는 `label`이 아닌 `memo` 필드가 화면에 표시됩니다.

## 엣지 데이터 속성

| 속성 | 타입 | 설명 | 기본값 |
|------|------|------|--------|
| `id` | string | 엣지 고유 ID | - |
| `source` | string | 시작 노드 ID | - |
| `target` | string | 종료 노드 ID | - |
| `label` | string | 엣지 레이블 | `""` |
| `lineColor` | string | 선 색상 | `#404040` |
| `lineStyle` | string | 선 스타일 (solid, dashed, dotted) | `solid` |
| `curveStyle` | string | 곡선 스타일 (taxi, unbundled-bezier, straight) | `taxi` |
| `controlPoint1` | object | Bezier 컨트롤 포인트 1 (unbundled-bezier용) | - |
| `controlPoint2` | object | Bezier 컨트롤 포인트 2 (unbundled-bezier용) | - |

## Cytoscape.js 스타일 시스템

스타일은 CSS-like 선택자로 적용됩니다. 우선순위:

1. 기본 `node` 스타일
2. `node[nodeType="xxx"]` 타입별 스타일
3. `node[bgColor]`, `node[borderColor]` 등 데이터 기반 스타일 (최우선)

### 주요 스타일 선택자

```javascript
// 기본 노드
selector: 'node'

// 타입별 노드
selector: 'node[nodeType="start"]'
selector: 'node[nodeType="state"]'
selector: 'node[nodeType="decision"]'
selector: 'node[nodeType="end"]'
selector: 'node[nodeType="text"]'

// 데이터 기반 스타일
selector: 'node[bgColor]'      // bgColor 데이터가 있는 노드
selector: 'node[borderColor]'  // borderColor 데이터가 있는 노드
selector: 'node[fontSize]'     // 텍스트 노드의 폰트 크기

// 엣지
selector: 'edge'
selector: 'edge[curveStyle]'
selector: 'edge[lineColor]'
```

## 주요 기능

### 편집기 (flowchart_editor.html)

1. **노드 추가**: 툴바에서 노드 타입 선택 후 클릭
2. **노드 편집**: 노드 선택 후 사이드바에서 속성 변경
3. **연결선 추가**: "연결 모드" 활성화 후 소스→타겟 노드 순서로 클릭
4. **Bezier 곡선**: 연결선 선택 후 "곡선 (Bezier)" 스타일 선택, 빨간 핸들로 조절
5. **텍스트 박스**: 주석용 텍스트, 메모 필드가 화면에 표시됨
6. **Undo/Redo**: Ctrl+Z / Ctrl+Y
7. **삭제**: Delete 키 또는 삭제 버튼

### 뷰어 (flowchart_view.html)

- 읽기 전용 표시
- 노드 클릭 시 메모 표시
- 확대/축소, 이미지 저장, 공유 링크 복사

### 공유 뷰어 (flowchart_share.html)

- 전체 화면 다이어그램
- 최소한의 UI
- 외부 공유용

## Flask 앱 통합

```python
from flowchart import flowchart_bp, init_db

app = Flask(__name__)
app.register_blueprint(flowchart_bp)

# 앱 시작 시 DB 초기화
with app.app_context():
    init_db()
```

## 의존성

- **Backend**: Flask, SQLite3
- **Frontend**: Cytoscape.js 3.21.1 (CDN)

## 파일별 상세

### __init__.py

- `flowchart_bp`: Flask Blueprint (`/flowchart` prefix)
- `init_db()`: 데이터베이스 테이블 생성
- `get_db()`: SQLite 연결 획득
- 라우트 핸들러: CRUD 및 API

### flowchart_editor.html

- ~1300줄의 HTML/CSS/JavaScript
- Cytoscape.js 인스턴스 생성 및 관리
- 사이드바 UI: 노드/엣지 속성 편집
- 툴바: 노드 추가, 연결 모드, Undo/Redo
- Bezier 컨트롤 포인트 시스템
- 자동 저장 아님 (수동 저장 버튼)

### flowchart_view.html / flowchart_share.html

- 읽기 전용 Cytoscape 인스턴스
- Bezier 컨트롤 포인트 자동 적용 (`applyBezierControlPoints()`)
- 이미지 내보내기 기능

## 스타일 변경 시 주의사항

세 템플릿 파일(editor, view, share)의 Cytoscape 스타일을 동일하게 유지해야 합니다:

1. 노드 타입별 스타일
2. 데이터 기반 스타일 (bgColor, borderColor 등)
3. 텍스트 노드 폰트 스타일

변경 시 세 파일 모두 업데이트 필요.
