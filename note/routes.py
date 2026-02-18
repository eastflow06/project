# note/routes.py (Product 연결 기능 추가)
from flask import render_template, request, redirect, url_for, abort, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
import os
import re
import uuid
import markdown
from . import note_bp
from .models import Note
from models import db, Product

# --- 한글 파일명 지원 함수 ---
def secure_filename_with_unicode(filename):
    """한글을 포함한 유니코드 파일명을 안전하게 처리합니다."""
    # 파일명에서 디렉토리 구분자 제거
    filename = os.path.basename(filename)
    # 널 바이트 제거
    filename = filename.replace('\x00', '')
    # 위험한 문자 제거
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 앞뒤 공백 제거
    filename = filename.strip()
    # 파일명 길이 제한
    filename = filename[:255]
    return filename

# --- 유틸리티 함수 (Markdown 렌더링) ---
def process_image_size(content):
    """이미지 크기 문법을 처리합니다. ![alt](url | width) -> <img src="url" alt="alt" width="width">"""
    # 패턴: ![alt](url | width) 또는 ![alt](url | widthxheight)
    pattern = r'!\[([^\]]*)\]\(([^|)]+)\s*\|\s*(\d+)(?:x(\d+))?\s*\)'

    def replace_image(match):
        alt = match.group(1)
        url = match.group(2).strip()
        width = match.group(3)
        height = match.group(4)

        if height:
            return f'<img src="{url}" alt="{alt}" width="{width}" height="{height}">'
        else:
            return f'<img src="{url}" alt="{alt}" width="{width}">'

    return re.sub(pattern, replace_image, content)

def render_note_content(note_content):
    """마크다운 텍스트를 HTML로 변환합니다."""
    if not note_content:
        return ""
    # 이미지 크기 문법 먼저 처리
    processed_content = process_image_size(note_content)
    return markdown.markdown(processed_content, extensions=['fenced_code', 'tables', 'nl2br'])

