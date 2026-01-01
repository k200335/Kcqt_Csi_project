import json
import time
from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
# 셀레늄 및 크롤링 관련
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
# 모델 임포트 (클래스명을 CsiReceipt로 통일)
from .models import OuterreceiptNew, CsiReceipt

# --- [1] 기본 게시판 및 페이지 렌더링 ---

def receipt_list(request):
    search_type = request.GET.get('search_type', 'rqcode')
    search_value = request.GET.get('search_value', '')
    date_type = request.GET.get('date_type', 'receiveday')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    receipts = OuterreceiptNew.objects.all().order_by('-idx')

    if search_value:
        filter_kwargs = {f"{search_type}__icontains": search_value}
        receipts = receipts.filter(**filter_kwargs)

    if start_date and end_date:
        date_filter = {f"{date_type}__range": [start_date, end_date]}
        receipts = receipts.filter(**date_filter)

    return render(request, 'board.html', {
        'receipts': receipts, 'search_type': search_type, 'search_value': search_value,
        'date_type': date_type, 'start_date': start_date, 'end_date': end_date,
    })

def save_csi_receipt(request):
    return render(request, 'save_csi_receipt.html')


# --- [2] CSI 사이트 데이터 크롤링 (Selenium) ---

@csrf_exempt
def fetch_csi_data(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'})

    driver = None
    try:
        data = json.loads(request.body)
        rq_numbers = data.get('rq_numbers', [])
        if not rq_numbers:
            return JsonResponse({'status': 'error', 'message': '선택된 RQ번호가 없습니다.'})

        # 브라우저 설정
        chrome_options = Options()
        chrome_options.add_argument("--headless") # 필요시 주석 처리 (창 보기)
        chrome_options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 10)

        # 로그인 로직
        driver.get("https://gcloud.csi.go.kr/cmq/main.do")
        wait.until(EC.element_to_be_clickable((By.ID, "userId"))).send_keys("youngjun")
        driver.find_element(By.ID, "pswd").send_keys("k*1800*92*")
        driver.find_element(By.CLASS_NAME, "login-btn").click()
        
        time.sleep(2)
        final_results = []

        for rq_no in rq_numbers:
            try:
                driver.get("https://gcloud.csi.go.kr/cmq/qtr/qltRqst/rqstRcvList.do")
                search_input = wait.until(EC.element_to_be_clickable((By.ID, "searchVal")))
                search_input.clear()
                search_input.send_keys(rq_no)
                driver.find_element(By.XPATH, "//button[contains(@onclick, 'go_search')]").click()
                
                time.sleep(1.5)
                wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "goSelectLink"))).click()
                wait.until(EC.presence_of_element_located((By.XPATH, "//th[contains(text(), '접수번호')]")))

                # 데이터 추출

                rcpt_no = driver.find_element(By.XPATH, "//th[contains(text(), '접수번호')]/following-sibling::td").text.strip()
                rcpt_date = driver.find_element(By.XPATH, "//th[contains(text(), '접수일시')]/following-sibling::td").text.strip()
                status = driver.find_element(By.XPATH, "//th[contains(text(), '최종진행상태')]/following-sibling::td").text.strip()
                biz_nm = driver.find_element(By.XPATH, "//th[text()='공사명']/following-sibling::td").text.strip()
                agency = driver.find_element(By.XPATH, "//th[contains(text(), '의뢰기관')]/following-sibling::td").text.strip()                

                    # 채취자 및 봉인명 추출 (에러 방지용 try-except)
                try:
                    pick_user = driver.find_element(By.XPATH, "//th[text()='채취자']/parent::tr/following-sibling::tr[1]/td[last()]").text
                    pick_user = pick_user.replace('성명', '').replace('(서명 완료)', '').strip()
                except: pick_user = ""
                
                try:
                    # [중요] 괄호 오타 수정됨
                    seal_name = driver.find_element(By.XPATH, "//th[contains(text(), '봉인명')]/following-sibling::td").text.strip()
                except: seal_name = ""

                # 3. [어제 성공한 코드] 특정처리자 추출 (BeautifulSoup 활용)
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                specific_user = "" # 특정처리자 초기값
                hist_section = soup.find(id="rqst_hist_div")

                if hist_section:
                    rows = hist_section.select("tbody tr")
                    for r in rows:
                        cols = r.find_all("td")
                        # 2번째 열에 기관명, 3번째 열에 이름이 있는 구조
                        if len(cols) >= 3 and "한국건설품질시험원" in cols[1].get_text():
                            specific_user = cols[2].get_text(strip=True)
                    # 4. 최종 리스트 구성 (순서가 매우 중요함!)
                    # 인덱스: 0:접수번호, 1:접수일시, 2:상태, 3:사업명, 4:의뢰기관, 5:채취자, 6:봉인명, 7:특정처리자

                    result_row = [rcpt_no, rcpt_date, status, biz_nm, agency, pick_user, seal_name, specific_user]
                    final_results.append(result_row)
            except Exception as e:
                print(f"항목 수집 실패 ({rq_no}): {e}")
                # 실패 시 목록으로 돌아가서 다음 번호 시도
            continue

        driver.quit()
        return JsonResponse({'status': 'success', 'results': final_results})

    except Exception as e:
        if driver: driver.quit()
        return JsonResponse({'status': 'error', 'message': str(e)})


