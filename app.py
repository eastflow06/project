from flask_migrate import Migrate
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, current_app, send_from_directory
from models import db, Project, Product, Task, Memo, Link, ProjectImage, Tag, MyMemo, Infolink, MemoImage
from note.models import Note
from werkzeug.utils import secure_filename
import os, random, uuid, re, base64, mimetypes, sys, unicodedata,pytz,markdown2, json
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()
from markupsafe import Markup
from operator import attrgetter
from itertools import groupby
from datetime import datetime, date, timedelta
from flask_cors import CORS
from auth import auth_bp, oauth, login_required
from PIL import Image
from flask import current_app as app
from collections import defaultdict
from requests.exceptions import RequestException
from sqlalchemy.orm import aliased, joinedload, selectinload
from sqlalchemy import or_, and_, func
from sqlalchemy.orm.attributes import flag_modified
from flask_wtf.csrf import CSRFProtect
from io import BytesIO
from contacts.routes import contact_bp, load_contacts
from gcal.gcal import fetch_calendar_events
import jinja2
from functools import lru_cache
from flask_caching import Cache
from werkzeug.datastructures import FileStorage
import uuid
import pandas as pd

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# Flask 앱 생성 (한 번만!)
app = Flask(__name__)

# 데이터 경로 기준 설정
BASE_DIR = "/home/ubuntu/project"
app.config['BASE_DIR'] = BASE_DIR

SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')

# 데이터베이스 (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/db/project.db"
app.config['SQLALCHEMY_BINDS'] = {
    'notes_db': f"sqlite:///{BASE_DIR}/db/notes.db",
    'todo_db': f"sqlite:///{BASE_DIR}/db/todo.db",  # Todo Database configuration
    'lims_db': f"sqlite:///{BASE_DIR}/db/lims.db"
}