# --- 1. 노트 목록 보기 ---
@note_bp.route('/')
def list_notes():
    """노트 목록을 보여줍니다."""
    try:
        notes = Note.query.order_by(Note.created_at.desc()).all()
        return render_template('list_notes.html', notes=notes)
    except Exception as e:
        print(f"Error in list_notes: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>에러 발생</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", 500

# --- 2. 노트 생성/편집 (Product 연결 포함) ---
@note_bp.route('/create', methods=['GET', 'POST'])
@note_bp.route('/edit/<int:note_id>', methods=['GET', 'POST'])
def create_or_edit_note(note_id=None):
    """노트를 생성하거나 기존 노트를 편집합니다."""
    note = None
    if note_id:
        note = Note.query.get_or_404(note_id)

    # 모든 Product 가져오기 (드롭다운용)
    all_products = Product.query.order_by(Product.name).all()

    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            
            # 선택된 Product ID들 가져오기 (다중 선택)
            selected_product_ids = request.form.getlist('product_ids')
            
            if not title:
                return "제목을 입력해주세요.", 400
            
            # 새 노트 생성
            if not note:
                slug = title.replace(' ', '-').lower()
                import re
                slug = re.sub(r'[^\w\s-]', '', slug)
                slug = re.sub(r'[-\s]+', '-', slug)
                
                new_note = Note(title=title, content=content, slug=slug)
                
                # Product 연결 (방법 1: 다대다 관계)
                if selected_product_ids:
                    selected_products = Product.query.filter(Product.id.in_(selected_product_ids)).all()
                    new_note.products = selected_products
                
                # 또는 (방법 2: 텍스트 필드)
                # new_note.product_ids = ','.join(selected_product_ids)
                
                db.session.add(new_note)
                db.session.commit()
                
                # ID 기반 슬러그 고유성 확보
                new_note.slug = f'{new_note.id}-{slug}'
                db.session.commit()
                
                return redirect(url_for('note.view_note_by_slug', slug=new_note.slug))
            
            # 기존 노트 수정
            else:
                note.title = title
                note.content = content
                
                # Product 업데이트 (방법 1: 다대다 관계)
                if selected_product_ids:
                    selected_products = Product.query.filter(Product.id.in_(selected_product_ids)).all()
                    note.products = selected_products
                else:
                    note.products = []
                
                # 또는 (방법 2: 텍스트 필드)
                # note.product_ids = ','.join(selected_product_ids) if selected_product_ids else None
                
                db.session.commit()
                return redirect(url_for('note.view_note_by_slug', slug=note.slug))
                
        except Exception as e:
            db.session.rollback()
            print(f"Error in create_or_edit_note: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"<h1>노트 저장 중 에러</h1><p>{str(e)}</p>", 500

    return render_template('Notes.html', note=note, all_products=all_products)

# --- 3. 노트 보기 (Product 정보 포함) ---
@note_bp.route('/s/<string:slug>')
def view_note_by_slug(slug):
    """슬러그 기반으로 특정 노트를 보여줍니다."""
    try:
        note = Note.query.filter_by(slug=slug).first_or_404()
        rendered_content = render_note_content(note.content)
        external_url = url_for('note.view_note_by_slug', slug=note.slug, _external=True)
        
        return render_template('view_note.html', 
                             note=note, 
                             content=rendered_content, 
                             external_url=external_url)
    except Exception as e:
        print(f"Error viewing note: {str(e)}")
        import traceback
        traceback.print_exc()
        abort(404)

# --- 3-1. ID 기반 노트 보기 ---
@note_bp.route('/view/<int:note_id>')
def view_note_by_id(note_id):
    """ID 기반으로 노트를 보여줍니다."""
    try:
        note = Note.query.get_or_404(note_id)
        rendered_content = render_note_content(note.content)
        external_url = url_for('note.view_note_by_slug', slug=note.slug, _external=True)
        
        return render_template('view_note.html', 
                             note=note, 
                             content=rendered_content, 
                             external_url=external_url)
    except Exception as e:
        print(f"Error viewing note by ID: {str(e)}")
        import traceback
        traceback.print_exc()
        abort(404)

# --- 4. Product별 노트 목록 ---
@note_bp.route('/by-product/<int:product_id>')
def notes_by_product(product_id):
    """특정 Product와 연결된 노트들을 보여줍니다."""
    try:
        product = Product.query.get_or_404(product_id)
        
        # 방법 1: 다대다 관계 사용
        notes = product.notes
        
        # 방법 2: 텍스트 필드 사용 시
        # notes = Note.query.filter(Note.product_ids.like(f'%{product_id}%')).all()
        
        return render_template('list_notes.html', 
                             notes=notes, 
                             product=product)
    except Exception as e:
        print(f"Error in notes_by_product: {str(e)}")
        abort(404)

# --- 5. 이미지 업로드 (TOAST UI Editor 훅을 위한 API) ---
def allowed_file(filename):
    """허용된 이미지 확장자를 확인합니다."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

@note_bp.route('/upload_image', methods=['POST'])
def upload_image():
    """TOAST UI Editor에서 이미지를 붙여넣거나 드래그할 때 호출됩니다."""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image part'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            # 한글 파일명 지원
            original_filename = file.filename
            sanitized_filename = secure_filename_with_unicode(original_filename)

            # 파일명이 비어있으면 기본 이름 사용
            if not sanitized_filename or sanitized_filename == '':
                sanitized_filename = 'image.png'

            # UUID 추가로 중복 방지
            short_uuid = uuid.uuid4().hex[:8]
            base_name, ext = os.path.splitext(sanitized_filename)
            filename = f"{short_uuid}_{base_name}{ext}"

            upload_folder = current_app.config['NOTE_UPLOAD_FOLDER']

            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # URL 인코딩 없이 직접 경로 생성 (한글 파일명 보존)
            image_url = f"/pdata/note/images/{filename}"
            return jsonify({'url': image_url}), 200

        return jsonify({'error': 'File type not allowed'}), 400
    except Exception as e:
        print(f"Error uploading image: {str(e)}")
        return jsonify({'error': str(e)}), 500

# --- 6. 이미지 서빙 ---
@note_bp.route('/images/<filename>')
def serve_image(filename):
    """업로드된 이미지를 제공합니다."""
    try:
        upload_folder = current_app.config['NOTE_UPLOAD_FOLDER']
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        print(f"Error serving image: {str(e)}")
        abort(404)

# --- 7. 노트 삭제 ---
@note_bp.route('/delete/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    """노트를 삭제합니다."""
    try:
        note = Note.query.get_or_404(note_id)
        
        # MyMemo에서 이 노트를 참조하는 것들의 linked_note_id를 NULL로 설정
        from models import MyMemo
        linked_mymemos = MyMemo.query.filter_by(linked_note_id=note_id).all()
        for mymemo in linked_mymemos:
            mymemo.linked_note_id = None
        
        db.session.delete(note)
        db.session.commit()
        return redirect(url_for('note.list_notes'))
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting note: {str(e)}")
        return f"삭제 중 에러: {str(e)}", 500

# --- 8. API: Product 검색 (자동완성용) ---
@note_bp.route('/api/products/search')
def search_products():
    """Product 검색 API (자동완성용)"""
    try:
        query = request.args.get('q', '').strip()
        if query:
            products = Product.query.filter(Product.name.like(f'%{query}%')).limit(10).all()
        else:
            products = Product.query.order_by(Product.name).limit(10).all()
        
        return jsonify({
            'success': True,
            'products': [{'id': p.id, 'title': p.title} for p in products]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 9. 테스트 라우트 ---
@note_bp.route('/test')
def test():
    """Blueprint 작동 테스트"""
    product_count = Product.query.count()
    note_count = Note.query.count()
    return f"""
    <h1>✅ Note Blueprint is working!</h1>
    <p>Using shared database (project.db)</p>
    <ul>
        <li>Total Products: {product_count}</li>
        <li>Total Notes: {note_count}</li>
    </ul>
    """

# --- 10. 이미지 갤러리 ---
@note_bp.route('/images')
def image_gallery():
    """업로드된 이미지 목록을 보여줍니다."""
    try:
        upload_folder = current_app.config['NOTE_UPLOAD_FOLDER']

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        # 이미지 파일 목록 가져오기
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        images = []

        for filename in os.listdir(upload_folder):
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext in allowed_extensions:
                file_path = os.path.join(upload_folder, filename)
                file_stat = os.stat(file_path)
                images.append({
                    'filename': filename,
                    'size': file_stat.st_size,
                    'modified': file_stat.st_mtime,
                    'url': f"/pdata/note/images/{filename}"
                })

        # 최신순 정렬
        images.sort(key=lambda x: x['modified'], reverse=True)

        return render_template('image_gallery.html', images=images)
    except Exception as e:
        print(f"Error in image_gallery: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>에러 발생</h1><p>{str(e)}</p>", 500

# --- 11. 이미지 삭제 ---
@note_bp.route('/images/delete/<path:filename>', methods=['POST'])
def delete_image(filename):
    """이미지를 삭제합니다."""
    try:
        upload_folder = current_app.config['NOTE_UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)

        # 보안: 경로 탐색 방지
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
            return jsonify({'success': False, 'error': '잘못된 경로'}), 400

        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': True, 'message': '이미지가 삭제되었습니다.'})
        else:
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'}), 404
    except Exception as e:
        print(f"Error deleting image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# --- 12. 갤러리용 이미지 업로드 ---
@note_bp.route('/images/upload', methods=['POST'])
def gallery_upload_image():
    """갤러리에서 이미지를 업로드합니다."""
    try:
        if 'images' not in request.files:
            return jsonify({'success': False, 'error': '이미지가 없습니다.'}), 400

        files = request.files.getlist('images')
        uploaded = []

        for file in files:
            if file.filename == '':
                continue

            if file and allowed_file(file.filename):
                original_filename = file.filename
                sanitized_filename = secure_filename_with_unicode(original_filename)

                if not sanitized_filename:
                    sanitized_filename = 'image.png'

                short_uuid = uuid.uuid4().hex[:8]
                base_name, ext = os.path.splitext(sanitized_filename)
                filename = f"{short_uuid}_{base_name}{ext}"

                upload_folder = current_app.config['NOTE_UPLOAD_FOLDER']
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                uploaded.append({
                    'filename': filename,
                    'url': f"/pdata/note/images/{filename}"
                })

        if uploaded:
            return jsonify({'success': True, 'uploaded': uploaded})
        else:
            return jsonify({'success': False, 'error': '업로드할 수 있는 파일이 없습니다.'}), 400
    except Exception as e:
        print(f"Error uploading images: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500