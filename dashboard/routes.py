from flask import render_template, current_app, jsonify, url_for
from . import dashboard_bp
import os
from models import Project, Task, Memo, Infolink, Product, Tag, db
from contacts.routes import load_contacts
from todo.models import TodoItem



def count_files_by_type(rootdir):
    stats = {'py': 0, 'html': 0, 'css': 0, 'js': 0, 'db': 0, 'total': 0}
    for dirpath, dirnames, filenames in os.walk(rootdir):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ['venv', '__pycache__', 'node_modules']]
        for f in filenames:
            stats['total'] += 1
            ext = f.split('.')[-1].lower()
            if ext in stats:
                stats[ext] += 1
    return stats

import shutil

def get_memory_usage():
    """Get server memory and swap usage from /proc/meminfo"""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1])  # in kB
                    meminfo[key] = value

            # RAM
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', 0)
            used = total - available

            # Swap
            swap_total = meminfo.get('SwapTotal', 0)
            swap_free = meminfo.get('SwapFree', 0)
            swap_used = swap_total - swap_free

            return {
                'total': f"{total / (1024**2):.1f} GB",
                'used': f"{used / (1024**2):.1f} GB",
                'available': f"{available / (1024**2):.1f} GB",
                'percent': int((used / total) * 100) if total > 0 else 0,
                'swap_total': f"{swap_total / (1024**2):.1f} GB",
                'swap_used': f"{swap_used / (1024**2):.1f} GB",
                'swap_free': f"{swap_free / (1024**2):.1f} GB",
                'swap_percent': int((swap_used / swap_total) * 100) if swap_total > 0 else 0
            }
    except Exception as e:
        return {'error': str(e)}

def get_disk_usage(path):
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            'total': f"{total / (1024**3):.1f} GB",
            'used': f"{used / (1024**3):.1f} GB",
            'free': f"{free / (1024**3):.1f} GB",
            'percent': int((used / total) * 100)
        }
    except Exception as e:
        return {'error': str(e)}

