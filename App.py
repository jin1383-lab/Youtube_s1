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
    st.caption("Streamlit v5.0 (Python)")
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
    elif duration_option == "20분 이상": filtered_data = [i for i in filtered_data if i["duration"] >= 1200]

    with col_sort:
        sort_by = st.radio("정렬 기준", ["조회수 순", "🔥 떡상 성과순", "최신순"], horizontal=True)
        
    if sort_by == "조회수 순":
        filtered_data = sorted(filtered_data, key=lambda x: x["viewCount"], reverse=True)
    elif "떡상" in sort_by:
        filtered_data = sorted(filtered_data, key=lambda x: x["viralScore"], reverse=True)
    elif sort_by == "최신순":
        filtered_data = sorted(filtered_data, key=lambda x: x["publishedAt"], reverse=True)

    with col_count:
        st.subheader(f"🔍 필터링 결과: {len(filtered_data)}개")

    # --- 대시보드 그리드 UI 출력 ---
    cols = st.columns(4)
    for idx, item in enumerate(filtered_data):
        col = cols[idx % 4]
        with col:
            with st.container(border=True):
                st.image(item["thumb"], use_container_width=True)
                
                # 순수 Streamlit 컴포넌트로 정보 깔끔하게 배치
                st.caption(f"⏱️ 영상 길이: {format_duration(item['duration'])}")
                st.markdown(f"**[{item['title']}](https://youtube.com/watch?v={item['id']})**")
                st.caption(f"👤 {item['channelTitle']}")
                
                # 떡상 배지를 순수 텍스트 이모지로 대체
                multiplier = item['viralScore'] / 100
                if item['viralScore'] >= 500:
                    st.error(f"🔥 떡상급 성과 (x{multiplier:.1f})")
                else:
                    st.info(f"📈 성과지수 (x{multiplier:.1f})")
                
                # 스탯 대시보드 구조화
                stat_col1, stat_col2 = st.columns(2)
                with stat_col1:
                    st.metric(label="조회수", value=format_num(item['viewCount']))
                with stat_col2:
                    st.metric(label="구독자", value=format_num(item['subCount']))
else:
    st.info("👈 왼쪽 사이드바에 정보를 입력하고 '🚀 분석 시작' 버튼을 눌러주세요.")
