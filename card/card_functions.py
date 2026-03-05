from flask import Blueprint, render_template, request, redirect, make_response, jsonify, send_from_directory
from google.oauth2.service_account import Credentials
import gspread
import traceback
from collections import defaultdict
from datetime import datetime
import csv, io
import uuid
import os

# card 블루프린트 생성
card_bp = Blueprint('card', __name__, 
                    template_folder='templates',
                    static_folder='static')

# Google Sheets API 설정 (card 폴더 기준)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
cred_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
credentials = Credentials.from_service_account_file(cred_path, scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open('bizcard').sheet1

@card_bp.route('/')
def card_index():
    """카드 메인 페이지"""
    try:
        # Google Sheets에서 데이터 로드
        raw_data = sheet.get_all_records()

        # 데이터가 없을 경우 처리
        if not raw_data:
            return render_template('card_index.html', data=[], year_months={}, year=None, month=None)

        # 데이터 매핑 및 정렬
        processed_data = []
        year_months = defaultdict(set)

        for row in raw_data:
            try:
                date_str = row.get('일자', '').strip()
                if len(date_str) >= 7:  # 유효한 날짜인지 확인
                    year, month, *_ = date_str.split('-')
                    year_months[year].add(month.zfill(2))  # 월을 두 자리로 정리

                processed_row = {
                    'id': row.get('ID', ''),  # ID 포함
                    'date': date_str,
                    'year': year,
                    'month': month.zfill(2),
                    'usage': row.get('사용처', ''),
                    'amount': int(row.get('금액', 0)) if row.get('금액') else 0,
                    'user': row.get('사용자', ''),
                    'purpose': row.get('목적', ''),
                    'content': row.get('내용', ''),
                    'note': row.get('비고', ''),
                    'receipt': 'Y' if row.get('영수증', '').strip().upper() == 'Y' else 'N'
                }
                processed_data.append(processed_row)
            except Exception as e:
                print(f"Error processing row: {row}")
                print(f"Error details: {e}")
                continue

        # 데이터 정렬
        processed_data.sort(key=lambda x: x['date'], reverse=False)

        # 연/월 정렬
        year_months = {year: sorted(months, reverse=True) for year, months in sorted(year_months.items(), reverse=True)}

        # 최신 연도와 월 설정
        latest_year = next(iter(year_months), None)
        latest_month = year_months[latest_year][0] if latest_year else None

        return render_template(
            'card_index.html',
            data=processed_data,  # ID를 포함한 데이터 전달
            year_months=year_months,
            year=latest_year,
            month=latest_month
        )

    except Exception as e:
        print(f"인덱스 페이지 오류: {e}")
        import traceback
        traceback.print_exc()
        return render_template('card_index.html', data=[], year_months={}, year=None, month=None)


@card_bp.route('/add', methods=['GET', 'POST'])
def card_add():
    """카드 추가 처리"""
    try:
        # Google Sheets에서 실시간 데이터 가져오기
        all_data = sheet.get_all_records() or []

        usages = sorted({row['사용처'] for row in all_data if row.get('사용처')})
        users = sorted({row['사용자'] for row in all_data if row.get('사용자')})
        purposes = sorted({row['목적'] for row in all_data if row.get('목적')})
        notes = sorted({note.strip() for row in all_data for note in row.get('비고', '').split(',') if note.strip()})
        contents = sorted({row['내용'] for row in all_data if row.get('내용')})  # 추가
        
        # 가장 최근 내용과 비고 가져오기 (마지막 행)
        last_content = all_data[-1].get('내용', '') if all_data else ''
        last_note = all_data[-1].get('비고', '') if all_data else ''

        if request.method == 'POST':
            # UUID 생성 후 하이픈 제거하고 16자리로 추출
            new_id = uuid.uuid4().hex[:16]

            # 데이터 추가
            sheet.append_row([
                new_id,
                request.form.get('date', ''),
                request.form.get('usage', ''),
                request.form.get('amount', ''),
                request.form.get('user', ''),
                request.form.get('purpose', ''),
                request.form.get('content', ''),
                request.form.get('note', ''),
                request.form.get('receipt', '')
            ])

            return redirect('/card')

        return render_template(
            'card_add.html',
            usages=usages,
            users=users,
            purposes=purposes,
            notes=notes,
            contents=contents,  # 추가
            last_content=last_content,
            last_note=last_note
        )

    except Exception as e:
        print(f"Error in add function: {str(e)}")
        traceback.print_exc()
        return redirect('/card')
        print(f"Error in add function: {str(e)}")
        traceback.print_exc()
        return redirect('/card')


@card_bp.route('/edit/<string:id>', methods=['GET', 'POST'])
def card_edit(id):
    """카드 수정 처리"""
    try:
        all_data = sheet.get_all_records()
        raw_record = next((row for row in all_data if row['ID'] == id), None)
        if not raw_record:
            return "Record not found", 404

        # 데이터 정리 (record 객체)
        record = {
            'ID': raw_record.get('ID', ''),
            'date': raw_record.get('일자', ''),
            'usage': raw_record.get('사용처', ''),
            'amount': int(raw_record.get('금액', 0)) if raw_record.get('금액') else 0,
            'user': raw_record.get('사용자', ''),
            'purpose': raw_record.get('목적', ''),
            'content': raw_record.get('내용', ''),
            'note': raw_record.get('비고', ''),
            'receipt': 'Y' if raw_record.get('영수증', '').strip().upper() == 'Y' else 'N'
        }

        # 사용처, 사용자, 목적, 비고 목록 가져오기
        usages = sorted({row['사용처'] for row in all_data if row.get('사용처')})
        users = sorted({row['사용자'] for row in all_data if row.get('사용자')})
        purposes = sorted({row['목적'] for row in all_data if row.get('목적')})
        notes = sorted({note.strip() for row in all_data for note in row.get('비고', '').split(',') if note.strip()})

        if request.method == 'POST':
            updated_data = [
                id,
                request.form['date'],
                request.form['usage'],
                request.form['amount'],
                request.form['user'],
                request.form['purpose'],
                request.form['content'],
                request.form['note'],
                request.form['receipt']
            ]
            row_index = next((i + 2 for i, row in enumerate(all_data) if row['ID'] == id), None)
            if row_index:
                sheet.update(f'A{row_index}:I{row_index}', [updated_data])
                return redirect('/card')
            return "Failed to update record", 500

        return render_template('card_edit.html', record=record, usages=usages, users=users, purposes=purposes, notes=notes)

    except Exception as e:
        traceback.print_exc()
        return "An unexpected error occurred", 500


@card_bp.route('/delete/<id>', methods=['POST'])
def card_delete(id):
    """카드 삭제 처리"""
    try:
        raw_data = sheet.get_all_records()
        target_row = next((i + 2 for i, row in enumerate(raw_data) if str(row.get('ID', '')) == str(id)), None)
        if target_row:
            sheet.delete_rows(target_row)
            return "", 200
        return "Record not found", 404
    except Exception as e:
        traceback.print_exc()
        return "An error occurred while deleting the record.", 500


@card_bp.route('/print/<year>/<month>', methods=['GET'])
def card_print_view(year, month):
    """카드 인쇄 뷰"""
    try:
        raw_data = sheet.get_all_records()
        filtered_data = [
            row for row in raw_data
            if row.get('일자', '').startswith(f"{year}-{month.zfill(2)}")
        ]

        if not filtered_data:
            return render_template('card_print.html', data=[], year=year, month=month, total_amount=0)

        filtered_data.sort(key=lambda x: (x.get('일자', ''), x.get('ID', '')))

        processed_data = []
        total_amount = 0
        for idx, row in enumerate(filtered_data, start=1):
            amount = int(row.get('금액', 0))
            total_amount += amount
            processed_data.append({
                'number': idx,
                'date': row.get('일자', ''),
                'usage': row.get('사용처', ''),
                'amount': amount,
                'user': row.get('사용자', ''),
                'purpose': row.get('목적', ''),
                'content': row.get('내용', ''),
                'note': row.get('비고', ''),
            })

        return render_template(
            'card_print.html',
            data=processed_data,
            year=year,
            month=month,
            total_amount=total_amount
        )
    except Exception as e:
        traceback.print_exc()
        return render_template('card_print.html', data=[], year=year, month=month, total_amount=0)


@card_bp.route('/download_csv/<year>/<month>')
def card_download_csv(year, month):
    """CSV 다운로드"""
    try:
        raw_data = sheet.get_all_records()
        if not raw_data:
            return "데이터가 없습니다.", 404

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['번호', '일자', '사용처', '금액', '사용자', '목적', '내용', '비고'])
        
        row_num = 1
        total = 0
        
        for row in raw_data:
            date = row.get('일자', '').split('-')
            if len(date) >= 2 and date[0] == year and date[1] == month.zfill(2):
                writer.writerow([
                    row_num,
                    row.get('일자'),
                    row.get('사용처'),
                    row.get('금액'),
                    row.get('사용자'),
                    row.get('목적'),
                    row.get('내용'),
                    row.get('비고')
                ])
                row_num += 1
                total += int(row.get('금액', 0))

        output.seek(0)
        response = make_response(output.getvalue().encode('utf-8-sig'))
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment;filename={year}{month}_card.csv'
        return response

    except Exception as e:
        print(f"CSV 다운로드 오류: {e}")
        return "오류가 발생했습니다.", 500


