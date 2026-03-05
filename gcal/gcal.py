from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# 로깅 설정 - 디버깅 메시지 제거
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()

# 서비스 계정 키 파일 경로 (상대 경로 사용 제거)
KEY_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_FILE')
if not KEY_FILE:
    # 절대 경로 대신 현재 파일 기준으로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    KEY_FILE = os.path.join(os.path.dirname(current_dir), 'instance', 'google_key.json')

# 스코프 설정 - 읽기 및 쓰기 권한
SCOPES = ['https://www.googleapis.com/auth/calendar']

# 캘린더 ID 설정
CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID', 'primary')

def get_credentials():
    """서비스 계정 자격 증명을 가져옵니다."""
    try:
        if not os.path.exists(KEY_FILE):
            logger.error(f"서비스 계정 키 파일이 존재하지 않습니다: {KEY_FILE}")
            raise FileNotFoundError(f"{KEY_FILE} 파일이 존재하지 않습니다.")
        
        creds = Credentials.from_service_account_file(
            KEY_FILE, 
            scopes=SCOPES
        )
        
        # 위임 이메일이 설정된 경우 (도메인 전체 위임을 사용하는 경우)
        delegate_email = os.getenv('GOOGLE_DELEGATE_EMAIL')
        if delegate_email:
            creds = creds.with_subject(delegate_email)
            
        return creds
        
    except Exception as e:
        logger.error(f"자격 증명 가져오기 오류: {e}")
        raise

# 캘린더 이벤트 캐시 (간단한 in-memory 캐싱)
_calendar_cache = {
    'events': None,
    'timestamp': None,
    'ttl': 300  # 5분 (300초)
}

def clear_calendar_cache():
    """캐시를 강제로 비웁니다."""
    _calendar_cache['events'] = None
    _calendar_cache['timestamp'] = None

def get_cached_calendar_events():
    """캐시된 캘린더 이벤트만 반환합니다. 없으면 빈 리스트를 반환합니다."""
    return _calendar_cache.get('events') or []

def fetch_calendar_events(date=None, max_results=30, include_future=True, force_refresh=False):
    """
    지정한 날짜가 속한 연도의 모든 이벤트를 가져옵니다.
    캐시가 유효하면 캐시된 데이터를 반환합니다.
    
    Args:
        date: datetime 객체 또는 'YYYY-MM-DD' 형식의 문자열
        max_results: 가져올 최대 이벤트 수
        include_future: 미래 이벤트 포함 여부
        force_refresh: 캐시 무시하고 강제로 새로 가져올지 여부
        
    Returns:
        list: 이벤트 목록
    """
    from datetime import datetime as dt
    
    # 1. 캐시 확인 (기본 날짜일 때만 캐시 적용)
    if not force_refresh and date is None:
        now = dt.now()
        if (_calendar_cache['events'] is not None and 
            _calendar_cache['timestamp'] is not None):
            elapsed = (now - _calendar_cache['timestamp']).total_seconds()
            if elapsed < _calendar_cache['ttl']:
                logger.info(f"캘린더 이벤트 캐시 사용 (남은 시간: {int(_calendar_cache['ttl'] - elapsed)}초)")
                return _calendar_cache['events']

    try:
        # 날짜가 지정되지 않으면 현재 날짜 사용
        if date is None:
            date = dt.now()
        elif isinstance(date, str):
            # 문자열 형식의 날짜를 datetime 객체로 변환 (YYYY-MM-DD 형식 예상)
            try:
                date = dt.strptime(date, '%Y-%m-%d')
            except ValueError:
                logger.error("날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요.")
                return []
                
        # 해당 날짜가 속한 연도 추출
        year = date.year
            
        # 시간 범위 설정 - 해당 연도의 1월 1일부터 12월 31일까지
        time_min = dt(year, 1, 1, 0, 0, 0).isoformat() + 'Z'
        time_max = dt(year, 12, 31, 23, 59, 59).isoformat() + 'Z'
        
        logger.info(f"'{date.strftime('%Y-%m-%d')}'의 연도({year}년)에 해당하는 이벤트를 가져옵니다.")
        
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # 이벤트 가져오기
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            logger.info(f"{year}년에 이벤트가 없습니다.")
            return []
        
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # 하루종일 이벤트 확인 (dateTime이 없고 date만 있는 경우)
            is_all_day = 'date' in event['start'] and 'date' in event['end']
            
            # 하루종일 이벤트이고, 종료일이 시작일과 다른 경우 종료일 조정
            if is_all_day and end > start:
                # 날짜 형식인 경우 날짜 객체로 변환 후 하루 빼기
                end_date = dt.strptime(end, '%Y-%m-%d')
                end_date = end_date - timedelta(days=1)
                end = end_date.strftime('%Y-%m-%d')
            
            event_list.append({
                'summary': event.get('summary', '제목 없음'),
                'start': start,
                'end': end,
                'id': event.get('id', ''),
                'description': event.get('description', '')
            })
        
        # 캐시 업데이트 (기본 호출일 때만)
        if date is None or (isinstance(date, dt) and date.year == dt.now().year):
            _calendar_cache['events'] = event_list
            _calendar_cache['timestamp'] = dt.now()

        logger.info(f'{year}년 캘린더에서 가져온 이벤트 수: {len(events)}')
        return event_list
    
    except Exception as e:
        logger.error(f"이벤트 가져오기 오류: {e}")
        return []


