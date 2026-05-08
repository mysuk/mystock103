import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import pandas as pd
import yfinance as yf
import pyupbit
from datetime import datetime

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
# 지수가져오기        
def get_market_indices():
    indices = {"코스피": "^KS11", "코스닥": "^KQ11"}
    market_data = {}
    
    for name, ticker in indices.items():
        try:
            # 1일치 데이터를 1분 단위로 가져와서 가장 최신 값을 씁니다.
            index_data = yf.Ticker(ticker)
            hist = index_data.history(period="1d", interval="1m") 
            
            if hist.empty:
                # 오늘 장이 아직 안 열렸거나 데이터가 없으면 전일 종가를 가져옵니다.
                hist = index_data.history(period="2d")
            
            if not hist.empty:
                current_val = hist['Close'].iloc[-1]
                prev_val = hist['Close'].iloc[0] # 오늘 시초가 혹은 전일 종가
                change = current_val - prev_val
                change_percent = (change / prev_val) * 100
                
                status = "🟢 상승" if change > 0 else "🔴 하락"
                market_data[name] = f"{current_val:,.2f} ({status}, {change_percent:+.2f}%)"
            else:
                market_data[name] = "데이터 확인 불가"
        except Exception as e:
            # 에러 로그를 살짝 남겨두면 나중에 디버깅하기 좋습니다.
            market_data[name] = f"연결 지연 (다시 시도)"
    return market_data
    
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

# 프롬프트 구성 부분 수정
# 1. 셀렉트박스 목록 설정 (맨 앞에 '선택' 추가)
options = ['선택'] + list(df['종목명'].unique())
# 2. 셀렉트박스 생성
selected_stock = st.selectbox("진단할 종목을 선택하세요", options)
if selected_stock != '선택':
    if st.button(f"{selected_stock} 분석 시작"):
        # 0. 오늘 날짜 가져오기 (YYYY년 MM월 DD일 형식)
        today_date = datetime.now().strftime("%Y년 %m월 %d일")
        # 1. 선택된 종목의 데이터 추출
        stock_info = df[df['종목명'] == selected_stock].iloc[0]
        
        # 2. 분석을 위한 주요 지표 변수화
        buy_price = stock_info['평단가']
        curr_price = stock_info['현재가']
        profit_loss = stock_info['수익금']
        ratio = stock_info['수익률']
        ticker = stock_info['Ticker']
        category = stock_info['구분']

        # 2. 화폐 단위 결정 (미국 주식 판단)
        # 한국 주식(.KS, .KQ)이 아니고, 가상화폐도 아닌 경우 미국 주식으로 간주
        is_us_stock = (category == '주식') and not (ticker.endswith('.KS') or ticker.endswith('.KQ'))
        unit = "$" if is_us_stock else "원"
        
        # 지수 정보를 먼저 가져옵니다 (함수 호출)
        market_indices = get_market_indices()
        kospi_val = market_indices.get("코스피", "데이터 로드 실패")
        kosdaq_val = market_indices.get("코스닥", "데이터 로드 실패")
    
        # 3. 고도화된 프롬프트 작성
        prompt = f"""
        너는 20년 경력의 월스트리트 출신 투자 전략가야.
        오늘은 **{today_date}**이야.
        아래 제공된 나의 실제 포트폴리오 데이터와 네가 실시간으로 파악할 수 있는 시장 정보를 결합해서 
        '{selected_stock}({ticker})' 종목에 대한 심층 진단 보고서를 작성해줘.
    
        ### [1. 나의 투자 현황]
        - 종목 구분: {category}
        - 나의 평균 단가: {buy_price:,.0f}{unit}
        - 현재 시장 가격: {curr_price:,.0f}{unit}
        - 현재 평가 손익: {profit_loss:,.0f}{unit} ({ratio:.2f}%)
        - 나의 투자 원칙: 최대 손실 허용 범위 5%, 목표 수익 달성 시 익절 고민 중.
    
        ### [2. 분석 요청 데이터 (직접 검색 및 추론 포함)]
        아래 항목들을 네가 알고 있는 최신 시장 데이터(최근 1달 기준)를 바탕으로 채워서 분석해줘.
        미국주식의 경우 달러로 적용해줘.
    
        ###【시장 환경】
        - 현재 KOSPI 지수: {kospi_val}
        - 현재 KOSDAQ 지수: {kosdaq_val}
        - 시장 심리: 중립~약세 (최신 뉴스 바탕으로 보완해줘)
    
        #### 【기업/자산 정보】
        - {selected_stock}의 최근 재무 지표 (PER, ROE, 부채비율 등 추정치)
        - 최근 분기 실적 및 향후 성장성 전망
    
        #### 【기술적 분석】
        - 200일 이동평균선 대비 현재가 위치 및 RSI 지수 추정
        - 최근 52주 신고가/신저가 범위 내 현재 위치
    
        ### [3. 핵심 질문 및 가이드라인]
        1. **현재 나의 의문:** "지금 수익권(혹은 손실권)인데 익절해야 할까? 아니면 손절인가? 혹은 홀딩인가?" 이에 대해 명확한 논리로 답해줘.
        2. **대응 전략:** 현재 {ratio:.2f}% 수익 상태에서의 심리적 조언과 함께 '추가 매수/홀딩/분할 익절/전량 매도' 중 최선의 액션을 추천해줘.
        3. **시나리오 분석:** 향후 3개월 내 발생 가능한 긍정/부정 시나리오와 각각의 대응 가격대를 설정해줘.
        4. **기술적 가이드:** 구체적인 지지선, 저항선, 그리고 반드시 지켜야 할 '최종 손절 가격'을 제시해줘.
    
        ### [4. 최종 권고 사항]
        - 마지막에 결론으로 '한 줄 요약 액션 플랜'을 작성해줘.
    
        ※ 모든 분석은 한국어로, 격조 있고 전문적인 투자 보고서 형식으로 출력해줘.
        """
        st.write(prompt)
        # with st.spinner(f'제미나이가 {selected_stock}의 실시간 시장 데이터를 분석 중입니다...'):
        #     response = model.generate_content(prompt)
        #     st.markdown(f"### 🚩 {selected_stock} AI 종합 분석 보고서")
        #     st.write(response.text)
        #     # --- 개발자용 비밀 확인 섹션 ---
        #     st.divider()
        #     # 분석 결과 출력 후 마지막에 배치
        #     st.popover("Prompt Debug").code(prompt)
    
    # with st.spinner('제미나이가 분석 중입니다...'):
    #     response = model.generate_content(prompt)
    #     st.markdown(f"### 🚩 {selected_stock} 분석 결과")
    #     st.write(response.text)
