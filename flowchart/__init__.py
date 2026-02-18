from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import sqlite3
import json
from datetime import datetime
import os

# Blueprint 생성
flowchart_bp = Blueprint('flowchart', __name__, 
                        template_folder='templates',
                        url_prefix='/flowchart')

# 데이터베이스 경로 (프로젝트 루트의 db 폴더)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'flowcharts.db')

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """데이터베이스 초기화 - 메인 앱에서 호출"""
    # db 폴더가 없으면 생성
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
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
    db.commit()
    db.close()

@flowchart_bp.route('/')
def index():
    db = get_db()
    flowcharts = db.execute('SELECT * FROM flowcharts ORDER BY updated_at DESC').fetchall()
    db.close()
    return render_template('flowchart_list.html', flowcharts=flowcharts)

@flowchart_bp.route('/create')
def create():
    return render_template('flowchart_editor.html', flowchart=None)

@flowchart_bp.route('/edit/<int:id>')
def edit(id):
    db = get_db()
    row = db.execute('SELECT * FROM flowcharts WHERE id = ?', (id,)).fetchone()
    db.close()
    if row:
        flowchart = dict(row)
        # Keep data as JSON string for template (template uses |safe filter)
        # flowchart['data'] is already a JSON string from database
        return render_template('flowchart_editor.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/view/<int:id>')
def view(id):
    db = get_db()
    row = db.execute('SELECT * FROM flowcharts WHERE id = ?', (id,)).fetchone()
    db.close()
    if row:
        flowchart = dict(row)
        # Keep data as JSON string for template (template uses |safe filter)
        # flowchart['data'] is already a JSON string from database
        return render_template('flowchart_view.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/share/<int:id>')
def share(id):
    """공유 전용 뷰 - 다이어그램만 전체 화면으로 표시"""
    db = get_db()
    row = db.execute('SELECT * FROM flowcharts WHERE id = ?', (id,)).fetchone()
    db.close()
    if row:
        flowchart = dict(row)
        return render_template('flowchart_share.html', flowchart=flowchart)
    return redirect(url_for('flowchart.index'))

@flowchart_bp.route('/api/save', methods=['POST'])
def save():
    data = request.json
    db = get_db()
    
    if data.get('id'):
        # 업데이트
        db.execute('''
            UPDATE flowcharts 
            SET title = ?, description = ?, data = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (data['title'], data['description'], json.dumps(data['flowchart_data']), data['id']))
        flowchart_id = data['id']
    else:
        # 새로 생성
        cursor = db.execute('''
            INSERT INTO flowcharts (title, description, data)
            VALUES (?, ?, ?)
        ''', (data['title'], data['description'], json.dumps(data['flowchart_data'])))
        flowchart_id = cursor.lastrowid
    
    db.commit()
    db.close()
    return jsonify({'success': True, 'id': flowchart_id})

@flowchart_bp.route('/api/delete/<int:id>', methods=['DELETE'])
def delete(id):
    db = get_db()
    db.execute('DELETE FROM flowcharts WHERE id = ?', (id,))
    db.commit()
    db.close()
    return jsonify({'success': True})
