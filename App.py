import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import isodate
import pandas as pd

# --- 페이지 설정 ---
st.set_page_config(
    page_title="YouTube Insight Dashboard V5.3",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 세션 상태 초기화 (데이터 보존용) ---
if "raw_data" not in st.session_state:
    st.session_state.raw_data = []

# --- 헬퍼 함수: 시간 변환 (구글 API 포맷 오류 수정 완료) ---
def get_published_after(option):
    if option == "전체": return None
    now = datetime.now(timezone.utc)
    if option == "최근 3일": delta = timedelta(days=3)
    elif option == "최근 1주일": delta = timedelta(days=7)
    elif option == "최근 1달": delta = timedelta(days=30)
    elif option == "최근 3개월": delta = timedelta(days=90)
    elif option == "최근 6개월": delta = timedelta(days=180)
    elif option == "최근 1년": delta = timedelta(days=365)
    
    # 마이크로초를 제외하고 구글 API가 원하는 표준 규격(YYYY-MM-DDTHH:MM:SSZ)으로 포맷팅
    target_time = now - delta
    return target_time.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

def format_duration(seconds):
    m, s = divmod(seconds, 60)
    return f"{m}분 {s}초" if m > 0 else f"{s}초"

def format_num(n):
    if n >= 100000000: return f"{n / 100000000:.1f}억"
    if n >= 10000: return f"{n / 10000:.1f}만"
    return f"{n:,}"

# --- 사이드바 제어 패널 ---
with st.sidebar:
    st.title("🚀 Insight Dash")
    st.caption("Streamlit v5.3 (오류 수정 및 자동 연동 버전)")
    st.markdown("---")
    
    # API Key 체크 로직 자동화 (secrets.toml 또는 Streamlit Cloud Secrets 연동)
    api_key = ""
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("✅ YouTube API KEY가 안전하게 연결되었습니다.")
    else:
        st.error("⚠️ API KEY가 등록되지 않았습니다!\n로컬 환경의 `.streamlit/secrets.toml` 파일이나 Streamlit Cloud의 Secrets 설정을 확인해 주세요.")
    
    st.markdown("---")
    
    # 2. 국가 선택
    region_dict = {
        "🌐 글로벌 (전체)": "", "🇰🇷 한국 (Korea)": "KR", "🇺🇸 미국 (USA)": "US", 
        "🇯🇵 일본 (Japan)": "JP", "🇪🇸 스페인 (Spain)": "ES", "🇩🇪 독일 (Germany)": "DE", 
        "🇬🇧 영국 (UK)": "GB", "🇫🇷 프랑스 (France)": "FR", "🇮🇹 이탈리아 (Italy)": "IT"
    }
    region_label = st.selectbox("🌍 국가 선택 (Region)", list(region_dict.keys()), index=1)
    region_code = region_dict[region_label]
    
    # 3. 키워드 검색
    keyword = st.text_input("🔍 키워드 검색", placeholder="검색어 입력")
    
    # 4. 기간 설정
    date_option = st.selectbox("📅 기간 설정", ["최근 3일", "최근 1주일", "최근 1달", "최근 3개월", "최근 6개월", "최근 1년", "전체"], index=2)
    
    st.markdown("---")
    st.subheader("📊 실시간 정밀 필터")
    
    # 5. 조회수 & 구독자 범위 필터 (실시간 반응형)
    col_v1, col_v2 = st.columns(2)
    with col_v1: min_view = st.number_input("최소 조회수", min_value=0, value=0, step=1000)
    with col_v2: max_view = st.number_input("최대 조회수 (0은 제한없음)", min_value=0, value=0, step=10000)
    
    col_s1, col_s2 = st.columns(2)
    with col_s1: min_sub = st.number_input("최소 구독자", min_value=0, value=0, step=100)
    with col_s2: max_sub = st.number_input("최대 구독자 (0은 제한없음)", min_value=0, value=0, step=1000)
    
    # 6. 초 단위 정밀 시간 필터 (실시간 반응형)
