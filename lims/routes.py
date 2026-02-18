from flask import render_template, jsonify, request, current_app
from lims import lims_bp
from lims.models import db, TestResult
from lims.utils import fetch_gsheet_data, get_worksheet_names, validate_cell_range
import json

import re
import os
import uuid
from werkzeug.utils import secure_filename
from flask import url_for
from auth import login_required

# ============================================================================
# 페이지 라우트
# ============================================================================

@lims_bp.route('/')
@login_required
def dashboard():
    """LIMS 대시보드 메인 페이지"""
    return render_template('lims/dashboard.html')


@lims_bp.route('/list')
@login_required
def test_list():
    """시험 목록 조회 페이지"""
    return render_template('lims/list.html')


@lims_bp.route('/edit/<int:test_id>')
@login_required
def edit_test(test_id):
    """시험 설정 편집 페이지
    
    Args:
        test_id (int): 시험 ID (0이면 신규 생성)
    """
    return render_template('lims/edit.html', test_id=test_id)


@lims_bp.route('/view/<int:test_id>')
@login_required
def view_test(test_id):
    """시험 결과 조회 페이지
    
    Args:
        test_id (int): 시험 ID
    """
    return render_template('lims/view.html', test_id=test_id)


@lims_bp.route('/upload')
@login_required
def upload_page():
    """HTML 템플릿 업로드 페이지"""
    return render_template('lims/upload.html')


@lims_bp.route('/result/<int:test_id>')
@login_required
def view_html_result(test_id):
    """HTML 템플릿 결과 조회 및 데이터 주입"""
    try:
        test = TestResult.query.get(test_id)
        if not test:
            return f"시험 ID {test_id}를 찾을 수 없습니다.", 404
        if not test.html_template:
            return f"시험 '{test.test_title}'에 등록된 HTML 템플릿이 없습니다.", 404

        # 1. 뒤로가기 버튼 HTML
        back_button_html = '''
        <style>
            .lims-back-button {
                position: fixed; top: 20px; right: 20px; z-index: 9999;
                padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; border: none; border-radius: 8px; font-size: 14px;
                font-weight: 600; cursor: pointer; text-decoration: none;
                display: inline-flex; align-items: center; gap: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: all 0.3s ease;
            }
            .lims-back-button:hover { transform: translateY(-2px); box-shadow: 0 6px 8px rgba(0,0,0,0.15); }
        </style>
        <a href="/lims/list" class="lims-back-button">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
            </svg>
            목록가기
        </a>
        '''

        # 2. 데이터 주입 스크립트 생성
        injected_script = ""
        if test.gsheet_url:
            try:
                df = fetch_gsheet_data(
                    gsheet_url=test.gsheet_url,
                    sheet_name=test.sheet_name or 'Sheet1',
                    cell_range=test.cell_range or 'A1:Z100'
                )
                
                if not df.empty:
                    data_dict = {'columns': df.columns.tolist(), 'rows': df.values.tolist()}
                    data_json = json.dumps(data_dict, ensure_ascii=False)
                    # JS 문자열 이스케이프 처리
                    data_csv = df.to_csv(index=False).replace('\\', '\\\\').replace('\n', '\\n').replace("'", "\\'")
                    
                    injected_script = f'''
                    <script>
                        window.gsheetData = {data_json};
                        window.gsheetCSV = '{data_csv}';
                        
                        // Fetch/XHR Interceptor 로직 (기존과 동일)
                        const originalFetch = window.fetch;
                        window.fetch = async function(input, init) {{
                            const url = (typeof input === 'string') ? input : input.url;
                            if (url && url.includes('docs.google.com/spreadsheets')) {{
                                return new Response(window.gsheetCSV, {{
                                    status: 200, headers: {{ 'Content-Type': 'text/csv' }}
                                }});
                            }}
                            return originalFetch(input, init);
                        }};
                    </script>
                    '''
            except Exception as e:
                current_app.logger.error(f"Data fetch failed: {e}")
                injected_script = f'<script>console.warn("LIMS Data Error: {str(e)}");</script>'

        # 3. HTML 조립 (정규표현식 대신 안전한 replace 사용 권장)
        final_html = test.html_template
        
        # 스크립트 주입 (<head> 바로 아래)
        if '<head>' in final_html.lower():
            final_html = re.sub(r'(<head.*?>)', r'\1' + injected_script, final_html, count=1, flags=re.IGNORECASE)
        else:
            final_html = injected_script + final_html

        # 버튼 주입 (</body> 바로 위)
        if '</body>' in final_html.lower():
            final_html = re.sub(r'(</body>)', back_button_html + r'\1', final_html, count=1, flags=re.IGNORECASE)
        else:
            final_html += back_button_html

        return final_html # 유일한 리턴 지점

    except Exception as e:
        current_app.logger.error(f"HTML 템플릿 처리 중 치명적 오류: {str(e)}")
        return f"서버 오류: {str(e)}", 500


