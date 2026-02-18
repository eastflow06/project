from flask import Blueprint

todo_bp = Blueprint('todo', __name__, template_folder='templates', static_folder='static', url_prefix='/todo')

from . import routes
