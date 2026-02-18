# note/__init__.py
from flask import Blueprint

# Blueprint 생성
note_bp = Blueprint(
    'note',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# routes import (Blueprint 생성 후에 import)
from . import routes