@card_bp.route('/monthly_viz')
def card_monthly_viz():
    """월별 시각화"""
    try:
        raw_data = sheet.get_all_records()
        selected_month = request.args.get('month')
        
        if not selected_month:
            year = request.args.get('year')
            month = request.args.get('month', '').zfill(2)
            if year and month:
                selected_month = f"{year}-{month}"
        
        monthly_purpose_totals = defaultdict(lambda: defaultdict(int))
        year_months = set()
        
        for row in raw_data:
            try:
                date_str = row.get('일자', '').strip()
                if date_str:
                    year_month = date_str[:7]
                    year_months.add(year_month)
                    
                    purpose = row.get('목적', 'Unknown')
                    amount = int(float(str(row.get('금액', '0')).replace(',', '')))
                    
                    monthly_purpose_totals[year_month][purpose] += amount
            except (ValueError, AttributeError) as e:
                print(f"Error processing row: {row}, Error: {e}")
                continue
        
        sorted_year_months = sorted(year_months, reverse=True)
        
        if selected_month and selected_month not in year_months:
            selected_month = sorted_year_months[0] if sorted_year_months else None
        
        all_purposes = set()
        for month_data in monthly_purpose_totals.values():
            all_purposes.update(month_data.keys())
        
        chart_data = {
            'months': sorted_year_months,
            'purpose_data': {}
        }
        
        for purpose in sorted(all_purposes):
            chart_data['purpose_data'][purpose] = [
                monthly_purpose_totals[month][purpose]
                for month in sorted_year_months
            ]
        
        return render_template(
            'card_monthly_viz.html',
            chart_data=chart_data,
            selected_month=selected_month,
            default_month=sorted_year_months[0] if sorted_year_months else None
        )

    except Exception as e:
        print(f"Visualization error: {e}")
        traceback.print_exc()
        return "Error generating visualization", 500


