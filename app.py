import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import pandas as pd
import yfinance as yf
import pyupbit

# 1. 환경 설정 및 세팅
st.set_page_config(page_title="My Investment Terminal", layout="wide")
st.title("📊 주식/가상화폐 수익률 & AI 대응 전략")

# Gemini API 설정 (Streamlit Secrets에 저장 권장)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

try:
    # 1. 모델명 앞에 'models/'를 붙여 경로를 명시합니다.
    model = genai.GenerativeModel(model_name='models/gemini-2.5-flash')
    
    # 2. 모델이 정상적으로 생성되었는지 간단한 테스트를 진행합니다. (선택 사항)
    # response = model.generate_content("test") 
except Exception as e:
    st.error(f"모델 초기화 중 오류 발생: {e}")

# # 사용 가능한 모델 확인
# try:
#     models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
#     st.write(f"📋 사용 가능한 모델: {models}")
# except Exception as e:
#     st.error(f"❌ 모델 조회 실패: {str(e)}")
#     st.stop()
    
# 2. 구글 시트 연결 (mystock 파일)
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600) # 10분마다 데이터 갱신
def load_data():
    # 시트 이름이 'Sheet1'인 경우 예시
    return conn.read()

# 실시간 가격 가져오기 함수
def get_current_price(ticker, category):
    try:
        if category == '주식':
            # 주식 Ticker (예: 삼성전자는 005930.KS, 미국주식은 AAPL)
            stock = yf.Ticker(ticker)
            price = stock.history(period='1d')['Close'].iloc[-1]
            return price
        elif category == '가상화폐':
            # 가상화폐 Ticker (예: KRW-BTC)
            return pyupbit.get_current_price(ticker)
    except Exception as e:
        return 0
        
df = load_data()
df.columns = df.columns.str.strip()

# 디버깅용: 실제 불러온 컬럼명들을 화면에 출력해봅니다.
# st.write("불러온 컬럼 목록:", df.columns.tolist()) 

# 데이터프레임에 실시간 현재가 적용
with st.spinner('실시간 시세를 가져오는 중...'):
    # 시트의 'Ticker'와 '구분'(주식/가상화폐) 컬럼을 활용
    df['현재가'] = df.apply(lambda x: get_current_price(x['Ticker'], x['구분']), axis=1)
    
# 3. 수익률 계산 로직
# 데이터를 불러온 직후 형 변환 로직 추가
df['평단가'] = pd.to_numeric(df['평단가'], errors='coerce')
df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce')

# 결측치(NaN)가 생길 경우를 대비해 0으로 채워줍니다 (선택 사항)
df['평단가'] = df['평단가'].fillna(0)
df['보유수량'] = df['보유수량'].fillna(0)

# 숫자형 변환 및 계산
df['평단가'] = pd.to_numeric(df['평단가'], errors='coerce').fillna(0)
df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)

df['평가금액'] = df['현재가'] * df['보유수량']
df['매수금액'] = df['평단가'] * df['보유수량']
df['수익금'] = df['평가금액'] - df['매수금액']
df['수익률'] = (df['수익금'] / df['매수금액'] * 100).fillna(0)

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
