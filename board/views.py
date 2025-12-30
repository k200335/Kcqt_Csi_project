import json
import time
from django.http import JsonResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from django.shortcuts import render
from .models import OuterreceiptNew
from django.db.models import Q

def receipt_list(request):
    # 1. 검색 데이터 가져오기
    search_type = request.GET.get('search_type', 'rqcode')  # 의뢰번호, 봉인명 등
    search_value = request.GET.get('search_value', '')     # 검색어
    date_type = request.GET.get('date_type', 'receiveday') # 등록일자, 접수일자 등
    start_date = request.GET.get('start_date', '')         # 시작일
    end_date = request.GET.get('end_date', '')             # 종료일

    # 2. 기본 쿼리셋
    receipts = OuterreceiptNew.objects.all().order_by('-idx')

    # 3. 텍스트 필터링
    if search_value:
        filter_kwargs = {f"{search_type}__icontains": search_value}
        receipts = receipts.filter(**filter_kwargs)

    # 4. 날짜 필터링 (선택한 날짜 종류에 따라 필터링)
    if start_date and end_date:
        date_filter = {f"{date_type}__range": [start_date, end_date]}
        receipts = receipts.filter(**date_filter)

    context = {
        'receipts': receipts,
        'search_type': search_type,
        'search_value': search_value,
        'date_type': date_type,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'board.html', context)

def save_csi_receipt(request):
    # 아직 HTML 파일명이 정확하지 않다면 templates 폴더 안에 
    # save_csi_receipt.html 이라는 이름으로 파일을 저장해 두어야 합니다.
    return render(request, 'save_csi_receipt.html')

#여기부터 csi불러오는 코드입니다

def fetch_csi_data(request):
    if request.method == 'POST':
        driver = None
        try:
            data = json.loads(request.body)
            rq_numbers = data.get('rq_numbers', [])
            
            if not rq_numbers:
                return JsonResponse({'status': 'error', 'message': '선택된 RQ번호가 없습니다.'})

            # 1) 셀레늄 브라우저 설정
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # 창이 자꾸 안 열리면 아래 주석을 해제해서 실제 브라우저가 뜨는지 확인해 보세요.
            # chrome_options.add_argument("--start-maximized") 

            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            wait = WebDriverWait(driver, 10) # 속도가 빠를 때는 20초 정도면 충분합니다.

            # 2) CSI 사이트 접속 및 로그인
            driver.get("https://gcloud.csi.go.kr/cmq/main.do")
            
            # ID 입력창 대기 및 입력
            user_input = wait.until(EC.element_to_be_clickable((By.ID, "userId")))
            user_input.send_keys("youngjun") 
            driver.find_element(By.ID, "pswd").send_keys("k*1800*92*")
            driver.find_element(By.CLASS_NAME, "login-btn").click()
            
            # 로그인 성공 후 게시판으로 직접 이동
            time.sleep(2)
            driver.get("https://gcloud.csi.go.kr/cmq/qtr/qltRqst/rqstRcvList.do") 
            wait.until(EC.presence_of_element_located((By.ID, "searchVal")))

            final_results = []

            # 3) RQ번호별 데이터 수집
            for rq_no in rq_numbers:
                try:
                    # 검색창 로딩 대기
                    search_input = wait.until(EC.element_to_be_clickable((By.ID, "searchVal")))
                    search_input.clear()
                    search_input.send_keys(rq_no)
                    
                    # 조회 버튼 클릭
                    driver.find_element(By.XPATH, "//button[contains(@onclick, 'go_search')]").click()
                    time.sleep(1.5) # 검색 결과 갱신 대기

                    # 상세 링크 클릭
                    detail_link = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "goSelectLink")))
                    detail_link.click()
                    
                    # 상세 페이지 로딩 대기
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

                    # 프론트엔드 순서에 맞춘 배열 생성
                    final_results.append([
                        rcpt_no, rcpt_date, status, biz_nm, agency, pick_user, seal_name
                    ])

                except Exception as e:
                    print(f"항목 수집 실패 ({rq_no}): {e}")
                    # 실패 시 목록으로 돌아가서 다음 번호 시도
                    driver.get("https://gcloud.csi.go.kr/cmq/qtr/qltRqst/rqstRcvList.do")
                    continue

                # 하나 완료 후 목록으로 복귀
                driver.back()
                time.sleep(1)

            driver.quit()
            return JsonResponse({'status': 'success', 'results': final_results, 'message': '데이터 수집 완료!'})

        except Exception as e:
            if driver: driver.quit()
            return JsonResponse({'status': 'error', 'message': f"접속 중 오류: {str(e)}"})

    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'})

