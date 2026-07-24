import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
from GoogleNews import GoogleNews
import requests
from datetime import datetime, timedelta

# =============================================================================
# CẤU HÌNH GIAO DIỆN
# =============================================================================
st.set_page_config(page_title="Wolf of Wall Street - Phân Tích", layout="wide", page_icon="🐺")
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    .stock-header { background: #fff; padding: 20px; border-radius: 12px; border-bottom: 4px solid #d4af37; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .header-ticker { font-size: 42px; font-weight: 900; color: #2c3e50; margin: 0; line-height: 1; }
    .metric-card { background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 15px; text-align: center; height: 120px; display: flex; flex-direction: column; justify-content: center; }
    .metric-value { font-size: 26px; font-weight: 900; }
    .text-green { color: #27ae60; } .text-red { color: #c0392b; } .text-dark { color: #2c3e50; }
    .wolf-box { background: #fff; border: 2px solid #d4af37; padding: 40px; border-radius: 8px; margin-top: 20px; color: #2c3e50; font-family: 'Segoe UI', Arial, sans-serif; font-size: 16px; }
    .pos-badge { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; color: white; margin-bottom: 10px; font-size: 18px;}
    .pos-green { background-color: #27ae60; } .pos-red { background-color: #c0392b; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATA ENGINE BẤT TỬ (VNDIRECT API)
# =============================================================================
@st.cache_data(ttl=3600)
def load_data_auto(ticker):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        from_ts = int(start_date.timestamp())
        to_ts = int(end_date.timestamp())
        url = f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={ticker}&resolution=D&from={from_ts}&to={to_ts}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data.get('s') != 'ok': return None, "Mã không tồn tại."
        df = pd.DataFrame({'Date': pd.to_datetime(data['t'], unit='s'), 'Open': data['o'], 'High': data['h'], 'Low': data['l'], 'Close': data['c'], 'Volume': data['v']})
        return df, "OK"
    except Exception as e: return None, str(e)

# =============================================================================
# AUTO-STORY ENGINE (QUÉT TIN TỨC TỰ ĐỘNG)
# =============================================================================
def get_auto_stories(ticker):
    try:
        # Quét tin tức trong 7 ngày qua từ các nguồn uy tín qua Google News
        googlenews = GoogleNews(lang='vi', region='VN', period='7d')
        googlenews.search(f"Cổ phiếu {ticker}")
        results = googlenews.result()
        if not results:
            return "Không tìm thấy câu chuyện riêng đáng chú ý trong tuần qua."
        
        # Lấy 5 tiêu đề tin tức mới nhất để AI tổng hợp
        stories = [f"- {res['title']} ({res['date']})" for res in results[:5]]
        return "\n".join(stories)
    except:
        return "Hiện chưa quét được tin tức mới từ hệ thống."

def detect_smart_money(open_p, high_p, low_p, close_p, vol, vol_ma20):
    if vol_ma20 == 0: return "Không xác định"
    vol_ratio = vol / vol_ma20
    body = close_p - open_p
    range_p = high_p - low_p
    if vol_ratio > 1.3:
        if close_p > open_p and (high_p - close_p) < (range_p * 0.3): return "🔥 CÁ MẬP VÀO HÀNG"
        elif close_p < open_p and (close_p - low_p) < (range_p * 0.3): return "⚠️ CÁ MẬP XẢ HÀNG"
    return "Dòng tiền bình thường"

def calculate_advanced_metrics(df):
    df['EMA_20'] = df['Close'].ewm(span=20).mean()
    df['MA_50'] = df['Close'].rolling(50).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    return df

# =============================================================================
# AI PROMPT (GEMINI 3.6 FLASH)
# =============================================================================
def ask_wolf_ai(api_key, ticker, tech_data, news_stories, pos_info):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    Bạn là "Sói già phố Wall", chuyên gia VSA 10 năm kinh nghiệm tại Việt Nam.
    KHÁCH HÀNG: {pos_info} (Mã: {ticker})
    
    1. DỮ LIỆU KỸ THUẬT & DÒNG TIỀN:
    {tech_data}
    
    2. CÂU CHUYỆN RIÊNG TỰ ĐỘNG (Quét từ báo chí):
    {news_stories}
    
    YÊU CẦU PHÂN TÍCH (Markdown, Ngôn ngữ sắc bén):
    ### 1. ĐỌC VỊ TẠO LẬP & TIN TỨC
    - Kết nối các tiêu đề tin tức với biến động giá: Tin ra để xả hay tin ra để gom?
    - Xu hướng kỹ thuật hiện tại có bền vững không?

    ### 2. CHIẾN THUẬT VỊ THẾ
    - Lệnh thực thi: **[NẮM GIỮ / CẮT LỖ / CHỐT LỜI / MUA THÊM]**. 
    - Ngưỡng phòng thủ tuyệt đối: ...

    ### 3. KẾ HOẠCH TÁC CHIẾN MỚI
    - Entry: **...** | Stoploss: **...** | Target: **...**

    ### 4. LỜI KHUYÊN SÓI GIÀ
    - Chốt hạ 1 câu về tâm lý hành vi của mã này.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"⚠️ Lỗi AI: {str(e)}"

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================
st.markdown("<div class='stock-header'><h1 class='header-ticker'>🐺 SÓI GIÀ PHÂN TÍCH TỰ ĐỘNG</h1></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("1. Cấu hình AI")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ Đã kết nối API Key!")
    else: api_key = st.text_input("Nhập API Key:", type="password")
    
    st.divider()
    st.header("2. Dữ liệu Đầu tư")
    ticker = st.text_input("Mã Cổ Phiếu:", "HPG").upper()
    buy_price = st.number_input("Giá Vốn Bạn Cầm:", 0.0, step=0.1)
    
    btn = st.button("🚀 PHÂN TÍCH TỔNG LỰC", type="primary", use_container_width=True)

if btn:
    if not api_key: st.error("Vui lòng nhập API Key.")
    else:
        with st.spinner(f"Sói Già đang lùng sục tin tức và soi chart {ticker}..."):
            df, msg = load_data_auto(ticker)
            if df is None: st.error(msg)
            else:
                df = calculate_advanced_metrics(df)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                
                # Quét câu chuyện tự động
                news_stories = get_auto_stories(ticker)
                
                change_pct = ((last['Close'] - prev['Close'])/prev['Close'])*100
                smart_money = detect_smart_money(last['Open'], last['High'], last['Low'], last['Close'], last['Volume'], last['Vol_MA20'])
                
                tech_data = f"- Giá: {last['Close']} ({change_pct:+.2f}%)\n- Dòng tiền: {smart_money}\n- RSI: {last['RSI']:.1f}\n- Vol Ratio: {last['Vol_Ratio']:.1f}x"
                
                pos_info = f"Vốn: {buy_price}" if buy_price > 0 else "Chưa có vị thế"
                wolf_advice = ask_wolf_ai(api_key, ticker, tech_data, news_stories, pos_info)
                
                # Hiển thị 4 thẻ chỉ số nhanh
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("GIÁ", f"{last['Close']:.2f}", f"{change_pct:+.2f}%")
                with c2: st.metric("VOL RATIO", f"{last['Vol_Ratio']:.1f}x")
                with c3: st.metric("RSI", f"{last['RSI']:.1f}")
                with c4: st.metric("DÒNG TIỀN", "CÁ MẬP" if "CÁ MẬP" in smart_money else "THƯỜNG")
                
                # Biểu đồ
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
                fig.update_layout(height=450, xaxis_rangeslider_visible=False, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                # Báo cáo Sói Già
                st.markdown(f"<div class='wolf-box'><h2 style='color:#d4af37; text-align:center;'>📜 CHIẾN LƯỢC TỰ ĐỘNG</h2>{wolf_advice}</div>", unsafe_allow_html=True)
