from sqlalchemy import create_engine, inspect
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'db/project.db')
# Try root project.db if db/project.db fails
if not os.path.exists(db_path):
    db_path = os.path.join(BASE_DIR, 'project.db')

print(f"Checking DB at: {db_path}")

engine = create_engine(f'sqlite:///{db_path}')
inspector = inspect(engine)
columns = inspector.get_columns('mymemo')
for column in columns:
    print(f"Column: {column['name']} - {column['type']}")
