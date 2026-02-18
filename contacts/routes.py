from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
import json
import os
from functools import wraps

# 블루프린트 설정
contact_bp = Blueprint("contact", __name__, template_folder="templates")

# JSON 파일 경로
CONTACTS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'contacts.json')

# 데이터 디렉토리 확인 및 생성
def ensure_data_dir():
    data_dir = os.path.dirname(CONTACTS_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

# 🌟 새로운 함수: 상위 settings.json에서 Contacts 배경 설정값을 읽어오는 함수
def load_contacts_settings():
    """
    상위 폴더의 settings.json에서 Contacts 관련 설정값을 로드합니다.
    새로운 계층 구조(Contacts.bg_url)와 기존 flat 구조(contacts_bg_url) 모두 지원합니다.
    """
    try:
        # Contacts 폴더의 상위 폴더(project)에 settings.json이 있다고 가정하고 경로 계산
        settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')
        
        if not os.path.exists(settings_path):
            if hasattr(current_app, 'logger'):
                current_app.logger.warning(f"Settings file not found at: {settings_path}")
            # 파일이 없으면 기본값 반환
            return {
                'contacts_bg_url': '',
                'contacts_bg_color': '#ffffff',
                'contacts_bg_opacity': '1.0',
            }

        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
            # 🌟 새로운 계층 구조 지원 (우선순위 높음)
            if 'Contacts' in settings and isinstance(settings['Contacts'], dict):
                contacts_settings = settings['Contacts']
                return {
                    'contacts_bg_url': contacts_settings.get('bg_url', ''),
                    'contacts_bg_color': contacts_settings.get('bg_color', '#ffffff'),
                    'contacts_bg_opacity': contacts_settings.get('opacity', '1.0'),
                }
            
            # 기존 flat 구조 지원 (하위 호환성)
            return {
                'contacts_bg_url': settings.get('contacts_bg_url', ''),
                'contacts_bg_color': settings.get('contacts_bg_color', '#ffffff'),
                'contacts_bg_opacity': settings.get('contacts_bg_opacity', '1.0'),
            }
            
    except Exception as e:
        # JSON 디코딩 오류 등 치명적인 오류 발생 시 기본 설정 반환
        if hasattr(current_app, 'logger'):
             current_app.logger.error(f"Error loading settings.json in contacts blueprint: {e}", exc_info=True)
        return {
            'contacts_bg_url': '',
            'contacts_bg_color': '#ffffff',
            'contacts_bg_opacity': '1.0',
        }
# ----------------------------------------------------------------------


# 연락처 데이터 로드
def load_contacts():
    ensure_data_dir()
    try:
        contacts = []
        with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
            contacts = json.load(f)
        
        # 스키마 마이그레이션 및 유효성 검사: 모든 연락처가 유효한 priority_score (정수)를 가지도록 보장
        for contact in contacts:
            score_value = contact.get("priority_score", 0) # 기본값 0 (정수)
            try:
                # 안전하게 정수로 변환 (소수점은 버림 처리)
                contact["priority_score"] = int(float(score_value))
            except (ValueError, TypeError):
                # 변환 실패 시 기본값 0
                contact["priority_score"] = 0
                
        return contacts
        
    except (FileNotFoundError, json.JSONDecodeError):
        # 기본 데이터 (priority_score를 정수로 설정)
        default_contacts = [
            {"id": 1, "name": "김가영", "position": "부장", "department": "경영지원부", "phone": "010-7758-1855", "extension": "602", "email": "kgy1855@hpnc.co.kr", "is_favorite": True, "priority_score": 8},
            {"id": 2, "name": "하용찬", "position": "이사", "department": "경영지원부", "phone": "010-3323-2950", "extension": "605", "is_favorite": True, "priority_score": 9}, 
            {"id": 3, "name": "한채은", "position": "과장", "department": "경영지원부", "phone": "010-9885-5519", "extension": "603", "is_favorite": False, "priority_score": 4},
            {"id": 4, "name": "이종욱", "position": "부사장", "department": "임원", "phone": "010-4280-1945", "extension": "506", "email": "", "is_favorite": False, "priority_score": 7},
            {"id": 5, "name": "김태만", "position": "이사", "department": "관리부", "phone": "010-3792-1945", "extension": "502", "email": "", "is_favorite": True, "priority_score": 5},
        ]
        save_contacts(default_contacts)
        return default_contacts

# 연락처 데이터 저장
def save_contacts(contacts):
    ensure_data_dir()
    with open(CONTACTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(contacts, f, ensure_ascii=False, indent=4)

# 새로운 ID 생성
def get_next_id(contacts):
    if not contacts:
        return 1
    return max(contact["id"] for contact in contacts) + 1

# 📌 즐겨찾기 연락처 목록 페이지
@contact_bp.route('/')
def index():
    contacts = load_contacts()
    # 🌟 설정값 로드 및 템플릿 전달
    settings = load_contacts_settings()
    
    # 1. 즐겨찾기만 필터링
    favorite_contacts = [c for c in contacts if c.get("is_favorite")]
    
    # 2. 정렬 함수 정의: 가중치(내림차순)와 이름(오름차순) 기반
    def favorite_sort_key(contact):
        priority_score = contact.get("priority_score", 0) 
        return (-priority_score, contact["name"])
        
    # 3. 정렬 적용
    sorted_favorites = sorted(favorite_contacts, key=favorite_sort_key)
    
    # 템플릿에 설정값 전달
    return render_template("add_index.html", 
                           contacts=sorted_favorites,
                           settings=settings) # 👈 설정값 전달

# 📌 모든 연락처 목록 페이지 (✅ 복합 가중치 기반 정렬)
@contact_bp.route('/all')
def all_contacts():
    contacts = load_contacts()
    # 🌟 설정값 로드 및 템플릿 전달
    settings = load_contacts_settings()
    
    # 즐겨찾기(가중치), 우선순위 점수 및 이름 기반 정렬 함수 정의
    def sort_key(contact):
        favorite_weight = 10 if contact.get("is_favorite", False) else 0
        priority_score = contact.get("priority_score", 0) 
        return (-favorite_weight, -priority_score, contact["name"]) 
    
    # 정렬 적용
    sorted_contacts = sorted(contacts, key=sort_key)
    
    # 템플릿에 설정값 전달
    return render_template("add_all.html", 
                           contacts=sorted_contacts,
                           settings=settings) # 👈 설정값 전달

# 📌 연락처 추가 (✅ priority_score 저장 및 자동 완성 목록 전달 로직 추가)
@contact_bp.route('/add', methods=['GET', 'POST'])
def add_contact():
    contacts = load_contacts()
    
    # 자동 완성을 위해 기존 연락처에서 직급과 부서 목록 추출
    unique_positions = sorted(list(set(c.get("position", "") for c in contacts if c.get("position"))))
    unique_departments = sorted(list(set(c.get("department", "") for c in contacts if c.get("department"))))
    
    if request.method == 'POST':
        # 폼 데이터에서 priority_score를 안전하게 가져와 정수로 변환
        try:
            priority_score = int(request.form.get("priority_score", 0))
        except (ValueError, TypeError):
            priority_score = 0 

        new_contact = {
            "id": get_next_id(contacts),
            "name": request.form["name"],
            "position": request.form["position"],
            "department": request.form["department"],
            "phone": request.form["phone"],
            "extension": request.form["extension"],
            "email": request.form.get("email", ""),
            "is_favorite": "is_favorite" in request.form,
            "priority_score": priority_score,
        }
        contacts.append(new_contact)
        save_contacts(contacts)
        return redirect(url_for("contact.all_contacts"))
    
    # GET 요청 시, 제안 목록을 템플릿에 전달
    return render_template("add_add_contact.html", 
                           unique_positions=unique_positions, 
                           unique_departments=unique_departments)

# 📌 연락처 수정 (✅ priority_score 업데이트 로직 포함)
@contact_bp.route('/edit/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contacts = load_contacts()
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    if not contact:
        return "Contact not found", 404
    
    if request.method == 'POST':
        # 폼 데이터에서 priority_score를 안전하게 가져와 정수로 변환
        try:
            priority_score = int(request.form.get("priority_score", 0))
        except (ValueError, TypeError):
            priority_score = 0
            
        contact["name"] = request.form["name"]
        contact["position"] = request.form["position"]
        contact["department"] = request.form["department"]
        contact["phone"] = request.form["phone"]
        contact["extension"] = request.form["extension"]
        contact["email"] = request.form.get("email", "")
        contact["is_favorite"] = "is_favorite" in request.form
        contact["priority_score"] = priority_score
        save_contacts(contacts)
        return redirect(url_for("contact.all_contacts"))
    
    # GET 요청 시, contact 객체가 유효한 priority_score를 가지도록 load_contacts에서 보장함
    return render_template("add_edit_contact.html", contact=contact)

# 📌 연락처 상세 보기
@contact_bp.route('/contact/<int:contact_id>')
def contact_detail(contact_id):
    contacts = load_contacts()
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    if contact:
        return render_template("add_contact_detail.html", contact=contact)
    return "Contact not found", 404

# 📌 연락처 삭제
@contact_bp.route('/delete/<int:contact_id>')
def delete_contact(contact_id):
    contacts = load_contacts()
    contacts = [c for c in contacts if c["id"] != contact_id]
    save_contacts(contacts)
    return redirect(url_for("contact.all_contacts"))

# 📌 즐겨찾기 토글
@contact_bp.route('/toggle_favorite/<int:contact_id>')
def toggle_favorite(contact_id):
    contacts = load_contacts()
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    if contact:
        contact["is_favorite"] = not contact["is_favorite"]
        save_contacts(contacts)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "is_favorite": contact["is_favorite"]})
        
        referrer = request.referrer or url_for('contact.all_contacts')
        return redirect(referrer)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": False}), 404
    
    return redirect(url_for("contact.all_contacts"))