# ============================================================================
# CRUD API
# ============================================================================

@lims_bp.route('/api/tests', methods=['GET'])
@login_required
def get_tests():
    """시험 목록 조회 API
    
    Returns:
        JSON: {
            "success": true,
            "data": [
                {
                    "id": 1,
                    "test_title": "페라스타AG의 안정성시험",
                    "product_name": "페라스타AG",
                    "created_at": "2026-02-09T12:00:00",
                    ...
                },
                ...
            ]
        }
    """
    try:
        tests = TestResult.query.order_by(TestResult.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [test.to_dict() for test in tests]
        })
    
    except Exception as e:
        current_app.logger.error(f"시험 목록 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/tests/<int:test_id>', methods=['GET'])
@login_required
def get_test(test_id):
    """특정 시험 조회 API
    
    Args:
        test_id (int): 시험 ID
        
    Returns:
        JSON: {
            "success": true,
            "data": {
                "id": 1,
                "test_title": "페라스타AG의 안정성시험",
                ...
            }
        }
    """
    try:
        test = TestResult.query.get(test_id)
        
        if not test:
            return jsonify({
                'success': False,
                'error': f'ID {test_id}에 해당하는 시험을 찾을 수 없습니다.'
            }), 404
        
        return jsonify({
            'success': True,
            'data': test.to_dict()
        })
    
    except Exception as e:
        current_app.logger.error(f"시험 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/tests', methods=['POST'])
@login_required
def create_test():
    """시험 생성 API
    
    Request Body:
        {
            "test_title": "페라스타AG의 안정성시험",
            "product_name": "페라스타AG",
            "html_template": "<html>...</html>",  # NEW: 선택사항
            "gsheet_url": "https://docs.google.com/spreadsheets/d/...",  # 선택사항
            "sheet_name": "Sheet1",
            "cell_range": "A1:D10",
            "main_title": "안정성 시험 결과",
            "sub_title": "페라스타AG",
            "chart_settings": {
                "x_axis": {...},
                "y_axis": {...},
                "spec_line": {...}
            }
        }
        
    Returns:
        JSON: {
            "success": true,
            "data": {...},
            "message": "시험이 생성되었습니다."
        }
    """
    try:
        data = request.get_json()
        
        # 필수 필드 검증 (test_title만 필수)
        if 'test_title' not in data or not data['test_title']:
            return jsonify({
                'success': False,
                'error': '필수 필드 "test_title"가 누락되었습니다.'
            }), 400
        
        # HTML 템플릿에서 JSON 데이터 추출
        chart_data_extracted = None
        if data.get('html_template'):
            try:
                # <data-store> 태그 내의 <script type="application/json"> 내용 추출
                pattern = r'<data-store[^>]*>.*?<script[^>]*type="application/json"[^>]*>(.*?)</script>.*?</data-store>'
                match = re.search(pattern, data['html_template'], re.DOTALL | re.IGNORECASE)
                if match:
                    json_str = match.group(1).strip()
                    # 유효성 검사
                    json.loads(json_str)
                    chart_data_extracted = json_str
            except Exception as e:
                current_app.logger.warning(f"HTML 템플릿 데이터 파싱 실패: {e}")

        # 새 시험 생성
        test = TestResult(
            test_title=data['test_title'],
            product_name=data.get('product_name'),
            html_template=data.get('html_template'),  # NEW
            chart_data=chart_data_extracted,          # NEW: 추출된 데이터 저장
            test_summary=data.get('test_summary'),    # NEW: 시험 개요
            formulation_info=data.get('formulation_info'), # NEW: 제형 정보
            start_month=data.get('start_month'),       # NEW: 시작월
            end_month=data.get('end_month')            # NEW: 종료월
        )
        
        # 이미지 및 링크 URL 리스트 저장
        if 'image_urls' in data and isinstance(data['image_urls'], list):
            test.set_image_urls(data['image_urls'])
            
        if 'reference_links' in data and isinstance(data['reference_links'], list):
            test.set_reference_links(data['reference_links'])
        
        # Google Sheets 정보는 선택사항
        if 'gsheet_url' in data and data['gsheet_url']:
            # 셀 범위 형식 검증
            if 'cell_range' in data and data['cell_range']:
                if not validate_cell_range(data['cell_range']):
                    return jsonify({
                        'success': False,
                        'error': '셀 범위 형식이 올바르지 않습니다. (예: A1:D10)'
                    }), 400
            
            test.gsheet_url = data['gsheet_url']
            test.sheet_name = data.get('sheet_name', 'Sheet1')
            test.cell_range = data.get('cell_range', 'A1:Z100')
            test.main_title = data.get('main_title')
            test.sub_title = data.get('sub_title')
        
        # 차트 설정 저장
        if 'chart_settings' in data and data['chart_settings']:
            test.set_chart_settings(data['chart_settings'])
        else:
            # 기본 차트 설정 사용
            test.set_chart_settings(TestResult.get_default_chart_settings())
        
        db.session.add(test)
        db.session.commit()
        
        current_app.logger.info(f"시험 생성 성공: ID {test.id}, 제목 '{test.test_title}'")
        
        return jsonify({
            'success': True,
            'data': test.to_dict(),
            'message': '시험이 성공적으로 생성되었습니다.'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"시험 생성 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/tests/<int:test_id>', methods=['PUT'])
@login_required
def update_test(test_id):
    """시험 수정 API
    
    Args:
        test_id (int): 시험 ID
        
    Request Body:
        {
            "test_title": "수정된 제목",
            ...
        }
        
    Returns:
        JSON: {
            "success": true,
            "data": {...},
            "message": "시험이 수정되었습니다."
        }
    """
    try:
        test = TestResult.query.get(test_id)
        
        if not test:
            return jsonify({
                'success': False,
                'error': f'ID {test_id}에 해당하는 시험을 찾을 수 없습니다.'
            }), 404
        
        data = request.get_json()
        
        # 필드 업데이트
        if 'test_title' in data:
            test.test_title = data['test_title']
        if 'product_name' in data:
            test.product_name = data['product_name']
        if 'html_template' in data:  # NEW
            test.html_template = data['html_template']
            # HTML 템플릿 변경 시 데이터 재추출
            try:
                pattern = r'<data-store[^>]*>.*?<script[^>]*type="application/json"[^>]*>(.*?)</script>.*?</data-store>'
                match = re.search(pattern, test.html_template, re.DOTALL | re.IGNORECASE)
                if match:
                    json_str = match.group(1).strip()
                    json.loads(json_str) # Validate
                    test.chart_data = json_str
                else:
                    # 데이터가 없으면 null 처리할지 유지할지? 보통 없으면 null
                    # 기존 데이터 유지 vs 덮어쓰기 -> 템플릿이 바뀌었으므로 데이터도 바뀌는게 맞음.
                    # 하지만 부분 업데이트일 수 있으므로 신중해야 함.
                    # 여기서는 템플릿에 데이터가 없으면 chart_data를 비우지 않고, 있으면 갱신.
                    pass 
            except Exception as e:
                current_app.logger.warning(f"HTML 템플릿 데이터 갱신 실패: {e}")

        if 'gsheet_url' in data:
            test.gsheet_url = data['gsheet_url']
        if 'sheet_name' in data:
            test.sheet_name = data['sheet_name']
        if 'cell_range' in data:
            # 셀 범위 형식 검증
            if not validate_cell_range(data['cell_range']):
                return jsonify({
                    'success': False,
                    'error': '셀 범위 형식이 올바르지 않습니다. (예: A1:D10)'
                }), 400
            test.cell_range = data['cell_range']
        if 'main_title' in data:
            test.main_title = data['main_title']
        if 'sub_title' in data:
            test.sub_title = data['sub_title']
        if 'chart_settings' in data:
            test.set_chart_settings(data['chart_settings'])

        # 추가 정보 업데이트
        if 'test_summary' in data:
            test.test_summary = data['test_summary']
        if 'formulation_info' in data:
            test.formulation_info = data['formulation_info']
        if 'image_urls' in data and isinstance(data['image_urls'], list):
            test.set_image_urls(data['image_urls'])
        if 'reference_links' in data and isinstance(data['reference_links'], list):
            test.set_reference_links(data['reference_links'])

        if 'start_month' in data:
            test.start_month = data['start_month']
        if 'end_month' in data:
            test.end_month = data['end_month']
        
        db.session.commit()
        
        current_app.logger.info(f"시험 수정 성공: ID {test.id}")
        
        return jsonify({
            'success': True,
            'data': test.to_dict(),
            'message': '시험이 성공적으로 수정되었습니다.'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"시험 수정 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/tests/<int:test_id>', methods=['DELETE'])
@login_required
def delete_test(test_id):
    """시험 삭제 API
    
    Args:
        test_id (int): 시험 ID
        
    Returns:
        JSON: {
            "success": true,
            "message": "시험이 삭제되었습니다."
        }
    """
    try:
        test = TestResult.query.get(test_id)
        
        if not test:
            return jsonify({
                'success': False,
                'error': f'ID {test_id}에 해당하는 시험을 찾을 수 없습니다.'
            }), 404
        
        db.session.delete(test)
        db.session.commit()
        
        current_app.logger.info(f"시험 삭제 성공: ID {test_id}")
        
        return jsonify({
            'success': True,
            'message': '시험이 성공적으로 삭제되었습니다.'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"시험 삭제 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Google Sheets 연동 API
# ============================================================================

@lims_bp.route('/api/gsheet/data/<int:test_id>', methods=['GET'])
@login_required
def get_gsheet_data(test_id):
    """Google Sheets 데이터 조회 API
    
    Args:
        test_id (int): 시험 ID
        
    Returns:
        JSON: {
            "success": true,
            "data": {
                "columns": ["컬럼1", "컬럼2", ...],
                "rows": [
                    ["값1", "값2", ...],
                    ...
                ]
            }
        }
    """
    try:
        test = TestResult.query.get(test_id)
        
        if not test:
            return jsonify({
                'success': False,
                'error': f'ID {test_id}에 해당하는 시험을 찾을 수 없습니다.'
            }), 404
        
        # Google Sheets에서 데이터 가져오기
        df = fetch_gsheet_data(
            gsheet_url=test.gsheet_url,
            sheet_name=test.sheet_name,
            cell_range=test.cell_range
        )
        
        # DataFrame을 JSON으로 변환
        data = {
            'columns': df.columns.tolist(),
            'rows': df.values.tolist()
        }
        
        current_app.logger.info(
            f"Google Sheets 데이터 조회 성공: 시험 ID {test_id}, "
            f"{len(df)} 행, {len(df.columns)} 열"
        )
        
        return jsonify({
            'success': True,
            'data': data
        })
    
    except Exception as e:
        current_app.logger.error(f"Google Sheets 데이터 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/gsheet/worksheets', methods=['POST'])
@login_required
def get_gsheet_worksheets():
    """Google Sheets 워크시트 목록 조회 API
    
    Request Body:
        {
            "gsheet_url": "https://docs.google.com/spreadsheets/d/..."
        }
        
    Returns:
        JSON: {
            "success": true,
            "data": ["Sheet1", "Sheet2", ...]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'gsheet_url' not in data:
            return jsonify({
                'success': False,
                'error': 'Google Sheets URL이 제공되지 않았습니다.'
            }), 400
        
        worksheets = get_worksheet_names(data['gsheet_url'])
        
        return jsonify({
            'success': True,
            'data': worksheets
        })
    
    except Exception as e:
        current_app.logger.error(f"워크시트 목록 조회 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# 유틸리티 API
# ============================================================================

@lims_bp.route('/api/chart-settings/default', methods=['GET'])
@login_required
def get_default_chart_settings():
    """기본 차트 설정 조회 API
    
    Returns:
        JSON: {
            "success": true,
            "data": {
                "x_axis": {...},
                "y_axis": {...},
                "spec_line": {...}
            }
        }
    """
    try:
        return jsonify({
            'success': True,
            'data': TestResult.get_default_chart_settings()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lims_bp.route('/api/sheet-data', methods=['GET'])
@login_required
def get_sheet_data_proxy():
    """Google Sheets Data Proxy API (Fallback for Private Sheets)"""
    try:
        from flask import Response
        sheet_id = request.args.get('sheet_id')
        gsheet_url = request.args.get('sheet_url')
        sheet_name = request.args.get('sheet_name', 'Sheet1')
        cell_range = request.args.get('range', 'A1:Z100')
        fmt = request.args.get('format', 'json')
        
        if not gsheet_url and sheet_id:
            gsheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit'
        
        if not gsheet_url:
            return jsonify({'error': 'sheet_id or sheet_url is required'}), 400

        # 데이터 가져오기 (utils.py 사용 - 서비스 계정 인증)
        df = fetch_gsheet_data(
            gsheet_url=gsheet_url,
            sheet_name=sheet_name,
            cell_range=cell_range
        )
        
        if fmt == 'csv':
            csv_data = df.to_csv(index=False)
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment;filename=data.csv'}
            )
        
        else:
            return jsonify({
                'columns': df.columns.tolist(),
                'rows': df.values.tolist()
            })
            
    except Exception as e:
        current_app.logger.error(f"Sheet Data Proxy Failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# 파일 업로드 API
# ============================================================================

@lims_bp.route('/api/upload/image', methods=['POST'])
@login_required
def upload_image():
    """이미지 업로드 API"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '파일이 없습니다.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '선택된 파일이 없습니다.'}), 400
            
        if file:
            filename = secure_filename(file.filename)
            # 고유 파일명 생성
            base, ext = os.path.splitext(filename)
            unique_filename = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
            
            # 저장 경로 설정 (project/static/uploads/lims)
            # current_app.root_path는 project 폴더를 가리킴 (app.py 위치)
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'lims')
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            
            # URL 반환
            url = url_for('static', filename=f'uploads/lims/{unique_filename}')
            
            return jsonify({
                'success': True,
                'url': url
            })
            
    except Exception as e:
        current_app.logger.error(f"이미지 업로드 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