# --- [3] MySQL 배정 현황 이력 조회 (핵심 로직) ---

@csrf_exempt
def fetch_assignment_history(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            results = []

            for item in items:
                proj = item.get('project', '').strip()
                clnt = item.get('client', '').strip()
                uid = item.get('u_id', '').strip()  # ⭐ 화면에서 보낸 의뢰번호 추출

                # 1. 과거 배정 이력 조회 (기존 로직 유지)
                history_qs = CsiReceipt.objects.filter(
                    project=proj, 
                    client=clnt
                ).exclude(manager__isnull=True).exclude(manager='').values_list('manager', flat=True).order_by('-id')

                unique_teams = []
                for team in history_qs:
                    if team not in unique_teams:
                        unique_teams.append(team)

                # 2. ⭐ 중복 확인: 현재 의뢰번호가 DB에 이미 존재하는지 체크
                # 존재하면 True, 없으면 False를 반환합니다.
                is_saved = CsiReceipt.objects.filter(u_id=uid).exists()

                results.append({
                    'history': ", ".join(unique_teams) if unique_teams else "이력 없음",
                    'is_saved': is_saved  # ⭐ 프론트엔드에 전달할 결과 추가
                })

            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            print(f"Error in fetch_assignment_history: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'})

# board/views.py

@csrf_exempt
def save_to_csi_receipts(request):
    if request.method == 'POST':
        try:
            # 1. 데이터 로드 및 검증
            raw_data = json.loads(request.body)
            data_list = raw_data.get('data', [])
            
            if not data_list:
                return JsonResponse({'status': 'error', 'message': '저장할 데이터가 선택되지 않았습니다.'})
            
            with connection.cursor() as cursor:
                # 2. UPSERT 쿼리 (의뢰번호가 UNIQUE 설정되어 있어야 작동함)
                sql = """
                    INSERT INTO csi_receipts (
                        의뢰번호, 접수번호, 접수일시, 진행상태, 사업명, 의뢰기관명, 
                        채취자, 봉인명, 처리자, 영업구분, 담당자, 확인, 
                        시료량, 구분, 현장담당자, 배정일자, 배정현황
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        접수번호 = VALUES(접수번호),
                        접수일시 = VALUES(접수일시),
                        진행상태 = VALUES(진행상태),
                        사업명 = VALUES(사업명),
                        의뢰기관명 = VALUES(의뢰기관명),
                        채취자 = VALUES(채취자),
                        봉인명 = VALUES(봉인명),
                        처리자 = VALUES(처리자),
                        영업구분 = VALUES(영업구분),
                        담당자 = VALUES(담당자),
                        확인 = VALUES(확인),
                        시료량 = VALUES(시료량),
                        구분 = VALUES(구분),
                        현장담당자 = VALUES(현장담당자),
                        배정일자 = VALUES(배정일자),
                        배정현황 = VALUES(배정현황)
                """
                
                # 3. 데이터 매핑 (KeyError 방지를 위해 .get() 사용)
                params = [
                    (
                        d.get('u_id'), d.get('receipt_id'), d.get('receipt_date'), 
                        d.get('status'), d.get('project'), d.get('client'),
                        d.get('sampler'), d.get('seal'), d.get('processor'), 
                        d.get('sales_type'), d.get('manager'), d.get('check_col'),
                        d.get('amount'), d.get('type_col'), d.get('manager_name'), 
                        d.get('assign_date'), d.get('assignment_history')
                    ) for d in data_list
                ]
                
                # 4. 일괄 실행
                cursor.executemany(sql, params)
                
            return JsonResponse({
                'status': 'success', 
                'message': f'{len(data_list)}건의 데이터가 DB에 반영(새로 저장 또는 기존 내용 갱신)되었습니다.'
            })
        except Exception as e:
            # 에러 발생 시 상세 내용 반환
            return JsonResponse({'status': 'error', 'message': f'DB 처리 중 오류: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'})

# 데이터 가져와서 표에 뿌려주는 코드임
def search_by_assign_date(request):
    if request.method == 'POST':
        try:
            params = json.loads(request.body)
            manager = params.get('manager', '전체')
            filter_type = params.get('filter') # u_id, project, client 중 하나
            keyword = params.get('keyword', '').strip() # 검색어
            start_date = params.get('start_date')
            end_date = params.get('end_date')

            with connection.cursor() as cursor:
                # 1. 기본 SQL (날짜 조건은 필수)
                sql = """
                    SELECT 
                        의뢰번호, 접수번호, 접수일시, 진행상태, 사업명, 의뢰기관명, 
                        채취자, 봉인명, 처리자, 영업구분, 담당자, 확인, 
                        시료량, 구분, 현장담당자, 배정일자, 배정현황
                    FROM csi_receipts
                    WHERE 배정일자 BETWEEN %s AND %s
                """
                query_params = [start_date, end_date]

                # 2. 담당자 조건 추가
                if manager != "전체":
                    sql += " AND 담당자 = %s"
                    query_params.append(manager)
                
                # 3. 추가 검색 필터 (의뢰번호, 사업명, 의뢰기관명) ⭐추가된 부분
                if keyword:
                    if filter_type == "u_id":
                        sql += " AND 의뢰번호 LIKE %s"
                        query_params.append(f"%{keyword}%")
                    elif filter_type == "project":
                        sql += " AND 사업명 LIKE %s"
                        query_params.append(f"%{keyword}%")
                    elif filter_type == "client":
                        sql += " AND 의뢰기관명 LIKE %s"
                        query_params.append(f"%{keyword}%")

                # 4. 정렬 추가 (조건이 다 붙은 뒤에 정렬이 와야 합니다)
                sql += " ORDER BY 배정일자 DESC, 의뢰번호 DESC"

                cursor.execute(sql, query_params)
                
                # 결과 변환
                columns = [
                    'u_id', 'receipt_id', 'receipt_date', 'status', 'project', 'client',
                    'sampler', 'seal', 'processor', 'sales_type', 'manager', 'check_col',
                    'amount', 'type_col', 'manager_name', 'assign_date', 'assignment_history'
                ]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return JsonResponse({'status': 'success', 'results': results})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'})

    
# board/views.py

def csi_issue_view(request):
    """
    성적서 발급 관리 페이지(4분할 화면)를 열어주는 기본 뷰
    """
    # 오늘 날짜를 기본값으로 전달 (선택 사항)
    import datetime
    default_date = datetime.date.today().strftime('%Y-%m-%d')
    
    return render(request, 'csi_issue.html', {
        'default_date': default_date
    })
    
# --- [4] CSI 성적서 발급 정보 수집 (상세페이지 역추적 방식) --- 
@csrf_exempt
def fetch_csi_issue_data(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'})

    driver = None
    try:
        data = json.loads(request.body)
        # 1. 프론트엔드에서 보낸 시작일과 종료일 가져오기
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not start_date or not end_date:
            return JsonResponse({'status': 'error', 'message': '시작일과 종료일이 누락되었습니다.'})

        # 2. 하이픈(-) 제거하여 YYYYMMDD 형식으로 변환
        clean_start = start_date.replace("-", "")
        clean_end = end_date.replace("-", "")

        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless") # 필요시 주석 처리 (창 보기)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 15)

        # 1. 로그인
        driver.get("https://gcloud.csi.go.kr/cmq/main.do")
        wait.until(EC.element_to_be_clickable((By.ID, "userId"))).send_keys("youngjun")
        driver.find_element(By.ID, "pswd").send_keys("k*1800*92*")
        driver.find_element(By.CLASS_NAME, "login-btn").click()
        time.sleep(2)

        # 2. 메뉴 이동 및 검색 설정
        driver.get("https://gcloud.csi.go.kr/cmq/qti/qltAgntQltSttus/qltAgntQltSttusList.do")
        wait.until(EC.presence_of_element_located((By.NAME, "ymdKey")))
        
        # 발급일자 선택 로직
        driver.execute_script("""
            var select = document.querySelector('select[name="ymdKey"]');
            if (select) {
                for (var i = 0; i < select.options.length; i++) {
                    if (select.options[i].text.indexOf('발급일자') !== -1) {
                        select.selectedIndex = i;
                        select.dispatchEvent(new Event('change')); 
                        break;
                    }
                }
            }
        """)
        time.sleep(1.5)

        # 날짜 입력 및 검색
        # 1. 시작일 입력
        start_input = driver.find_element(By.ID, "startYmd")
        start_input.clear()
        start_input.send_keys(clean_start)  # clean_date 대신 clean_start 사용
        start_input.send_keys(Keys.ENTER)

        # 2. 종료일 입력
        end_input = driver.find_element(By.ID, "endYmd")
        end_input.clear()
        end_input.send_keys(clean_end)      # clean_date 대신 clean_end 사용
        end_input.send_keys(Keys.ENTER)
        
        driver.execute_script("go_search();")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "pagination")))
        time.sleep(2)

        # 3. 데이터 수집 루프
        final_results = []
        current_page_idx = 1 

        while True:
            wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "goSelectLink")))
            time.sleep(2) 
            
            first_cert_before = driver.find_elements(By.CLASS_NAME, "goSelectLink")[0].text.strip()
            rows = driver.find_elements(By.CSS_SELECTOR, "table.table-striped tbody tr")

            for i in range(len(rows)):
                current_rows = driver.find_elements(By.CSS_SELECTOR, "table.table-striped tbody tr")
                if i >= len(current_rows): break
                row = current_rows[i]
                
                # 목록 데이터 8개 추출
                try:
                    list_info = {
                        'cert_no': row.find_element(By.XPATH, "./td[2]").text.strip(),
                        'seal_name': row.find_element(By.XPATH, "./td[3]").text.strip(),
                        'project_name': row.find_element(By.XPATH, "./td[4]").text.strip(),
                        'agency': row.find_element(By.XPATH, "./td[5]").text.strip(),
                        'req_date': row.find_element(By.XPATH, "./td[6]").text.strip(),
                        'recv_date': row.find_element(By.XPATH, "./td[7]").text.strip(),
                        'wait_date': row.find_element(By.XPATH, "./td[8]").text.strip(),
                        'issue_date': row.find_element(By.XPATH, "./td[9]").text.strip()
                    }
                    target_link = row.find_element(By.XPATH, "./td[2]//a")
                except Exception:
                    continue

                # 상세페이지 진입하여 '의뢰번호' 수집
                try:
                    driver.execute_script("arguments[0].click();", target_link)
                    expand_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '품질시험 의뢰서 내역')]")))
                    driver.execute_script("arguments[0].click();", expand_btn)
                    time.sleep(1.2)
                    
                    rq_no = driver.find_element(By.XPATH, "//th[contains(text(), '의뢰번호')]/following-sibling::td").text.strip()
                except Exception:
                    rq_no = "추출 실패"

                # 최종 데이터 결합 (화면 표 순서에 최적화)
                final_results.append({
                    'u_id': rq_no,                   # 의뢰번호 (1순위)
                    'cert_no': list_info['cert_no'],   # 성적서번호
                    'seal_name': list_info['seal_name'], # 봉인명
                    'project_name': list_info['project_name'],
                    'agency': list_info['agency'],
                    'req_date': list_info['req_date'],
                    'recv_date': list_info['recv_date'],
                    'wait_date': list_info['wait_date'],
                    'issue_date': list_info['issue_date']                    
                })

                driver.execute_script("window.history.back();")
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "goSelectLink")))
                time.sleep(1.5)

            # 4. 페이징 처리
            try:
                next_page_num = current_page_idx + 1
                btn_xpath = f"//ul[contains(@class,'pagination')]//a[text()='{next_page_num}']"
                next_btns = driver.find_elements(By.XPATH, btn_xpath)
                
                if next_btns:
                    driver.execute_script("arguments[0].click();", next_btns[0])
                else:
                    driver.execute_script(f"goPage({next_page_num});")
                
                is_changed = False
                for _ in range(15):
                    time.sleep(1)
                    current_links = driver.find_elements(By.CLASS_NAME, "goSelectLink")
                    if current_links and current_links[0].text.strip() != first_cert_before:
                        is_changed = True
                        current_page_idx = next_page_num
                        break
                if not is_changed: break
            except: break

        driver.quit()
        return JsonResponse({'status': 'success', 'results': final_results})

    except Exception as e:
        if driver: driver.quit()
        return JsonResponse({'status': 'error', 'message': str(e)})


# 여기서부터 발급일 DB저장하는 코드임
@csrf_exempt
def save_csi_matching_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            selected_items = data.get('items', [])

            if not selected_items:
                return JsonResponse({'status': 'error', 'message': '저장할 항목이 없습니다.'})

            with connection.cursor() as cursor:
                # 🚀 INSERT + UPDATE (UPSERT) 쿼리
                # 성적서번호가 중복될 경우, 의뢰번호와 발급일자를 최신으로 갱신합니다.
                sql = """
                    INSERT INTO csi_issue_results (의뢰번호, 성적서번호, 발급일자)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        의뢰번호 = VALUES(의뢰번호),
                        발급일자 = VALUES(발급일자)
                """
                
                params = [
                    (item['u_id'], item['cert_no'], item['issue_date']) 
                    for item in selected_items
                ]
                
                cursor.executemany(sql, params)

            return JsonResponse({'status': 'success', 'message': f'{len(selected_items)}건 처리 완료 (저장/업데이트)'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})