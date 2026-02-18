#!/usr/bin/env python3
"""
LIMS 데이터베이스 초기화 스크립트

사용법:
    python init_lims_db.py
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from lims.models import db, TestResult

def init_database():
    """LIMS 데이터베이스 테이블 생성"""
    with app.app_context():
        # 테이블 생성
        db.create_all()
        print("✅ LIMS 데이터베이스 테이블이 생성되었습니다.")
        
        # 테이블 확인
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'test_results' in tables:
            print("✅ test_results 테이블이 확인되었습니다.")
            
            # 컬럼 정보 출력
            columns = inspector.get_columns('test_results')
            print("\n테이블 구조:")
            print("-" * 60)
            for col in columns:
                print(f"  {col['name']:20} {str(col['type']):20}")
            print("-" * 60)
        else:
            print("❌ test_results 테이블을 찾을 수 없습니다.")
            return False
        
        return True

if __name__ == '__main__':
    print("LIMS 데이터베이스 초기화를 시작합니다...\n")
    
    success = init_database()
    
    if success:
        print("\n✅ 초기화가 완료되었습니다!")
        print("\n다음 단계:")
        print("1. /home/ubuntu/project/instance/google_key.json 파일이 있는지 확인")
        print("2. Flask 앱 재시작")
        print("3. http://your-server/lims 접속")
    else:
        print("\n❌ 초기화 중 오류가 발생했습니다.")
        sys.exit(1)
