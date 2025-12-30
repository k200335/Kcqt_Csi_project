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
        driver = None  # 오류 발생 시 브라우저를 닫기 위해 미리 선언
        try:
            # 1) JSON 데이터 로드
            data = json.loads(request.body)
            rq_numbers = data.get('rq_numbers', [])
            
            if not rq_numbers:
                return JsonResponse({'status': 'error', 'message': '선택된 RQ번호가 없습니다.'})

            # 2) 셀레늄 브라우저 설정
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
            chrome_options.add_experimental_option("detach", True)
            
            # [중요] 드라이버는 여기서 '딱 한 번'만 생성합니다. (기존 중복 코드 제거)
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            
            # 3) CSI 사이트 접속 및 로그인
            driver.get("https://gcloud.csi.go.kr/cmq/main.do") # 실제 접속 주소 추가
            time.sleep(1)
            
            driver.find_element(By.ID, "userId").send_keys("youngjun") 
            driver.find_element(By.ID, "pswd").send_keys("k*1800*92*")
            driver.find_element(By.CLASS_NAME, "login-btn").click()
            time.sleep(2)


            driver.get("https://gcloud.csi.go.kr/cmq/qtr/qltRqst/rqstRcvList.do") 
            time.sleep(2) # 게시판 로딩 대기

            # 4) 각 RQ번호별 순회 작업
            for rq_no in rq_numbers:
                # 검색창 입력
                search_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchVal")))
                search_input.clear()
                search_input.send_keys(rq_no)
                driver.find_element(By.XPATH, "//button[contains(@onclick, 'go_search')]").click()
                time.sleep(2)

                # 상세 링크 클릭
                driver.find_element(By.CLASS_NAME, "goSelectLink").click()
                time.sleep(3) # 상세 페이지 로딩 대기시간 상향

                try:
                # 1~4번 항목 (기존과 동일하지만 명칭 확인)
                    rcpt_no = driver.find_element(By.XPATH, "//th[contains(text(), '접수번호')]/following-sibling::td").text.strip()
                    status = driver.find_element(By.XPATH, "//th[contains(text(), '최종진행상태')]/following-sibling::td").text.strip()
                    agency = driver.find_element(By.XPATH, "//th[contains(text(), '의뢰기관')]/following-sibling::td").text.strip()
                    rcpt_date = driver.find_element(By.XPATH, "//th[contains(text(), '접수일시')]/following-sibling::td").text.strip() #

                    # 5. 봉인자 성명 추출
                    # '봉인자' 제목 칸의 부모(tr) 다음 줄(tr)에서 마지막 칸(td)인 '성명'을 가져옵니다.
                    # 5. 봉인자 성명 (필요 없는 글자 제거)
                    seal_user = driver.find_element(By.XPATH, "//th[text()='봉인자']/parent::tr/following-sibling::tr[1]/td[last()]").text.replace('성명', '').replace('(서명 완료)', '').strip()

                    # 6. 채취자 성명 (필요 없는 글자 제거)
                    pick_user = driver.find_element(By.XPATH, "//th[text()='채취자']/parent::tr/following-sibling::tr[1]/td[last()]").text.replace('성명', '').replace('(서명 완료)', '').strip()

                    # 7. 공사명 (하단 공사개요 테이블)
                    biz_nm = driver.find_element(By.XPATH, "//th[text()='공사명']/following-sibling::td").text.strip()

                        # --- [데이터 확인용 출력 코드] ---
                    print("\n" + "="*50)
                    print(f"RQ번호: {rq_no}")
                    print(f"접수번호: {rcpt_no}")
                    print(f"상태: {status}")
                    print(f"의뢰기관: {agency}")
                    print(f"공사명: {biz_nm}")
                    print(f"봉인자: {seal_user}")
                    print(f"채취자: {pick_user}")
                    print(f"접수일시: {rcpt_date}")                     
                    print("="*50 + "\n")
                            # ------------------------------

                    # [수정] DB 저장을 지우고 데이터를 딕셔너리에 담아 보냅니다.
                    result_data = {
                    'receipt_no': rcpt_no,
                    'status': status,
                    'agency': agency,
                    'rcpt_date': rcpt_date,
                    'seal_user': seal_user,
                    'pick_user': pick_user,
                    'biz_nm': biz_nm
                    }

                except Exception as e:
                    print(f"데이터 추출 중 오류 ({rq_no}): {e}")
                    continue

                driver.back() # 다시 목록으로 이동
                time.sleep(2)

            driver.quit()
            return JsonResponse({'status': 'success', 'message': f'{len(rq_numbers)}건 업데이트 완료!'})

        except Exception as e:
            if driver: driver.quit()
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'})

