from flask import Blueprint

# LIMS Blueprint 정의
lims_bp = Blueprint(
    'lims',
    __name__,
    template_folder='templates',
    url_prefix='/lims'
)

# routes 모듈 import (순환 참조 방지를 위해 Blueprint 정의 후 import)
from . import routes