# 파일/업로드 관련 설정 - 원하시는 대로 수정
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static/data')  
app.config['INFOLINK_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'pdata/Infolink')  
app.config['IMAGE_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static/photo')
app.config['NOTE_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'pdata/Note/images')  

# 보안 및 업로드 제약
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'gif',
    'pdf', 'xls', 'xlsx', 'ppt', 'pptx', 'md',
    'html', 'htm'
}
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB
app.config['THUMBNAIL_SIZE'] = (150, 150)

# OpenWeatherMap API Key
app.config['OPENWEATHER_API_KEY'] = os.environ.get('OPENWEATHER_API_KEY', '')

# 캐시 설정
cache = Cache()
cache.init_app(app, config={'CACHE_TYPE': 'simple'})

# card 모듈 경로 추가 및 import
# 기본 템플릿 로더 설정 (순서: 기본 -> 각 모듈)
template_loaders = [
    jinja2.FileSystemLoader('templates'),
    jinja2.FileSystemLoader('flowchart/templates'),
    jinja2.FileSystemLoader('lims/templates')
]

# card 모듈 사용 설정
try:
    card_path = os.path.join(os.path.dirname(__file__), 'card')
    sys.path.insert(0, card_path)
    
    # card 기능들 import
    import card_functions as card_module
    
    # import 성공 시 card 템플릿 경로 추가
    if os.path.exists(os.path.join(card_path, 'templates')):
        template_loaders.append(jinja2.FileSystemLoader(os.path.join(card_path, 'templates')))
    
    CARD_ENABLED = True
    print("Card module imported successfully")
    
except ImportError as e:
    print(f"Card module import failed: {e}")
    CARD_ENABLED = False
except Exception as e:
    print(f"Card module setup failed: {e}")
    CARD_ENABLED = False
    
# 최종적으로 수집된 템플릿 로더들을 Flask 앱에 적용
app.jinja_loader = jinja2.ChoiceLoader(template_loaders)

# 프로젝트 상태 상수 정의
#PROJECT_STATUSES = ['기술개발', '시험평가', '제품개발', '허가승인', '사업화', '규제개선', '연구', '개발', '관리', '검토', '진행', '보류', '완료', '기타']


db.init_app(app)
migrate = Migrate(app, db)

# OAuth 초기화
oauth.init_app(app)

# Blueprint 등록
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(contact_bp, url_prefix="/contacts")

from note import note_bp
from note import note_bp
app.register_blueprint(note_bp, url_prefix='/pdata/note')

from todo import todo_bp
app.register_blueprint(todo_bp)  # Registers at /todo by default as defined in __init__.py

from flowchart import flowchart_bp, init_db as flowchart_init_db
app.register_blueprint(flowchart_bp)  # Registers at /flowchart by default

from dashboard import dashboard_bp
app.register_blueprint(dashboard_bp)

from lims import lims_bp
app.register_blueprint(lims_bp)  # Registers at /lims by default

CSRF_ENABLED = os.environ.get('CSRF_ENABLED', 'False').lower() == 'true'
app.config['WTF_CSRF_ENABLED'] = CSRF_ENABLED

# CSRF 보호 (설정에 따라)
if CSRF_ENABLED:
    csrf = CSRFProtect(app)

# card 관련 라우트들 추가 (card가 정상적으로 import된 경우에만)
if CARD_ENABLED:
    @app.route('/card')
    def card_index_route():
        return card_module.card_index()

    @app.route('/card/add', methods=['GET', 'POST'])
    def card_add_route():
        return card_module.card_add()

    @app.route('/card/edit/<string:id>', methods=['GET', 'POST'])
    def card_edit_route(id):
        return card_module.card_edit(id)

    @app.route('/card/delete/<id>', methods=['POST'])
    def card_delete_route(id):
        return card_module.card_delete(id)

    @app.route('/card/print/<year>/<month>', methods=['GET'])
    def card_print_route(year, month):
        return card_module.card_print_view(year, month)

    @app.route('/card/download_csv/<year>/<month>')
    def card_download_csv_route(year, month):
        return card_module.card_download_csv(year, month)

    @app.route('/card/monthly_viz')
    def card_monthly_viz_route():
        return card_module.card_monthly_viz()

    @app.route('/card/yearly_viz')
    def card_yearly_viz_route():
        return card_module.card_yearly_viz()

    @app.route('/card/get_notes')
    def card_get_notes_route():
        return card_module.card_get_notes()

    # card의 정적 파일 서빙 (CSS, JS, 이미지 등)
    @app.route('/card/static/<path:filename>')
    def card_static(filename):
        card_static_dir = os.path.join(os.path.dirname(__file__), 'card', 'static')
        return send_from_directory(card_static_dir, filename)

def load_settings():
    """JSON 파일에서 설정값을 읽어오는 함수"""
    default_settings = {
        "Index": {
            "bg_url": "/static/images/default_index_bg.jpg",
            "bg_color": "#ffffff",
            "opacity": "1.0"
        },
        "Panels": {
            "panel1": {
                "bg_url": "",
                "bg_color": "#f8f9fa",
                "opacity": "0.4"
            },
            "panel2": {
                "bg_url": "",
                "bg_color": "#f8f9fa",
                "opacity": "0.4"
            },
            "panel3": {
                "bg_url": "",
                "bg_color": "#f8f9fa",
                "opacity": "0.4"
            }
        },
        "Project": {
            "statuses": ['기술개발', '시험평가', '제품개발', '허가승인', '사업화', '규제개선', '연구', '개발', '관리', '검토', '진행', '보류', '완료', '기타']
        },
        "Status": {
            "Research": ['기술개발', '시험평가', '제품개발', '연구'],
            "Development": ['허가승인', '사업화', '규제개선', '개발'],
            "Others": ['관리', '보류', '기타']
        },
        "Contacts": {
            "bg_url": "/static/images/default_contacts_bg.jpg",
            "bg_color": "#ffffff",
            "opacity": "1.0"
        },
        "Summary": {
            "bg_url": "",
            "bg_color": "#f8f9fa",
            "opacity": "1.0"
        },
        "Login": {
            "bg_url": "/static/images/background.jpg",
            "terminal_user": "six"
        }
    }

    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
            # 기존 flat 구조를 새로운 계층 구조로 마이그레이션
            if "index_bg_url" in settings:
                # 구버전 형식 감지 - 자동 변환
                migrated_settings = {
                    "Index": {
                        "bg_url": settings.get("index_bg_url", ""),
                        "bg_color": settings.get("index_bg_color", "#ffffff"),
                        "opacity": settings.get("index_opacity", "1.0")
                    },
                    "Panels": {
                        "panel1": {
                            "bg_url": settings.get("panel1_bg_url", ""),
                            "bg_color": settings.get("panel1_bg_color", "#f8f9fa"),
                            "opacity": settings.get("panel1_opacity", "0.4")
                        },
                        "panel2": {
                            "bg_url": settings.get("panel2_bg_url", ""),
                            "bg_color": settings.get("panel2_bg_color", "#f8f9fa"),
                            "opacity": settings.get("panel2_opacity", "0.4")
                        },
                        "panel3": {
                            "bg_url": settings.get("panel3_bg_url", ""),
                            "bg_color": settings.get("panel3_bg_color", "#f8f9fa"),
                            "opacity": settings.get("panel3_opacity", "0.4")
                        }
                    },
                    "Project": {
                        "statuses": settings.get("project_statuses", default_settings["Project"]["statuses"])
                    },
                    "Status": {
                        "Research": settings.get("research_statuses", default_settings["Status"]["Research"]),
                        "Development": settings.get("development_statuses", default_settings["Status"]["Development"]),
                        "Others": settings.get("other_statuses", [])
                    },
                    "Contacts": {
                        "bg_url": settings.get("contacts_bg_url", ""),
                        "bg_color": settings.get("contacts_bg_color", "#ffffff"),
                        "opacity": settings.get("contacts_bg_opacity", "1.0")
                    },
                    "Summary": {
                        "bg_url": settings.get("summary_bg_url", ""),
                        "bg_color": settings.get("summary_bg_color", "#f8f9fa"),
                        "opacity": settings.get("summary_bg_opacity", "1.0")
                    }
                }
                # 마이그레이션된 설정 저장
                save_settings(migrated_settings)
                return migrated_settings
            
            return settings
    
    # 파일이 없으면 기본 설정값 반환
    return default_settings


def save_settings(settings):
    """JSON 파일에 설정값을 저장하는 함수"""
    try:
        print(f"[save_settings] Starting save process...")
        print(f"[save_settings] Target file: {SETTINGS_FILE}")
        
        # 디렉토리 존재 확인
        settings_dir = os.path.dirname(SETTINGS_FILE)
        if not os.path.exists(settings_dir):
            print(f"[save_settings] Creating directory: {settings_dir}")
            os.makedirs(settings_dir, exist_ok=True)
        
        # 백업 생성 (기존 파일이 있는 경우)
        if os.path.exists(SETTINGS_FILE):
            backup_file = SETTINGS_FILE + '.backup'
            import shutil
            shutil.copy2(SETTINGS_FILE, backup_file)
            print(f"[save_settings] Backup created: {backup_file}")
        
        # JSON 파일에 저장
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        
        print(f"[save_settings] ✅ File written successfully")
        
        # 저장 확인
        if os.path.exists(SETTINGS_FILE):
            file_size = os.path.getsize(SETTINGS_FILE)
            print(f"[save_settings] ✅ File exists, size: {file_size} bytes")
            return True
        else:
            print(f"[save_settings] ❌ ERROR: File does not exist after writing!")
            return False
            
    except PermissionError as e:
        print(f"[save_settings] ❌ Permission Error: {str(e)}")
        return False
    except Exception as e:
        print(f"[save_settings] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# 앱 실행 전에 설정값을 로드하여 전역 상수로 사용
INITIAL_SETTINGS = load_settings()
PROJECT_STATUSES = INITIAL_SETTINGS.get("Project", {}).get("statuses", [])
RESEARCH_STATUSES = INITIAL_SETTINGS.get("Status", {}).get("Research", [])
DEVELOPMENT_STATUSES = INITIAL_SETTINGS.get("Status", {}).get("Development", [])
OTHERS_STATUSES = INITIAL_SETTINGS.get("Status", {}).get("Others", [])

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    print("=" * 50)
    print("ADMIN SETTINGS ROUTE CALLED")
    print(f"Method: {request.method}")
    print(f"Is JSON: {request.is_json if request.method == 'POST' else 'N/A'}")
    print("=" * 50)
    
    settings = load_settings()
    print(f"Settings loaded: {len(settings)} sections")

    # JSON POST 요청 처리
    if request.method == 'POST' and request.is_json:
        data = request.json
        action = data.get('action')
        print(f"Action: {action}")

        if action == 'delete_image':
            try:
                # 🚨 수정: 프론트엔드가 'url'을 보낸다고 가정하고 처리 로직 통합
                url = data.get('url') 
                if not url:
                    # 파일명이 아닌 URL을 기대하므로, URL 유효성 검사 추가
                    return jsonify({'success': False, 'error': '파일 URL을 제공하지 않았습니다.'}), 400
                
                # /static/images/ 경로에서 파일명 추출
                if '/static/images/' not in url:
                    return jsonify({'success': False, 'error': '유효하지 않은 이미지 URL입니다.'}), 400
                filename = url.split('/static/images/')[-1]
                
                sanitized_filename = secure_filename(filename)
                # Note: 프론트엔드 JS는 sanitized filename을 보장할 수 없으므로, 서버에서 다시 확인
                if sanitized_filename != filename:
                    print(f"WARNING: Filename mismatch (received: {filename}, sanitized: {sanitized_filename}). Processing sanitized version.")
                    filename = sanitized_filename
                    
                file_path = os.path.join(app.static_folder, 'images', filename)
                    
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✅ Image deleted: {filename}")
                    
                    deleted_url = url_for('static', filename=f'images/{filename}')
                    
                    # 새로운 구조에서 이미지 URL 제거
                    settings = load_settings() # 최신 설정 다시 로드
                    sections_to_check = ['Index', 'Contacts', 'Summary']
                    for section in sections_to_check:
                        if section in settings and settings[section].get('bg_url') == deleted_url:
                            settings[section]['bg_url'] = ''
                            print(f"  - Removed {section} bg_url")
                    
                    # Panels 체크
                    if 'Panels' in settings:
                        for panel_key in ['panel1', 'panel2', 'panel3']:
                            if panel_key in settings['Panels'] and settings['Panels'][panel_key].get('bg_url') == deleted_url:
                                settings['Panels'][panel_key]['bg_url'] = ''
                                print(f"  - Removed Panels.{panel_key} bg_url")
                    
                    result = save_settings(settings)
                    if result:
                        return jsonify({'success': True, 'message': '이미지가 성공적으로 삭제되었습니다.'})
                    else:
                        return jsonify({'success': False, 'error': '설정 저장 실패'}), 500
                else:
                    return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'}), 404
            except Exception as e:
                print(f"❌ Image deletion failed: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'삭제 중 오류: {str(e)}'}), 500
        
        elif action == 'save_all_settings':
            print("=" * 50)
            print("SAVING ALL SETTINGS")
            print("=" * 50)
            
            try:
                # 새로운 계층 구조로 업데이트
                settings = {
                    "Index": {
                        "bg_url": data.get('index_bg_url', ''),
                        "bg_color": data.get('index_bg_color', '#ffffff'),
                        "opacity": str(data.get('index_opacity', '1.0'))
                    },
                    "Panels": {
                        "panel1": {
                            "bg_url": data.get('panel1_bg_url', ''),
                            "bg_color": data.get('panel1_bg_color', '#f8f9fa'),
                            "opacity": str(data.get('panel1_opacity', '0.4'))
                        },
                        "panel2": {
                            "bg_url": data.get('panel2_bg_url', ''),
                            "bg_color": data.get('panel2_bg_color', '#f8f9fa'),
                            "opacity": str(data.get('panel2_opacity', '0.4'))
                        },
                        "panel3": {
                            "bg_url": data.get('panel3_bg_url', ''),
                            "bg_color": data.get('panel3_bg_color', '#f8f9fa'),
                            "opacity": str(data.get('panel3_opacity', '0.4'))
                        }
                    },
                    "Project": {
                        "statuses": data.get('project_statuses', [])
                    },
                    "Status": {
                        "Research": data.get('research_statuses', []),
                        "Development": data.get('development_statuses', []),
                        # 🚨 수정된 부분: 프론트엔드가 'other_statuses'를 보내므로, 그 값을 받습니다.
                        "Others": data.get('other_statuses', []) 
                    },
                    "Contacts": {
                        "bg_url": data.get('contacts_bg_url', ''),
                        "bg_color": data.get('contacts_bg_color', '#ffffff'),
                        "opacity": str(data.get('contacts_bg_opacity', '1.0'))
                    },
                    "Summary": {
                        "bg_url": data.get('summary_bg_url', ''),
                        "bg_color": data.get('summary_bg_color', '#f8f9fa'),
                        "opacity": str(data.get('summary_bg_opacity', '1.0'))
                    },
                    "Login": {
                        "bg_url": data.get('login_bg_url', '/static/images/background.jpg'),
                        "terminal_user": data.get('login_terminal_user', 'six')
                    }
                }

                print("✅ Settings dictionary updated")
                print(f"📝 Calling save_settings()...")
                
                result = save_settings(settings)
                
                print(f"💾 Save result: {result}")
                
                if result:
                    # 전역 변수 업데이트
                    global PROJECT_STATUSES, RESEARCH_STATUSES, DEVELOPMENT_STATUSES
                    PROJECT_STATUSES = settings["Project"]["statuses"]
                    RESEARCH_STATUSES = settings["Status"]["Research"]
                    DEVELOPMENT_STATUSES = settings["Status"]["Development"]
                    
                    
                    
                    print("✅ Global variables updated")
                    print("✅ ALL SETTINGS SAVED SUCCESSFULLY!")
                    
                    return jsonify({
                        'success': True, 
                        'message': '모든 설정이 성공적으로 저장되었습니다.', 
                        'redirect_url': url_for('admin_settings')
                    })
                else:
                    print("❌ save_settings() returned False")
                    return jsonify({'success': False, 'error': 'JSON 파일 저장 실패'}), 500
                    
            except Exception as e:
                print(f"❌ Exception in save_all_settings: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'설정 저장 중 오류: {str(e)}'}), 500

        return jsonify({'success': False, 'error': '알 수 없는 액션입니다.'}), 400

    # 파일 업로드 처리 (multipart/form-data)
    if request.method == 'POST' and not request.is_json:
        print("📤 File upload POST detected")
        uploaded_files = request.files.getlist('upload_files')
        
        if uploaded_files and uploaded_files[0].filename:
            images_folder = os.path.join(app.static_folder, 'images')
            if not os.path.exists(images_folder):
                os.makedirs(images_folder)
            
            upload_count = 0
            for file in uploaded_files:
                if file and file.filename != '':
                    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
                    filename = secure_filename(file.filename)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    if file_ext in allowed_extensions:
                        name_part = os.path.splitext(filename)[0]
                        unique_filename = f"{name_part}_{uuid.uuid4().hex[:8]}{file_ext}"
                        
                        file_path = os.path.join(images_folder, unique_filename)
                        file.save(file_path)
                        upload_count += 1
                        print(f"✅ File uploaded: {unique_filename}")
            
            if upload_count > 0:
                flash(f'{upload_count}개의 이미지가 성공적으로 업로드되었습니다.', 'success')
        
        return redirect(url_for('admin_settings'))

    # GET 요청 처리
    print("📄 GET request - rendering settings_edit.html template")
    
    # 템플릿에 필요한 데이터 로드
    images_folder = os.path.join(app.static_folder, 'images')
    if not os.path.exists(images_folder):
        os.makedirs(images_folder)
      
    photo_files = [f for f in os.listdir(images_folder)
                   if os.path.isfile(os.path.join(images_folder, f))
                   and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
    photo_urls = [url_for('static', filename=f'images/{file}') for file in photo_files]

    return render_template(
        'settings_edit.html',
        settings=settings,
        photo_urls=photo_urls
    )


def read_json_data():
    """settings.json 파일을 읽어 딕셔너리를 반환"""

    if not os.path.exists(SETTINGS_FILE):
        return None, "오류: settings.json 파일을 찾을 수 없습니다."
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError:
        return None, "오류: settings.json 파일 형식이 올바르지 않습니다."
    except Exception as e:
        return None, f"파일을 읽는 중 오류가 발생했습니다: {e}"

def write_json_data(data):

    """딕셔너리를 settings.json 파일에 저장"""

    try:
        # ensure_ascii=False를 사용하여 한글이 깨지지 않도록 저장
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True, None

    except Exception as e:
        return False, f"파일을 저장하는 중 오류가 발생했습니다: {e}"

def import_gcal_module():
    """gcal 모듈을 안전하게 import하는 함수"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gcal_dir = os.path.join(current_dir, 'gcal')
        if gcal_dir not in sys.path:
            sys.path.append(gcal_dir)
        
        from gcal.gcal import fetch_calendar_events
        return fetch_calendar_events
    except ImportError as e:
        app.logger.warning(f"gcal 모듈을 import할 수 없습니다: {e}")
        def dummy_fetch_calendar_events():
            return []
        return dummy_fetch_calendar_events

# gcal 함수 import
fetch_calendar_events = import_gcal_module()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 라우트 파일 상단에 필터 정의
def render_markdown(text):
    if not text:
        return ""
        
    extras = {
        "fenced-code-blocks": {"cssclass": "highlight"}, # cssclass 지정
        "tables": None,
        "break-on-newline": True,
        "code-friendly": True,
        "highlightjs-lang": True  # 언어 강조 지원
    }
    
    html = markdown2.markdown(text, extras=extras)
    return Markup(html)

app.jinja_env.filters['custom_markdown'] = render_markdown

@app.template_filter('markdown')
def markdown_filter(text):
    if text is None:
        return ""
    
    extras = [
        'fenced-code-blocks',
        'tables',
        'break-on-newline',
        'header-ids',
        'footnotes',
        'cuddled-lists',
        'code-friendly',
        'highlightjs-lang',  # 언어 기반 코드 강조
        'code-color',        # 코드 색상 지원 (선택적)
        'preserve-tabs'      # 탭 및 들여쓰기 보존
    ]
    
    # 마크다운 변환 전에 수식 처리 및 기타 전처리
    text = process_special_content(text)
    
    # Markdown 변환
    return Markup(markdown2.markdown(text, extras=extras))

def process_special_content(text):
    if text is None:
        return ""

    # 들여쓰기 보존
    text = text.replace('\n    ', '\n&nbsp;&nbsp;&nbsp;&nbsp;')

    # 중괄호를 안전하게 변환
    text = text.replace(r'\{', '&#123;').replace(r'\}', '&#125;')

    # 빈 줄을 <p>&nbsp;</p>로 변환
    text = text.replace('\n\n', '\n<p>&nbsp;</p>\n')

    return text

@app.context_processor
def inject_now():
    # 한국 시간대 기준 오늘 날짜
    kst_now = datetime.now(KST).date()
    return {'now': kst_now, 'datetime': datetime,'date': date}

# 캐시된 함수들
def get_project_summary():
    """프로젝트 요약 정보 캐시"""
    return Project.query.with_entities(
        Project.status, 
        func.count(Project.id)
    ).group_by(Project.status).all()

@app.route('/')
def login_page():
    """로그인 페이지"""
    import time
    from flask import make_response
    settings = load_settings()
    login_settings = settings.get('Login', {})
    bg_url = login_settings.get('bg_url', '/static/images/background.jpg')
    terminal_user = login_settings.get('terminal_user', 'six')
    # 캐시 무효화를 위한 타임스탬프 추가
    cache_buster = int(time.time())
    if bg_url and '?' not in bg_url:
        bg_url = f"{bg_url}?v={cache_buster}"
    elif bg_url:
        bg_url = f"{bg_url}&v={cache_buster}"
    response = make_response(render_template('login.html', bg_url=bg_url, terminal_user=terminal_user))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/login', methods=['POST'])
def password_login():
    """비밀번호 로그인 - KST 기준 오늘날짜로 동적 생성 (MMDD/)"""
    from datetime import datetime, timezone, timedelta

    # KST 시간대 (UTC+9)
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)

    # 비밀번호: MMDD/ 형식
    today_password = now_kst.strftime('%m%d') + '/'

    submitted_password = request.form.get('password', '')

    if submitted_password == today_password:
        # 세션에 사용자 정보 저장 (간단한 형태)
        session['user_info'] = {
            'email': 'local_user@redapril.net',
            'name': 'Local User'
        }
        return redirect(url_for('index'))
    else:
        flash('비밀번호가 올바르지 않습니다.', 'error')
        return redirect(url_for('login_page'))

# 추가된 코드 - 에러 핸들러
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# 메인 페이지 - 최적화된 버전
@app.route('/index', endpoint='index')
@login_required
def index():
    # 설정 로드 시도 - load_settings() 함수 사용 (새로운 계층 구조 지원)
    settings_data = load_settings()
    
    # 새로운 계층 구조에서 상태 목록 추출
    all_project_statuses = settings_data.get('Project', {}).get('statuses', [])
    research_statuses = settings_data.get('Status', {}).get('Research', [])
    development_statuses = settings_data.get('Status', {}).get('Development', [])
    other_statuses = settings_data.get('Status', {}).get('Others', [])
    
    # 기본값 설정 (혹시 설정이 비어있을 경우 대비)
    if not all_project_statuses:
        print("경고: project_statuses가 비어있습니다. 기본값을 사용합니다.")
        all_project_statuses = [
            '기술개발', '시험평가', '제품개발', '허가승인', 
            '사업화', '규제개선', '연구', '개발', '관리', 
            '검토', '진행', '보류', '완료', '기타'
        ]
    
    if not research_statuses:
        research_statuses = ['기술개발', '시험평가', '제품개발', '연구']
    
    if not development_statuses:
        development_statuses = ['허가승인', '사업화', '규제개선', '개발']
    
    # 1. 모든 상태를 그룹으로 사용하여 프로젝트 조회
    status_groups = {}
    
    for status in all_project_statuses: 
        status_groups[status] = Project.query.options(
            selectinload(Project.products),
            selectinload(Project.tasks)
        ).filter(
            Project.is_completed == False,
            Project.status == status
        ).all()
    
    # 자료 메모 조회
    data_memos = Memo.query.options(
        joinedload(Memo.tag),
        joinedload(Memo.project)
    ).join(
        Project, Memo.project_id == Project.id, isouter=True
    ).join(
        Tag, Memo.tag_id == Tag.id, isouter=True
    ).filter(
        or_(
            Project.title == '자료',
            Tag.name == '자료'
        )
    ).order_by(
        Memo.created_at.desc()
    ).all()

    # '생각' 메모 조회
    thought_memos = get_thought_memos() 

    return render_template(     
        'index.html',    
        status_projects=status_groups,  
        project_statuses=all_project_statuses,
        
        # 🌟 새로운 계층 구조에서 추출한 분류 리스트 전달 🌟
        research_statuses_list=research_statuses, 
        development_statuses_list=development_statuses,
        other_statuses_list=other_statuses,  # Others 카테고리 추가
        
        settings=settings_data,  
        data_memos=data_memos,  
        thought_memos=thought_memos
    )

@app.route('/api/data_memos')
@login_required
def get_data_memos():
    """자료 프로젝트의 메모와 자료 태그가 달린 모든 메모를 반환"""
    try:
        # 1. '자료' 프로젝트의 ID 찾기
        data_project = Project.query.filter_by(title='자료').first()
        data_project_id = data_project.id if data_project else None

        # 2. '자료' 태그의 ID 찾기
        data_tag = Tag.query.filter_by(name='자료').first()
        data_tag_id = data_tag.id if data_tag else None

        # 3. 메모 불러오기
        data_memos = []
        
        if data_project_id or data_tag_id:
            conditions = []
            
            if data_project_id:
                conditions.append(Memo.project_id == data_project_id)
                
            if data_tag_id:
                conditions.append(Memo.tag_id == data_tag_id)
                
            if conditions:
                data_memos = Memo.query.options(
                    joinedload(Memo.tag),
                    joinedload(Memo.project)
                ).filter(or_(*conditions)).order_by(Memo.created_at.desc()).all()

        # 4. JSON 형식으로 변환
        memos_data = []
        for memo in data_memos:
            memo_dict = {
                'id': memo.id,
                'created_at': memo.created_at.strftime('%Y-%m-%d'),
                'content': memo.content,
                'tag': {'name': memo.tag.name if memo.tag else None},
                'project_title': memo.project.title if memo.project else None,
                'image_filename': bool(memo.image_filename),
                'pdf_filename': bool(memo.pdf_filename),
                'excel_filename': bool(memo.excel_filename),
                'ppt_filename': bool(memo.ppt_filename),
                'md_filename': bool(memo.md_filename),
                'html_filename': bool(memo.html_filename)
            }
            memos_data.append(memo_dict)

        # 5. 모든 태그 목록 가져오기
        all_tags = Tag.query.all()
        tags_data = [{'name': tag.name} for tag in all_tags]

        return jsonify({
            'memos': memos_data,
            'tags': tags_data
        })

    except Exception as e:
        app.logger.error(f"Error fetching data memos: {str(e)}")
        return jsonify({'error': str(e)}), 500                           

def get_thought_memos():
    """'생각' 태그가 달린 메모 목록을 캐시"""
    thought_tag = Tag.query.filter_by(name='생각').first()

    if not thought_tag:
        return []

    # 2. '생각' 태그 ID로 메모 불러오기 (Eager Loading 최적화)
    thought_memos = Memo.query.options(
        joinedload(Memo.tag),
        joinedload(Memo.project)
    ).filter(
        Memo.tag_id == thought_tag.id
    ).order_by(
        Memo.created_at.desc()
    ).all()

    return thought_memos

@app.route('/data/<path:filename>')
@login_required
def serve_data_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/infolink/<path:filename>')
@login_required
def serve_infolink_file(filename):
    return send_from_directory(app.config['INFOLINK_UPLOAD_FOLDER'], filename)

@app.route('/photo/<path:filename>')
@login_required
def serve_photo_file(filename):
    return send_from_directory(app.config['IMAGE_UPLOAD_FOLDER'], filename)

@app.route('/api/projects')
@login_required
def api_projects():
    """프로젝트 현황 데이터만 반환"""
    active_projects = Project.query.options(
        selectinload(Project.products)
    ).filter(Project.status != '완료').all()
    
    # 🌟 하드코딩된 리스트 대신 전역 상수를 사용하도록 수정 🌟
    # RESEARCH_STATUSES와 DEVELOPMENT_STATUSES는 이미 load_settings()에서 로드되어 전역 변수에 할당되었습니다.
    research_projects = [p for p in active_projects if p.status in RESEARCH_STATUSES]
    development_projects = [p for p in active_projects if p.status in DEVELOPMENT_STATUSES]

    # Other 프로젝트 목록 재정의 (전역 상수를 활용하여 동적으로 'Other' 목록 생성)
    ALL_CUSTOM_STATUSES = RESEARCH_STATUSES + DEVELOPMENT_STATUSES
    
    other_projects = [p for p in active_projects if p.status not in ALL_CUSTOM_STATUSES]
    
    def serialize_project(project):
        return {
            'id': project.id,
            'title': project.title,
            'status': project.status,
            'products': [{'name': p.name} for p in project.products]
        }
    
    return jsonify({
        'research': [serialize_project(p) for p in research_projects],
        'development': [serialize_project(p) for p in development_projects],
        'other': [serialize_project(p) for p in other_projects]
    })

@app.route('/api/tasks')
@login_required
def api_tasks():
    """Task 데이터만 반환"""
    # 완료되지 않은 Task만 조회 (성능 개선)
    todo_tasks = Task.query.options(
        joinedload(Task.project)
    ).filter(
        Task.status == 'To Do'
    ).order_by(
        Task.due_date.is_(None),  # NULL 값을 뒤로
        Task.due_date.asc()
    ).all()
    
    def serialize_task(task):
        # ... (이전과 동일한 직렬화 로직)
        return {
            'id': task.id,
            'title': task.title,
            'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else None, # 👈 start_date 추가
            'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
            'finished_date': task.finished_date.strftime('%Y-%m-%d') if task.finished_date else None, # 👈 finished_date 추가
            'status': task.status, # 👈 status 추가
            'comment': task.comment, # 👈 comment 추가
            'project': {
                'id': task.project.id,
                'title': task.project.title,
                'status': task.project.status
            } if task.project else None
        }
    
    return jsonify({
        'tasks': [serialize_task(t) for t in todo_tasks]
    })

@app.route('/api/completed')
@login_required
def api_completed():
    """
    is_completed=True 인 완료된 프로젝트만 반환합니다.
    """
    # 🌟 필터링 로직 수정: status 대신 is_completed=True 사용
    completed_projects = Project.query.options(
        selectinload(Project.products),
        selectinload(Project.tasks)
    ).filter(Project.is_completed == True).all() # <-- is_completed 필터 사용
    
    def serialize_completed_project(project):
        completed_tasks = [t for t in project.tasks if t.status == 'Done']
        total_tasks = len(project.tasks)
        
        return {
            'id': project.id,
            'title': project.title,
            'status': project.status, # <-- 상태 종류(예: '사업화', '개발') 추가
            'products': [p.name for p in project.products],
            'completed_tasks': len(completed_tasks),
            'total_tasks': total_tasks
        }
    
    return jsonify({
        'completed': [serialize_completed_project(p) for p in completed_projects]
    })

@app.route('/api/on-hold')
@login_required
def api_on_hold():
    """
    status='보류' 인 보류된 프로젝트만 반환합니다.
    """
    on_hold_projects = Project.query.options(
        selectinload(Project.products),
        selectinload(Project.tasks)
    ).filter(Project.status == '보류').all()
    
    def serialize_on_hold_project(project):
        completed_tasks = [t for t in project.tasks if t.status == 'Done']
        total_tasks = len(project.tasks)
        
        return {
            'id': project.id,
            'title': project.title,
            'description': project.description or '',
            'products': [p.name for p in project.products],
            'completed_tasks': len(completed_tasks),
            'total_tasks': total_tasks
        }
    
    return jsonify({
        'on_hold': [serialize_on_hold_project(p) for p in on_hold_projects]
    })


# 기존 admin 라우트를 projects로 변경
@app.route('/projects', methods=['GET', 'POST'])
@login_required
def projects():
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 프로젝트 생성, 수정, 상태 업데이트, 삭제 로직...
        if action == 'create_project':
            title = request.form.get('title')
            description = request.form.get('description')
            status = request.form.get('status')
            product_id = request.form.get('product')
            
            # 🌟 is_completed 값 처리: 체크되었으면 'True' 문자열, 아니면 None
            is_completed_form_value = request.form.get('is_completed')
            is_completed = (is_completed_form_value == 'True') # True 또는 False

            if status not in PROJECT_STATUSES:
                flash('잘못된 프로젝트 상태입니다.', 'error')
                return redirect(url_for('projects'))

            # is_completed 값을 포함하여 새 프로젝트 객체 생성
            new_project = Project(
                title=title, 
                description=description, 
                status=status,
                is_completed=is_completed # 🌟 값 할당 🌟
            )

            if product_id:
                selected_product = Product.query.get(product_id)
                new_project.products.append(selected_product)

            db.session.add(new_project)

        elif action == 'edit_project':
            project_id = request.form.get('project_id')
            project = Project.query.get_or_404(project_id)
            
            # 🌟 is_completed 값 처리: 체크되었으면 'True' 문자열, 아니면 None
            is_completed_form_value = request.form.get('is_completed')
            
            # 폼에서 값이 전송되었으면 True, 전송되지 않았으면 False로 설정
            project.is_completed = (is_completed_form_value == 'True') # 🌟 값 업데이트 🌟
            
            project.title = request.form.get('title')
            status = request.form.get('status')
            
            if status not in PROJECT_STATUSES:
                flash('잘못된 프로젝트 상태입니다.', 'error')
                return redirect(url_for('projects'))
                
            project.status = status
            product_id = request.form.get('product')

            if product_id:
                selected_product = Product.query.get(product_id)
                project.products = [selected_product]
            else:
                project.products = []

        elif action == 'update_status':
            project_id = request.form.get('project_id')
            project = Project.query.get_or_404(project_id)
            status = request.form.get('status')
            
            if status not in PROJECT_STATUSES:
                flash('잘못된 프로젝트 상태입니다.', 'error')
                return redirect(url_for('projects'))
                
            project.status = status

        elif action == 'delete_project':
            project_id = request.form.get('project_id')
            project = Project.query.get_or_404(project_id)
            
            for image in project.images:
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(image)

            for memo in project.memos:
                if memo.image_filename:
                    image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], memo.image_filename)
                    if os.path.exists(image_path):
                        os.remove(image_path)
                if memo.pdf_filename:
                    pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], memo.pdf_filename)
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                if memo.excel_filename:
                    excel_path = os.path.join(current_app.config['UPLOAD_FOLDER'], memo.excel_filename)
                    if os.path.exists(excel_path):
                        os.remove(excel_path)
                if memo.ppt_filename:
                    ppt_path = os.path.join(current_app.config['UPLOAD_FOLDER'], memo.ppt_filename)
                    if os.path.exists(ppt_path):
                        os.remove(ppt_path)
                db.session.delete(memo)
            
            db.session.delete(project)

        db.session.commit()
        return redirect(url_for('projects'))

    # 상태 필터링
    status_filter = request.args.get('status_filter', '')
    
    if status_filter and status_filter != 'All':
        # 필터링 로직: status_filter가 'is_completed'를 의미하는지 확인 (프론트엔드와 맞춰야 함)
        if status_filter == '완료': # 프론트엔드에서 '완료' 버튼이 눌렸을 때의 필터 값으로 가정
            projects = Project.query.filter_by(is_completed=True).all()
        elif status_filter not in PROJECT_STATUSES:
            flash('잘못된 필터 상태입니다.', 'error')
            projects = Project.query.all()
        else:
            projects = Project.query.filter_by(status=status_filter).all()
    else:
        # 'All' 또는 필터 없음
        projects = Project.query.all()

    products = Product.query.all()
    
    return render_template('projects.html',
                           projects=projects, 
                           products=products, 
                           status_filter=status_filter,
                           project_statuses=PROJECT_STATUSES)
                           
@app.route('/project/<int:project_id>')
@login_required
def project(project_id):
    project = Project.query.get_or_404(project_id)
    products = Product.query.all()
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    # Memo 쿼리 수행 - 페이지네이션 적용
    recent_memos = Memo.query.filter_by(project_id=project_id) \
                             .order_by(Memo.created_at.desc(), Memo.id.desc()) \
                             .limit(per_page).all()

    # datetime 처리 및 그룹화 로직
    for memo in recent_memos:
        if isinstance(memo.created_at, str):
            try:
                memo.created_at = datetime.fromisoformat(memo.created_at)
            except ValueError:
                memo.created_at = datetime.now()
        elif not isinstance(memo.created_at, datetime):
            memo.created_at = datetime.now()
        
        memo.created_date = memo.created_at.date()

    # date 기준으로 그룹화하고 정렬
    grouped_memos = []
    sorted_memos = sorted(recent_memos, key=attrgetter('created_date'), reverse=True)
    for date, memos in groupby(sorted_memos, key=attrgetter('created_date')):
        grouped_memos.append((date, list(memos)))

    view_mode = session.get('view_mode', 'note')
    tags = Tag.query.all()
    
    return render_template('project.html', project=project, products=products, 
                         grouped_memos=grouped_memos, recent_memos=recent_memos, 
                         tags=tags, view_mode=view_mode, project_statuses=PROJECT_STATUSES)

@app.route('/api/project/<int:project_id>/memos')
@login_required
def get_project_memos(project_id):
    page = request.args.get('page', 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page
    
    # 추가 메모 쿼리
    memos = Memo.query.filter_by(project_id=project_id) \
                      .order_by(Memo.created_at.desc(), Memo.id.desc()) \
                      .offset(offset) \
                      .limit(per_page + 1).all()  # 다음 페이지 존재 여부 확인을 위해 1개 더 가져옴
    
    has_more = len(memos) > per_page
    memos = memos[:per_page]  # 실제로는 per_page 개수만큼만 반환
    
    memo_list = []
    for memo in memos:
        created_at = memo.created_at
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif not isinstance(created_at, datetime):
            created_at = datetime.now()
            
        memo_list.append({
            'id': memo.id,
            'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'tag': memo.tag.name if memo.tag else '',
            'content': memo.content,
            'content_html': str(markdown_filter(memo.content)),
            'has_image': bool(memo.image_filename),
            'image_filename': memo.image_filename,
            'images': [img.filename for img in memo.images],
            'image_count': len(memo.images) if memo.images else (1 if memo.image_filename else 0),
            'has_pdf': bool(memo.pdf_filename),
            'pdf_filename': memo.pdf_filename,
            'has_excel': bool(memo.excel_filename),
            'excel_filename': memo.excel_filename,
            'has_ppt': bool(memo.ppt_filename),
            'ppt_filename': memo.ppt_filename,
            'has_md': bool(memo.md_filename),
            'md_filename': memo.md_filename,
            'html_filename': memo.html_filename
        })
    
    return jsonify({
        'memos': memo_list,
        'has_more': has_more
    })

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    for image in project.images:
        if not is_file_used_by_other_projects(image.file_path, project.id):
            delete_file(os.path.join(current_app.config['UPLOAD_FOLDER'], image.file_path))
    
    for link in project.links:
        if link.file_path and not is_file_used_by_other_projects(link.file_path, project.id):
            delete_file(os.path.join(current_app.config['UPLOAD_FOLDER'], link.file_path))
    
    db.session.delete(project)
    db.session.commit()
    
    return redirect(url_for('projects'))

@app.route('/edit_project_description/<int:project_id>', methods=['POST'])
@login_required
def edit_project_description(project_id):
    project = Project.query.get_or_404(project_id)
    project.description = request.form.get('description')
    db.session.commit()
    return redirect(url_for('project', project_id=project.id))

@app.route('/create_task/<int:project_id>', methods=['POST'])
@login_required
def create_task(project_id):
    title = request.form.get('title')
    start_date_str = request.form.get('start_date')

    # Initialize the new task with the title and project_id
    new_task = Task(
        title=title,
        project_id=project_id,
        start_date=datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.now(pytz.timezone('Asia/Seoul')).date(),
        due_date=None,   # Explicitly setting due_date to None
        finished_date=None  # Explicitly setting finished_date to None
    )

    # Add the new task to the session
    db.session.add(new_task)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error creating task: {e}")
        return jsonify({'message': 'An error occurred while creating the task'}), 500

    # Redirect to the project page after creating the task
    return redirect(url_for('project', project_id=project_id))

#creae_task 와 다르게 전체 변수들이 있음
@app.route('/new_task/<int:project_id>', methods=['GET', 'POST'])
@login_required
def new_task(project_id):
    if request.method == 'POST':
        title = request.form.get('title')
        status = request.form.get('status')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        due_date = request.form.get('due_date')
        due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        
        # Get comment (default to None if not provided)
        comment = request.form.get('comment') or None

        # Create new task
        new_task = Task(
            title=title,
            project_id=project_id,
            status=status,
            start_date=start_date,
            due_date=due_date,
            comment=comment
        )

        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect(url_for('project_tasks', project_id=project_id))
        except Exception as e:
            db.session.rollback()
            return str(e), 500
            
    # GET 요청의 경우 new_task.html 템플릿 렌더링
    project = Project.query.get_or_404(project_id)
    return render_template('new_task.html', project=project)

@app.route('/view_task/<int:task_id>', methods=['GET'])
@login_required
def view_task(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('view_task.html', task=task)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.status = request.form.get('status')
        task.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        due_date = request.form.get('due_date')
        task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        
        # Update comment (default to None if not provided)
        task.comment = request.form.get('comment') or None

        try:
            db.session.commit()
            return redirect(url_for('project_tasks', project_id=task.project_id))
        except Exception as e:
            db.session.rollback()
            return str(e), 500
    return render_template('edit_task.html', task=task)

@app.route('/update_task/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    """
    특정 Task의 세부 정보를 업데이트하고 Index 페이지로 리다이렉션합니다.
    """
    # 1. Task 객체 조회
    task = Task.query.get_or_404(task_id)
    form = request.form
    
    # (선택 사항: Task 소유권 확인 로직)
    # if task.user_id != current_user.id:
    #     flash("권한이 없습니다.", "danger")
    #     return redirect(url_for('index'))

    try:
        # 2. 폼 데이터로 Task 필드 업데이트
        task.title = form.get('title')
        task.status = form.get('status')
        task.comment = form.get('comment')

        # 날짜 문자열을 Python의 date 객체로 변환
        start_date_str = form.get('start_date')
        due_date_str = form.get('due_date')
        finished_date_str = form.get('finished_date')

        task.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        
        # 상태가 'Done'일 때 완료 날짜 업데이트 로직
        if task.status == 'Done':
            # 폼에서 finished_date가 왔다면 사용
            if finished_date_str:
                task.finished_date = datetime.strptime(finished_date_str, '%Y-%m-%d').date()
            # finished_date가 없고 기존에 설정된 것도 없다면 오늘 날짜로 설정
            elif not task.finished_date:
                task.finished_date = datetime.now(KST).date()
        else: # 'To Do' 상태로 변경되면 완료 날짜 초기화
            task.finished_date = None

        # 3. DB 커밋
        db.session.commit()
        # flash("Task가 성공적으로 업데이트되었습니다.", "success")

        # 4. 리다이렉션: Index 페이지로 돌아가기
        return_url = form.get('return_url')
        
        # return_url이 있다면 해당 URL로 리다이렉트 (대부분 index 페이지가 될 것입니다)
        if return_url:
            return redirect(return_url)
        else:
            # return_url이 없는 경우, 기본 Index 페이지로 리다이렉트
            return redirect(url_for('index'))
            
    except Exception as e:
        db.session.rollback()
        # flash(f"Task 업데이트 중 오류가 발생했습니다: {e}", "danger")
        
        # 오류 발생 시에도 Index 페이지로 리다이렉트하여 사용자에게 메시지를 전달 (flash 사용 가정)
        return redirect(url_for('index'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    try:
        task = Task.query.get_or_404(task_id)
        project_id = task.project_id  # 삭제 전에 project_id 저장
        db.session.delete(task)
        db.session.commit()
        
        # AJAX 요청인지 확인 (index.html에서 fetch로 호출하는 경우)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                  request.headers.get('Content-Type') == 'application/json'
        
        if is_ajax:
            # AJAX 요청: JSON 응답 반환
            return jsonify({'success': True, 'message': 'Task가 삭제되었습니다.'}), 200
        
        # 일반 form submit: 프로젝트 페이지로 리다이렉트
        if project_id:
            return redirect(url_for('project', project_id=project_id))
        else:
            return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        
        # 에러 처리도 요청 타입에 따라 다르게
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                  request.headers.get('Content-Type') == 'application/json'
        
        if is_ajax:
            return jsonify({'success': False, 'error': str(e)}), 500
        
        flash(f'Task 삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(request.referrer or url_for('index'))

@app.route('/project_tasks/<int:project_id>')
@login_required
def project_tasks(project_id):
    project = Project.query.get_or_404(project_id)

    # 완료되지 않은 태스크가 먼저 오도록 정렬하고, 완료된 태스크를 필터링
    todo_tasks = Task.query.filter_by(project_id=project_id, status='To Do').order_by(Task.due_date.asc()).all()
    done_tasks = Task.query.filter_by(project_id=project_id, status='Done').order_by(Task.finished_date.desc()).all()

    return render_template('project_tasks.html', project=project, todo_tasks=todo_tasks, done_tasks=done_tasks)

@app.route('/update_task_status', methods=['POST'])
@login_required
def update_task_status():
    data = request.get_json()
    task_id = data.get('task_id')
    status = data.get('status')

    # task_id가 제공되지 않았을 경우의 예외 처리 추가
    if not task_id:
        return jsonify({'message': 'Task ID is missing'}), 400

    task = Task.query.get(task_id)
    if task:
        task.status = status

        if status == 'Done':
            # 완료 시 현재 날짜 기록
            task.finished_date = datetime.now(pytz.timezone('Asia/Seoul')).date()
        else:
            task.finished_date = None

        try:
            db.session.commit()
            
            # 🎯 캐시 무효화 로직 삭제됨 (cache.delete_memoized('index'))
            # 캐시를 사용하지 않으므로, 데이터 변경 후 별도의 캐시 처리 로직이 필요 없습니다.

            # 성공적인 JSON 응답을 반환합니다. (클라이언트 JavaScript가 이 응답을 받아 새로고침해야 함)
            return jsonify({'message': 'Task status updated successfully (No cache clear)'}), 200
            
        except Exception as e:
            db.session.rollback()
            # DB 오류 발생 시 500 응답
            app.logger.error(f"Task status update failed: {str(e)}")
            return jsonify({'message': 'An error occurred while updating the task in DB', 'error': str(e)}), 500
    else:
        # Task를 찾지 못했을 경우 404 응답
        return jsonify({'message': 'Task not found'}), 404

@app.route('/update_task_comment/<int:task_id>', methods=['POST'])
@login_required
def update_task_comment(task_id):
    task = Task.query.get(task_id)
    if task:
        task.comment = request.form.get('comment')
        db.session.commit()
        return redirect(url_for('project_tasks', project_id=task.project_id))
    else:
        return jsonify({'message': 'Task not found'}), 404

def slugify(value):
    """한글 파일명을 ASCII 문자열로 변환하기 위한 함수"""
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

def secure_filename_with_unicode(filename):
    # 파일명에서 디렉토리 구분자 제거
    filename = os.path.basename(filename)
    # 널 바이트 제거
    filename = filename.replace('\x00', '')
    # 위험한 문자 제거 (필요에 따라 확장 가능)
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 앞뒤 공백 제거
    filename = filename.strip()
    # 파일명 길이 제한 (예: 255바이트 이하로 제한)
    filename = filename[:255]
    return filename

def get_file_extension(filename):
    # 마지막 마침표 이후의 문자열을 확장자로 간주
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    else:
        return ''

# 메모관련
@app.route('/create_memo', methods=['GET', 'POST'])
@login_required
def create_memo():
    parent_id = request.args.get('parent_id', type=int)
    project_id = request.args.get('project_id', type=int)

    if not project_id:
        general_project = Project.query.filter_by(title='일반업무').first()
        if general_project:
            project_id = general_project.id

    parent_memo = None
    if parent_id:
        parent_memo = Memo.query.get_or_404(parent_id)

    tags = Tag.query.all()
    products = Product.query.all()

    if request.method == 'POST':
        content = request.form.get('content')
        created_at_str = request.form.get('created_at')
        
        # 폼에서 전달받은 'next_url'을 가져옵니다.
        next_url = request.form.get('next_url')

        try:
            created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            created_at = datetime.now()
        
        tag_id = request.form.get('tag')
        product_id = request.form.get('product')
        form_project_id = request.form.get('project_id')
        image_option = request.form.get('image_option', 'file')
        
        if form_project_id:
            try:
                project_id = int(form_project_id)
            except (ValueError, TypeError):
                pass
        
        if not project_id:
            general_project = Project.query.filter_by(title='일반업무').first()
            if general_project:
                project_id = general_project.id
        
        if product_id:
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                product_id = None
        else:
            product_id = None
        
        if tag_id:
            try:
                tag_id = int(tag_id)
            except (ValueError, TypeError):
                tag_id = None
        else:
            tag_id = None
            
        new_memo = Memo(
            content=content,
            created_at=created_at,
            project_id=project_id,
            product_id=product_id,
            tag_id=tag_id,
            parent_id=parent_id
        )
        
        try:
            if image_option == 'file':
                files = request.files.getlist('file')
                
                # 이미지 파일과 기타 파일 분리
                image_files = []
                other_files = []
                
                for file in files:
                    if file and file.filename:
                        filename = secure_filename_with_unicode(file.filename)
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                            image_files.append(file)
                        else:
                            other_files.append(file)
                
                # 이미지 개수 제한 확인 (최대 5장)
                if len(image_files) > 5:
                    flash("이미지는 최대 5장까지만 업로드할 수 있습니다.", "error")
                    return redirect(request.url)

                # 이미지 저장 처리
                for i, file in enumerate(image_files):
                    original_filename = file.filename
                    sanitized_filename = secure_filename_with_unicode(original_filename)
                    filename = f"{uuid.uuid4().hex[:8]}_{sanitized_filename}"
                    
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    # MemoImage 모델에 저장
                    memo_image = MemoImage(memo=new_memo, filename=filename)
                    db.session.add(memo_image)
                    
                    # 첫 번째 이미지는 대표 이미지로 설정 (레거시 호환성)
                    if i == 0:
                        new_memo.image_filename = filename
                        new_memo.original_filename = original_filename

                # 기타 파일 저장 처리 (기존 로직 유지 - 각 타입별 1개만)
                for file in other_files:
                    original_filename = file.filename
                    sanitized_filename = secure_filename_with_unicode(original_filename)
                    filename = f"{uuid.uuid4().hex[:8]}_{sanitized_filename}"
                    
                    _, file_extension = os.path.splitext(sanitized_filename)
                    file_extension = file_extension.lower()
                    
                    if file_extension == '.pdf':
                        new_memo.pdf_filename = filename
                    elif file_extension in ['.xls', '.xlsx']:
                        new_memo.excel_filename = filename
                    elif file_extension in ['.ppt', '.pptx']:
                        new_memo.ppt_filename = filename
                    elif file_extension == '.md':
                        new_memo.md_filename = filename
                    elif file_extension in ['.html', '.htm']:
                        new_memo.html_filename = filename    
                    
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
            elif image_option == 'paste':
                pasted_image_data = request.form.get('pasted_image_data')
                if pasted_image_data:
                    if 'base64,' in pasted_image_data:
                        pasted_image_data = pasted_image_data.split('base64,')[1]
                    
                    image_data = base64.b64decode(pasted_image_data)
                    image = Image.open(BytesIO(image_data))
                    
                    filename = f"pasted_image_{uuid.uuid4().hex[:8]}.png"
                    new_memo.image_filename = filename
                    new_memo.original_filename = "붙여넣은 이미지"
                    
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(file_path, 'PNG')
                    
        except Exception as e:
            flash(f"파일 처리 중 오류가 발생했습니다: {str(e)}", "error")
            app.logger.error(f"File processing error in create_memo: {str(e)}")
            return redirect(request.url)
        
        try:
            db.session.add(new_memo)
            db.session.commit()
            flash("메모가 성공적으로 생성되었습니다.", "success")
            
            # 다음 페이지로 리디렉션합니다. next_url이 있다면 그곳으로, 없다면 search_memos로 갑니다.
            return redirect(next_url or url_for('search_memos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"메모 저장 중 오류가 발생했습니다: {str(e)}", "error")
            app.logger.error(f"Database error in create_memo: {str(e)}")
            return redirect(request.url)
            
    relevant_projects = Project.query.filter(Project.status != '완료').all()
    general_project = Project.query.filter_by(title='일반업무').first()
    if general_project and general_project not in relevant_projects:
        relevant_projects.append(general_project)
    
    return render_template('create_memo.html', 
                            parent_memo=parent_memo, 
                            tags=Tag.query.all(), 
                            products=Product.query.all(), 
                            projects=relevant_projects,
                            project_id=project_id,
                            project_statuses=PROJECT_STATUSES)

@app.route('/edit_memo/<int:memo_id>', methods=['GET', 'POST'])
@login_required
def edit_memo(memo_id):
    memo = Memo.query.get_or_404(memo_id)
    tags = Tag.query.all()

    # 🌟 수정된 프로젝트 검색 로직 🌟
    # 1. is_completed가 True인 프로젝트만 필터링하여 가져옵니다.
    completed_projects = Project.query.filter(Project.is_completed == False).all()

    relevant_projects = list(completed_projects)
    
    # 2. 현재 메모가 연결된 프로젝트를 가져와 목록에 추가합니다.
    # 이 로직은 해당 프로젝트가 완료되지 않았더라도 편집을 위해 목록에 포함되도록 합니다.
    if memo.project_id:
        existing_project = Project.query.get(memo.project_id)
        # 현재 메모의 프로젝트가 완료된 목록에 없으면 추가
        if existing_project and existing_project not in relevant_projects:
            relevant_projects.append(existing_project)
    
    # 프로젝트 이름 순으로 정렬 (선택 사항)
    relevant_projects.sort(key=lambda p: p.title)

    products = Product.query.all()
    
    if request.method == 'POST':
        try:
            # 메모 내용 및 생성 시간 업데이트
            memo.content = request.form.get('content', '')
            created_at_str = request.form.get('created_at')
            if created_at_str:
                memo.created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M')
            
            # 태그, 프로젝트, 제품 ID 처리
            tag_id = request.form.get('tag')
            project_id = request.form.get('project')
            product_id = request.form.get('product')
            
            memo.tag_id = int(tag_id) if tag_id else None
            memo.project_id = int(project_id) if project_id else None
            memo.product_id = int(product_id) if product_id else None
            
            # 부모 메모와의 연관성 해제 처리
            if request.form.get('remove_parent') == 'on':
                memo.parent = None

            # 파일 삭제 처리 함수
            def delete_file(file_key, file_attr):
                if request.form.get(file_key) and getattr(memo, file_attr):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], getattr(memo, file_attr))
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        setattr(memo, file_attr, None)
                        # 대표 이미지가 삭제되면 original_filename도 초기화 (단, 다른 파일이 아닐 경우)
                        if file_attr == 'image_filename':
                             memo.original_filename = None 
                    except OSError as e:
                        flash(f"파일 삭제 중 오류 발생: {e}", "error")

            # 기존 단일 파일 삭제 처리
            for file_type in ['image', 'pdf', 'excel', 'ppt', 'md', 'html']:
                delete_file(f'delete_{file_type}', f'{file_type}_filename')

            # MemoImage 다중 이미지 삭제 처리
            delete_image_ids = request.form.getlist('delete_memo_image_ids')
            if delete_image_ids:
                for img_id in delete_image_ids:
                    image_to_delete = MemoImage.query.get(img_id)
                    if image_to_delete and image_to_delete.memo_id == memo.id:
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_to_delete.filename)
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            db.session.delete(image_to_delete)
                        except OSError as e:
                            flash(f"이미지 삭제 중 오류 발생: {e}", "error")

            # 이미지/파일 업로드 처리
            image_option = request.form.get('image_option', 'file')
            
            if image_option == 'paste':
                # 붙여넣은 이미지 처리 (기존 로직 유지 - 단일 이미지) - TODO: 붙여넣기도 다중 지원? 현재는 단일 유지
                pasted_image_data = request.form.get('pasted_image_data')
                if pasted_image_data:
                    try:
                        if 'base64,' in pasted_image_data:
                            image_data = pasted_image_data.split('base64,')[1]
                        else:
                            image_data = pasted_image_data
                        
                        image_binary = base64.b64decode(image_data)
                        image = Image.open(BytesIO(image_binary))
                        
                        filename = f"pasted_image_{uuid.uuid4().hex[:8]}.png"
                        
                        # 기존 이미지 파일이 있다면 삭제 (image_filename 사용 시)
                        if memo.image_filename:
                            old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], memo.image_filename)
                            try:
                                if os.path.exists(old_file_path):
                                    os.remove(old_file_path)
                            except OSError:
                                pass
                        
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        image.save(file_path, 'PNG')
                        
                        memo.image_filename = filename
                        memo.original_filename = "붙여넣은 이미지"
                        
                        # 붙여넣은 이미지도 MemoImage에 추가
                        memo_image = MemoImage(memo=memo, filename=filename)
                        db.session.add(memo_image)

                    except Exception as e:
                        flash(f"이미지 처리 중 오류 발생: {e}", "error")
                        return redirect(request.url)
                
            else:
                # 다중 파일 업로드 처리
                files = request.files.getlist('file')
                
                image_files = []
                other_files = []
                
                for file in files:
                    if file and file.filename:
                        filename = secure_filename_with_unicode(file.filename)
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                            image_files.append(file)
                        else:
                            other_files.append(file)
                
                # 이미지 개수 확인
                current_image_count = len(memo.images)
                # 삭제할 이미지는 이미 세션에서 deleted 상태일 것이나 commit 전이라 count에 포함될 수 있음.
                # 그러나 commit은 마지막에 하므로, 여기서는 삭제 요청된 ID를 제외하고 계산하거나,
                # 간단히 "추가되는 이미지 + 현재 이미지 - 삭제할 이미지"로 계산
                
                deleted_count = len(delete_image_ids)
                if current_image_count - deleted_count + len(image_files) > 5:
                    flash(f"이미지는 최대 5장까지만 저장할 수 있습니다. (현재: {current_image_count}장, 삭제: {deleted_count}장, 추가: {len(image_files)}장)", "error")
                    return redirect(request.url)

                # 이미지 저장 및 MemoImage 추가
                for i, file in enumerate(image_files):
                    original_filename = file.filename
                    sanitized_filename = secure_filename_with_unicode(original_filename)
                    filename = f"{uuid.uuid4().hex[:8]}_{sanitized_filename}"
                    
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    memo_image = MemoImage(memo=memo, filename=filename)
                    db.session.add(memo_image)
                    
                    # 만약 대표 이미지가 없다면 첫 번째 추가된 이미지를 대표로 설정
                    if not memo.image_filename:
                        memo.image_filename = filename
                        memo.original_filename = original_filename

                # 기타 파일 처리 (기존 로직: 덮어쓰기)
                if other_files:
                    # 여러 개여도 마지막 것만 각 타입별로 저장됨 (기존 로직 특성)
                    for file in other_files:
                        original_filename = file.filename
                        sanitized_filename = secure_filename_with_unicode(original_filename)
                        filename = f"{uuid.uuid4().hex[:8]}_{sanitized_filename}"
                        
                        _, file_extension = os.path.splitext(sanitized_filename)
                        file_extension = file_extension.lower()
                        
                        file_type_mapping = {
                            'pdf': (['.pdf'], 'pdf_filename'),
                            'excel': (['.xls', '.xlsx'], 'excel_filename'),
                            'ppt': (['.ppt', '.pptx'], 'ppt_filename'),
                            'markdown': (['.md'], 'md_filename'),
                            'html': (['.html', '.htm'], 'html_filename')
                        }

                        file_attr = None
                        for type_key, (extensions, attr) in file_type_mapping.items():
                            if file_extension in extensions:
                                file_attr = attr
                                break
                        
                        if file_attr:
                            # 기존 파일 삭제
                            old_filename = getattr(memo, file_attr)
                            if old_filename:
                                old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], old_filename)
                                try:
                                    if os.path.exists(old_file_path):
                                        os.remove(old_file_path)
                                except OSError:
                                    pass
                            
                            setattr(memo, file_attr, filename)
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            file.save(file_path)

            db.session.commit()
            flash("메모가 성공적으로 수정되었습니다.", "success")
            return redirect(url_for('view_memo', memo_id=memo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"메모 수정 중 오류가 발생했습니다: {e}", "error")
            return redirect(request.url)

    return render_template('edit_memo.html',  
                       memo=memo,  
                       tags=tags,  
                       projects=relevant_projects, # 🌟 수정된 프로젝트 목록 전달 🌟
                       products=products,
                       project_statuses=PROJECT_STATUSES)

@app.route('/get_products/<int:project_id>')
@login_required
def get_products(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify([{"id": p.id, "name": p.name} for p in project.products])

@app.route('/get_all_products')
@login_required
def get_all_products():
    products = Product.query.all()
    return jsonify([{"id": p.id, "name": p.name} for p in products])
@app.route('/view_memo/<int:memo_id>', methods=['GET'])
@login_required
def view_memo(memo_id):
    memo = Memo.query.get_or_404(memo_id)

    # 메모에 직접 연결된 개별 Product 객체 조회 (일반정보 프로젝트에 해당)
    memo_product = Product.query.get(memo.product_id) if memo.product_id else None

    # 프로젝트에 연결된 제품들 조회
    project_products = []
    if memo.project and memo.project.products:
        project_products = memo.project.products

    # 부모 메모 조회
    parent_memo = memo.parent

    # Markdown 파일 내용 로드
    md_content = load_markdown_content(memo)

    # 뷰 모드 가져오기
    view_mode = session.get('view_mode', 'note')

    return render_template(
        'view_memo.html',
        memo=memo,
        parent_memo=parent_memo,
        md_content=md_content,        
        memo_product=memo_product,  # 개별 저장된 product 정보
        project_products=project_products,  # 프로젝트 연관 제품 리스트
        view_mode=view_mode
    )


def load_markdown_content(memo):
    """메모의 마크다운 파일 내용을 로드하는 함수"""
    if not memo.md_filename:
        return None
    
    md_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], memo.md_filename)
    try:
        if os.path.exists(md_file_path):
            with open(md_file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except IOError as e:
        current_app.logger.error(f"마크다운 파일 읽기 오류: {e}")
    return None

@app.route('/view_html/<int:memo_id>')
@login_required
def view_html_file(memo_id):
    """
    HTML 파일을 다운로드하지 않고 브라우저에 인라인으로 표시합니다.
    """
    # 🚨 DB 마이그레이션이 완료되었다는 가정 하에, 여기서 문제가 발생할 확률은 낮습니다.
    memo = Memo.query.get_or_404(memo_id) 
    filename = memo.html_filename

    if not filename:
        flash('이 메모에 연결된 HTML 파일이 없습니다.', 'warning')
        if memo.project_id:
            return redirect(url_for('project', project_id=memo.project_id))
        else:
            return redirect(url_for('search_memos'))

    # current_app을 사용하도록 수정
    upload_folder = current_app.config['UPLOAD_FOLDER'] 
    
    safe_filename = secure_filename_with_unicode(filename)

    file_path = os.path.join(upload_folder, safe_filename) # 수정: app.config 대신 upload_folder 변수 사용

    if not os.path.exists(file_path):
        flash('파일을 찾을 수 없습니다.', 'error')
        if memo.project_id:
            return redirect(url_for('project', project_id=memo.project_id))
        else:
            return redirect(url_for('search_memos'))
    
    # MIME Type 설정
    mimetype = mimetypes.guess_type(safe_filename)[0] or 'text/html'
    
    # send_from_directory에 current_app의 config 사용
    return send_from_directory(
        upload_folder, # 수정: app.config['UPLOAD_FOLDER'] 대신 변수 사용
        safe_filename,
        as_attachment=False,
        mimetype=mimetype
    )

# Updated function to delete a memo, including handling file deletions
@app.route('/delete_memo/<int:memo_id>', methods=['POST'])
@login_required
def delete_memo(memo_id):
    memo = Memo.query.get_or_404(memo_id)

    # Delete associated files if they exist
    def remove_file(file_attr):
        file_path = getattr(memo, file_attr)
        if file_path:
            file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

    # Remove all associated files
    remove_file('image_filename')
    remove_file('pdf_filename')
    remove_file('excel_filename')
    remove_file('ppt_filename')
    remove_file('md_filename')
    remove_file('html_filename')

    # Delete the memo from the database
    db.session.delete(memo)
    db.session.commit()

    flash('Memo and associated files were successfully deleted.')

    # If the memo doesn't have a project, redirect to a default page
    if memo.project_id:
        return redirect(url_for('project', project_id=memo.project_id))
    else:
        return redirect(url_for('memo_list'))


@app.route('/add_memo', methods=['GET', 'POST'])
@login_required
def add_memo():
    parent_id = request.args.get('parent_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    # 프로젝트 ID가 없는 경우 '일반업무' 프로젝트를 기본값으로 사용
    if not project_id:
        general_project = Project.query.filter_by(title='일반업무').first()
        if general_project:
            project_id = general_project.id
        else:
            # '일반업무' 프로젝트가 없는 경우 생성 (기본 상태는 '기타'로 설정)
            general_project = Project(
                title='일반업무', 
                description='일반적인 업무를 위한 기본 프로젝트',
                status='기타'  # PROJECT_STATUSES에 포함된 상태 사용
            )
            db.session.add(general_project)
            db.session.commit()
            project_id = general_project.id
    
    parent_memo = None
    if parent_id:
        parent_memo = Memo.query.get_or_404(parent_id)
    
    tags = Tag.query.all()
    products = Product.query.all()
    
    # 활성 상태의 프로젝트만 선택 가능하도록 필터링
    active_statuses = ['진행', '검토', '시험', '인허가']
    projects = Project.query.filter(Project.status.in_(active_statuses)).all()
    
    # 현재 선택된 프로젝트가 활성 상태가 아니면 목록에 추가
    if project_id:
        current_project = Project.query.get(project_id)
        if current_project and current_project not in projects:
            projects.append(current_project)
    
    if request.method == 'POST':
        content = request.form.get('content')
        created_at_str = request.form.get('created_at')
        
        try:
            created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            created_at = datetime.now()
            
        tag_id = request.form.get('tag')
        product_id = request.form.get('product')
        form_project_id = request.form.get('project_id')
        image_option = request.form.get('image_option', 'file')
        
        # 폼에서 전달된 project_id가 있으면 사용
        if form_project_id:
            try:
                project_id = int(form_project_id)
            except (ValueError, TypeError):
                # project_id가 유효하지 않으면 기존 값 유지
                pass
        
        # 여전히 project_id가 없으면 '일반업무' 프로젝트 사용
        if not project_id:
            general_project = Project.query.filter_by(title='일반업무').first()
            if general_project:
                project_id = general_project.id
        
        # product_id 처리
        if product_id:
            try:
                product_id = int(product_id)
            except (ValueError, TypeError):
                product_id = None
        else:
            product_id = None
            
        # tag_id 처리
        if tag_id:
            try:
                tag_id = int(tag_id)
            except (ValueError, TypeError):
                tag_id = None
        else:
            tag_id = None
        
        new_memo = Memo(
            content=content,
            created_at=created_at,
            project_id=project_id,
            product_id=product_id,
            tag_id=tag_id,
            parent_id=parent_id
        )
        
        # 이미지/파일 처리
        try:
            if image_option == 'file':
                # 기존 파일 업로드 처리
                file = request.files.get('file')
                if file and file.filename:
                    original_filename = file.filename
                    sanitized_filename = secure_filename_with_unicode(original_filename)
                    filename = f"{uuid.uuid4().hex[:8]}_{sanitized_filename}"
                    new_memo.original_filename = original_filename
                    
                    # 파일 확장자 추출 및 소문자로 변환
                    _, file_extension = os.path.splitext(sanitized_filename)
                    file_extension = file_extension.lower()
                    
                    # 파일 확장자에 따른 속성 설정
                    if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                        new_memo.image_filename = filename
                    elif file_extension == '.pdf':
                        new_memo.pdf_filename = filename
                    elif file_extension in ['.xls', '.xlsx']:
                        new_memo.excel_filename = filename
                    elif file_extension in ['.ppt', '.pptx']:
                        new_memo.ppt_filename = filename
                    elif file_extension == '.md':
                        new_memo.md_filename = filename
                    elif file_extension in ['.html', '.htm']:
                        new_memo.html_filename = filename
                    else:
                        flash("지원하지 않는 파일 확장자입니다.", "error")
                        return redirect(request.url)
                    
                    # 파일을 업로드 폴더에 저장
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
            elif image_option == 'paste':
                # 붙여넣은 이미지 처리
                pasted_image_data = request.form.get('pasted_image_data')
                if pasted_image_data:
                    # base64 데이터에서 실제 이미지 데이터 추출
                    if 'base64,' in pasted_image_data:
                        pasted_image_data = pasted_image_data.split('base64,')[1]
                    
                    # 이미지 데이터 디코딩
                    image_data = base64.b64decode(pasted_image_data)
                    image = Image.open(BytesIO(image_data))
                    
                    # 파일명 생성
                    filename = f"pasted_image_{uuid.uuid4().hex[:8]}.png"
                    new_memo.image_filename = filename
                    new_memo.original_filename = "붙여넣은 이미지"
                    
                    # 이미지 저장
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(file_path, 'PNG')
        
        except Exception as e:
            flash(f"파일 처리 중 오류가 발생했습니다: {str(e)}", "error")
            return redirect(request.url)
        
        try:
            db.session.add(new_memo)
            db.session.commit()
            flash("메모가 성공적으로 생성되었습니다.", "success")
            return redirect(url_for('view_memo', memo_id=new_memo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"메모 저장 중 오류가 발생했습니다: {str(e)}", "error")
            return redirect(request.url)
        
    return render_template('add_memo.html', 
                           parent_memo=parent_memo, 
                           tags=tags, 
                           products=products, 
                           projects=projects, 
                           project_id=project_id,
                           project_statuses=PROJECT_STATUSES)

# 최적화된 search_memos 함수
@app.route('/search_memos', methods=['GET', 'POST'])
def search_memos():
    try:
        # 페이지네이션 파라미터
        page = request.args.get('page', 1, type=int)
        per_page = 50  # 100에서 50으로 줄여서 응답 속도 개선
        
        # 검색 필터 값 받기
        content_query = request.args.get('content', '').strip().lower()
        tag_query = request.args.get('tag', '').strip().lower()
        project_query = request.args.get('project', '').strip().lower()
        product_query = request.args.get('product', '').strip().lower()
        
        # 태그 타입 확인 (todo 또는 data)
        tag_type = request.args.get('tag_type')
        
        # 필요한 모든 데이터 먼저 조회
        tags = Tag.query.all()
        projects = Project.query.all()
        products = Product.query.all()

        # Product 테이블에 대한 별칭 설정
        memo_product = aliased(Product)
        project_product = aliased(Product)
        
        # Memo에 대한 기본 쿼리 생성 (eager loading 최적화)
        query = Memo.query.options(
            joinedload(Memo.tag),
            joinedload(Memo.project),
            joinedload(Memo.product)
        )
        
        # 태그 타입 필터링 최적화
        if tag_type == 'todo':
            query = query.join(Tag).filter(Tag.name == 'Todo')
        elif tag_type == 'data':
            query = query.join(Tag).filter(Tag.name == '자료')
            
        # 검색어 AND 조건 처리 최적화
        if content_query:
            search_terms = [term.strip() for term in content_query.split('&&')]
            for term in search_terms:
                query = query.filter(Memo.content.ilike(f"%{term}%"))
                
        if tag_query:
            if not (tag_type == 'todo' or tag_type == 'data'):  # 이미 join되지 않은 경우에만
                query = query.join(Tag)
            query = query.filter(Tag.name.ilike(f"%{tag_query}%"))
        
        if project_query:
            query = query.join(Project).filter(Project.title.ilike(f"%{project_query}%"))
        
        if product_query:
            query = query.outerjoin(memo_product, Memo.product).outerjoin(Project).outerjoin(
                project_product, Project.products).filter(
                or_(
                    memo_product.name.ilike(f"%{product_query}%"),
                    project_product.name.ilike(f"%{product_query}%")
                )
            )

        # 정렬 적용
        query = query.order_by(Memo.created_at.desc(), Memo.id.desc())
        
        # 전체 결과 개수
        total_count = query.count()
        
        # 페이지네이션 적용
        start = (page - 1) * per_page
        memos = query.offset(start).limit(per_page).all()

        # 관련 메모 확인 최적화 (배치 처리)
        memo_ids = [memo.id for memo in memos]
        child_memo_counts = {}
        parent_memo_ids = {}
        
        if memo_ids:
            # 자식 메모 개수를 한 번의 쿼리로 조회
            child_counts = db.session.query(
                Memo.parent_id, 
                func.count(Memo.id)
            ).filter(
                Memo.parent_id.in_(memo_ids)
            ).group_by(Memo.parent_id).all()
            
            child_memo_counts = dict(child_counts)
            
            # 부모 메모 정보를 한 번의 쿼리로 조회
            parent_info = db.session.query(
                Memo.id, Memo.parent_id
            ).filter(Memo.id.in_(memo_ids)).all()
            
            parent_memo_ids = {memo_id: parent_id for memo_id, parent_id in parent_info}

        # AJAX 요청 처리
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            memo_data = []
            for memo in memos:
                has_children = memo.id in child_memo_counts
                has_parent = parent_memo_ids.get(memo.id) is not None
                
                relation_type = None
                if has_children and has_parent:
                    relation_type = "both"
                elif has_children:
                    relation_type = "parent"
                elif has_parent:
                    relation_type = "child"
                
                memo_data.append({
                    'id': memo.id,
                    'datetime': memo.created_at.isoformat(),
                    'date': memo.created_at.strftime('%Y-%m-%d'),
                    'content': memo.content,
                    'tag': memo.tag.name if memo.tag else '',
                    'project': memo.project.title if memo.project else '',
                    'product': memo.product.name if memo.product else '',
                    'image': memo.image_filename,
                    'image_count': len(memo.images) if memo.images else (1 if memo.image_filename else 0),
                    'file': memo.pdf_filename or memo.excel_filename or memo.ppt_filename or memo.md_filename or memo.html_filename,
                    'has_related_memos': has_children or has_parent,
                    'relation_type': relation_type,
                    'source': 'Memo'
                })
            
            has_next = total_count > (page * per_page)
            return jsonify({
                'memos': memo_data,
                'has_next': has_next,
                'total_count': total_count,
                'current_page': page
            })

        # 일반 페이지 요청 처리
        memo_data = []
        for memo in memos:
            has_children = memo.id in child_memo_counts
            has_parent = parent_memo_ids.get(memo.id) is not None
            
            relation_type = None
            if has_children and has_parent:
                relation_type = "both"
            elif has_children:
                relation_type = "parent"
            elif has_parent:
                relation_type = "child"
            
            memo_data.append({
                'id': memo.id,
                'datetime': memo.created_at,
                'date': memo.created_at.strftime('%Y-%m-%d'),
                'content': memo.content,
                'tag': memo.tag.name if memo.tag else '',
                'project': memo.project.title if memo.project else '',
                'product': memo.product.name if memo.product else '',
                'image': memo.image_filename,
                'image_count': len(memo.images) if memo.images else (1 if memo.image_filename else 0),
                'file': memo.pdf_filename or memo.excel_filename or memo.ppt_filename or memo.md_filename or memo.html_filename,
                'has_related_memos': has_children or has_parent,
                'relation_type': relation_type,
                'source': 'Memo'
            })
        
        # 검색 결과 렌더링
        return render_template('search_results.html',
                             memos=memo_data,
                             tags=tags,
                             projects=projects,
                             products=products,
                             has_next=(total_count > per_page))

    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/memo_table')
@login_required
def memo_table():
    memos = Memo.query.order_by(Memo.created_at.desc()).all()
    memo_data = []
    for memo in memos:
        project = memo.project  # 메모에 연결된 프로젝트를 직접 가져옴
        products = ', '.join([p.name for p in project.products]) if project else ''
        memo_data.append({
            'id': memo.id,  # 메모 ID 추가
            'date': memo.created_at.strftime('%Y-%m-%d'),
            'content': memo.content,
            'tag': memo.tag.name if memo.tag else '',
            'products': products,
            'project': project.title if project else ''  # 프로젝트 명칭 추가
        })
    return render_template('memo_table.html', memo_data=memo_data)

@app.route('/memos')
@login_required
def memos():
    # Memo 테이블에서 데이터 가져오기
    memos = Memo.query.all()
    
    # Memo 데이터를 리스트로 만듦
    memo_data = []
    for memo in memos:
        project_name = memo.project.title if memo.project else ''
        product_name = memo.project.products[0].name if memo.project and memo.project.products else ''
        memo_data.append({
            'id': memo.id,
            'datetime': memo.created_at,
            'date': memo.created_at.strftime('%Y-%m-%d'),
            'content': memo.content,
            'tag': memo.tag.name if memo.tag else '',
            'project': project_name,
            'product': product_name,
            'image': memo.image_filename,
            'file': memo.pdf_filename or memo.excel_filename or memo.ppt_filename or memo.md_filename or memo.html_filename,
            'source': 'Memo'
        })
    
    # datetime 기준으로 역순 정렬
    memo_data.sort(key=lambda x: (x['datetime'], x['id']), reverse=True)

    # 태그, 프로젝트, 제품 정보 가져오기
    tags = Tag.query.all()
    projects = Project.query.all()
    products = Product.query.all()
    
    return render_template('memos.html', memo_data=memo_data, 
                           tags=tags, projects=projects, products=products)

@app.route('/api/memo/prev_all')
def get_prev_memo_all():
    memo_id = request.args.get('memo_id', type=int)
    current_memo = Memo.query.get_or_404(memo_id)
    
    prev_memo = Memo.query\
        .filter(Memo.created_at < current_memo.created_at)\
        .order_by(Memo.created_at.desc())\
        .first()
    
    return jsonify({'id': prev_memo.id if prev_memo else None})

@app.route('/api/memo/next_all')
def get_next_memo_all():
    memo_id = request.args.get('memo_id', type=int)
    current_memo = Memo.query.get_or_404(memo_id)
    
    next_memo = Memo.query\
        .filter(Memo.created_at > current_memo.created_at)\
        .order_by(Memo.created_at.asc())\
        .first()
    
    return jsonify({'id': next_memo.id if next_memo else None})

@app.route('/api/memo/prev_in_project')
def get_prev_memo_in_project():
    memo_id = request.args.get('memo_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    if not memo_id or not project_id:
        return jsonify({'error': 'Both memo_id and project_id are required'}), 400
        
    current_memo = Memo.query.get_or_404(memo_id)
    
    # 같은 프로젝트 내에서 현재 메모보다 이전 메모 찾기
    prev_memo = Memo.query\
        .filter(Memo.project_id == project_id)\
        .filter(Memo.created_at < current_memo.created_at)\
        .order_by(Memo.created_at.desc())\
        .first()
    
    return jsonify({'id': prev_memo.id if prev_memo else None})

@app.route('/api/memo/next_in_project')
def get_next_memo_in_project():
    memo_id = request.args.get('memo_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    if not memo_id or not project_id:
        return jsonify({'error': 'Both memo_id and project_id are required'}), 400
        
    current_memo = Memo.query.get_or_404(memo_id)
    
    # 같은 프로젝트 내에서 현재 메모보다 다음 메모 찾기
    next_memo = Memo.query\
        .filter(Memo.project_id == project_id)\
        .filter(Memo.created_at > current_memo.created_at)\
        .order_by(Memo.created_at.asc())\
        .first()
    
    return jsonify({'id': next_memo.id if next_memo else None})

@app.route('/get_related_memos/<int:memo_id>')
@login_required
def get_related_memos(memo_id):
    """특정 메모와 관련된 메모들을 조회하는 API (부모-자식 관계만 고려)"""
    try:
        # 현재 메모 조회
        memo = Memo.query.get_or_404(memo_id)
        related_memos = []
        
        # 1. 자식 메모 조회 (현재 메모가 부모인 경우)
        child_memos = Memo.query.filter_by(parent_id=memo.id).all()
        
        # 2. 부모 메모와 형제 메모 조회 (현재 메모가 자식인 경우)
        parent_memo = None
        siblings = []
        if memo.parent_id:
            # 부모 메모
            parent_memo = Memo.query.get(memo.parent_id)
            # 같은 부모를 가진 다른 자식들 (현재 메모 제외)
            siblings = Memo.query.filter(
                Memo.parent_id == memo.parent_id,
                Memo.id != memo.id
            ).all()
        
        # 모든 관련 메모 결합
        all_related = []
        all_related.extend(child_memos)
        if parent_memo:
            all_related.append(parent_memo)
        all_related.extend(siblings)
        
        # 관련 메모를 JSON으로 직렬화
        related_memos_json = []
        for related_memo in all_related:
            memo_type = ""
            if related_memo in child_memos:
                memo_type = "자식 메모"
            elif related_memo == parent_memo:
                memo_type = "부모 메모"
            elif related_memo in siblings:
                memo_type = "형제 메모"
            
            related_memos_json.append({
                'id': related_memo.id,
                'content': related_memo.content,
                'date': related_memo.created_at.strftime('%Y-%m-%d'),
                'tag': related_memo.tag.name if related_memo.tag else '',
                'project': related_memo.project.title if related_memo.project else '',
                'product': related_memo.product.name if related_memo.product else '',
                'url': url_for('view_memo', memo_id=related_memo.id),
                'type': memo_type
            })
        
        return jsonify({
            'success': True,
            'related_memos': related_memos_json
        })
        
    except Exception as e:
        # 오류 발생 시 로깅하고 오류 메시지 반환
        app.logger.error(f"관련 메모 조회 중 오류 발생: {str(e)}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'related_memos': []
        }), 500

@app.route('/project/<int:project_id>/memos', methods=['GET'])
@app.route('/project/memos', methods=['GET'])  # 프로젝트 선택 없이 메모만 표시
@login_required
def memo_list(project_id=None):
    # project_id가 없는 경우 None으로 처리
    if project_id:
        project = Project.query.get(project_id)
    else:
        project = None

    # 프로젝트가 없는 경우 공백 처리, 프로젝트에 속한 메모가 없을 수도 있음
    if project:
        memos = Memo.query.filter_by(project_id=project_id).order_by(Memo.created_at.desc(), Memo.id.desc()).all()
    else:
        memos = Memo.query.filter_by(project_id=None).order_by(Memo.created_at.desc(), Memo.id.desc()).all()

    # 프로젝트에 속한 모든 메모에서 고유한 태그 목록을 추출
    tags = list(set(memo.tag for memo in memos if memo.tag))

    # 선택된 태그가 있으면 해당 태그로 필터링된 메모 목록을 가져옴
    selected_tag = request.args.get('tag')
    if selected_tag:
        memos = Memo.query.join(Tag).filter(Tag.name == selected_tag).order_by(Memo.created_at.desc(), Memo.id.desc()).all()

    return render_template('memo_list.html', project=project, memos=memos, tags=tags, selected_tag=selected_tag)

@app.route('/load_memos', methods=['GET'])
@login_required
def load_memos():
    # Get the page number from the request args
    page = int(request.args.get('page', 1))
    per_page = 50  # Number of memos per page
    # Calculate the offset
    offset = (page - 1) * per_page
    # Fetch memos with limit and offset (Check if there are memos in your database)
    memos = Memo.query.order_by(Memo.created_at.desc(), Memo.id.desc()).all()
    if not memos:
        return jsonify({
            'memos_data': [],
            'has_more': False
        }), 200  # Return empty data if no memos are found
    # Memo 데이터 리스트로 생성
    memo_data = []
    for memo in memos:
        project_name = memo.project.title if memo.project else ''
        product_name = memo.project.products[0].name if memo.project and memo.project.products else ''
        memo_data.append({
            'id': memo.id,
            'datetime': memo.created_at,
            'date': memo.created_at.strftime('%Y-%m-%d'),
            'content': memo.content,
            'tag': memo.tag.name if memo.tag else '',
            'project': project_name,
            'product': product_name,
            'image': memo.image_filename,
            'file': memo.pdf_filename or memo.excel_filename or memo.ppt_filename or memo.md_filename,
            'source': 'Memo'
        })
    # Sort memos by datetime in descending order
    memo_data.sort(key=lambda x: (x['datetime'], x['id']), reverse=True)
    # Paginate memos
    paginated_memos = memo_data[offset:offset + per_page]
    # Check if there are more memos to load
    has_more = len(memo_data) > offset + per_page
    return jsonify({
        'memos_data': paginated_memos,
        'has_more': has_more
    })

@app.route('/download_file/<int:memo_id>')
@login_required
def download_file(memo_id):
    memo = Memo.query.get_or_404(memo_id)
    # 파일명을 가져옴
    filename = memo.image_filename or memo.pdf_filename or memo.excel_filename or memo.ppt_filename or memo.md_filename or memo.html_filename
    if not filename:
        flash('이 메모에 연결된 파일이 없습니다.', 'warning')
        return redirect(url_for('view_memo', memo_id=memo.id))
    
    safe_filename = secure_filename_with_unicode(filename)
    if safe_filename != filename:
        abort(400) 

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    
    if not os.path.exists(file_path):
        abort(404)  

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        safe_filename,
        as_attachment=True,
        download_name=memo.original_filename or safe_filename  # Flask 2.x 버전
    )

@app.route('/edit_link/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    link = Link.query.get_or_404(link_id)
    if request.method == 'POST':
        link.url = request.form.get('url')
        link.description = request.form.get('description')
        db.session.commit()
        return redirect(url_for('project', project_id=link.project_id))
    return render_template('edit_link.html', link=link)

@app.route('/delete_link/<int:link_id>', methods=['POST'])
@login_required
def delete_link(link_id):
    link = Link.query.get_or_404(link_id)
    project_id = link.project_id
    db.session.delete(link)
    db.session.commit()
    return redirect(url_for('project', project_id=project_id))

@app.route('/create_link/<int:project_id>', methods=['POST'])
@login_required
def create_link(project_id):
    url = request.form.get('url')
    description = request.form.get('description')
    new_link = Link(url=url, description=description, project_id=project_id)
    db.session.add(new_link)
    db.session.commit()
    return redirect(url_for('project', project_id=project_id))

@app.route('/products')
@login_required
def product_list():
    products = Product.query.all()
    
    # 필터링 처리 (파이썬 레벨에서 처리)
    category_filter = request.args.get('category')
    api_filter = request.args.get('api')
    
    if category_filter:
        products = [p for p in products if p.category and category_filter in p.category]
        
    if api_filter:
        products = [p for p in products if p.api and api_filter in p.api]
        
    print(f"DEBUG: Categories: {Product.ALLOWED_CATEGORIES}")
    return render_template('product_list.html', 
                         products=products,
                         active_category=category_filter,
                         active_api=api_filter,
                         allowed_categories=Product.ALLOWED_CATEGORIES,
                         allowed_apis=Product.ALLOWED_APIS)

@app.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    # 관련 프로젝트를 메모 관계와 함께 Eager Loading 합니다.
    related_projects = Project.query.options(
        selectinload(Project.memos) 
    ).filter(
        Project.products.any(id=product_id)
    ).all()

    # 🚨 수정: 상태(status)를 키로, 그 안에 '진행' 리스트와 '완료' 리스트를 갖는 딕셔너리를 만듭니다.
    # 예: grouped_projects['사업화'] = {'진행': [P1], '완료': [P2]}
    grouped_projects = defaultdict(lambda: {'진행': [], '완료': []})
    
    # 모든 상태를 순회하며 프로젝트를 분류합니다.
    # 완료된 프로젝트는 원래의 status를 유지해야 행을 찾을 수 있습니다.
    for project in related_projects:
        status_key = project.status
        
        # is_completed가 True인 경우 '완료' 리스트에 추가
        if project.is_completed == True:
            grouped_projects[status_key]['완료'].append(project)
        # is_completed가 False인 경우 '진행' 리스트에 추가
        elif project.is_completed == False:
            grouped_projects[status_key]['진행'].append(project)
        # is_completed 필드가 None인 경우는 제외됩니다.

    # 템플릿에서 사용할 모든 상태 목록 (분류되지 않은 상태는 제외)
    # 템플릿에서 사용할 상태 목록은 PROJECT_STATUSES에서 프로젝트가 실제로 존재하는 상태만 필터링합니다.
    active_statuses_in_use = [s for s in PROJECT_STATUSES if grouped_projects[s]['진행'] or grouped_projects[s]['완료']]
    
    # 메모 쿼리 및 태그 로직 (기존과 동일하게 유지)
    project_ids = [p.id for p in related_projects]
    
    # 메모 쿼리
    if not project_ids:
        memo_query = Memo.query.filter(Memo.product_id == product_id)
    else:
        memo_query = Memo.query.filter(
            or_(
                Memo.project_id.in_(project_ids),
                Memo.product_id == product_id
            )
        )
        
    selected_tag = request.args.get('tag', '')
    if selected_tag:
        memo_query = memo_query.join(Tag).filter(Tag.name == selected_tag)
    # 메모 가져오기 (최신순)
    memos = memo_query.order_by(Memo.created_at.desc()).all()
    
    # 사용된 태그 목록 가져오기 (기존 로직 유지)
    used_tags = Tag.query.join(Memo).filter(
        or_(
            Memo.project_id.in_(project_ids),
            and_(
                Memo.product_id == product_id,
                Memo.project_id.is_(None)
            )
        )
    ).distinct().all()
    
    # 관련 태스크 가져오기 (기존 로직 유지)
    todo_tasks = Task.query.filter(
        Task.project_id.in_(project_ids),
        Task.status == 'To Do'
    ).order_by(
        Task.due_date.is_(None),
        Task.due_date.asc()
    ).all()
    
    done_tasks = Task.query.filter(
        Task.project_id.in_(project_ids),
        Task.status == 'Done'
    ).order_by(
        Task.finished_date.desc()
    ).limit(10).all()
    
    # 템플릿 렌더링 시 새 변수를 전달합니다.
    return render_template('product_detail.html', 
                          product=product,
                          # 🚨 수정된 변수 전달
                          grouped_projects=grouped_projects,
                          active_statuses_in_use=active_statuses_in_use, # 실제로 프로젝트가 있는 상태만
                          memos=memos,
                          todo_tasks=todo_tasks,
                          done_tasks=done_tasks,
                          used_tags=used_tags,
                          selected_tag=selected_tag,
                          project_statuses=PROJECT_STATUSES) # 전체 상태 목록은 그대로 전달

@app.route('/product/create', methods=['GET', 'POST'])
@login_required
def create_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        # 카테고리와 API 리스트 데이터 처리
        categories = request.form.getlist('category')
        apis = request.form.getlist('api')
        
        new_product = Product(
            name=name, 
            description=description,
            category=categories,
            api=apis
        )
        
        db.session.add(new_product)
        db.session.commit()
        flash('Product created successfully!', 'success')
        return redirect(url_for('product_list'))
        
    return render_template('create_product.html', 
                         allowed_categories=Product.ALLOWED_CATEGORIES,
                         allowed_apis=Product.ALLOWED_APIS)

@app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form.get('description', '')
        
        # 카테고리와 API 리스트 데이터 업데이트
        product.category = request.form.getlist('category')
        product.api = request.form.getlist('api')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product_detail', product_id=product.id))
        
    return render_template('edit_product.html', 
                         product=product,
                         allowed_categories=Product.ALLOWED_CATEGORIES,
                         allowed_apis=Product.ALLOWED_APIS)

@app.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('product_list'))

@app.route('/project/<int:project_id>/add_product', methods=['POST'])
@login_required
def add_product_to_project(project_id):
    project = Project.query.get_or_404(project_id)
    product_id = request.form['product_id']
    product = Product.query.get_or_404(product_id)
    
    if product in project.products:
        flash('This product is already added to the project.', 'error')
    else:
        project.products.append(product)
        db.session.commit()
        flash('Product added to project successfully!', 'success')
    
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product_from_project(project_id, product_id):
    project = Project.query.get_or_404(project_id)
    product = Product.query.get_or_404(product_id)
    project.products.remove(product)
    db.session.commit()
    flash('Product removed from project successfully!', 'success')
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/images')
@login_required
def project_images(project_id):
    project = Project.query.get_or_404(project_id)
    # 모든 이미지를 가져오되, 최근 순(ID 역순)으로 정렬합니다
    all_images = ProjectImage.query.filter_by(project_id=project_id).order_by(ProjectImage.id.desc()).all()
    return render_template('project_images.html', project=project, images=all_images)

@app.route('/project/<int:project_id>/upload_image', methods=['POST'])
@login_required
def upload_image(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 파일 업로드 처리
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # 이미지 파일 저장
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            memo = request.form.get('memo')
            new_image = ProjectImage(filename=filename, project_id=project.id, memo=memo)
            db.session.add(new_image)
            db.session.commit()
            
            flash('Image uploaded successfully!', 'success')
            return redirect(url_for('project_images', project_id=project.id))
            
    # 붙여넣은 이미지 처리
    pasted_image_data = request.form.get('pasted_image_data')
    if pasted_image_data:
        header, encoded = pasted_image_data.split(',', 1)
        image_data = base64.b64decode(encoded)
        
        filename = secure_filename(f"pasted_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        memo = request.form.get('memo')
        new_image = ProjectImage(filename=filename, project_id=project.id, memo=memo)
        db.session.add(new_image)
        db.session.commit()
        
        flash('Pasted image uploaded successfully!', 'success')
        return redirect(url_for('project_images', project_id=project.id))

    flash('No image provided', 'error')
    return redirect(request.url)

@app.route('/project/<int:project_id>/delete_image/<int:image_id>', methods=['POST'])
@login_required
def delete_image(project_id, image_id):
    image = ProjectImage.query.get_or_404(image_id)
    db.session.delete(image)
    db.session.commit()
    flash('Image deleted successfully!', 'success')
    return redirect(url_for('project_images', project_id=project_id))


@app.route('/project/<int:project_id>/edit_image/<int:image_id>', methods=['POST'])
@login_required
def edit_image(project_id, image_id):
    project = Project.query.get_or_404(project_id)
    image = ProjectImage.query.get_or_404(image_id)
    
    images = ProjectImage.query.filter_by(project_id=project_id).order_by(ProjectImage.id).all()
    current_index = images.index(image)

    if 'delete' in request.form:
        db.session.delete(image)
        db.session.commit()
        flash('Image deleted successfully!', 'success')
        
        if current_index < len(images) - 1:
            next_image = images[current_index + 1]
            return redirect(url_for('view_image', project_id=project_id, image_id=next_image.id))
        elif current_index > 0:
            prev_image = images[current_index - 1]
            return redirect(url_for('view_image', project_id=project_id, image_id=prev_image.id))
        else:
            return redirect(url_for('project_images', project_id=project_id))
    
    image.memo = request.form.get('memo')
    db.session.commit()
    flash('Memo updated successfully!', 'success')

    action = request.form.get('action')
    if action == 'prev' and current_index > 0:
        prev_image = images[current_index - 1]
        return redirect(url_for('view_image', project_id=project_id, image_id=prev_image.id))
    elif action == 'next' and current_index < len(images) - 1:
        next_image = images[current_index + 1]
        return redirect(url_for('view_image', project_id=project_id, image_id=next_image.id))

    return redirect(url_for('view_image', project_id=project_id, image_id=image_id))
    

@app.route('/project/<int:project_id>/view_image/<int:image_id>')
@login_required
def view_image(project_id, image_id):
    project = Project.query.get_or_404(project_id)
    image = ProjectImage.query.get_or_404(image_id)
    return render_template('view_image.html', project=project, image=image)


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    try:
        # 검색어 처리
        if request.method == 'POST':
            keyword = request.form.get('keyword', '').strip()
        else:  # GET
            keyword = request.args.get('keyword', '').strip()
            
        # 초기화
        task_results = []
        link_results = []
        image_results = []
        memo_results = []
        contact_results = []
        infolink_results = []
        project_filter = None
        
        # 키워드가 있으면 검색 수행
        if keyword:
            # 유니코드 정규화 적용
            import unicodedata
            normalized_keyword = unicodedata.normalize('NFC', keyword)
            
            # @프로젝트명 필터 추출
            import re
            # 간단한 정규표현식으로 변경
            project_match = re.search(r'@(\S+)', normalized_keyword)
            project_ids = []
            
            if project_match:
                project_name = project_match.group(1).strip()
                
                # 검색어에서 @프로젝트명 제거
                normalized_keyword = re.sub(r'@\S+', '', normalized_keyword).strip()
                
                # 프로젝트 찾기 (정확한 매칭 우선, 없으면 부분 매칭)
                project_filter = Project.query.filter(
                    Project.title == project_name
                ).first()
                
                if not project_filter:
                    project_filter = Project.query.filter(
                        Project.title.ilike(f"%{project_name}%")
                    ).first()
                
                if project_filter:
                    project_ids = [project_filter.id]
                    
                    # 하위 프로젝트 재귀적으로 찾기 (parent_id가 있는 경우에만)
                    if hasattr(Project, 'parent_id'):
                        def get_all_subprojects(parent_id):
                            subprojects = Project.query.filter(Project.parent_id == parent_id).all()
                            sub_ids = [p.id for p in subprojects]
                            for p in subprojects:
                                sub_ids.extend(get_all_subprojects(p.id))
                            return sub_ids
                        
                        subproject_ids = get_all_subprojects(project_filter.id)
                        project_ids.extend(subproject_ids)
                else:
                    flash(f'"{project_name}" 프로젝트를 찾을 수 없습니다.', 'warning')
            
            # 검색어 분할 (AND 검색 지원)
            search_terms = [term.strip() for term in normalized_keyword.split('&&')] if '&&' in normalized_keyword else [normalized_keyword]
            
            # 빈 검색어 제거
            search_terms = [term for term in search_terms if term]
            
            if search_terms:
                # 1. Task 검색
                task_query = Task.query
                if project_ids:
                    task_query = task_query.filter(Task.project_id.in_(project_ids))
                for term in search_terms:
                    task_query = task_query.filter(Task.title.ilike(f"%{term}%"))
                task_results = task_query.all()
                
                # 2. Link 검색
                link_query = Link.query
                if project_ids:
                    link_query = link_query.filter(Link.project_id.in_(project_ids))
                for term in search_terms:
                    link_query = link_query.filter(
                        db.or_(
                            Link.url.ilike(f"%{term}%"),
                            Link.description.ilike(f"%{term}%")
                        )
                    )
                link_results = link_query.all()
                
                # 3. ProjectImage 검색
                image_query = ProjectImage.query
                if project_ids:
                    image_query = image_query.filter(ProjectImage.project_id.in_(project_ids))
                for term in search_terms:
                    image_query = image_query.filter(ProjectImage.memo.ilike(f"%{term}%"))
                image_results = image_query.all()
                
                # 4. Memo 검색
                memo_query = Memo.query
                if project_ids:
                    memo_query = memo_query.filter(Memo.project_id.in_(project_ids))
                for term in search_terms:
                    memo_query = memo_query.filter(Memo.content.ilike(f"%{term}%"))
                    
                memo_results = memo_query.order_by(Memo.created_at.desc(), Memo.id.desc()).all()
                
                # 5. Infolink 검색 (프로젝트와 무관)
                infolink_query = Infolink.query
                for term in search_terms:
                    infolink_query = infolink_query.filter(
                        db.or_(
                            Infolink.name.ilike(f"%{term}%"),
                            Infolink.url.ilike(f"%{term}%"),
                            Infolink.detail.ilike(f"%{term}%"),
                            Infolink.category.ilike(f"%{term}%"),
                            Infolink.subcategory.ilike(f"%{term}%")
                        )
                    )
                infolink_results = infolink_query.all()
                
                # 6. Contact 검색 (JSON 파일에서)
                from contacts.routes import load_contacts
                all_contacts = load_contacts()
                
                contact_results = []
                for contact in all_contacts:
                    match_all = True
                    for term in search_terms:
                        term_lower = term.lower()
                        searchable_text = " ".join([
                            contact.get("name", ""),
                            contact.get("position", ""),
                            contact.get("department", ""),
                            contact.get("phone", ""),
                            contact.get("extension", ""),
                            contact.get("email", "")
                        ]).lower()
                        
                        if term_lower not in searchable_text:
                            match_all = False
                            break
                    
                    if match_all:
                        contact_results.append(contact)
            
            elif project_ids:
                # @프로젝트명만 있고 검색어가 없는 경우
                task_results = Task.query.filter(Task.project_id.in_(project_ids)).all()
                link_results = Link.query.filter(Link.project_id.in_(project_ids)).all()
                image_results = ProjectImage.query.filter(ProjectImage.project_id.in_(project_ids)).all()
                memo_results = Memo.query.filter(Memo.project_id.in_(project_ids)).order_by(Memo.created_at.desc()).all()
            
            # 결과 메모리 관리
            db.session.expire_all()
        
        # 템플릿 렌더링
        return render_template('search.html', 
                               keyword=keyword, 
                               task_results=task_results, 
                               link_results=link_results, 
                               image_results=image_results, 
                               memo_results=memo_results,
                               contact_results=contact_results,
                               infolink_results=infolink_results,
                               project_filter=project_filter)
                               
    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        flash('검색 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
        
        return render_template('search.html', 
                              keyword=keyword if 'keyword' in locals() else '', 
                              task_results=[], 
                              link_results=[], 
                              image_results=[], 
                              memo_results=[],
                              contact_results=[],
                              infolink_results=[])

# 하이라이트 필터 등록
@app.template_filter('highlight')
def highlight_filter(text, keyword):
    """안전하게 검색 키워드를 하이라이트"""
    if not text or not keyword or not isinstance(text, str) or not isinstance(keyword, str):
        return text if text else ''
    
    try:
        # 특수문자 이스케이프 처리
        escaped_keyword = re.escape(keyword)
        
        # 대소문자 구분 없이 검색
        pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
        
        # 키워드 하이라이트 처리
        highlighted = pattern.sub(r'<span class="keyword-highlight">\1</span>', text)
        
        # 안전한 HTML 마크업으로 반환
        return Markup(highlighted)
    except Exception as e:
        # 오류 시 원본 텍스트 반환 (로깅 추가)
        app.logger.error(f"Highlight error: {str(e)}")
        return text

def is_allowed_image_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
@app.route('/image_upload_gallery', methods=['GET', 'POST'])
@login_required
def image_upload_gallery():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and is_allowed_image_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
            file.save(file_path)
            flash('File successfully uploaded')
            return redirect(url_for('image_upload_gallery'))

    image_files = os.listdir(app.config['IMAGE_UPLOAD_FOLDER'])
    image_files = [f for f in image_files if is_allowed_image_file(f)]
    return render_template('upload_gallery.html', images=image_files)
    
@app.route('/image_delete/<filename>', methods=['POST'])
@login_required
def delete_image_file(filename):
    file_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'{filename} deleted successfully')
    else:
        flash(f'{filename} not found')
    return redirect(url_for('image_upload_gallery'))

@app.route('/uploads/<filename>')
@login_required
def serve_uploaded_file(filename):
    return send_from_directory(app.config['IMAGE_UPLOAD_FOLDER'], filename)

@app.template_filter('auto_link')
def auto_link(text):
    if text is None:
        return ""
    
    # 특수한 Google 문서 링크 패턴 처리
    special_pattern = re.compile(r'(Google 문서)"(?:target="_blank"\s*)?style="color: #0066cc;">([^<]+)')
    if special_pattern.search(text):
        matches = special_pattern.findall(text)
        for prefix, link_text in matches:
            old_text = f'{prefix}"target="_blank" style="color: #0066cc;">{link_text}'
            new_text = f'<a href="https://docs.google.com/" target="_blank" style="color: #0066cc;">{link_text}</a>'
            text = text.replace(old_text, new_text)
        return Markup(text)
    
    # 여기서부터는 기존 auto_link 코드
    # HTML 태그 보호 (a, img, iframe 태그)
    protected_tags_pattern = re.compile(r'(<a[^>]*>.*?</a>|<img[^>]*>|<iframe[^>]*>)', re.DOTALL | re.IGNORECASE)
    segments = protected_tags_pattern.split(text)
    
    def replace_url(text):
        # Gmail 링크 처리
        gmail_pattern = re.compile(r'(https?://mail\.google\.com[^\s<>]+)')
        text = gmail_pattern.sub(
            lambda m: f'<span style="white-space: nowrap; display: inline-flex; align-items: center;">'
                     f'<img src="/static/icons/gmaillogo.png" alt="Gmail" '
                     f'style="height: 20px; vertical-align: middle; margin-right: 4px;"> '
                     f'<a href="{m.group(1)}" target="_blank" style="color: #0066cc;">보기</a></span>',
            text
        )
        
        # Google Docs/Slides 링크 처리
        gdocs_pattern = re.compile(r'(https?://docs\.google\.com/(?:document|presentation|spreadsheets)[^\s<>"\']+)')
        text = gdocs_pattern.sub(
            lambda m: f'<span style="white-space: nowrap; display: inline-flex; align-items: center;">'
                     f'<img src="/static/icons/google-docs.png" alt="Google Docs" '
                     f'style="height: 20px; vertical-align: middle; margin-right: 4px;"> '
                     f'<a href="{m.group(1)}" target="_blank" style="color: #0066cc;">Google 문서</a></span>',
            text
        )
        
        # 일반 URL 처리 (Gmail, Google Docs URL 제외)
        url_pattern = re.compile(r'(https?://(?!mail\.google\.com)(?!docs\.google\.com)[^\s<>"\']+)')
        text = url_pattern.sub(
            lambda m: f'<a href="{m.group(1)}" target="_blank" style="color: #0066cc;">{m.group(1)}</a>',
            text
        )
        
        return text
    
    processed_segments = []
    for i, segment in enumerate(segments):
        if i % 2 == 1:  # 홀수 인덱스는 보호된 태그 (그대로 유지)
            processed_segments.append(segment)
        else:  # 짝수 인덱스는 일반 텍스트 (URL 변환 적용)
            processed_segments.append(replace_url(segment))
            
    return Markup(''.join(processed_segments))

@app.route('/tags', methods=['GET', 'POST'])
@login_required
def manage_tags():
    if request.method == 'POST':
        # Create Tag
        name = request.form.get('name')
        if name:
            new_tag = Tag(name=name)
            db.session.add(new_tag)
            db.session.commit()
            flash('Tag created successfully!', 'success')
        else:
            flash('Tag name cannot be empty', 'danger')
        return redirect(url_for('manage_tags'))
    
    tags = Tag.query.all()
    return render_template('tags.html', tags=tags)

@app.route('/tags/update/<int:tag_id>', methods=['POST'])
@login_required
def update_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    new_name = request.form.get('name')
    if new_name:
        tag.name = new_name
        db.session.commit()
        flash('Tag updated successfully!', 'success')
    else:
        flash('Tag name cannot be empty', 'danger')
    return redirect(url_for('manage_tags'))

@app.route('/tags/delete/<int:tag_id>', methods=['POST'])
@login_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash('Tag deleted successfully!', 'success')
    return redirect(url_for('manage_tags'))

@app.route('/set_view_mode', methods=['POST'])
@login_required
def set_view_mode():
    data = request.json
    view_mode = data.get('view_mode')
    session['view_mode'] = view_mode
    return jsonify({'status': 'success'})

# 카테고리 상수 정의
CATEGORIES = ['개발', '인허가', '학술', 'MEA']
SUBCATEGORIES = ['의약품', 'BPR', '식품', '기타']

@app.route('/infolinks', methods=['GET'])
@login_required
def infolinks():
    # 모든 Infolink 데이터베이스 항목 가져오기
    infolinks = Infolink.query.all()

    def serialize_infolink(infolink):
        return {
            'id': infolink.id,
            'name': infolink.name,
            'url': infolink.url,
            'detail': infolink.detail,
            'category': infolink.category,
            'subcategory': infolink.subcategory,
            'image_filename': infolink.image_filename,
            'attachment_filename': infolink.attachment_filename
        }

    # 모든 infolinks를 직렬화
    serialized_infolinks = [serialize_infolink(link) for link in infolinks]

    # 세션에서 이전 검색 상태 가져오기
    selected_categories = session.get('selected_categories', [])
    selected_subcategories = session.get('selected_subcategories', [])
    search_keyword = session.get('search_keyword', '')

    # 템플릿으로 데이터 전달
    return render_template('infolinks.html', 
                           infolinks=serialized_infolinks,
                           categories=CATEGORIES,
                           subcategories=SUBCATEGORIES,
                           selected_categories=selected_categories,
                           selected_subcategories=selected_subcategories,
                           search_keyword=search_keyword)

@app.route('/save_search_state', methods=['POST'])
def save_search_state():
    data = request.json
    session['selected_categories'] = data.get('selectedCategories', [])
    session['selected_subcategories'] = data.get('selectedSubcategories', [])
    session['search_keyword'] = data.get('searchKeyword', '')
    return '', 204

@app.route('/infolink/create', methods=['GET', 'POST'])
@login_required
def create_infolink():
    # GET 요청 시 기존 flash 메시지 클리어
    if request.method == 'GET':
        # 세션에서 flash 메시지 제거
        session.pop('_flashes', None)
    
    if request.method == 'POST':
        try:
            # 기존 코드...
            name = request.form.get('name', '').strip()
            url = request.form.get('url', '').strip()
            detail = request.form.get('detail', '').strip()
            selected_categories = request.form.get('selected_categories', '').strip()
            selected_subcategories = request.form.get('selected_subcategories', '').strip()
            image_upload_method = request.form.get('image_upload_method', 'file')

            # 필수 필드 검증
            if not name:
                flash('Name is required', 'danger')
                return render_template('create_infolink.html', 
                                     categories=CATEGORIES, 
                                     subcategories=SUBCATEGORIES)

            # URL 형식 정리
            if url and not url.startswith(('http://', 'https://')):
                url = 'http://' + url

            # 업로드 폴더 존재 확인 및 생성
            upload_folder = app.config.get('INFOLINK_UPLOAD_FOLDER')
            if not upload_folder:
                flash('Upload folder not configured', 'danger')
                return render_template('create_infolink.html', 
                                     categories=CATEGORIES, 
                                     subcategories=SUBCATEGORIES)
            
            if not os.path.exists(upload_folder):
                try:
                    os.makedirs(upload_folder, exist_ok=True)
                except OSError as e:
                    flash(f'Could not create upload folder: {str(e)}', 'danger')
                    return render_template('create_infolink.html', 
                                         categories=CATEGORIES, 
                                         subcategories=SUBCATEGORIES)

            image_filename = None

            # 이미지 업로드 처리
            if image_upload_method == 'file':
                image_file = request.files.get('images')
                if image_file and image_file.filename and image_file.filename.strip() != '':
                    try:
                        image_filename = save_uploaded_file(image_file, upload_folder)
                    except Exception as e:
                        flash(f'Error uploading image file: {str(e)}', 'danger')
                        return render_template('create_infolink.html', 
                                             categories=CATEGORIES, 
                                             subcategories=SUBCATEGORIES)
                        
            elif image_upload_method == 'paste':
                pasted_image_data = request.form.get('pasted_image_data', '').strip()
                if pasted_image_data:
                    try:
                        image_filename = save_base64_image(pasted_image_data, upload_folder)
                        if not image_filename:
                            flash('Error processing pasted image', 'warning')
                    except Exception as e:
                        flash(f'Error processing pasted image: {str(e)}', 'danger')
                        
            elif image_upload_method == 'url':
                image_url = request.form.get('image_url', '').strip()
                if image_url:
                    if image_url.startswith(('http://', 'https://')):
                        image_filename = image_url
                    else:
                        flash('Invalid image URL format', 'warning')

            # 첨부 파일 처리
            attachment_filename = None
            attachment_file = request.files.get('attachment_file')
            if attachment_file and attachment_file.filename and attachment_file.filename.strip() != '':
                try:
                    attachment_filename = save_uploaded_file(attachment_file, upload_folder)
                    
                    # PDF 파일이고 이미지가 없는 경우 썸네일 자동 생성
                    if (attachment_filename.lower().endswith('.pdf') and not image_filename):
                        pdf_path = os.path.join(upload_folder, attachment_filename)
                        thumbnail = generate_pdf_thumbnail(pdf_path, upload_folder)
                        if thumbnail:
                            image_filename = thumbnail
                            app.logger.info(f"PDF 썸네일 자동 생성: {thumbnail}")
                    
                except Exception as e:
                    flash(f'Error uploading attachment file: {str(e)}', 'danger')
                    return render_template('create_infolink.html', 
                                         categories=CATEGORIES, 
                                         subcategories=SUBCATEGORIES)
            
            # URL이 Google Docs이고 이미지가 없는 경우 썸네일 자동 생성
            if url and not image_filename:
                if any(domain in url.lower() for domain in ['docs.google.com/document', 
                                                              'docs.google.com/spreadsheets',
                                                              'docs.google.com/presentation']):
                    thumbnail_url = generate_google_docs_thumbnail(url)
                    if thumbnail_url:
                        image_filename = thumbnail_url
                        app.logger.info(f"Google Docs 썸네일 URL 생성: {thumbnail_url}")

            # 인포링크 객체 생성 및 저장
            new_infolink = Infolink(
                name=name,
                url=url if url else None,
                detail=detail if detail else None,
                category=selected_categories if selected_categories else None,
                subcategory=selected_subcategories if selected_subcategories else None,
                image_filename=image_filename,
                attachment_filename=attachment_filename
            )
            
            db.session.add(new_infolink)
            db.session.commit()
            flash('Infolink created successfully!', 'success')
            return redirect(url_for('infolinks'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error creating infolink: {str(e)}')
            flash(f'Error saving infolink: {str(e)}', 'danger')
            return render_template('create_infolink.html', 
                                 categories=CATEGORIES, 
                                 subcategories=SUBCATEGORIES)

    # GET 요청 처리
    return render_template('create_infolink.html', 
                         categories=CATEGORIES, 
                         subcategories=SUBCATEGORIES)


# 파일 저장 함수
def save_uploaded_file(file, upload_folder):
    original_filename = file.filename
    sanitized_filename = secure_filename_with_unicode(original_filename)
    short_uuid = uuid.uuid4().hex[:6]
    new_filename = f"{short_uuid}_{sanitized_filename}"
    file.save(os.path.join(upload_folder, new_filename))
    return new_filename

# Base64 이미지 저장 함수
def save_base64_image(base64_data, upload_folder):
    try:
        # Base64 데이터에서 이미지 포맷 추출
        image_format = base64_data.split(';')[0].split('/')[1]
        # Base64 데이터 디코딩
        image_data = base64.b64decode(base64_data.split(',')[1])
        # 파일명 생성
        short_uuid = uuid.uuid4().hex[:6]
        filename = f"{short_uuid}_pasted_image.{image_format}"
        # 파일 저장
        with open(os.path.join(upload_folder, filename), 'wb') as f:
            f.write(image_data)
        return filename
    except Exception as e:
        print(f"Error saving base64 image: {str(e)}")
        return None

# Board Management API
@app.route('/api/mymemo/board/rename', methods=['POST'])
@login_required
def rename_board():
    data = request.json
    old_title = data.get('old_title')
    new_title = data.get('new_title')
    
    if not old_title or not new_title:
        return jsonify({'success': False, 'message': 'Missing title'}), 400
        
    try:
        # Update all memos with the old title
        # Handle 'null' string from frontend if necessary, but usually it's real text
        MyMemo.query.filter_by(title=old_title).update(dict(title=new_title))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mymemo/board/delete', methods=['POST'])
@login_required
def delete_board():
    data = request.json
    title = data.get('title')
    
    if not title:
        return jsonify({'success': False, 'message': 'Missing title'}), 400
        
    try:
        # Delete all memos with this title
        MyMemo.query.filter_by(title=title).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# PDF 썸네일 생성 함수
def generate_pdf_thumbnail(pdf_path, output_folder, max_size=(800, 800)):
    """
    PDF 파일의 첫 페이지를 썸네일 이미지로 생성
    
    Args:
        pdf_path: PDF 파일 경로
        output_folder: 썸네일 저장 폴더 (Infolink 폴더)
        max_size: 썸네일 최대 크기 (width, height)
    
    Returns:
        생성된 썸네일 파일명 (thumbnails/xxx.jpg 형식) 또는 None
    """
    try:
        from pdf2image import convert_from_path
        
        # thumbnails 서브폴더 경로
        thumbnails_folder = os.path.join(output_folder, 'thumbnails')
        
        # thumbnails 폴더가 없으면 생성
        os.makedirs(thumbnails_folder, exist_ok=True)
        
        # PDF 첫 페이지만 이미지로 변환 (poppler 경로 명시)
        images = convert_from_path(
            pdf_path, 
            first_page=1, 
            last_page=1, 
            dpi=150,
            poppler_path='/usr/bin'
        )
        
        if not images:
            return None
        
        # 첫 페이지 이미지
        image = images[0]
        
        # 썸네일 크기로 조정 (비율 유지)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # 파일명 생성 (UUID + thumbnail.jpg)
        short_uuid = uuid.uuid4().hex[:6]
        thumbnail_filename = f"{short_uuid}_thumbnail.jpg"
        thumbnail_path = os.path.join(thumbnails_folder, thumbnail_filename)
        
        # JPEG로 저장 (품질 85)
        image.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
        
        # DB에는 상대 경로로 저장 (thumbnails/xxx.jpg)
        return f"thumbnails/{thumbnail_filename}"
        
    except Exception as e:
        app.logger.error(f"PDF 썸네일 생성 실패: {e}")
        return None


def extract_google_file_id(url):
    """
    Google Docs/Sheets/Slides URL에서 파일 ID 추출
    
    Args:
        url: Google 문서 URL
    
    Returns:
        파일 ID 또는 None
    """
    import re
    patterns = [
        r'/document/d/([a-zA-Z0-9-_]+)',
        r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
        r'/presentation/d/([a-zA-Z0-9-_]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def generate_google_docs_thumbnail(url):
    """
    Google Docs URL에서 썸네일 URL 생성 (파일 다운로드 없음)
    
    Args:
        url: Google 문서 URL
    
    Returns:
        Google Drive 썸네일 URL 또는 None
    """
    try:
        file_id = extract_google_file_id(url)
        if not file_id:
            return None
        
        # Google Drive 썸네일 URL (800px 크기)
        thumbnail_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"
        app.logger.info(f"Google Docs 썸네일 URL 생성: {thumbnail_url}")
        return thumbnail_url
        
    except Exception as e:
        app.logger.error(f"Google Docs 썸네일 URL 생성 실패: {e}")
        return None


@app.route('/infolink/<int:infolink_id>')
@login_required
def view_infolink(infolink_id):
    infolink = Infolink.query.get_or_404(infolink_id)
    return render_template('view_infolink.html', infolink=infolink)

@app.route('/infolink/<int:infolink_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_infolink(infolink_id):
    infolink = Infolink.query.get_or_404(infolink_id)
    
    if request.method == 'POST':
        infolink.name = request.form.get('name')
        infolink.url = request.form.get('url')
        infolink.detail = request.form.get('detail')
        infolink.category = request.form.get('selected_categories')
        infolink.subcategory = request.form.get('selected_subcategories')

        # URL에 http 또는 https가 없으면 추가, 비어있는 경우는 추가하지 않음
        if infolink.url and not infolink.url.startswith(('http://', 'https://')):
            infolink.url = 'http://' + infolink.url

        image_upload_method = request.form.get('image_upload_method')
        
        # 이미지 업로드 방식에 따른 처리
        if image_upload_method == 'file':
            image_file = request.files.get('images')
            if image_file and image_file.filename != '':
                image_filename = save_uploaded_file(image_file, app.config['INFOLINK_UPLOAD_FOLDER'])
                infolink.image_filename = image_filename
        elif image_upload_method == 'paste':
            pasted_image_data = request.form.get('pasted_image_data')
            if pasted_image_data:
                image_filename = save_base64_image(pasted_image_data, app.config['INFOLINK_UPLOAD_FOLDER'])
                if image_filename:
                    infolink.image_filename = image_filename
        elif image_upload_method == 'url':
            image_url = request.form.get('image_url')
            if image_url:
                infolink.image_filename = image_url

        # 첨부 파일 처리
        attachment_file = request.files.get('attachment_file')
        if attachment_file and attachment_file.filename != '':
            attachment_filename = save_uploaded_file(attachment_file, app.config['INFOLINK_UPLOAD_FOLDER'])
            infolink.attachment_filename = attachment_filename
            
            # PDF 파일이고 이미지가 없는 경우 썸네일 자동 생성
            if (attachment_filename.lower().endswith('.pdf') and not infolink.image_filename):
                pdf_path = os.path.join(app.config['INFOLINK_UPLOAD_FOLDER'], attachment_filename)
                thumbnail = generate_pdf_thumbnail(pdf_path, app.config['INFOLINK_UPLOAD_FOLDER'])
                if thumbnail:
                    infolink.image_filename = thumbnail
                    app.logger.info(f"PDF 썸네일 자동 생성: {thumbnail}")
        
        # URL이 Google Docs이고 이미지가 없는 경우 썸네일 자동 생성
        if infolink.url and not infolink.image_filename:
            if any(domain in infolink.url.lower() for domain in ['docs.google.com/document',
                                                                   'docs.google.com/spreadsheets',
                                                                   'docs.google.com/presentation']):
                thumbnail_url = generate_google_docs_thumbnail(infolink.url)
                if thumbnail_url:
                    infolink.image_filename = thumbnail_url
                    app.logger.info(f"Google Docs 썸네일 URL 생성: {thumbnail_url}")

        # 기존 이미지 삭제 처리
        if request.form.get('delete_image'):
            if infolink.image_filename and not infolink.image_filename.startswith(('http://', 'https://')):
                image_path = os.path.join(app.config['INFOLINK_UPLOAD_FOLDER'], infolink.image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
            infolink.image_filename = None
        
        # 기존 첨부파일 삭제 처리
        if request.form.get('delete_attachment'):
            if infolink.attachment_filename:
                attachment_path = os.path.join(app.config['INFOLINK_UPLOAD_FOLDER'], infolink.attachment_filename)
                if os.path.exists(attachment_path):
                    os.remove(attachment_path)
                infolink.attachment_filename = None

        try:
            db.session.commit()
            flash('Infolink updated successfully!', 'success')
            return redirect(url_for('view_infolink', infolink_id=infolink_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating infolink: {str(e)}', 'danger')

    return render_template('edit_infolink.html', 
                           infolink=infolink, 
                           categories=CATEGORIES, 
                           subcategories=SUBCATEGORIES)

    
@app.route('/infolink/<int:infolink_id>/delete', methods=['POST'])
@login_required
def delete_infolink(infolink_id):
    infolink = Infolink.query.get_or_404(infolink_id)
    # 파일 삭제
    if infolink.image_filename:
        image_path = os.path.join(app.config['INFOLINK_UPLOAD_FOLDER'], infolink.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    if infolink.attachment_filename:
        attachment_path = os.path.join(app.config['INFOLINK_UPLOAD_FOLDER'], infolink.attachment_filename)
        if os.path.exists(attachment_path):
            os.remove(attachment_path)
    db.session.delete(infolink)
    db.session.commit()
    flash('Infolink deleted successfully!', 'success')
    return redirect(url_for('infolinks'))

@app.route('/infolink_uploads/<path:filename>')
@login_required
def infolink_uploads(filename):
    return send_from_directory(app.config['INFOLINK_UPLOAD_FOLDER'], filename)

# Managing categories independently
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    categories = Category.query.all()

    if request.method == 'POST':
        # Adding a new category
        category_name = request.form.get('category_name')
        if category_name:
            new_category = Category(name=category_name)
            db.session.add(new_category)
            db.session.commit()
            flash('Category added successfully!', 'success')
        return redirect(url_for('manage_categories'))

    return render_template('categories.html', categories=categories)

# Deleting a category
@app.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('manage_categories'))

# Managing subcategories independently
@app.route('/subcategories', methods=['GET', 'POST'])
@login_required
def manage_subcategories():
    subcategories = Subcategory.query.all()

    if request.method == 'POST':
        # Adding a new subcategory
        subcategory_name = request.form.get('subcategory_name')
        if subcategory_name:
            new_subcategory = Subcategory(name=subcategory_name)
            db.session.add(new_subcategory)
            db.session.commit()
            flash('Subcategory added successfully!', 'success')
        return redirect(url_for('manage_subcategories'))

    return render_template('subcategories.html', subcategories=subcategories)

# Deleting a subcategory
@app.route('/subcategory/<int:subcategory_id>/delete', methods=['POST'])
@login_required
def delete_subcategory(subcategory_id):
    subcategory = Subcategory.query.get_or_404(subcategory_id)
    db.session.delete(subcategory)
    db.session.commit()
    flash('Subcategory deleted successfully!', 'success')
    return redirect(url_for('manage_subcategories'))


@app.route('/summary')
def summary():
    """캘린더 이벤트와 가장 중요한 연락처를 표시하는 요약 페이지"""
    
    # 1. 관리자 설정 값 로드
    settings = load_settings() 

    # ---------------------------------------------------------
    # [수정됨] 연락처 개수(limit) 결정 로직 (세션 사용)
    # ---------------------------------------------------------
    # 1. URL 파라미터로 'limit'이 들어왔는지 확인 (사용자가 변경했을 때)
    if 'limit' in request.args:
        try:
            limit = int(request.args.get('limit'))
            # 사용자가 선택한 값을 세션(서버 메모리)에 저장하여 기억함
            session['summary_limit'] = limit 
        except (ValueError, TypeError):
            limit = 5
    else:
        # 2. URL에 'limit'이 없으면(메뉴 클릭 등), 이전에 저장된 값을 세션에서 가져옴
        # 저장된 값이 없으면 기본값 5 사용
        limit = session.get('summary_limit', 5)
        
    # ---------------------------------------------------------
    
    # 기존 연락처 데이터 로드
    contacts = load_contacts()
    
    # 1. 즐겨찾기 연락처 필터링
    favorite_contacts = [contact for contact in contacts if contact.get("is_favorite")]
    
    # 2. 정렬 함수 정의
    def summary_sort_key(contact):
        priority_score = contact.get("priority_score", 0.0)
        return (-priority_score, contact["name"])
    
    # 3. 정렬 적용
    sorted_favorites = sorted(favorite_contacts, key=summary_sort_key)
    
    # 4. 연락처 개수 제한 보정 (5~20 사이)
    if limit < 5: limit = 5
    elif limit > 20: limit = 20
    else: limit = (limit // 5) * 5
    
    # 보정된 값을 다시 세션에 업데이트 (혹시 이상한 값이 들어왔을 경우 대비)
    session['summary_limit'] = limit
        
    limited_contacts = sorted_favorites[:limit]
    
    # 캐시된 캘린더 이벤트가 있으면 템플릿에 전달 (즉시 표시용)
    try:
        cached_events = _calendar_cache.get('events') or []
    except (NameError, AttributeError):
        cached_events = []
    
    # Summary 설정 추출
    summary_settings = settings.get('Summary', {})
    
    return render_template('summary.html', 
                            contacts=limited_contacts, 
                            cached_calendar_events=cached_events,  # 캐시된 이벤트 전달
                            current_limit=limit,
                            summary_bg_url=summary_settings.get('bg_url', ''),
                            summary_bg_color=summary_settings.get('bg_color', '#f8f9fa'),
                            summary_opacity=summary_settings.get('opacity', '1.0')
                            )


# 캘린더 이벤트 캐시 (간단한 in-memory 캐싱)
_calendar_cache = {
    'events': None,
    'timestamp': None,
    'ttl': 300  # 5분 (300초)
}

@app.route('/api/calendar-events')
def api_calendar_events():
    """비동기 캘린더 이벤트 API (캐싱 포함)"""
    from datetime import datetime as dt
    
    try:
        # 캐시 확인
        now = dt.now()
        if (_calendar_cache['events'] is not None and 
            _calendar_cache['timestamp'] is not None):
            # 캐시가 유효한지 확인 (TTL 체크)
            elapsed = (now - _calendar_cache['timestamp']).total_seconds()
            if elapsed < _calendar_cache['ttl']:
                app.logger.info(f"캘린더 이벤트 캐시 사용 (남은 시간: {int(_calendar_cache['ttl'] - elapsed)}초)")
                return jsonify({
                    'events': _calendar_cache['events'],
                    'success': True,
                    'cached': True
                })
        
        # 캐시가 없거나 만료됨 - 새로 가져오기
        app.logger.info("캘린더 이벤트 새로 가져오기...")
        calendar_events = fetch_calendar_events()
        
        # 캐시 업데이트
        _calendar_cache['events'] = calendar_events
        _calendar_cache['timestamp'] = now
        
        return jsonify({
            'events': calendar_events,
            'success': True,
            'cached': False
        })
    except Exception as e:
        app.logger.error(f"캘린더 이벤트 가져오기 오류: {e}")
        return jsonify({
            'events': [],
            'success': False,
            'error': str(e),
            'cached': False
        })

@app.route('/gcal')
def gcal():
    events = fetch_calendar_events()  # gcal.py에서 이벤트 가져오기
    return render_template('gcal.html', events=events)


# Flask 앱 파일 (app.py 등)에 추가할 코드 예시
@app.route('/memos/add_mobile')
def add_memo_mobile():
    # 이 라우트는 add_memo_mobile.html 템플릿을 렌더링합니다.
    return render_template('add_memo_mobile.html')

@app.route('/api/get_tags_and_products', methods=['GET'])
def get_tags_and_products():
    """태그와 제품 데이터를 JSON으로 반환하는 API 엔드포인트"""
    try:
        # 데이터베이스에서 태그와 제품 조회
        tags = Tag.query.all()
        products = Product.query.all()
        
        # 완료와 보류 상태만 제외하고 나머지 프로젝트 조회
        excluded_statuses = ['완료', '보류']
        projects = Project.query.filter(~Project.status.in_(excluded_statuses)).order_by(Project.title).all()
        
        # JSON 형태로 변환
        tags_data = [{'id': tag.id, 'name': tag.name} for tag in tags]
        products_data = [{'id': product.id, 'name': product.name} for product in products]
        projects_data = [{'id': project.id, 'title': project.title} for project in projects]
        
        # 프로젝트를 한글 기준으로 정렬
        import locale
        try:
            locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
            projects_data.sort(key=lambda x: locale.strxfrm(x['title']))
        except:
            # locale 설정 실패 시 기본 정렬 사용
            projects_data.sort(key=lambda x: x['title'])
        
        return jsonify({
            'tags': tags_data,
            'products': products_data,
            'projects': projects_data
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching tags and products: {str(e)}")
        return jsonify({'error': 'Failed to fetch data'}), 500

# 또는 기존 메모 작성 페이지 라우트에서 직접 데이터를 전달하는 방법:
@app.route('/new_memo')
def new_memo():
    """새 메모 작성 페이지"""
    try:
        # 데이터베이스에서 태그와 제품 조회
        tags = Tag.query.all()
        products = Product.query.all()
        
        return render_template('new_memo.html', tags=tags, products=products)
    
    except Exception as e:
        app.logger.error(f"Error loading new memo page: {str(e)}")
        return render_template('new_memo.html', tags=[], products=[])

@app.route('/statistics')
@login_required
def statistics():
    """Renders the statistics dashboard page."""
    return render_template('statistics.html')

@app.route('/api/stats_data')
@login_required
def api_stats_data():
    """Provides data for charts in JSON format. (Excluding is_completed=True projects where applicable)"""
    try:
        # 1. Project status summary (모든 프로젝트 상태 집계 - '완료' 상태도 포함)
        # 이 데이터가 대시보드에 사용되는지 명확하지 않으나, 원본 코드를 유지합니다.
        project_status_summary = db.session.query(
            Project.status,
            func.count(Project.id)
        ).group_by(Project.status).all()
        
        project_status_data = {
            'labels': [status for status, _ in project_status_summary],
            'data': [count for _, count in project_status_summary]
        }

        # 2. Task status summary (모든 Task 상태 집계)
        task_status_summary = db.session.query(
            Task.status,
            func.count(Task.id)
        ).group_by(Task.status).all()
        
        task_status_data = {
            'labels': [status for status, _ in task_status_summary],
            'data': [count for _, count in task_status_summary]
        }
        
        # 3. Projects per product (미완료 프로젝트만)
        projects_per_product_summary = db.session.query(
            Product.name,
            func.count(Project.id)
        ).join(Product.projects).filter(
            Project.is_completed == False  # ⬅️ is_completed 필터 적용
        ).group_by(Product.name).all()
        
        projects_per_product_data = {
            'labels': [name for name, _ in projects_per_product_summary],
            'data': [count for _, count in projects_per_product_summary]
        }

        # 4. Tasks per project (Top 10, 미완료 프로젝트의 미완료 Task만)
        tasks_per_project_summary = db.session.query(
            Project.title,
            func.count(Task.id),
            Project.id # 🌟 프로젝트 ID 추가
        ).join(Task.project).filter(
            Project.is_completed == False, # ⬅️ is_completed 필터 적용
            Task.status != 'Done'
        ).group_by(Project.title, Project.id).order_by(func.count(Task.id).desc()).limit(10).all()

        tasks_per_project_data = {
            'labels': [title for title, _, _ in tasks_per_project_summary],
            'data': [count for _, count, _ in tasks_per_project_summary],
            'ids': [id for _, _, id in tasks_per_project_summary] # 🌟 ID 리스트 추가
        }
        
        result = {
            'project_status': project_status_data,
            'task_status': task_status_data,
            'projects_per_product': projects_per_product_data,
            'tasks_per_project': tasks_per_project_data
        }
        
        app.logger.info(f"API 응답 데이터: {result}")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"통계 데이터 조회 오류: {str(e)}")
        return jsonify({
            'error': str(e),
            'project_status': {'labels': [], 'data': []},
            'task_status': {'labels': [], 'data': []},
            'projects_per_product': {'labels': [], 'data': []},
            'tasks_per_project': {'labels': [], 'data': []}
        }), 500


@app.route('/api/tasks_per_product_data')
@login_required
def api_tasks_per_product_data():
    """Provides data for tasks per product, excluding 'Done' tasks."""
    try:
        tasks_per_product_summary = db.session.query(
            Product.name,
            func.count(Task.id)
        ).join(Product.projects).join(Project.tasks).filter(
            Task.status != 'Done'
        ).group_by(
            Product.name
        ).order_by(
            func.count(Task.id).desc()
        ).all()
        
        tasks_per_product_data = {
            'labels': [name for name, _ in tasks_per_product_summary],
            'data': [count for _, count in tasks_per_product_summary]
        }
        
        # 로깅 추가 (디버깅용)
        app.logger.info(f"제품별 태스크 데이터: {tasks_per_product_data}")
        
        return jsonify(tasks_per_product_data)
        
    except Exception as e:
        app.logger.error(f"제품별 태스크 데이터 조회 오류: {str(e)}")
        return jsonify({
            'error': str(e),
            'labels': [],
            'data': []
        }), 500

@app.route('/api/stats_per_category')
@login_required
def api_stats_per_category():
    """
    Research, Development, 기타 카테고리별로 프로젝트 상태 분포 데이터를 제공합니다.
    (is_completed=False 인 프로젝트만 포함)
    """
    try:
        # 프로젝트 상태를 카테고리로 매핑
        RESEARCH_STATUSES = ['기술개발', '시험평가', '제품개발', '연구']
        DEVELOPMENT_STATUSES = ['허가승인', '규제개선', '사업화']
        
        # 기본 필터 설정: is_completed가 False인 미완료 프로젝트만 대상으로 합니다.
        base_filter = Project.is_completed == False

        # 1. Research 카테고리 데이터
        research_summary = db.session.query(
            Project.status,
            func.count(Project.id)
        ).filter(
            base_filter, # <-- is_completed 필터 적용
            Project.status.in_(RESEARCH_STATUSES)
        ).group_by(Project.status).all()

        research_data = {
            'labels': [status for status, _ in research_summary],
            'data': [count for _, count in research_summary]
        }

        # 2. Development 카테고리 데이터
        development_summary = db.session.query(
            Project.status,
            func.count(Project.id)
        ).filter(
            base_filter, # <-- is_completed 필터 적용
            Project.status.in_(DEVELOPMENT_STATUSES)
        ).group_by(Project.status).all()

        development_data = {
            'labels': [status for status, _ in development_summary],
            'data': [count for _, count in development_summary]
        }

        # 3. 기타 카테고리 데이터
        # '완료' 상태 자체와 Research/Development에 속하지 않는 모든 상태를 '기타'로 분류합니다.
        # base_filter가 이미 is_completed=False를 걸러주므로, '완료' 상태가 걸러지지만,
        # 명시적인 상태 목록에서도 제외하는 것이 좋습니다.
        other_statuses = [
            status for status in PROJECT_STATUSES 
            if status not in RESEARCH_STATUSES and status not in DEVELOPMENT_STATUSES and status != '완료'
        ]       
        
        etc_summary = db.session.query(
            Project.status,
            func.count(Project.id)
        ).filter(
            base_filter, # <-- is_completed 필터 적용
            Project.status.in_(other_statuses)
        ).group_by(Project.status).all()

        etc_data = {
            'labels': [status for status, _ in etc_summary],
            'data': [count for _, count in etc_summary]
        }

        result = {
            'research': research_data,
            'development': development_data,
            'etc': etc_data
        }
        
        app.logger.info(f"카테고리별 통계 데이터: {result}")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"카테고리별 통계 데이터 조회 오류: {str(e)}")
        return jsonify({
            'error': str(e),
            'research': {'labels': [], 'data': []},
            'development': {'labels': [], 'data': []},
            'etc': {'labels': [], 'data': []}
        }), 500

@app.route('/api/task_due_date_summary')
@login_required
def api_task_due_date_summary():
    """
    Provides a summary of tasks by due date timeframe.
    """
    try:
        # 한국 시간대 기준 오늘 날짜
        today = datetime.now(KST).date()
        
        within_1_week = Task.query.filter(
            Task.status != 'Done',
            Task.due_date >= today,
            Task.due_date <= today + timedelta(weeks=1)
        ).count()

        within_1_month = Task.query.filter(
            Task.status != 'Done',
            Task.due_date > today + timedelta(weeks=1),
            Task.due_date <= today + timedelta(weeks=4)
        ).count()

        within_3_months = Task.query.filter(
            Task.status != 'Done',
            Task.due_date > today + timedelta(weeks=4),
            Task.due_date <= today + timedelta(weeks=13)
        ).count()

        within_6_months = Task.query.filter(
            Task.status != 'Done',
            Task.due_date > today + timedelta(weeks=13),
            Task.due_date <= today + timedelta(weeks=26)
        ).count()
        
        after_6_months = Task.query.filter(
            Task.status != 'Done',
            Task.due_date > today + timedelta(weeks=26)
        ).count()

        summary_data = {
            "labels": ["일주일 내", "한달 내", "3개월 내", "6개월 내", "6개월 이후"],
            "data": [within_1_week, within_1_month, within_3_months, within_6_months, after_6_months]
        }

        return jsonify(summary_data)

    except Exception as e:
        app.logger.error(f"Task due date summary error: {str(e)}")
        return jsonify({
            'error': str(e),
            'labels': [],
            'data': []
        }), 500


@app.route('/all_tasks', methods=['GET'])
@login_required
def all_tasks():
    """
    모든 Task를 가져와서 테이블로 표시합니다. 
    """
    try:
        # 한국 시간대 기준 오늘 날짜
        today_date = datetime.now(KST).date()
        status_filter = request.args.get('status', 'todo').strip().lower() 

        # Task 쿼리 - joinedload로 프로젝트 정보 미리 로드
        from sqlalchemy.orm import joinedload
        query = Task.query.options(joinedload(Task.project))

        if status_filter == 'todo':
            # 미완료 Task
            query = query.filter(Task.status != 'Done')
            # SQLite 호환 정렬: CASE 문 사용 (NULL을 마지막으로)
            query = query.order_by(
                db.case(
                    (Task.due_date.is_(None), 1),
                    else_=0
                ),
                Task.due_date.asc(),
                Task.start_date.desc(),
                Task.id.desc()
            )
        elif status_filter == 'done':
            # 완료 Task
            query = query.filter(Task.status == 'Done')
            query = query.order_by(
                db.case(
                    (Task.finished_date.is_(None), 1),
                    else_=0
                ),
                Task.finished_date.desc(),
                Task.id.desc()
            )
        else:
            # 전체 Task
            query = query.order_by(
                db.case(
                    (Task.start_date.is_(None), 1),
                    else_=0
                ),
                Task.start_date.desc(),
                Task.id.desc()
            )
            
        all_tasks = query.all()
        app.logger.info(f"Loaded {len(all_tasks)} tasks with filter: {status_filter}")

        # 안전한 날짜 포맷팅 함수
        def safe_date_format(dt):
            """날짜를 안전하게 문자열로 변환"""
            if dt is None:
                return ''
            try:
                if isinstance(dt, datetime):
                    return dt.strftime('%Y-%m-%d')
                elif isinstance(dt, date):
                    return dt.strftime('%Y-%m-%d')
                elif isinstance(dt, str):
                    return dt
                else:
                    return str(dt)
            except Exception as e:
                app.logger.warning(f"Date format error: {e}, value: {dt}")
                return ''

        # Task 데이터 준비
        task_data = []
        for task in all_tasks:
            try:
                # 마감일 초과 여부 계산
                is_overdue = False
                if task.due_date and task.status != 'Done':
                    try:
                        due_date_obj = task.due_date
                        if isinstance(due_date_obj, datetime):
                            due_date_obj = due_date_obj.date()
                        
                        if due_date_obj < today_date:
                            is_overdue = True
                    except Exception as date_error:
                        app.logger.warning(f"Due date comparison error for task {task.id}: {date_error}")
                
                # 프로젝트 정보
                project_title = 'N/A'
                project_id = None
                project_url = '#'
                
                if task.project:
                    project_title = task.project.title or 'Untitled Project'
                    project_id = task.project.id
                    project_url = url_for('project', project_id=task.project.id)
                
                task_data.append({
                    'id': task.id,
                    'title': task.title or 'Untitled Task',
                    'start_date': safe_date_format(task.start_date),
                    'due_date': safe_date_format(task.due_date),
                    'finished_date': safe_date_format(task.finished_date),
                    'status': task.status or 'To Do',
                    'is_overdue': is_overdue,
                    'project_title': project_title,
                    'project_id': project_id,
                    'project_url': project_url,
                    'comment': task.comment or ''
                })
                
            except Exception as task_error:
                app.logger.error(f"Error processing task {task.id}: {task_error}")
                import traceback
                app.logger.error(traceback.format_exc())
                continue

        app.logger.info(f"Successfully prepared {len(task_data)} tasks")
        
        return render_template('task_list.html', 
                             tasks=task_data, 
                             status_filter=status_filter,
                             error_message=None)
        
    except Exception as e:
        app.logger.error(f"Critical error in all_tasks: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        
        return render_template('task_list.html', 
                             tasks=[], 
                             status_filter='todo',
                             error_message=f'Task 목록을 불러오는 중 오류가 발생했습니다: {str(e)}')

@app.route('/tasks_timeline', methods=['GET'])
@login_required
def tasks_timeline():
    """
    Gantt 차트 스타일의 타임라인 뷰로 Task를 상태별로 그룹화하여 표시합니다.
    view 파라미터로 week/month 전환 가능
    """
    try:
        # 한국 시간대 기준 오늘 날짜
        today_date = datetime.now(KST).date()
        
        # 뷰 타입 (week 또는 month)
        view_type = request.args.get('view', 'week')
        
        # 날짜 범위 필터 (옵션)
        start_filter = request.args.get('start_date')
        end_filter = request.args.get('end_date')
        
        # Task 쿼리 - 프로젝트 정보와 함께 로드
        query = Task.query.options(
            joinedload(Task.project).selectinload(Project.products)
        ).filter(Task.status != 'Done')  # 미완료 Task만 표시
        
        # 날짜 필터 적용
        if start_filter:
            try:
                start_date = datetime.strptime(start_filter, '%Y-%m-%d').date()
                query = query.filter(
                    or_(Task.due_date >= start_date, Task.due_date.is_(None))
                )
            except ValueError:
                pass
        
        if end_filter:
            try:
                end_date = datetime.strptime(end_filter, '%Y-%m-%d').date()
                query = query.filter(
                    or_(Task.start_date <= end_date, Task.start_date.is_(None))
                )
            except ValueError:
                pass
        
        # 시작일 기준으로 정렬
        query = query.order_by(
            db.case(
                (Task.start_date.is_(None), 1),
                else_=0
            ),
            Task.start_date.asc(),
            Task.id.asc()
        )
        
        all_tasks = query.all()
        app.logger.info(f"Loaded {len(all_tasks)} tasks for timeline view")
        
        # 날짜 범위 계산
        min_date = None
        max_date = None
        
        for task in all_tasks:
            if task.start_date:
                if min_date is None or task.start_date < min_date:
                    min_date = task.start_date
            if task.due_date:
                if max_date is None or task.due_date > max_date:
                    max_date = task.due_date
        
        # 날짜 범위가 없으면 기본값 설정 (오늘부터 30일)
        if min_date is None:
            min_date = today_date
        if max_date is None:
            max_date = today_date + timedelta(days=30)
        
        # 여유 공간 추가 (앞뒤로 7일씩)
        min_date = min_date - timedelta(days=7)
        max_date = max_date + timedelta(days=7)
        
        # 상태별로 Task 그룹화
        status_groups_map = {}
        tasks_without_project = []
        
        # 프로젝트 상태 정의 및 순서
        status_order = ['규제개선', '시험평가', '허가승인', '보류', '기술개발']
        status_icons = {
            '규제개선': '📋',
            '시험평가': '🔬',
            '허가승인': '✅',
            '보류': '⏸️',
            '기술개발': '⚙️'
        }
        
        for task in all_tasks:
            if task.project:
                status = task.project.status or '기타'
                
                # 상태 그룹이 없으면 생성
                if status not in status_groups_map:
                    status_groups_map[status] = {
                        'status': status,
                        'icon': status_icons.get(status, '📌'),
                        'tasks': []
                    }
                
                # Task에 프로젝트 정보 추가
                task.project_title = task.project.title
                task.project_color = None
                
                status_groups_map[status]['tasks'].append(task)
            else:
                tasks_without_project.append(task)
        
        # 정의된 순서대로 status_groups 정렬
        status_groups = []
        for status in status_order:
            if status in status_groups_map:
                status_groups.append(status_groups_map[status])
        
        # 정의되지 않은 상태가 있으면 추가
        for status, group in status_groups_map.items():
            if status not in status_order:
                status_groups.append(group)
        
        # 상태별 색상 할당
        status_colors = {
            '규제개선': '#4A90E2',
            '시험평가': '#F5A623',
            '허가승인': '#7ED321',
            '보류': '#BD10E0',
            '기술개발': '#50E3C2',
            '기타': '#95A5A6'
        }
        
        for group in status_groups:
            group['color'] = status_colors.get(group['status'], '#95A5A6')
            for task in group['tasks']:
                task.project_color = group['color']
        
        # ========== 주별 헤더 생성 ==========
        days_to_monday = min_date.weekday()
        week_start = min_date - timedelta(days=days_to_monday)
        
        date_headers = []
        current_week_start = week_start
        week_number = 1
        
        while current_week_start <= max_date:
            week_end = current_week_start + timedelta(days=6)
            is_current_week = current_week_start <= today_date <= week_end
            
            date_headers.append({
                'week_start': current_week_start,
                'week_end': week_end,
                'week_number': week_number,
                'month': current_week_start.month,
                'year': current_week_start.year,
                'is_current_week': is_current_week,
                'display_label': f"{current_week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}"
            })
            
            current_week_start += timedelta(days=7)
            week_number += 1
        
        # ========== 월별 헤더 생성 ==========
        month_headers = []
        current_month_start = min_date.replace(day=1)
        month_counter = 1
        
        while current_month_start <= max_date:
            # 해당 월의 마지막 날
            if current_month_start.month == 12:
                next_month = current_month_start.replace(year=current_month_start.year + 1, month=1)
            else:
                next_month = current_month_start.replace(month=current_month_start.month + 1)
            
            month_end = next_month - timedelta(days=1)
            
            # 현재 월인지 확인
            is_current_month = (
                current_month_start.year == today_date.year and 
                current_month_start.month == today_date.month
            )
            
            month_headers.append({
                'month_start': current_month_start,
                'month_end': month_end,
                'month_number': month_counter,
                'month': current_month_start.month,
                'year': current_month_start.year,
                'is_current_month': is_current_month,
                'display_label': f"{current_month_start.year}년 {current_month_start.month}월"
            })
            
            current_month_start = next_month
            month_counter += 1
        
        total_weeks = len(date_headers)
        total_months = len(month_headers)
        
        # 총 row 수 계산
        total_rows = 0
        for group in status_groups:
            total_rows += 1
            total_rows += len(group['tasks'])
        
        if tasks_without_project:
            total_rows += 1
            total_rows += len(tasks_without_project)
        
        return render_template(
            'tasks_timeline.html',
            status_groups=status_groups,
            tasks_without_project=tasks_without_project,
            date_headers=date_headers,
            month_headers=month_headers,  # 월별 헤더 추가
            min_date=min_date,
            max_date=max_date,
            week_start=week_start,
            total_weeks=total_weeks,
            total_months=total_months,
            total_rows=total_rows,
            today=today_date,
            view_type=view_type  # week 또는 month
        )
        
    except Exception as e:
        app.logger.error(f"Error in tasks_timeline: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        
        return render_template(
            'tasks_timeline.html',
            status_groups=[],
            tasks_without_project=[],
            date_headers=[],
            month_headers=[],
            min_date=today_date,
            max_date=today_date + timedelta(days=30),
            week_start=today_date,
            total_weeks=5,
            total_months=2,
            total_rows=0,
            today=today_date,
            view_type='week',
            error_message=f'타임라인을 불러오는 중 오류가 발생했습니다: {str(e)}'
        )

@app.route('/db_status')
@login_required
def db_status():
    conn_status, conn_message = check_db_connection()
    table_status, table_message = check_db_tables()
    
    return jsonify({
        'connection_status': conn_status,
        'connection_message': conn_message,
        'table_status': table_status,
        'table_message': table_message
    })

# Flowchart DB 초기화
with app.app_context():
    flowchart_init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
# ==========================================
# MyMemo Board Routes
# ==========================================

@app.route('/mymemo/uploads/<filename>')
@login_required
def mymemo_uploads(filename):
    """MyMemo 첨부 파일 서빙"""
    upload_folder = os.path.join(BASE_DIR, 'pdata', 'MyMemo')
    return send_from_directory(upload_folder, filename)

@app.route('/mymemo')
@login_required
def mymemo_board():
    projects = Project.query.filter_by(is_completed=False).all()
    products = Product.query.all()
    # 모든 MyMemo 가져오기 (계층 구조는 프론트에서 처리 or 재귀적으로 가져오기)
    # 일단 평면적으로 가져와서 프론트에서 필터링
    mymemos = MyMemo.query.all()
    return render_template('mymemo_board.html', projects=projects, products=products, mymemos=mymemos)

@app.route('/api/mymemo/create', methods=['POST'])
@login_required
def create_mymemo():
    # JSON 또는 FormData 모두 처리
    if request.content_type and 'multipart/form-data' in request.content_type:
        title = request.form.get('title')
        content = request.form.get('content')
        parent_id = request.form.get('parent_id')
        project_id = request.form.get('project_id')
        product_id = request.form.get('product_id')
        meta_data_str = request.form.get('meta_data', '{}')
        try:
            meta_data = json.loads(meta_data_str) if meta_data_str else {}
        except:
            meta_data = {}
    else:
        data = request.json or {}
        title = data.get('title')
        content = data.get('content')
        parent_id = data.get('parent_id')
        project_id = data.get('project_id')
        product_id = data.get('product_id')
        meta_data = data.get('meta_data', {})

    # smemo 아이템은 빈 content 허용 (meta_data에 smemo_type이 있으면 OK)
    is_smemo_item = meta_data and 'smemo_type' in meta_data
    if not content and not is_smemo_item:
        return jsonify({'success': False, 'message': 'Content is required'}), 400

    new_mymemo = MyMemo(
        title=title if title else None,
        content=content,
        parent_id=parent_id if parent_id else None,
        project_id=project_id if project_id else None,
        product_id=product_id if product_id else None,
        meta_data=meta_data,
        created_at=datetime.now(pytz.timezone('Asia/Seoul'))
    )
    
    # 이미지 파일 처리
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file and image_file.filename:
            filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(image_file.filename)}"
            upload_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', filename)
            image_file.save(upload_path)
            new_mymemo.image_filename = filename
    
    # 일반 파일 처리
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
            upload_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', filename)
            file.save(upload_path)
            new_mymemo.file_filename = filename
    
    db.session.add(new_mymemo)
    db.session.commit()

    return jsonify({'success': True, 'id': new_mymemo.id})

@app.route('/api/mymemo/update/<int:id>', methods=['POST'])
@login_required
def update_mymemo(id):
    mymemo = MyMemo.query.get_or_404(id)
    
    # JSON 또는 FormData 모두 처리
    if request.content_type and 'multipart/form-data' in request.content_type:
        title = request.form.get('title')
        content = request.form.get('content')
        project_id = request.form.get('project_id')
        product_id = request.form.get('product_id')
        meta_data_str = request.form.get('meta_data')
        delete_image = request.form.get('delete_image') == 'true'
        delete_file = request.form.get('delete_file') == 'true'
        
        if title is not None:
            mymemo.title = title if title else None
        if content is not None:
            mymemo.content = content
        if project_id is not None:
            mymemo.project_id = project_id if project_id else None
        if product_id is not None:
            mymemo.product_id = product_id if product_id else None
        if meta_data_str:
            try:
                new_meta = json.loads(meta_data_str)
                current_meta = mymemo.meta_data if mymemo.meta_data else {}
                current_meta.update(new_meta)
                mymemo.meta_data = current_meta
                flag_modified(mymemo, "meta_data")
            except:
                pass
        
        # 이미지 삭제
        if delete_image and mymemo.image_filename:
            old_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', mymemo.image_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            mymemo.image_filename = None
        
        # 파일 삭제
        if delete_file and mymemo.file_filename:
            old_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', mymemo.file_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            mymemo.file_filename = None
        
        # 새 이미지 업로드
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                # 기존 이미지 삭제
                if mymemo.image_filename:
                    old_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', mymemo.image_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(image_file.filename)}"
                upload_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', filename)
                image_file.save(upload_path)
                mymemo.image_filename = filename
        
        # 새 파일 업로드
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                # 기존 파일 삭제
                if mymemo.file_filename:
                    old_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', mymemo.file_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
                upload_path = os.path.join(BASE_DIR, 'pdata', 'MyMemo', filename)
                file.save(upload_path)
                mymemo.file_filename = filename
    else:
        data = request.json or {}
        
        if 'content' in data:
            mymemo.content = data['content']
        if 'title' in data:
            mymemo.title = data['title']
        if 'meta_data' in data:
            current_meta = mymemo.meta_data if mymemo.meta_data else {}
            current_meta.update(data['meta_data'])
            mymemo.meta_data = current_meta
            flag_modified(mymemo, "meta_data")
        if 'project_id' in data:
            mymemo.project_id = data['project_id']
        if 'product_id' in data:
            mymemo.product_id = data['product_id']

    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/mymemo/update_position/<int:id>', methods=['POST'])
@login_required
def update_mymemo_position(id):
    mymemo = MyMemo.query.get_or_404(id)
    data = request.json
    
    # 위치 정보만 업데이트 (x, y)
    if not mymemo.meta_data:
        mymemo.meta_data = {}
    
    if 'x' in data:
        mymemo.meta_data['x'] = data['x']
    if 'y' in data:
        mymemo.meta_data['y'] = data['y']
        
    flag_modified(mymemo, "meta_data")
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/mymemo/update_size/<int:id>', methods=['POST'])
@login_required
def update_mymemo_size(id):
    mymemo = MyMemo.query.get_or_404(id)
    data = request.json
    
    # 크기 정보만 업데이트 (width, height)
    if not mymemo.meta_data:
        mymemo.meta_data = {}
    
    if 'width' in data:
        mymemo.meta_data['width'] = data['width']
    if 'height' in data:
        mymemo.meta_data['height'] = data['height']
        
    flag_modified(mymemo, "meta_data")
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/trash')
@login_required
def trash():
    """휴지통 페이지"""
    from collections import defaultdict
    
    # 삭제된 항목만 조회
    deleted_items = MyMemo.query.filter(MyMemo.deleted_at.isnot(None)).order_by(MyMemo.deleted_at.desc()).all()
    
    # 날짜별로 그룹화
    items_by_date = defaultdict(list)
    
    for item in deleted_items:
        if item.deleted_at:
            date_str = item.deleted_at.strftime('%Y년 %m월 %d일')
            items_by_date[date_str].append(item)
    
    return render_template('trash.html', deleted_items_by_date=dict(items_by_date))


@app.route('/api/mymemo/delete/<int:id>', methods=['POST'])
@login_required
def delete_mymemo(id):
    """Soft delete: 실제 삭제 대신 deleted_at에 타임스탬프 기록"""
    mymemo = MyMemo.query.get_or_404(id)
    
    # Soft delete
    mymemo.deleted_at = datetime.now(pytz.timezone('Asia/Seoul'))
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/mymemo/restore/<int:id>', methods=['POST'])
@login_required
def restore_mymemo(id):
    """휴지통에서 복원"""
    mymemo = MyMemo.query.get_or_404(id)
    
    if mymemo.deleted_at is None:
        return jsonify({'success': False, 'message': 'Item is not deleted'}), 400
    
    mymemo.deleted_at = None
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/mymemo/delete-permanently/<int:id>', methods=['POST'])
@login_required
def delete_mymemo_permanently(id):
    """완전 삭제: DB와 파일 모두 삭제"""
    mymemo = MyMemo.query.get_or_404(id)
    
    # 연결된 파일이 있으면 실제 파일도 삭제
    upload_folder = os.path.join(BASE_DIR, 'pdata', 'MyMemo')
    
    if mymemo.image_filename:
        image_path = os.path.join(upload_folder, mymemo.image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"✅ Permanently deleted image file: {mymemo.image_filename}")
            except Exception as e:
                print(f"❌ Failed to delete image file: {e}")
    
    if mymemo.file_filename:
        file_path = os.path.join(upload_folder, mymemo.file_filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✅ Permanently deleted file: {mymemo.file_filename}")
            except Exception as e:
                print(f"❌ Failed to delete file: {e}")
    
    db.session.delete(mymemo)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/mymemo/empty-trash', methods=['POST'])
@login_required
def empty_trash():
    """휴지통 비우기: 모든 삭제된 항목 완전 삭제"""
    deleted_items = MyMemo.query.filter(MyMemo.deleted_at.isnot(None)).all()
    
    upload_folder = os.path.join(BASE_DIR, 'pdata', 'MyMemo')
    deleted_count = 0
    
    for item in deleted_items:
        # 파일 삭제
        if item.image_filename:
            image_path = os.path.join(upload_folder, item.image_filename)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"❌ Failed to delete image file: {e}")
        
        if item.file_filename:
            file_path = os.path.join(upload_folder, item.file_filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"❌ Failed to delete file: {e}")
        
        db.session.delete(item)
        deleted_count += 1
    
    db.session.commit()
    
    return jsonify({'success': True, 'deleted_count': deleted_count})


@app.route('/api/mymemo/create_linked_memo/<int:id>', methods=['POST'])
@login_required
def create_linked_note_from_mymemo(id):
    mymemo = MyMemo.query.get_or_404(id)
    
    # 이미 연결된 노트가 있는지 확인
    if mymemo.linked_note_id:
        return jsonify({'success': False, 'message': 'Already linked to a note'}), 400
        
    # 새 노트 생성 (Note 모듈 사용)
    # 제목은 내용의 첫 줄이나 앞부분 사용
    title = mymemo.content.split('\n')[0][:50]
    if len(title) < len(mymemo.content.split('\n')[0]):
        title += "..."
        
    # Slug 생성
    slug = title.replace(' ', '-').lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    
    new_note = Note(
        title=title,
        content=mymemo.content,
        slug=slug
        # products connection could be added if MyMemo has product_id
    )
    
    # Product 연결
    if mymemo.product_id:
         product = Product.query.get(mymemo.product_id)
         if product:
             new_note.products.append(product)

    db.session.add(new_note)
    db.session.commit()
    
    # ID 기반 슬러그 보정
    new_note.slug = f'{new_note.id}-{slug}'
    
    # 연결
    mymemo.linked_note_id = new_note.id
    db.session.commit()
    
    return jsonify({'success': True, 'note_id': new_note.id, 'slug': new_note.slug})

# MyMemo API: 제목 목록 조회
@app.route('/api/mymemo/titles')
@login_required
def get_mymemo_titles():
    """제목별 MyMemo 개수 반환 (조사 주제 목록)"""
    titles = db.session.query(
        MyMemo.title,
        func.count(MyMemo.id).label('count')
    ).filter(
        MyMemo.title.isnot(None),
        MyMemo.title != ''
    ).group_by(MyMemo.title).order_by(MyMemo.title).all()
    
    return jsonify([
        {'title': t[0], 'count': t[1]} 
        for t in titles
    ])

# MyMemo API: 여러 MyMemo를 Note로 통합 (smemo 지원 포함)
@app.route('/api/mymemo/merge_to_note', methods=['POST'])
@login_required
def merge_mymemos_to_note():
    """선택된 MyMemo들을 하나의 Note로 통합 (smemo 스티커 메모 지원)"""
    mymemo_ids = request.json.get('mymemo_ids', [])
    
    if not mymemo_ids:
        return jsonify({'success': False, 'message': 'No memos selected'}), 400
    
    # MyMemo들 조회 (생성일 순)
    mymemos = MyMemo.query.filter(
        MyMemo.id.in_(mymemo_ids)
    ).order_by(MyMemo.created_at).all()
    
    if not mymemos:
        return jsonify({'success': False, 'message': 'No memos found'}), 404
    
    # smemo 메모인지 확인 (meta_data에 smemo_type이 있는지)
    is_smemo = False
    first_memo = mymemos[0]
    meta = first_memo.meta_data or {}
    if meta.get('smemo_type'):
        is_smemo = True
    
    # 제목 결정
    if is_smemo:
        # smemo의 경우: meta_data의 tags를 제목으로 사용하거나, 내용 첫 줄 사용
        smemo_tags = meta.get('tags', '')
        if smemo_tags:
            title = smemo_tags.split(',')[0].strip()  # 첫 번째 태그를 제목으로
        elif first_memo.content and first_memo.content.strip():
            # 내용 첫 줄에서 제목 추출 (최대 50자)
            first_line = first_memo.content.strip().split('\n')[0][:50]
            title = first_line if first_line else f"스티커 메모 {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y%m%d')}"
        else:
            title = f"스티커 메모 {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y%m%d')}"
    else:
        # 일반 MyMemo의 경우
        title = first_memo.title or f"자료 정리 {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y%m%d')}"
    
    # 마크다운 생성 (smemo/일반 분기 처리)
    if is_smemo:
        content = generate_smemo_note_markdown(mymemos, title)
    else:
        content = generate_consolidated_markdown_from_mymemos(mymemos, title)
    
    # slug 생성 (한글 지원)
    slug = generate_safe_slug(title)
    
    # Note 생성
    from note.models import Note
    new_note = Note(title=title, content=content, slug=slug)
    
    db.session.add(new_note)
    db.session.flush()  # ID 생성
    
    # slug에 ID 추가하여 유일성 보장
    new_note.slug = f'{new_note.id}-{slug}'
    
    # MyMemo들을 Note에 연결
    for memo in mymemos:
        memo.linked_note_id = new_note.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'note_id': new_note.id,
        'note_slug': new_note.slug
    })


def generate_safe_slug(title):
    """한글을 포함한 제목을 안전한 slug로 변환"""
    import hashlib
    
    # 날짜 prefix
    date_prefix = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y%m%d')
    
    # 기본 slug: 공백을 하이픈으로
    base_slug = title.replace(' ', '-').lower()
    
    # ASCII가 아닌 문자(한글 등)가 있으면 해시로 변환
    try:
        base_slug.encode('ascii')
        # ASCII만 있는 경우
        safe_slug = re.sub(r'[^\w\s-]', '', base_slug)
        safe_slug = re.sub(r'[-\s]+', '-', safe_slug)
    except UnicodeEncodeError:
        # 한글 등 비ASCII 문자가 있는 경우
        # 짧은 해시 생성
        hash_suffix = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
        safe_slug = f"note-{hash_suffix}"
    
    return f"{date_prefix}-{safe_slug}"


def generate_smemo_note_markdown(mymemos, title):
    """스티커 메모의 제목, 표, 헤더를 모두 제거하고 본문만 추출"""
    lines = []
    for m in mymemos:
        if m.content and m.content.strip():
            # 불필요한 헤더 없이 내용만 추가
            lines.append(f"{m.content}\n\n")
    return "".join(lines)

def generate_consolidated_markdown_from_mymemos(mymemos, title):
    """일반 메모의 본문과 미디어 파일만 추출"""
    lines = []
    
    # 1. 본문 텍스트
    for m in mymemos:
        if m.content and m.content.strip():
            lines.append(f"{m.content}\n\n")
    
    # 2. 이미지 (있는 경우만 하단에 표시)
    images = [m for m in mymemos if m.image_filename]
    if images:
        lines.append("---\n")
        for m in images:
            lines.append(f"![이미지](/mymemo/uploads/{m.image_filename})\n\n")
            
    # 3. 파일 (있는 경우만 최하단에 표시)
    files = [m for m in mymemos if m.file_filename]
    if files:
        if not images: lines.append("---\n")
        for m in files:
            lines.append(f"📎 첨부파일: [{m.file_filename}](/mymemo/uploads/{m.file_filename})\n\n")
            
    return "".join(lines)

# ============================================================================
# Smemo Routes (using MyMemo model)
# ============================================================================

@app.route('/smemo')
@login_required
def smemo():
    """Smemo 페이지 - 포스트잇과 폴라로이드 사진"""
    settings = load_settings()
    settings = load_settings()
    # 기본 페이지는 전체 보기 또는 특정 로직에 따름 (현재는 전체 보기)
    return render_template('smemo.html', settings=settings, board_title=None)

@app.route('/smemo/<path:board_title>')
@login_required
def smemo_board_view(board_title):
    """Smemo 특정 보드 페이지"""
    settings = load_settings()
    return render_template('smemo.html', settings=settings, board_title=board_title)

# app.py 또는 routes 파일 내의 해당 부분 수정
@app.route('/api/mymemo/smemo-items', methods=['GET'])
@login_required
def get_smemo_items():
    """Smemo 아이템 조회 (연결된 Note의 slug 포함)"""
    from note.models import Note  # Note 모델 임포트 (경로에 맞게 수정하세요)
    
    title_filter = request.args.get('title')
    
    query = MyMemo.query.filter(MyMemo.deleted_at.is_(None))  # 삭제되지 않은 항목만
    
    if title_filter:
        # Specific board: show only items with this exact title
        query = query.filter(MyMemo.title == title_filter)
    else:
        # Main board: show only items with NO title (null)
        query = query.filter(MyMemo.title.is_(None))
    
    mymemos = query.all()
    smemo_items = []
    
    for memo in mymemos:
        if memo.meta_data and 'smemo_type' in memo.meta_data:
            # 기본 데이터
            item_data = {
                'id': memo.id,
                'content': memo.content,
                'meta_data': memo.meta_data,
                'created_at': memo.created_at.isoformat() if memo.created_at else None,
                'title': memo.title,
                'image_filename': memo.image_filename,  # 업로드된 이미지 파일명
                'note_slug': None  # 기본값은 없음
            }
            
            # linked_note_id가 있으면 Note 테이블에서 slug를 찾아옴
            if memo.linked_note_id:
                linked_note = Note.query.get(memo.linked_note_id)
                if linked_note:
                    item_data['note_slug'] = linked_note.slug
            
            smemo_items.append(item_data)
    
    return jsonify(smemo_items)

@app.route('/note/s/<path:slug>')
@login_required
def note_detail(slug):
    """
    확장된 노트를 보여주는 상세 페이지
    한글 슬러그 처리를 위해 <path:slug>를 사용합니다.
    """
    from note.models import Note  # Note 모델 임포트 확인
    
    # 1. 데이터베이스에서 슬러그로 노트 조회
    note = Note.query.filter_by(slug=slug).first()
    
    # 2. 만약 해당 슬러그의 노트가 없다면 404 에러 반환
    if not note:
        # 슬러그에 한글이 포함되어 인코딩 문제가 있을 수 있으므로 
        # 디버깅을 위해 print를 찍어볼 수 있습니다.
        print(f"노트를 찾을 수 없음: {slug}")
        abort(404)
        
    # 3. 노트 상세 페이지 렌더링 (해당 템플릿 파일이 있어야 합니다)
    return render_template('note_detail.html', note=note)