def create_calendar_event(summary, start_datetime, end_datetime, is_all_day=False, description=None, location=None, calendar_id=None):
    """
    구글 캘린더에 이벤트를 생성합니다.

    Args:
        summary: 이벤트 제목
        start_datetime: 시작 시간 (datetime 객체 또는 'YYYY-MM-DD' 또는 'YYYY-MM-DDTHH:MM:SS' 형식)
        end_datetime: 종료 시간 (datetime 객체 또는 'YYYY-MM-DD' 또는 'YYYY-MM-DDTHH:MM:SS' 형식)
        is_all_day: 종일 이벤트 여부
        description: 이벤트 설명
        location: 위치
        calendar_id: 캘린더 ID (None이면 환경변수 CALENDAR_ID 사용)

    Returns:
        str: 생성된 이벤트 ID (실패 시 None)
    """
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # calendar_id가 지정되지 않으면 환경변수 사용
        target_calendar_id = calendar_id if calendar_id else CALENDAR_ID

        # 이벤트 구조 생성
        event = {
            'summary': summary,
        }

        # 종일 이벤트 처리
        if is_all_day:
            # datetime 객체인 경우 날짜만 추출
            if isinstance(start_datetime, datetime):
                start_date = start_datetime.strftime('%Y-%m-%d')
            else:
                # 문자열인 경우 날짜 부분만 추출
                start_date = start_datetime.split('T')[0]

            if isinstance(end_datetime, datetime):
                # 종일 이벤트는 다음날까지로 설정
                end_date = (end_datetime + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                end_date_obj = datetime.strptime(end_datetime.split('T')[0], '%Y-%m-%d')
                end_date = (end_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

            # 종일 이벤트는 date만 사용하고 timeZone을 포함하지 않음
            event['start'] = {'date': start_date}
            event['end'] = {'date': end_date}
        else:
            # 시간이 포함된 이벤트
            if isinstance(start_datetime, datetime):
                start_str = start_datetime.isoformat()
            else:
                start_str = start_datetime

            if isinstance(end_datetime, datetime):
                end_str = end_datetime.isoformat()
            else:
                end_str = end_datetime

            event['start'] = {'dateTime': start_str, 'timeZone': 'Asia/Seoul'}
            event['end'] = {'dateTime': end_str, 'timeZone': 'Asia/Seoul'}

        # 선택적 필드 추가
        if description:
            event['description'] = description
        if location:
            event['location'] = location

        # 이벤트 생성
        created_event = service.events().insert(
            calendarId=target_calendar_id,
            body=event
        ).execute()

        event_id = created_event.get('id')
        logger.info(f"캘린더 이벤트 생성 성공: {summary} (ID: {event_id}, Calendar: {target_calendar_id})")
        return event_id

    except Exception as e:
        logger.error(f"캘린더 이벤트 생성 오류: {e}")
        return None

def delete_calendar_event(event_id, calendar_id=None):
    """
    구글 캘린더에서 이벤트를 삭제합니다.

    Args:
        event_id: 삭제할 이벤트 ID
        calendar_id: 캘린더 ID (None이면 환경변수 CALENDAR_ID 사용)

    Returns:
        bool: 성공 여부
    """
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # calendar_id가 지정되지 않으면 환경변수 사용
        target_calendar_id = calendar_id if calendar_id else CALENDAR_ID

        service.events().delete(
            calendarId=target_calendar_id,
            eventId=event_id
        ).execute()

        logger.info(f"캘린더 이벤트 삭제 성공 (ID: {event_id}, Calendar: {target_calendar_id})")
        return True

    except Exception as e:
        logger.error(f"캘린더 이벤트 삭제 오류: {e}")
        return False

# 메인 함수 - 다른 모듈에서 import 시 실행되지 않음
def main():
    import sys
    
    # 명령줄 인자로 날짜를 받을 수 있도록 설정
    if len(sys.argv) > 1:
        date_arg = sys.argv[1]
        print(f"입력한 날짜 '{date_arg}'의 연도에 해당하는 Google Calendar 이벤트 가져오기...")
        events = fetch_calendar_events(date_arg)
    else:
        # 현재 날짜 사용
        today = datetime.now()
        print(f"오늘 날짜({today.strftime('%Y-%m-%d')})의 연도({today.year}년)에 해당하는 Google Calendar 이벤트 가져오기...")
        events = fetch_calendar_events()
    
    try:
        if events:
            print(f"\n총 {len(events)}개의 이벤트를 찾았습니다:")
            for i, event in enumerate(events, 1):
                print(f"\n{i}. 제목: {event['summary']}")
                print(f"   시작: {event['start']}")
                print(f"   종료: {event['end']}")
                if event.get('description'):
                    print(f"   설명: {event['description'][:100]}..." if len(event['description']) > 100 else f"   설명: {event['description']}")
        else:
            print(f"\n해당 연도에 이벤트가 없습니다.")
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")

# 직접 실행될 때만 main() 함수 호출
if __name__ == '__main__':
    main()