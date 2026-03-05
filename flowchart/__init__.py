from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import pymysql
import json
from datetime import datetime
import os

# Blueprint 생성
flowchart_bp = Blueprint('flowchart', __name__, 
                        template_folder='templates',
                        url_prefix='/flowchart')

# MySQL 접속 정보
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'projectuser'),
    'password': os.environ.get('MYSQL_PASSWORD', 'ProjectDB2026!'),
    'database': os.environ.get('MYSQL_DATABASE', 'project_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**MYSQL_CONFIG)

def init_db():
    """데이터베이스 초기화 - 메인 앱에서 호출"""
    db = pymysql.connect(**MYSQL_CONFIG)
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flowcharts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            data LONGTEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ''')
    db.commit()
    db.close()

@flowchart_bp.route('/')
def index():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM flowcharts ORDER BY updated_at DESC')
    flowcharts = cursor.fetchall()
    db.close()
    return render_template('flowchart_list.html', flowcharts=flowcharts)

@flowchart_bp.route('/create')
def create():
    return render_template('flowchart_editor.html', flowchart=None)

@flowchart_bp.route('/edit/<int:id>')
def edit(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM flowcharts WHERE id = %s', (id,))
    flowchart = cursor.fetchone()
    db.close()
    if flowchart:
        # Keep data as JSON string for template (template uses |safe filter)
        # flowchart['data'] is already a JSON string from database
        return render_template('flowchart_editor.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/view/<int:id>')
def view(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM flowcharts WHERE id = %s', (id,))
    flowchart = cursor.fetchone()
    db.close()
    if flowchart:
        # Keep data as JSON string for template (template uses |safe filter)
        # flowchart['data'] is already a JSON string from database
        return render_template('flowchart_view.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/share/<int:id>')
def share(id):
    """공유 전용 뷰 - 다이어그램만 전체 화면으로 표시"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM flowcharts WHERE id = %s', (id,))
    flowchart = cursor.fetchone()
    db.close()
    if flowchart:
        return render_template('flowchart_share.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/api/save', methods=['POST'])
def save():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    if data.get('id'):
        # 업데이트
        cursor.execute('''
            UPDATE flowcharts 
            SET title = %s, description = %s, data = %s, updated_at = NOW()
            WHERE id = %s
        ''', (data['title'], data['description'], json.dumps(data['flowchart_data']), data['id']))
        flowchart_id = data['id']
    else:
        # 새로 생성
        cursor.execute('''
            INSERT INTO flowcharts (title, description, data)
            VALUES (%s, %s, %s)
        ''', (data['title'], data['description'], json.dumps(data['flowchart_data'])))
        flowchart_id = cursor.lastrowid
    
    db.commit()
    db.close()
    return jsonify({'success': True, 'id': flowchart_id})

@flowchart_bp.route('/api/delete/<int:id>', methods=['DELETE'])
def delete(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM flowcharts WHERE id = %s', (id,))
    db.commit()
    db.close()
    return jsonify({'success': True})
