import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import re
from flask import current_app

# Google Sheets API 스코프 설정
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_gspread_client():
    """Google Sheets 클라이언트 생성 (서비스 계정 인증)
    
    Returns:
        gspread.Client: 인증된 gspread 클라이언트
        
    Raises:
        FileNotFoundError: 서비스 계정 키 파일을 찾을 수 없는 경우
        Exception: 인증 실패 시
    """
    try:
        # instance 폴더에서 서비스 계정 키 파일 로드
        key_path = os.path.join(current_app.root_path, 'instance', 'google_key.json')
        
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Google API 키 파일을 찾을 수 없습니다: {key_path}")
        
        credentials = Credentials.from_service_account_file(key_path, scopes=SCOPES)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        current_app.logger.error(f"Google Sheets 클라이언트 생성 실패: {str(e)}")
        raise


def extract_spreadsheet_id(url):
    """Google Sheets URL에서 스프레드시트 ID 추출
    
    Args:
        url (str): Google Sheets URL
        
    Returns:
        str: 스프레드시트 ID 또는 None
        
    Example:
        >>> extract_spreadsheet_id('https://docs.google.com/spreadsheets/d/1ABC123/edit')
        '1ABC123'
    """
    # URL 패턴: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/...
    pattern = r'/spreadsheets/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def fetch_gsheet_data(gsheet_url, sheet_name='Sheet1', cell_range='A1:Z100'):
    """Google Sheets에서 데이터를 가져와 Pandas DataFrame으로 반환
    
    Args:
        gsheet_url (str): Google Sheets URL
        sheet_name (str): 워크시트 이름 (기본값: 'Sheet1')
        cell_range (str): 셀 범위 (기본값: 'A1:Z100')
        
    Returns:
        pd.DataFrame: 가져온 데이터를 담은 DataFrame
        
    Raises:
        ValueError: URL이 유효하지 않은 경우
        gspread.exceptions.SpreadsheetNotFound: 스프레드시트를 찾을 수 없는 경우
        gspread.exceptions.WorksheetNotFound: 워크시트를 찾을 수 없는 경우
        Exception: 기타 오류
        
    Example:
        >>> df = fetch_gsheet_data(
        ...     'https://docs.google.com/spreadsheets/d/1ABC123/edit',
        ...     'Sheet1',
        ...     'A1:D10'
        ... )
        >>> print(df.head())
    """
    try:
        # Check for CSV URL (Published Google Sheet or generic CSV)
        if 'output=csv' in gsheet_url or gsheet_url.lower().endswith('.csv'):
            try:
                current_app.logger.info(f"CSV URL 감지, 직접 다운로드 시도: {gsheet_url}")
                df = pd.read_csv(gsheet_url)
                
                # Check directly if empty
                if df.empty:
                    current_app.logger.warning(f"CSV 데이터가 비어있습니다: {gsheet_url}")
                    return pd.DataFrame()
                    
                current_app.logger.info(
                    f"CSV 데이터 로드 성공: {len(df)} 행, {len(df.columns)} 열"
                )
                return df
            except Exception as e:
                current_app.logger.error(f"CSV 데이터 로드 실패: {str(e)}")
                raise Exception(f"CSV 데이터를 불러오는데 실패했습니다: {str(e)}")

        # URL에서 스프레드시트 ID 추출
        spreadsheet_id = extract_spreadsheet_id(gsheet_url)
        if not spreadsheet_id:
            raise ValueError("유효하지 않은 Google Sheets URL입니다.")
        
        # 클라이언트 생성
        client = get_gspread_client()
        
        # 스프레드시트 열기
        spreadsheet = client.open_by_key(spreadsheet_id)
        current_app.logger.info(f"스프레드시트 '{spreadsheet.title}' 열기 성공")
        
        # 워크시트 선택
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # 워크시트가 없으면 첫 번째 워크시트 사용
            worksheet = spreadsheet.get_worksheet(0)
            current_app.logger.warning(
                f"워크시트 '{sheet_name}'를 찾을 수 없어 "
                f"첫 번째 워크시트 '{worksheet.title}' 사용"
            )
        
        # 데이터 가져오기
        values = worksheet.get(cell_range)
        
        if not values or len(values) == 0:
            current_app.logger.warning(f"범위 '{cell_range}'에 데이터가 없습니다.")
            return pd.DataFrame()
        
        # DataFrame 생성 (첫 번째 행을 헤더로 사용)
        if len(values) > 1:
            df = pd.DataFrame(values[1:], columns=values[0])
        else:
            df = pd.DataFrame(values)
        
        current_app.logger.info(
            f"데이터 로드 성공: {len(df)} 행, {len(df.columns)} 열"
        )
        
        return df
        
    except gspread.exceptions.SpreadsheetNotFound:
        raise Exception(f"스프레드시트를 찾을 수 없습니다. URL을 확인해주세요.")
    except gspread.exceptions.WorksheetNotFound:
        raise Exception(f"워크시트 '{sheet_name}'를 찾을 수 없습니다.")
    except Exception as e:
        current_app.logger.error(f"Google Sheets 데이터 로드 실패: {str(e)}")
        raise


def get_worksheet_names(gsheet_url):
    """Google Sheets의 모든 워크시트 이름 목록 반환
    
    Args:
        gsheet_url (str): Google Sheets URL
        
    Returns:
        list: 워크시트 이름 목록
        
    Raises:
        ValueError: URL이 유효하지 않은 경우
        Exception: 기타 오류
    """
    try:
        # Check for CSV URL
        if 'output=csv' in gsheet_url or gsheet_url.lower().endswith('.csv'):
            return ['CSV Data']

        spreadsheet_id = extract_spreadsheet_id(gsheet_url)
        if not spreadsheet_id:
            raise ValueError("유효하지 않은 Google Sheets URL입니다.")
        
        client = get_gspread_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        worksheets = spreadsheet.worksheets()
        return [ws.title for ws in worksheets]
        
    except Exception as e:
        current_app.logger.error(f"워크시트 목록 조회 실패: {str(e)}")
        raise


def validate_cell_range(cell_range):
    """셀 범위 형식 검증
    
    Args:
        cell_range (str): 셀 범위 (예: 'A1:D10')
        
    Returns:
        bool: 유효한 형식이면 True, 아니면 False
        
    Example:
        >>> validate_cell_range('A1:D10')
        True
        >>> validate_cell_range('invalid')
        False
    """
    pattern = r'^[A-Z]+\d+:[A-Z]+\d+$'
    return bool(re.match(pattern, cell_range))
