from models import db
from datetime import datetime
import pytz

class TodoList(db.Model):
    __bind_key__ = 'todo_db'
    __tablename__ = 'todo_list'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    
    items = db.relationship('TodoItem', backref='list', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'is_default': self.is_default,
            'count': len([i for i in self.items if not i.completed])
        }

class TodoItem(db.Model):
    __bind_key__ = 'todo_db'
    __tablename__ = 'todo_item'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    is_my_day = db.Column(db.Boolean, default=False)
    my_day_date = db.Column(db.Date, nullable=True)  # Date when added to "My Day"
    
    due_date = db.Column(db.DateTime, nullable=True)
    is_all_day = db.Column(db.Boolean, default=False)
    
    google_event_id = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    
    memo = db.Column(db.Text, nullable=True)
    steps = db.Column(db.JSON, default=list, nullable=True) # Subtasks structure: [{'id': 1, 'text': 'step 1', 'completed': False}]
    
    list_id = db.Column(db.Integer, db.ForeignKey('todo_list.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'completed': self.completed,
            'is_important': self.is_important,
            'is_my_day': self.is_my_day,
            'my_day_date': self.my_day_date.isoformat() if self.my_day_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'is_all_day': self.is_all_day,
            'google_event_id': self.google_event_id,
            'location': self.location,
            'steps': self.steps,
            'memo': self.memo,
            'list_id': self.list_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }        