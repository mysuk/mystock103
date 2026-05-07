import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import pandas as pd

# 1. 환경 설정 및 세팅
st.set_page_config(page_title="My Investment Terminal", layout="wide")
st.title("📊 주식/가상화폐 수익률 & AI 대응 전략")

# Gemini API 설정 (Streamlit Secrets에 저장 권장)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. 구글 시트 연결 (mystock 파일)
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600) # 10분마다 데이터 갱신
def load_data():
    # 시트 이름이 'Sheet1'인 경우 예시
    return conn.read(worksheet="Sheet1")

df = load_data()

# 3. 수익률 계산 로직
# 시트에 '종목명', '평단가', '보유수량', '현재가', '구분(주식/코인)' 컬럼이 있다고 가정
df['매수금액'] = df['평단가'] * df['보유수량']
df['평가금액'] = df['현재가'] * df['보유수량']
df['수익금'] = df['평가금액'] - df['매수금액']
df['수익률'] = (df['수익금'] / df['매수금액']) * 100

# 4. 화면 구성: 포트폴리오 요약
st.subheader("✅ 보유 자산 현황")
st.dataframe(df.style.format({'수익률': '{:.2f}%', '평가금액': '{:,.0f}원'}), width="stretch")

# 5. 제미나이 AI 분석 섹션
st.divider()
st.subheader("🤖 제미나이 AI 종목 진단")

selected_stock = st.selectbox("진단할 종목을 선택하세요", df['종목명'].unique())

if st.button(f"{selected_stock} 분석 시작"):
    # 선택된 종목의 데이터 추출
    stock_info = df[df['종목명'] == selected_stock].iloc[0]
    
    # AI에게 보낼 프롬프트 구성
    prompt = f"""
    너는 전문 투자 전략가야. 아래 정보를 바탕으로 {stock_info['구분']} 종목인 '{selected_stock}'에 대해 분석해줘.
    
    - 현재 나의 평단가: {stock_info['평단가']}
    - 현재 시장 가격: {stock_info['현재가']}
    - 현재 나의 수익률: {stock_info['수익률']:.2f}%
    
    요청 사항:
    1. 해당 종목의 최근 시장 트렌드를 요약해줘.
    2. 나의 수익률 상태에 따른 심리적 조언과 기술적 대응(익절/물타기/홀딩)을 제안해줘.
    3. 향후 3개월간의 전망을 긍정/부정 시나리오로 나누어 설명해줘.
    """
    
    with st.spinner('제미나이가 분석 중입니다...'):
        response = model.generate_content(prompt)
        st.markdown(f"### 🚩 {selected_stock} 분석 결과")
        st.write(response.text)
