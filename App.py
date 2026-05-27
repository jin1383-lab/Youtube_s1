import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import isodate
import pandas as pd

# --- 페이지 설정 ---
st.set_page_config(
    page_title="YouTube Insight Dashboard V5.0",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 커스텀 스타일 디자인 (안전한 한 줄 압축 방식) ---
custom_css = (
    "<style>"
    ".viral-badge-high { background: linear-gradient(135deg, #d50000, #ff1744, #ff5252); color: white; padding: 4px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; text-align: center; } "
    ".viral-badge-normal { background-color: #333333; color: #aaaaaa; padding: 4px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; text-align: center; } "
    ".stats-container { background-color: #111111; padding: 8px; border-radius: 6px; font-size: 12px; margin-top: 5px; } "
    ".duration-tag { background-color: rgba(0,0,0,0.8); color: #fff; padding: 2px 6px; font-size: 11px; border-radius: 4px; font-weight: bold; }"
    "</style>"
)
st.markdown(custom_css, unsafe_content_html=True)

# --- 세션 상태 초기화 (데이터 보존용) ---
if "raw_data" not in st.session_state:
    st.session_state.raw_data = []

# --- 헬퍼 함수: 시간 변환 ---
def get_published_after(option):
    if option == "전체": return None
    now = datetime.utcnow()
    if option == "최근 3일": delta = timedelta(days=3)
    elif option == "최근 1주일": delta = timedelta(days=7)
    elif option == "최근 1달": delta = timedelta(days=30)
    elif option == "최근 3개월": delta = timedelta(days=90)
    elif option == "최근 6개월": delta = timedelta(days=180)
    elif option == "최근 1년": delta = timedelta(days=365)
    
    return (now - delta).isoformat() + "Z"

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
    st.caption("Streamlit v5.0 (Python) 변환 버전")
    st.markdown("---")
    
    # 1. API Key 입력
    api_key = st.text_input("🔑 API KEY", type="password", help="유튜브 v3 API 키를 입력하세요.")
    
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
    
    # 5. 분석 시작 버튼
    search_triggered = st.button("🚀 분석 시작", use_container_width=True)

    st.markdown("---")
    st.subheader("📊 실시간 정밀 필터")
    
    # 6. 조회수 & 구독자 범위 필터 (실시간 반응형)
    col_v1, col_v2 = st.columns(2)
    with col_v1: min_view = st.number_input("최소 조회수", min_value=0, value=0, step=1000)
    with col_v2: max_view = st.number_input("최대 조회수 (0은 제한없음)", min_value=0, value=0, step=10000)
    
    col_s1, col_s2 = st.columns(2)
    with col_s1: min_sub = st.number_input("최소 구독자", min_value=0, value=0, step=100)
    with col_s2: max_sub = st.number_input("최대 구독자 (0은 제한없음)", min_value=0, value=0, step=1000)
    
    # 7. 초 단위 정밀 시간 필터 (실시간 반응형)
    duration_option = st.selectbox(
        "⏱️ 영상 길이 (정밀 필터)", 
        ["전체 길이", "10초 미만", "30초 미만", "1분(60초) 미만", "3분 미만", "10분 미만", "20분 이상"],
        index=0
    )

# --- 데이터 수집 로직 ---
if search_triggered:
    if not api_key or not keyword:
        st.error("⚠️ API 키와 검색 키워드를 모두 입력해 주세요.")
    else:
        with st.spinner("데이터 수집 및 분석 중..."):
            try:
                youtube = build("youtube", "v3", developerKey=api_key)
                published_after = get_published_after(date_option)
                
                # Step 1: Search API 호출
                search_kwargs = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "maxResults": 50
                }
                if region_code: search_kwargs["regionCode"] = region_code
                if published_after: search_kwargs["publishedAfter"] = published_after
                
                search_res = youtube.search().list(**search_kwargs).execute()
                video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
                
                if not video_ids:
                    st.warning("
