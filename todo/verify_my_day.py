
import unittest
import sys
import os
from datetime import datetime, date, timedelta
import pytz

# Add parent directory to path to find app.py
# Insert at 0 to ensure we find root 'models.py' instead of 'todo/models.py'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app
from models import db
from todo.models import TodoItem, TodoList

class TestMyDayLogic(unittest.TestCase):
    def setUp(self):
        self.app = flask_app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create a default list
        self.list = TodoList(title="Default List")
        db.session.add(self.list)
        db.session.commit()

        self.kst = pytz.timezone('Asia/Seoul')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_my_day_filtering(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # 1. Task manually added to My Day (Today) -> Should show
        task1 = TodoItem(content="Manual My Day", list_id=self.list.id, is_my_day=True, my_day_date=today)
        
        # 2. Task with Due Date = Today -> Should show
        # Convert date to datetime for due_date (assuming end of day or specific time, but check logic uses range)
        due_today = datetime.now(self.kst).replace(hour=12, minute=0, second=0, microsecond=0)
        # Ensure it matches 'today' in local time
        task2 = TodoItem(content="Due Today", list_id=self.list.id, due_date=due_today)
        
        # 3. Task with Due Date = Tomorrow -> Should NOT show
        due_tomorrow = due_today + timedelta(days=1)
        task3 = TodoItem(content="Due Tomorrow", list_id=self.list.id, due_date=due_tomorrow)
        
        # 4. Old My Day Task (Yesterday) -> Should NOT show (auto reset logic check)
        task4 = TodoItem(content="Old My Day", list_id=self.list.id, is_my_day=True, my_day_date=yesterday)

        db.session.add_all([task1, task2, task3, task4])
        db.session.commit()

        # Fetch "my_day" items
        response = self.client.get('/todo/api/items?filter=my_day')
        self.assertEqual(response.status_code, 200)
        items = response.json
        
        content_list = [i['content'] for i in items]
        print(f"Items found in My Day: {content_list}")

        self.assertIn("Manual My Day", content_list)
        self.assertIn("Due Today", content_list)
        self.assertNotIn("Due Tomorrow", content_list)
        self.assertNotIn("Old My Day", content_list)

if __name__ == '__main__':
    unittest.main()
