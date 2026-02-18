import sys
import os
# 상위 디렉토리의 models를 찾기 위해 경로 확보가 필요한 경우
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from models import db  # 공통 db 객체 임포트
from datetime import datetime
import json

class TestResult(db.Model):
    """시험결과 관리 테이블"""
    __tablename__ = 'test_results'
    # 별도의 DB 파일을 사용할 경우 아래 주석을 해제하세요.
    __bind_key__ = 'lims_db' 
    
    # 기본 필드
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_title = db.Column(db.String(200), nullable=False)
    product_name = db.Column(db.String(200), nullable=True)
    
    # Google Sheets 연동 정보
    gsheet_url = db.Column(db.String(500), nullable=True)
    sheet_name = db.Column(db.String(100), nullable=True, default='Sheet1')
    cell_range = db.Column(db.String(50), nullable=True, default='A1:Z100')
    
    # 그래프 및 HTML 템플릿
    main_title = db.Column(db.String(200), nullable=True)
    sub_title = db.Column(db.String(200), nullable=True)
    chart_settings = db.Column(db.Text, nullable=True)
    html_template = db.Column(db.Text, nullable=True)
    chart_data = db.Column(db.Text, nullable=True)  # NEW: 그래프 데이터 (JSON)
    
    # 추가 정보 필드
    test_summary = db.Column(db.Text, nullable=True)      # 시험 개요
    formulation_info = db.Column(db.Text, nullable=True)  # 제형 정보
    image_urls = db.Column(db.Text, nullable=True)        # 관련 이미지 URL (JSON)
    reference_links = db.Column(db.Text, nullable=True)   # 관련 링크 (JSON)
    
    # 일정 정보
    start_month = db.Column(db.String(20), nullable=True) # 시작월 (YYYY-MM)
    end_month = db.Column(db.String(20), nullable=True)   # 종료월 (YYYY-MM)
    
    # 시간 설정 (utcnow 대신 KST 등 로컬 시간 권장)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """JSON 변환 시 호출"""
        return {
            'id': self.id,
            'test_title': self.test_title,
            'product_name': self.product_name,
            'gsheet_url': self.gsheet_url,
            'sheet_name': self.sheet_name,
            'cell_range': self.cell_range,
            'main_title': self.main_title,
            'sub_title': self.sub_title,
            'chart_settings': self.get_chart_settings(),
            'html_template': self.html_template,
            'chart_data': self.chart_data,  # NEW
            'test_summary': self.test_summary,
            'formulation_info': self.formulation_info,
            'image_urls': self.get_image_urls(),
            'reference_links': self.get_reference_links(),
            'start_month': self.start_month,
            'end_month': self.end_month,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def set_image_urls(self, urls_list):
        self.image_urls = json.dumps(urls_list, ensure_ascii=False)

    def get_image_urls(self):
        if self.image_urls:
            try: return json.loads(self.image_urls)
            except: return []
        return []

    def set_reference_links(self, links_list):
        self.reference_links = json.dumps(links_list, ensure_ascii=False)

    def get_reference_links(self):
        if self.reference_links:
            try: return json.loads(self.reference_links)
            except: return []
        return []

    def set_chart_settings(self, settings_dict):
        self.chart_settings = json.dumps(settings_dict, ensure_ascii=False)

    def get_chart_settings(self):
        if self.chart_settings:
            try: return json.loads(self.chart_settings)
            except: return None
        return self.get_default_chart_settings()

    @staticmethod
    def get_default_chart_settings():
        return {
            'x_axis': {'title': 'X축', 'min': 0, 'max': 100, 'interval': 10, 'show_grid': True},
            'y_axis': {'title': 'Y축', 'min': 0, 'max': 100, 'interval': 10, 'show_grid': True},
            'y_spec_line': {'show': True, 'value': 90, 'color': '#ff0000', 'label': '기준선'}
        }