@card_bp.route('/yearly_viz')
def card_yearly_viz():
    """연별 시각화"""
    try:
        raw_data = sheet.get_all_records()
        
        yearly_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        all_purposes = set()
        years = set()
        
        for row in raw_data:
            try:
                date_str = row.get('일자', '').strip()
                if not date_str:
                    continue
                    
                year = date_str[:4]
                month = int(date_str[5:7])
                purpose = row.get('목적', 'Unknown')
                
                # Convert amount to integer, handling potential errors
                try:
                    amount = int(float(str(row.get('금액', '0')).replace(',', '')))
                except (ValueError, TypeError):
                    print(f"Invalid amount in row: {row}")  # 디버깅용 로그
                    amount = 0
                
                yearly_data[year][month][purpose] += amount
                all_purposes.add(purpose)
                years.add(year)
                
            except (ValueError, AttributeError, IndexError) as e:
                print(f"Error processing row: {row}, Error: {e}")  # 디버깅용 로그
                continue
        
        # Print debug information
        print("Years found:", years)  # 디버깅용 로그
        print("Purposes found:", all_purposes)  # 디버깅용 로그
        
        # Prepare data for plotting
        chart_data = {
            'years': sorted(list(years), reverse=True),
            'purposes': sorted(list(all_purposes)),
            'monthly_data': {}
        }
        
        # For each year, prepare monthly data with zero-filling
        for year in chart_data['years']:
            chart_data['monthly_data'][year] = {}
            for purpose in chart_data['purposes']:
                monthly_values = []
                for month in range(1, 13):
                    value = yearly_data[year][month][purpose]
                    monthly_values.append(value)
                chart_data['monthly_data'][year][purpose] = monthly_values
        
        # Print sample of prepared data
        print("Sample of prepared data:", 
              {year: chart_data['monthly_data'][year].keys() 
               for year in list(chart_data['years'])[:1]})  # 디버깅용 로그
            
        return render_template('card_yearly_viz.html', chart_data=chart_data)

    except Exception as e:
        print(f"Visualization error: {e}")
        traceback.print_exc()
        return "Error generating visualization", 500


@card_bp.route('/get_notes')
def card_get_notes():
    """비고 목록 조회"""
    try:
        all_data = sheet.get_all_records()

        # 비고 데이터 병합 및 중복 제거
        notes_set = set()
        for row in all_data:
            note_value = row.get('비고', '').strip()
            if note_value:
                names = map(str.strip, note_value.split(','))  # 쉼표로 분리 후 공백 제거
                notes_set.update(names)  # 이름 단위로 중복 제거

        return jsonify(sorted(notes_set))  # 중복 제거 및 정렬된 목록 반환

    except Exception as e:
        traceback.print_exc()
        return jsonify([]), 500


def get_monthly_card_summary():
    """이번 달 카드 사용량 요약 (총액 + 목적별)"""
    try:
        raw_data = sheet.get_all_records()
        now = datetime.now()
        current_year_month = now.strftime("%Y-%m")
        
        total_amount = 0
        breakdown = defaultdict(int)
        
        for row in raw_data:
            date_str = str(row.get('일자', '')).strip()
            if date_str.startswith(current_year_month):
                try:
                    amount = int(str(row.get('금액', '0')).replace(',', ''))
                    purpose = row.get('목적', '기타')
                    if not purpose: purpose = '기타'
                    
                    total_amount += amount
                    breakdown[purpose] += amount
                except ValueError:
                    continue
                    
        return {
            'year_month': current_year_month,
            'total': total_amount,
            'breakdown': dict(breakdown)
        }
    except Exception as e:
        print(f"Card summary error: {e}")
        return {'year_month': '', 'total': 0, 'breakdown': {}}