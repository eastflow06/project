from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Table, MetaData, CheckConstraint
import pytz
import json
import secrets

metadata = MetaData()

db = SQLAlchemy()

# 중간 테이블 정의
project_product = db.Table('project_product',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

class Project(db.Model):
    __tablename__ = 'project'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='검토')
    is_completed = db.Column(db.Boolean, nullable=False, default=False) # True/False로 완료 여부 저장
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")
    memos = db.relationship('Memo', backref='project', lazy=True, cascade="all, delete-orphan")
    links = db.relationship('Link', backref='project', lazy=True, cascade="all, delete-orphan")
    images = db.relationship('ProjectImage', backref='project', lazy=True, cascade="all, delete-orphan")
    products = db.relationship('Product', secondary=project_product, back_populates='projects')

class Product(db.Model):
    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # [보완 1] default=list 를 추가해야 나중에 에러가 안 납니다.
    # 기존: db.Column(db.JSON, nullable=True)
    # 수정: 값이 없으면 자동으로 [] (빈 리스트)가 들어갑니다.
    category = db.Column(db.JSON, default=list, nullable=True) 
    api = db.Column(db.JSON, default=list, nullable=True)

    # 허용된 목록 (Master List)
    ALLOWED_CATEGORIES = ['의약품', '의약외품', '살생물제품', '위생용품', '식품첨가물']
    ALLOWED_APIS = ['PAA', 'BKC', 'DDAC', 'Citric Acid', 'Ethanol']

    # 기존 관계 유지
    projects = db.relationship('Project', secondary=project_product, back_populates='products')

    # [보완 2] 안전하게 데이터를 넣는 함수 (이게 없으면 아무거나 다 들어감)
    def add_category(self, item):
        if item not in self.ALLOWED_CATEGORIES:
            raise ValueError(f"'{item}'은(는) 허용된 카테고리가 아닙니다.")
        
        # 현재 리스트 가져오기 (없으면 빈 리스트)
        current_list = self.category if self.category else []
        
        # 중복 체크 후 추가
        if item not in current_list:
            current_list.append(item)
            # SQLAlchemy가 JSON 변경을 감지하도록 재할당
            self.category = list(current_list)

    def add_api(self, item):
        if item not in self.ALLOWED_APIS:
            raise ValueError(f"'{item}'은(는) 허용된 API가 아닙니다.")
        
        current_list = self.api if self.api else []
        
        if item not in current_list:
            current_list.append(item)
            self.api = list(current_list)

class Memo(db.Model):
    __tablename__ = 'memo'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True, index=True)
    image_filename = db.Column(db.String(120), nullable=True)
    pdf_filename = db.Column(db.String(120), nullable=True)
    excel_filename = db.Column(db.String(255), nullable=True)
    ppt_filename = db.Column(db.String(255), nullable=True)
    md_filename = db.Column(db.String(255), nullable=True)
    html_filename = db.Column(db.String(255), nullable=True) 
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=True, index=True)

    product = db.relationship('Product', backref='search_memos')
    
    images = db.relationship('MemoImage', backref='memo', lazy=True, cascade="all, delete-orphan")
    

    # 부모 메모를 가리키는 외래 키
    parent_id = db.Column(db.Integer, db.ForeignKey('memo.id'), nullable=True, index=True)
    
    # 부모-자식 관계 설정
    parent = db.relationship('Memo', remote_side=[id], backref=db.backref('replies', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Memo {self.content}>'

class Link(db.Model):
    __tablename__ = 'link'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)


class Task(db.Model):
    __tablename__ = 'task'  # 테이블 이름을 명시적으로 설정

    STATUS_CHOICES = ('To Do', 'Done')
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    #status = db.Column(db.String(20), nullable=False, default='To Do')
    status = db.Column(db.String(20), nullable=False, default='To Do', index=True)  # 인덱스 추가
    start_date = db.Column(db.Date, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')).date())
    due_date = db.Column(db.Date, nullable=True)  # due_date 기본값 설정
    finished_date = db.Column(db.Date, nullable=True)  # finished_date 컬럼 추가
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=True)

    __table_args__ = (
    CheckConstraint('finished_date >= start_date', name='check_finished_date'),
    )

    def __repr__(self):
        return f'<Task {self.title}>'

class ProjectImage(db.Model):
    __tablename__ = 'project_image'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    memo = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)

class MemoImage(db.Model):
    __tablename__ = 'memo_image'
    
    id = db.Column(db.Integer, primary_key=True)
    memo_id = db.Column(db.Integer, db.ForeignKey('memo.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))

class ProjectMemoImage(db.Model):
    __tablename__ = 'project_memo_image'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    memo_id = db.Column(db.Integer, db.ForeignKey('memo.id'), nullable=False, index=True)
    image_filename = db.Column(db.String(120), nullable=True)
    pdf_filename = db.Column(db.String(120), nullable=True)

class Tag(db.Model):
    __tablename__ = 'tag'  # 테이블 이름을 명시적으로 설정

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    memos = db.relationship('Memo', backref='tag', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Tag {self.name}>'

class MyMemo(db.Model):
    __tablename__ = 'mymemo'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True, index=True)  # 조사 주제 제목
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), index=True)
    tag = db.relationship('Tag', backref='mymemos')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), index=True)
    project = db.relationship('Project', backref='mymemos')
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True)
    product = db.relationship('Product', backref='mymemos')
    image_filename = db.Column(db.String(255), nullable=True)
    file_filename = db.Column(db.String(255), nullable=True)

    # Post-it Meta Data (Color, Position: x, y, width, height, etc.)
    meta_data = db.Column(db.JSON, default={}, nullable=True)

    # 링크된 정식 메모 (Promote to Note 기능)
    # linked_memo_id (Legacy) - Removing or keeping for safety? Let's switch to Note ID
    linked_note_id = db.Column(db.Integer, nullable=True) # Linked to notes.db (No FK constraint enforcement in SQLite cross-db)

    # 부모-자식 관계
    parent_id = db.Column(db.Integer, db.ForeignKey('mymemo.id'), nullable=True, index=True)
    
    parent = db.relationship('MyMemo', remote_side=[id], backref=db.backref('replies'))
    
    # Soft delete 지원
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f'<MyMemo {self.content}>'

class Infolink(db.Model):
    __tablename__ = 'infolink'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=True)
    detail = db.Column(db.String(500), nullable=True)

    # VARCHAR fields for category and subcategory
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100), nullable=True)

    image_filename = db.Column(db.String(255), nullable=True)
    attachment_filename = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Infolink {self.name}>'           
