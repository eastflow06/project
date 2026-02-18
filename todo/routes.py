from flask import render_template, request, jsonify, current_app, abort, make_response, redirect, url_for
from . import todo_bp
from .models import TodoList, TodoItem
from models import db, Task
from datetime import datetime, date
import pytz
import json
import os
from sqlalchemy import or_

# 구글 캘린더 연동을 위한 import
try:
    from gcal.gcal import create_calendar_event, delete_calendar_event
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False
    print("Google Calendar integration not available")

# Todo 전용 캘린더 ID (환경변수에서 로드, 기본값: primary)
TODO_CALENDAR_ID = os.getenv('TODO_CALENDAR_ID', 'primary')

KST = pytz.timezone('Asia/Seoul')

def get_db():
    return db

@todo_bp.route('/')
@todo_bp.route('/index.html')  # 이 줄만 추가
def index():
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(device in user_agent for device in ['iphone', 'android', 'mobile', 'ipad'])
    
    if is_mobile:
        return render_template('todo/mobile.html')
    return render_template('todo/index.html')

# === List APIs ===
@todo_bp.route('/api/lists', methods=['GET'])
def get_lists():
    lists = TodoList.query.all()
    return jsonify([l.to_dict() for l in lists])

@todo_bp.route('/api/lists', methods=['POST'])
def create_list():
    data = request.json
    title = data.get('title')
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    new_list = TodoList(title=title)
    db.session.add(new_list)
    db.session.commit()
    return jsonify(new_list.to_dict()), 201

@todo_bp.route('/api/lists/<int:list_id>', methods=['DELETE'])
def delete_list(list_id):
    todo_list = TodoList.query.get_or_404(list_id)
    db.session.delete(todo_list)
    db.session.commit()
    return jsonify({'success': True})

@todo_bp.route('/api/lists/<int:list_id>', methods=['PUT'])
def update_list(list_id):
    todo_list = TodoList.query.get_or_404(list_id)
    data = request.json
    if 'title' in data:
        todo_list.title = data['title']
    
    db.session.commit()
    return jsonify(todo_list.to_dict())

# === Item APIs ===
@todo_bp.route('/api/items', methods=['GET'])
def get_items():
    list_id = request.args.get('list_id', type=int)
    filter_type = request.args.get('filter')
    
    # 오늘 날짜 (KST 기준)
    now_kst = datetime.now(KST)
    today_date = now_kst.date()
    
    query = TodoItem.query
    
    if filter_type == 'my_day':
        start_of_day = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_kst.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # my_day_date가 오늘인 항목 또는 due_date가 오늘인 항목
        query = query.filter(
            or_(
                (TodoItem.is_my_day == True) & (TodoItem.my_day_date == today_date),
                (TodoItem.due_date >= start_of_day) & (TodoItem.due_date <= end_of_day)
            )
        )
    elif filter_type == 'important':
        query = query.filter_by(is_important=True)
    elif filter_type == 'planned':
        query = query.filter(TodoItem.due_date != None)
        query = query.order_by(TodoItem.due_date)
    elif filter_type == 'tasks':
        if list_id:
            query = query.filter_by(list_id=list_id)
    elif list_id:
        query = query.filter_by(list_id=list_id)
        
    items = query.all()
    return jsonify([i.to_dict() for i in items])

@todo_bp.route('/api/items', methods=['POST'])
def create_item():
    data = request.json
    content = data.get('content')
    list_id = data.get('list_id')
    
    if not content or not list_id:
        return jsonify({'error': 'Content and List ID are required'}), 400
    
    is_my_day = data.get('is_my_day', False)
    is_important = data.get('is_important', False)
    is_all_day = data.get('is_all_day', True)
    due_date_str = data.get('due_date')
    my_day_date_str = data.get('my_day_date')
    
    due_date = None
    if due_date_str:
        try:
            if is_all_day or 'T' not in due_date_str:
                # Date only provided (YYYY-MM-DD) -> Default to 09:00 KST
                naive_dt = datetime.fromisoformat(due_date_str.split('T')[0] + 'T09:00:00')
                due_date = naive_dt
                is_all_day = False
            else:
                # With time: datetime-local format (YYYY-MM-DDTHH:MM)
                # Browser sends local time, assume it's KST
                naive_dt = datetime.fromisoformat(due_date_str.replace('Z', ''))
                due_date = naive_dt
        except (ValueError, AttributeError) as e:
            print(f"Date parse error: {e}")
    
    my_day_date = None
    if my_day_date_str:
        try:
            my_day_date = datetime.fromisoformat(my_day_date_str).date()
        except (ValueError, AttributeError) as e:
            print(f"My day date parse error: {e}")

    new_item = TodoItem(
        content=content,
        list_id=list_id,
        is_my_day=is_my_day,
        my_day_date=my_day_date,
        is_important=is_important,
        is_all_day=is_all_day,
        due_date=due_date
    )
    
    db.session.add(new_item)
    db.session.commit()
    return jsonify(new_item.to_dict()), 201

@todo_bp.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    item = TodoItem.query.get_or_404(item_id)
    data = request.json
    
    if 'content' in data:
        item.content = data['content']
    if 'completed' in data:
        item.completed = data['completed']
        if item.completed:
            item.completed_at = datetime.now(KST)
        else:
            item.completed_at = None
    if 'is_important' in data:
        item.is_important = data['is_important']
    if 'is_my_day' in data:
        item.is_my_day = data['is_my_day']
        if not item.is_my_day:
            item.my_day_date = None
    if 'my_day_date' in data:
        if data['my_day_date'] is None:
            item.my_day_date = None
        else:
            try:
                item.my_day_date = datetime.fromisoformat(data['my_day_date']).date()
            except (ValueError, AttributeError):
                pass
    if 'is_all_day' in data:
        item.is_all_day = data['is_all_day']
    if 'due_date' in data:
        if data['due_date'] is None:
            item.due_date = None
        else:
            try:
                is_all_day = data.get('is_all_day', item.is_all_day)
                due_date_str = data['due_date']
                
                if is_all_day or 'T' not in due_date_str:
                    # All-day
                    naive_dt = datetime.fromisoformat(due_date_str.split('T')[0] + 'T00:00:00')
                    item.due_date = naive_dt
                else:
                    # With time
                    naive_dt = datetime.fromisoformat(due_date_str.replace('Z', ''))
                    item.due_date = naive_dt
            except (ValueError, AttributeError):
                pass
    if 'memo' in data:
        item.memo = data['memo']
    if 'steps' in data:
        item.steps = data['steps']
    if 'list_id' in data:
        item.list_id = data['list_id']
        
    db.session.commit()
    return jsonify(item.to_dict())

@todo_bp.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    item = TodoItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})

@todo_bp.route('/api/project/tasks', methods=['GET'])
def get_project_tasks():
    tasks = Task.query.filter(Task.status != 'Done').order_by(
        Task.due_date.is_(None),
        Task.due_date.asc()
    ).all()
    
    result = []
    for t in tasks:
        result.append({
            'id': t.id,
            'title': t.title,
            'status': t.status,
            'start_date': t.start_date.isoformat() if t.start_date else None,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'project_id': t.project_id,
            'project_title': t.project.title if t.project else "Unknown Project"
        })
    return jsonify(result)

# === Google Calendar Integration APIs ===
@todo_bp.route('/api/items/<int:item_id>/calendar', methods=['POST'])
def add_to_calendar(item_id):
    """할 일을 구글 캘린더에 추가"""
    if not GCAL_AVAILABLE:
        return jsonify({'error': 'Google Calendar integration not available'}), 503

    item = TodoItem.query.get_or_404(item_id)

    # 이미 캘린더에 추가된 경우
    if item.google_event_id:
        return jsonify({'error': 'Already added to calendar', 'event_id': item.google_event_id}), 400

    # 일정이 없는 경우
    if not item.due_date:
        return jsonify({'error': 'No due date set'}), 400

    try:
        # 메모가 있으면 description에 추가
        description = item.memo if item.memo else None

        # 캘린더 이벤트 생성 (Todo 전용 캘린더 사용)
        event_id = create_calendar_event(
            summary=item.content,
            start_datetime=item.due_date,
            end_datetime=item.due_date,
            is_all_day=item.is_all_day,
            description=description,
            location=item.location,
            calendar_id=TODO_CALENDAR_ID
        )

        if event_id:
            # google_event_id 저장
            item.google_event_id = event_id
            db.session.commit()
            return jsonify({'success': True, 'event_id': event_id})
        else:
            return jsonify({'error': 'Failed to create calendar event'}), 500

    except Exception as e:
        print(f"Calendar creation error: {e}")
        return jsonify({'error': str(e)}), 500

@todo_bp.route('/api/items/<int:item_id>/calendar', methods=['DELETE'])
def remove_from_calendar(item_id):
    """할 일을 구글 캘린더에서 제거"""
    if not GCAL_AVAILABLE:
        return jsonify({'error': 'Google Calendar integration not available'}), 503

    item = TodoItem.query.get_or_404(item_id)

    # 캘린더에 추가되지 않은 경우
    if not item.google_event_id:
        return jsonify({'error': 'Not added to calendar'}), 400

    try:
        # 캘린더 이벤트 삭제 (Todo 전용 캘린더에서)
        success = delete_calendar_event(item.google_event_id, calendar_id=TODO_CALENDAR_ID)

        if success:
            # google_event_id 제거
            item.google_event_id = None
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete calendar event'}), 500

    except Exception as e:
        print(f"Calendar deletion error: {e}")
        return jsonify({'error': str(e)}), 500
