"""
기존 프로젝트의 app.py에 플로우차트 기능을 통합하는 예시

사용 방법:
1. flowchart 폴더를 프로젝트 루트에 배치
2. 아래 코드를 기존 app.py에 추가
"""

from flask import Flask, render_template
from flowchart import flowchart_bp, init_db

app = Flask(__name__)

# ============================================
# 플로우차트 Blueprint 등록 (새로 추가)
# ============================================
app.register_blueprint(flowchart_bp)

# ============================================
# 기존 라우트들 (예시)
# ============================================

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>프로젝트 관리 시스템</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: white;
                padding: 60px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 600px;
            }
            h1 { color: #333; margin-bottom: 30px; }
            .btn {
                display: inline-block;
                padding: 15px 30px;
                background: #2196F3;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px;
                transition: all 0.3s;
            }
            .btn:hover {
                background: #1976D2;
                transform: translateY(-3px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 프로젝트 관리 시스템</h1>
            <a href="/flowchart/" class="btn">📊 플로우차트 관리</a>
        </div>
    </body>
    </html>
    '''

# 기존의 다른 라우트들...
# @app.route('/your-route')
# def your_function():
#     ...

# ============================================
# 데이터베이스 초기화 (새로 추가)
# ============================================
with app.app_context():
    init_db()

# ============================================
# 서버 실행
# ============================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