@dashboard_bp.route('/dashboard')
def index():
    import json
    
    # 0. Load Bookmarks
    bookmarks_path = os.path.join(os.path.dirname(__file__), 'bookmarks.json')
    bookmarks = []
    try:
        if os.path.exists(bookmarks_path):
            with open(bookmarks_path, 'r', encoding='utf-8') as f:
                bookmarks = json.load(f)
    except Exception as e:
        print(f"Error loading bookmarks: {e}")
        
    if not bookmarks:
        # Fallback Defaults
        try:
            bookmarks = [
                {"name": "Projects", "url": url_for('projects'), "icon": "fas fa-folder"},
                {"name": "Tasks", "url": url_for('all_tasks'), "icon": "fas fa-tasks"},
                {"name": "Memos", "url": url_for('search_memos'), "icon": "fas fa-sticky-note"},
                {"name": "Statistics", "url": url_for('statistics'), "icon": "fas fa-chart-bar"}
            ]
        except Exception as e:
            print(f"Error generating default bookmarks: {e}")
            bookmarks = []

    base_dir = current_app.config.get('BASE_DIR', os.getcwd())

    # 1. File Stats
    file_stats = count_files_by_type(base_dir)

    # 2. DB Stats
    db_stats = {}
    try:
        db_stats['Projects'] = Project.query.count()
        db_stats['Tasks'] = Task.query.count()
        db_stats['Memos'] = Memo.query.count()
        db_stats['Products'] = Product.query.count()
        db_stats['Tags'] = Tag.query.count()
        db_stats['Infolinks'] = Infolink.query.count()
    except Exception as e:
        db_stats['error'] = str(e)

    # 3. Disk Usage
    disk_stats = {
        'Root (/)': get_disk_usage('/'),
        'Data (/data)': get_disk_usage('/home/ubuntu/project/pdata')
    }

    # 4. Memory Usage
    memory_stats = get_memory_usage()

    # 5. Chart Data
    chart_data = {}
    try:
        from sqlalchemy import func

        from app import load_settings

        # Load Settings for Status Grouping
        settings = load_settings()
        status_config = settings.get("Status", {})
        research_statuses = status_config.get("Research", [])
        development_statuses = status_config.get("Development", [])
        others_statuses = status_config.get("Others", [])

        # Project Status Grouping
        # Only count projects with statuses defined in settings.json
        all_valid_statuses = research_statuses + development_statuses + others_statuses
        
        project_status_counts = db.session.query(
            Project.status, func.count(Project.id)
        ).filter(
            Project.is_completed == False,
            Project.status.in_(all_valid_statuses)  # Only include statuses from settings.json
        ).group_by(Project.status).all()

        research_data = {'labels': [], 'data': [], 'total': 0}
        development_data = {'labels': [], 'data': [], 'total': 0}
        others_data = {'labels': [], 'data': [], 'total': 0}

        for status, count in project_status_counts:
            if status in research_statuses:
                research_data['labels'].append(status)
                research_data['data'].append(count)
                research_data['total'] += count
            elif status in development_statuses:
                development_data['labels'].append(status)
                development_data['data'].append(count)
                development_data['total'] += count
            elif status in others_statuses:
                others_data['labels'].append(status)
                others_data['data'].append(count)
                others_data['total'] += count
                
        chart_data['projects'] = {
            'research': research_data,
            'development': development_data,
            'others': others_data
        }

        # Task Status (Deadlines)
        from datetime import date, timedelta
        today = date.today()
        
        tasks_active = Task.query.filter(Task.status != 'Done').all()
        
        task_deadlines = {
            'overdue': 0,
            'today': 0,
            'soon': 0,
            'later': 0,
            'no_date': 0
        }
        
        for task in tasks_active:
            if not task.due_date:
                task_deadlines['no_date'] += 1
            elif task.due_date < today:
                task_deadlines['overdue'] += 1
            elif task.due_date == today:
                task_deadlines['today'] += 1
            elif task.due_date <= today + timedelta(days=3):
                task_deadlines['soon'] += 1
            else:
                task_deadlines['later'] += 1
                
        chart_data['tasks'] = {
            'labels': ['Overdue', 'Today', 'Due Soon', 'Due Later', 'No Date'],
            'data': [
                task_deadlines['overdue'],
                task_deadlines['today'],
                task_deadlines['soon'],
                task_deadlines['later'],
                task_deadlines['no_date']
            ]
        }

        # Todo Status (Todos per Project) - Using Memos with 'Todo' tag
        
        # 'Todo' 태그를 가진 메모들을 프로젝트별로 그룹화
        todo_project_counts = db.session.query(
            Project.title, func.count(Memo.id)
        ).join(Memo.project).join(Memo.tag).filter(
            Tag.name == 'Todo'
        ).group_by(Project.title).order_by(func.count(Memo.id).desc()).all()
        
        # 프로젝트 없는 Todo (Optional: 확인 필요)
        no_project_todos = db.session.query(func.count(Memo.id)).join(Memo.tag).filter(
            Tag.name == 'Todo',
            Memo.project_id == None
        ).scalar()
        
        todo_labels = [title for title, count in todo_project_counts]
        todo_data = [count for title, count in todo_project_counts]
        
        if no_project_todos and no_project_todos > 0:
            todo_labels.append('No Project')
            todo_data.append(no_project_todos)
            
        chart_data['todos'] = {
            'labels': todo_labels,
            'data': todo_data
        }
        
    except Exception as e:
        print(f"Error generating chart data: {e}")
        chart_data['projects'] = {'labels': [], 'data': []} # Safety fallback
        chart_data['tasks'] = {'labels': [], 'data': []}
        chart_data['todos'] = {'labels': [], 'data': []}
        chart_data['error'] = str(e)

    # 6. Planned Todos (from Todo App)
    planned_todos = []
    try:
        from todo.models import TodoItem
        # Get items with due_date that are not completed, ordered by due_date
        planned_todos = TodoItem.query.filter(
            TodoItem.due_date != None,
            TodoItem.completed == False
        ).order_by(TodoItem.due_date.asc()).limit(10).all()
    except Exception as e:
        print(f"Error loading planned todos: {e}")

    # 7. Favorite Contacts
    favorite_contacts = []
    try:
        contacts = load_contacts()
        favorites = [c for c in contacts if c.get('is_favorite')]
        favorites.sort(key=lambda x: (-x.get('priority_score', 0), x.get('name', '')))
        favorite_contacts = favorites[:8]
    except Exception as e:
        print(f"Error loading favorite contacts: {e}")

    # 8. Calendar Events
    calendar_events = []
    try:
        from gcal import fetch_calendar_events
        calendar_events = fetch_calendar_events()
    except Exception as e:
        print(f"Error loading calendar events: {e}")

    return render_template('dashboard/index.html',
                           file_stats=file_stats,
                           db_stats=db_stats,
                           disk_stats=disk_stats,
                           memory_stats=memory_stats,
                           chart_data=chart_data,
                           planned_todos=planned_todos,
                           favorite_contacts=favorite_contacts,
                           calendar_events=calendar_events,
                           bookmarks=bookmarks)


@dashboard_bp.route('/api/memory')
def api_memory():
    """API endpoint for real-time memory stats"""
    from datetime import datetime
    stats = get_memory_usage()
    stats['timestamp'] = datetime.now().strftime('%H:%M:%S')
    return jsonify(stats)


@dashboard_bp.route('/api/cities')
def api_cities():
    """API endpoint for city data"""
    import json
    city_data_path = os.path.join(os.path.dirname(__file__), 'city_data.json')
    try:
        with open(city_data_path, 'r', encoding='utf-8') as f:
            cities = json.load(f)
        return jsonify(cities)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/card/summary')
def api_card_summary():
    """API endpoint for card usage summary"""
    try:
        from card.card_functions import get_monthly_card_summary
        data = get_monthly_card_summary()
        return jsonify(data)
    except ImportError:
        return jsonify({'error': 'Card module not enabled'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@dashboard_bp.route('/api/holidays')
def api_holidays():
    """API endpoint for holidays"""
    import json
    holidays_path = os.path.join(os.path.dirname(__file__), 'holidays.json')
    try:
        with open(holidays_path, 'r', encoding='utf-8') as f:
            holidays = json.load(f)
        return jsonify(holidays)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/bookmarks', methods=['POST'])
def save_bookmarks():
    import json
    from flask import request
    
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({'error': 'Invalid data format'}), 400
            
        bookmarks_path = os.path.join(os.path.dirname(__file__), 'bookmarks.json')
        with open(bookmarks_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
