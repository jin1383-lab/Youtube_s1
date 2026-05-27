import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import isodate
import pandas as pd

# --- 페이지 설정 ---
st.set_page_config(
    page_title="YouTube Insight Dashboard V5.1",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    st.caption("Streamlit v5.1 (Auto API 등록 버전)")
    st.markdown("---")
    
    # 1. API Key 자동 로드 및 수동 백업 처리
    default_api_key = ""
    if "YOUTUBE_API_KEY" in st.secrets:
        default_api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("✅ 고유 API KEY가 시스템에 자동 등록되었습니다.")
    else:
        st.warning("⚠️ 자동 등록된 API KEY가 없습니다. 아래에 수동 입력하거나 Secrets를 설정하세요.")

    api_key = st.text_input(
        "🔑 API KEY 설정", 
        value=default_api_key, 
        type="password", 
        help="Secrets에 키가 등록되어 있으면 자동으로 채워집니다."
    )
    
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
    duration_option = st.selectbox(
        "⏱️ 영상 길이 (정밀 필터)", 
        ["전체 길이", "10초 미만", "30초 미만", "1분(60초) 미만", "3분 미만", "10분 미만", "20분 이상"],
        index=0
    )

    st.markdown("---")
    # 7. 분석 시작 버튼 (맨 아래 영상길이 밑으로 이동 완료)
    search_triggered = st.button("🚀 분석 시작", use_container_width=True)

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
                if region_code: 
                    search_kwargs["regionCode"] = region_code
                if published_after: 
                    search_kwargs["publishedAfter"] = published_after
                
                search_res = youtube.search().list(**search_kwargs).execute()
                video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
                
                if not video_ids:
                    st.warning("검색 결과가 없습니다.")
                    st.session_state.raw_data = []
                else:
                    # Step 2: Videos API 호출
                    video_res = youtube.videos().list(
                        part="statistics,snippet,contentDetails",
                        id=",".join(video_ids)
                    ).execute()
                    
                    # Step 3: Channels API 호출
                    channel_ids = list(set([item["snippet"]["channelId"] for item in video_res.get("items", [])]))
                    channel_res = youtube.channels().list(
                        part="statistics",
                        id=",".join(channel_ids)
                    ).execute()
                    
                    channel_map = {c["id"]: int(c["statistics"].get("subscriberCount", 1)) for c in channel_res.get("items", [])}
                    
                    # 데이터 가공 및 세션 저장
                    parsed_list = []
                    for item in video_res.get("items", []):
                        views = int(item["statistics"].get("viewCount", 0))
                        subs = channel_map.get(item["snippet"]["channelId"], 1)
                        if subs == 0: subs = 1
                        
                        iso_duration = item["contentDetails"].get("duration", "PT0S")
                        duration_sec = int(isodate.parse_duration(iso_duration).total_seconds())
                        
                        parsed_list.append({
                            "id": item["id"],
                            "title": item["snippet"]["title"],
                            "channelTitle": item["snippet"]["channelTitle"],
                            "publishedAt": item["snippet"]["publishedAt"],
                            "thumb": item["snippet"]["thumbnails"]["high"]["url"],
                            "viewCount": views,
                            "subCount": subs,
                            "duration": duration_sec,
                            "viralScore": (views / subs) * 100
                        })
                    
                    st.session_state.raw_data = parsed_list
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# --- 상단 탑바 및 정렬 설정 ---
st.title("📺 YouTube Insight Dashboard")

col_count, col_sort = st.columns([2, 3])

# 데이터 필터링 가동 (세션 데이터 기준)
filtered_data = st.session_state.raw_data

if filtered_data:
    # 1. 뷰어단 필터링 적용
    filtered_data = [
        item for item in filtered_data
        if item["viewCount"] >= min_view and (max_view == 0 or item["viewCount"] <= max_view)
        and item["subCount"] >= min_sub and (max_sub == 0 or item["subCount"] <= max_sub)
    ]
    
    # 2. 초 단위 시간 필터링 적용
    if duration_option == "10초 미만": filtered_data = [i for i in filtered_data if i["duration"] < 10]
    elif duration_option == "30초 미만": filtered_data = [i for i in filtered_data if i["duration"] < 30]
    elif duration_option == "1분(60초) 미만": filtered_data = [i for i in filtered_data if i["duration"] < 60]
    elif duration_option == "3분 미만": filtered_data = [i for i in filtered_data if i["duration"] < 180]
    elif duration_option == "10분 미만": filtered_data = [i for i in filtered_data if i["duration"] < 600]
    elif duration_option == "20분 이상": filtered_data = [i for i in filtered_data if i["duration"] >=
