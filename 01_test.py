import streamlit as st
import time
import random
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import hashlib
import hmac
import base64
import traceback

st.set_page_config(
    page_title="법무법인 동주 SEO",
    layout='wide'
)

# Naver API 관련 함수 및 설정
BASE_URL = 'https://api.naver.com'
API_KEY = '010000000094450d1dd02d9f94675fb0c3b77ee5d03ef32f1f0b956eae9cb19851dcb59d5b'
SECRET_KEY = 'AQAAAACURQ0d0C2flGdfsMO3fuXQj9OGFEyr4CjF7kcsHnhtOg=='
CUSTOMER_ID = '1943381'

class Signature:
    @staticmethod
    def generate(timestamp, method, uri, secret_key):
        message = "{}.{}.{}".format(timestamp, method, uri)
        hash = hmac.new(bytes(secret_key, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        
        hash.hexdigest()
        return base64.b64encode(hash.digest())

def process_smartblock_results(driver, dongju_id_list):
    extracted_ids = []
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    keywords = soup.select('.kmB6JnsyOzYVwnAzyoAL.fds-info-inner-text')

    for keyword in keywords:
        href = keyword.get('href', '').split('/')[3]
        
        # 카페 아이디 추출 ('?art' 앞부분만)
        if '?art' in href:
            extracted_id = href.split('?art')[0]
        # 블로그 아이디 추출
        else:
            extracted_id = href
        
        extracted_ids.append(extracted_id)

    # dongju_id_list와 비교
    matching_id = next((id for id in extracted_ids if id in dongju_id_list), None)
    
    return matching_id

def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(round(time.time() * 1000))
    signature = Signature.generate(timestamp, method, uri, secret_key)
    
    return {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Timestamp': timestamp,
        'X-API-KEY': api_key,
        'X-Customer': str(customer_id),
        'X-Signature': signature
    }

def get_search_volume(keyword):
    uri = '/keywordstool'
    method = 'GET'
    params = {'hintKeywords': keyword, 'showDetail': '1'}
    
    r = requests.get(BASE_URL + uri, params=params, 
                     headers=get_header(method, uri, API_KEY, SECRET_KEY, CUSTOMER_ID))
    
    data = r.json()['keywordList']
    result = next((item for item in data if item['relKeyword'] == keyword), None)
    
    if result:
        return result['monthlyPcQcCnt'], result['monthlyMobileQcCnt']
    else:
        return 0, 0

# 색상 적용 함수
def color_keyword(val, keyword_types, keyword, column_name):
    keyword_type = keyword_types.get(keyword, '')
    if column_name == '키워드':
        if keyword_type == 'knowledge_snippet':
            return 'background-color: #90EE90'  # 초록색
        elif keyword_type == 'smartblock':
            return 'background-color: #ADD8E6'  # 파란색
        elif keyword_type == 'both':
            return 'background-color: #FFB3BA'  # 빨간색
    elif column_name == '스니펫':
        if val:  # 값이 있을 때만 배경색 적용
            return 'background-color: #90EE90'  # 초록색
    elif column_name == '스블':
        if val:  # 값이 있을 때만 배경색 적용
            return 'background-color: #ADD8E6'  # 파란색
    return ''

# 엑셀 파일 생성 함수 수정
def create_excel(df, keyword_types, smartblock_keywords):
    output = BytesIO()
    workbook = Workbook()
    sheet = workbook.active

    # 헤더 추가
    for col, value in enumerate(df.columns.values, start=1):
        sheet.cell(row=1, column=col, value=value)

    # 데이터 추가 및 스타일 적용
    for row, (index, data) in enumerate(df.iterrows(), start=2):
        keyword = data['키워드']
        keyword_type = keyword_types.get(keyword, '')
        for col, value in enumerate(data.values, start=1):
            cell = sheet.cell(row=row, column=col, value=value)
            if col == 1:  # 키워드 열
                if keyword_type == 'knowledge_snippet':
                    cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
                elif keyword_type == 'smartblock':
                    cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")
                elif keyword_type == 'both':
                    cell.fill = PatternFill(start_color="FFB3BA", end_color="FFB3BA", fill_type="solid")
            elif col == 2:  # 스니펫 열
                if value:  # 값이 있는 경우에만 배경색 적용
                    cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            elif col == 3:  # 스블 열
                if value:  # 값이 있는 경우에만 배경색 적용
                    cell.fill = PatternFill(start_color="ADD8E6", end_color="ADD8E6", fill_type="solid")

    # 스마트블럭 키워드 및 연관 키워드 추가
    sheet = workbook.create_sheet(title="스마트블럭 키워드")
    sheet.append(["스마트블럭 키워드", "연관 키워드"])
    for keyword, related_keywords in smartblock_keywords.items():
        sheet.append([keyword, ", ".join(related_keywords)])

    # 열 너비 자동 조정
    for sheet in workbook.worksheets:
        for column in sheet.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column[0].column_letter].width = adjusted_width

    workbook.save(output)
    return output.getvalue()

# 키워드 전처리 함수 추가
def preprocess_keyword(keyword):
    return keyword.replace(" ", "")

# 사이드탭 생성
selected_tab = st.sidebar.radio("검색 엔진 선택", ["네이버", "구글"])

if selected_tab == "네이버":
    # 네이버 탭 내용
    st.title("🔍 네이버 순위 체크 및 검색량 조회")

    # 팀 선택
    selected_team = st.selectbox("팀 선택", ["청소년팀", "형사팀", "경제팀", "신규팀(음주&고소대리)"])

    # 키워드 입력
    keywords = st.text_area("키워드를 입력해 주세요 (한 줄에 하나씩)", height=200)

    # 동주 ID 리스트 (업데이트됨)
    dongju_id_list = [
        # 청소년팀
        "designersiun", "singsong0514", "phoenixjeong", "hamas3000", "roses777",
        "dongjulaw1", "dongjulaw2", "dongjusuwon1", "dongjulaw6", "dj_ehdwn1",
        # 형사팀
        "rudnfdldi00", "ehtlarhdwn", "widance", "yellowoi", "dongjulaw",
        "tale1396", "dongjulaw5", "dongjulaw100", "dongjulaw4", "dongjulaw02",
        # 경제팀
        "dksro018",
        # 신규팀(음주&고소대리)
        "cckjjt", "qusghtkehdwn", "dongjulaw7", "ujm159",
        # 기타 ID (기존에 있던 ID들)
        "dong-ju-law", "dongjulaw3", "ehdwnfh", "kkobugi39"
    ]

    # 순위 확인 버튼
    if st.button("순위 확인"):
        if not keywords:
            st.error("키워드를 입력해주세요.")
        else:
            # 키워드 리스트 생성 (원본 키워드 유지)
            keyword_list = [keyword.strip() for keyword in keywords.split('\n') if keyword.strip()]

            if not keyword_list:
                st.error("유효한 키워드를 입력해주세요.")
            else:
                # Chrome 옵션 설정
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")

                try:
                    # WebDriver 초기화
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    st.error(f"WebDriver 초기화 중 오류 발생: {str(e)}")
                    st.info("관리자에게 문의하세요.")
                    st.stop()

                # 결과를 저장할 리스트 초기화
                results_list = []
                keyword_types = {}  # 키워드 유형을 저장할 딕셔너리
                smartblock_keywords = {}  # 스마트블럭 키워드와 연관 키워드를 저장할 딕셔너리

                # 실시간 결과 표시를 위한 placeholder
                result_placeholder = st.empty()

                # 진행 상황 표시를 위한 progress bar
                progress_bar = st.progress(0)

                # 스타일 정의 부분 수정
                st.markdown("""
                <style>
                    .color-box {
                        padding: 10px;
                        border-radius: 4px;  # 모서리 둥글기 적용
                        margin-bottom: 10px;
                    }
                    .color-box p {
                        margin: 0;
                        font-size: 16px;  # 설명 텍스트 폰트 크기 증가
                        text-align: center;  # 텍스트 중앙 정렬
                    }
                    .section-header {
                        font-size: 20px;
                        font-weight: bold;
                        margin-bottom: 15px;
                    }
                    </style>
                """, unsafe_allow_html=True)

                # 각 키워드에 대해 검색 수행
                for i, keyword in enumerate(keyword_list):
                    try:
                        preprocessed_keyword = preprocess_keyword(keyword)
                        driver.get(f"https://search.naver.com/search.naver?ssc=tab.nx.all&where=nexearch&sm=tab_jum&query={preprocessed_keyword}")

                        keyword_type = ''
                        is_knowledge_snippet = False
                        is_smartblock = False
                        
                        # 지식스니펫 확인 (이전과 동일)
                        snippet_id = ''
                        try:
                            knowledge_snippet = driver.find_element(By.CSS_SELECTOR, '.source_box .txt.elss').get_attribute('href')
                            split_knowledge_snippet = knowledge_snippet.split('/')[3]
                            is_knowledge_snippet = True
                            if split_knowledge_snippet in dongju_id_list:
                                snippet_id = split_knowledge_snippet
                        except:
                            pass
                        
                        # 스마트블럭 확인 및 처리 (수정됨)
                        smartblock_id = ''
                        try:
                            smartblock_research = driver.find_element(By.CSS_SELECTOR, '.gSQMmoVs7gF12hlu3vMg.desktop_mode.api_subject_bx')
                            is_smartblock = True
                            smartblock_id = process_smartblock_results(driver, dongju_id_list)
                        except:
                            pass
                        
                        # 키워드 유형 결정
                        if is_knowledge_snippet and is_smartblock:
                            keyword_type = 'both'
                        elif is_knowledge_snippet:
                            keyword_type = 'knowledge_snippet'
                        elif is_smartblock:
                            keyword_type = 'smartblock'

                        # 키워드 유형 저장 (원본 키워드 사용)
                        keyword_types[keyword] = keyword_type

                        # 블로그 탭 클릭
                        WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, '.flick_bx:nth-of-type(3) > a'))
                        ).click()

                        # 무한스크롤 처리
                        last_height = driver.execute_script("return document.body.scrollHeight")
                        while True:
                            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(random.uniform(1, 1.5))
                            new_height = driver.execute_script("return document.body.scrollHeight")
                            if new_height == last_height:
                                break
                            last_height = new_height

                        # 블로그 순위 체크
                        blog_ids = driver.find_elements(By.CSS_SELECTOR, '.user_info a')
                        results = {j: '' for j in range(1, 16)}  # 모든 순위를 빈 문자열로 초기화
                        for rank, blog_id in enumerate(blog_ids, start=1):
                            if rank > 15:  # 15위까지만 체크
                                break
                            href = blog_id.get_attribute('href')
                            extracted_id = href.split('/')[-1]
                            if extracted_id in dongju_id_list:
                                results[rank] = extracted_id

                        # 검색량 조회 (전처리된 키워드 사용)
                        pc_volume, mobile_volume = get_search_volume(preprocessed_keyword)

                        # 결과 리스트에 추가 (원본 키워드 사용, 스마트블럭 ID 추가)
                        row = {'키워드': keyword, '스니펫': snippet_id, '스블': smartblock_id, 'M': mobile_volume, 'P': pc_volume}
                        row.update(results)
                        results_list.append(row)

                        # 실시간으로 결과 표시 부분 수정
                        with result_placeholder.container():
                            st.markdown('<p class="section-header">실시간 검색 결과</p>', unsafe_allow_html=True)
                            df = pd.DataFrame(results_list)
                            styled_df = df.style.apply(lambda row: [color_keyword(val, keyword_types, row['키워드'], col) for col, val in row.items()], axis=1)
                            st.dataframe(styled_df, use_container_width=True)  # 반응형 데이터프레임
                        
                            st.markdown("<br>", unsafe_allow_html=True)
                        
                            st.markdown('<p class="section-header">키워드 배경색 설명</p>', unsafe_allow_html=True)
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.markdown(
                                    """
                                    <div class="color-box" style="background-color: #FFB3BA;">
                                        <p>지식스니펫 + 스마트블럭</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            
                            with col2:
                                st.markdown(
                                    """
                                    <div class="color-box" style="background-color: #90EE90;">
                                        <p>지식스니펫</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            
                            with col3:
                                st.markdown(
                                    """
                                    <div class="color-box" style="background-color: #ADD8E6;">
                                        <p>스마트블럭</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        
                            if smartblock_keywords:
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.markdown('<p class="section-header">스마트블럭 키워드 및 연관 키워드</p>', unsafe_allow_html=True)
                                for kw, related_kws in smartblock_keywords.items():
                                    with st.expander(f"키워드: {kw}"):
                                        st.write(f"연관 키워드: {', '.join(related_kws)}")

                        # 진행 상황 업데이트
                        progress_bar.progress((i + 1) / len(keyword_list))

                        # 각 키워드 검색 후 잠시 대기
                        time.sleep(random.uniform(1, 3))

                    except Exception as e:
                        error_msg = traceback.format_exc()
                        st.error(f"키워드 '{keyword}' 처리 중 오류 발생: {str(e)}")
                        st.text(error_msg)
                        st.info("오류가 지속되면 관리자에게 문의하세요.")

                driver.quit()

                # 엑셀 다운로드 버튼
                excel_data = create_excel(df, keyword_types, smartblock_keywords)
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=excel_data,
                    file_name="search_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    st.info("'순위 확인' 버튼을 클릭해서 검색 결과를 실시간으로 확인하세요.")

elif selected_tab == "구글":
    st.title("🔍 구글 순위 체크 및 검색량 조회")

    # 팀 선택
    google_selected_team = st.selectbox("팀 선택", ["성범죄연구센터", "교통음주연구센터", "청소년연구센터", "사기횡령연구센터", "신규 형사(SEO)"])

    # 키워드 입력
    google_keywords = st.text_area("키워드를 입력해 주세요 (한 줄에 하나씩)", height=200)

    # 동주 URL 리스트와 이름 매핑 (업데이트됨)
    google_dongju_url_dict = {
        "https://dongju-lawfirm.com/": "통합 웹사이트",
        "https://oneclick-law-dongju.com": "원클릭소송센터",
        "https://student-tomolaw.com": "청소년 연구센터 내일law",
        "https://criminal-law-dongju.com": "형사전담센터",
        "https://divorce-law-dongju.com": "가사이혼전담센터",
        "https://civil-law-dongju.com": "민사기업전담센터",
        "https://trafficdrinking-law-dongju.com": "교통음주전담센터",
        "https://fraudembezzlement-dongju.com": "사기횡령전담센터",
        "https://criminal-lawfirm-dongju.com/": "신규 형사 홈페이지(SEO)",
    }

    def get_google_search_results(keyword, dongju_url_dict):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            st.error(f"WebDriver 초기화 중 오류 발생: {str(e)}")
            st.info("관리자에게 문의하세요.")
            return None, None

        results = {
            '키워드': keyword,
            '스니펫': '',
            'VOL': '',
            'SD': '',
        }

        for i in range(1, 16):
            results[f'{i}'] = ''

        try:
            driver.get(f"https://www.google.com/search?q={keyword}")
            time.sleep(2)

            # 스니펫 확인
            try:
                snippet = driver.find_element(By.CSS_SELECTOR, ".g.wF4fFd.JnwWd.g-blk .tjvcx.GvPZzd.cHaqb")
                snippet_text = snippet.text.split('›')[0].strip()
                for url, name in dongju_url_dict.items():
                    if url in snippet_text:
                        results['스니펫'] = name
                        break
            except:
                pass

            # 순위 확인
            links = driver.find_elements(By.CSS_SELECTOR, '.g a')
            for i, link in enumerate(links[:15], start=1):
                href = link.get_attribute('href')
                for url, name in dongju_url_dict.items():
                    if url in href:
                        results[f'{i}'] = name
                        break

            # 연관 검색어 추출
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            rel_keywords = soup.select(".oatEtb .dg6jd")
            related_keywords = [rel_keyword.text for rel_keyword in rel_keywords]

        except Exception as e:
            error_msg = traceback.format_exc()
            st.error(f"검색 중 오류 발생: {str(e)}")
            st.text(error_msg)
            st.info("오류가 지속되면 관리자에게 문의하세요.")
            related_keywords = []
        finally:
            driver.quit()

        return results, related_keywords

    # 스니펫 배경색 적용 함수
    def highlight_snippet(val):
        if val:
            return 'background-color: #90EE90'
        return ''

    # 순위 확인 버튼
    if st.button("순위 확인"):
        if not google_keywords:
            st.error("키워드를 입력해주세요.")
        else:
            keyword_list = [keyword.strip().replace(" ", "") for keyword in google_keywords.split('\n') if keyword.strip()]
            
            if not keyword_list:
                st.error("유효한 키워드를 입력해주세요.")
            else:
                results_list = []
                related_keywords_dict = {}

                # 실시간 결과 표시를 위한 placeholder
                result_placeholder = st.empty()
                progress_bar = st.progress(0)

                for i, keyword in enumerate(keyword_list):
                    results, related_keywords = get_google_search_results(keyword, google_dongju_url_dict)
                    if results is not None:
                        results_list.append(results)
                        related_keywords_dict[keyword] = related_keywords

                        # 실시간으로 결과 표시
                        with result_placeholder.container():
                            st.markdown('<p class="section-header">실시간 검색 결과</p>', unsafe_allow_html=True)
                            df = pd.DataFrame(results_list)
                            styled_df = df.style.applymap(highlight_snippet, subset=['스니펫'])
                            st.dataframe(styled_df, use_container_width=True)

                    # 진행 상황 업데이트
                    progress_bar.progress((i + 1) / len(keyword_list))

                    # 각 키워드 검색 후 잠시 대기
                    time.sleep(random.uniform(1, 3))

                # 스니펫 추가 설명 UI
                st.markdown('<p class="section-header">스니펫 추가 설명</p>', unsafe_allow_html=True)
                st.info("스니펫에 배경색이 칠해진 경우, 법무법인 동주의 홈페이지가 스니펫에 있다는 뜻입니다.")

                # 연관 검색어 UI
                st.markdown('<p class="section-header">연관 검색어</p>', unsafe_allow_html=True)
                for keyword, related_kws in related_keywords_dict.items():
                    with st.expander(f"키워드: {keyword}"):
                        st.write(f"연관 검색어: {', '.join(related_kws)}")

    st.info("'순위 확인' 버튼을 클릭해서 검색 결과를 실시간으로 확인하세요.")