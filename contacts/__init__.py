from flask import Blueprint

# 연락처 블루프린트 생성
contact_bp = Blueprint("contact", __name__, template_folder="templates")

# 라우트 모듈 임포트 (순환 참조 방지)
from . import routes
