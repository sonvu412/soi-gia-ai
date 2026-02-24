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
    .wolf-box strong { color: #000; font-weight: 900; }
    .pos-badge { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; color: white; margin-bottom: 10px; font-size: 18px;}
    .pos-green { background-color: #27ae60; } .pos-red { background-color: #c0392b; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATA ENGINE BẤT TỬ (VNDIRECT PUBLIC API)
# =============================================================================
@st.cache_data(ttl=3600)
def load_data_auto(ticker):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Chuyển đổi ngày sang định dạng Unix Timestamp
        from_ts = int(start_date.timestamp())
        to_ts = int(end_date.timestamp())
        
        # Gọi thẳng vào API Biểu đồ của VNDirect
        url = f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={ticker}&resolution=D&from={from_ts}&to={to_ts}"
        
        # Ngụy trang thành trình duyệt Chrome để không bao giờ bị chặn
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('s') != 'ok': return None, "Không có dữ liệu hoặc mã không tồn tại."
        
        # Đóng gói dữ liệu siêu tốc
        df = pd.DataFrame({
            'Date': pd.to_datetime(data['t'], unit='s'),
            'Open': data['o'],
            'High': data['h'],
            'Low': data['l'],
            'Close': data['c'],
            'Volume': data['v']
        })
        return df, "OK"
    except Exception as e: return None, f"Lỗi API Dữ liệu: {str(e)}"

def detect_smart_money(open_p, high_p, low_p, close_p, vol, vol_ma20):
    if vol_ma20 == 0: return "Không xác định"
    vol_ratio = vol / vol_ma20
    body = close_p - open_p
    range_p = high_p - low_p
    
    if vol_ratio > 1.3:
        if close_p > open_p and (high_p - close_p) < (range_p * 0.3): return "🔥 CÁ MẬP VÀO HÀNG"
        elif close_p < open_p and (close_p - low_p) < (range_p * 0.3): return "⚠️ CÁ MẬP XẢ HÀNG"
        elif range_p > 0 and (abs(body) / range_p) < 0.3: return "⚡ RUNG LẮC MẠNH"
    elif vol_ratio < 0.6: return "💤 CẠN CUNG / TÍCH LŨY"
    return "Dòng tiền bình thường"

def identify_candle_pattern(open_p, high_p, low_p, close_p):
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0: return "Doji"
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    if body <= total_range * 0.1: return "Doji (Lưỡng lự)"
    if lower_shadow >= body * 2 and upper_shadow <= body * 0.5: return "Hammer (Rút chân)"
    if upper_shadow >= body * 2 and lower_shadow <= body * 0.5: return "Shooting Star (Bị bán ngược)"
    if body >= total_range * 0.8: return "Marubozu (Lực mạnh)"
    return "Nến thường"

def calculate_advanced_metrics(df):
    df['EMA_20'] = df['Close'].ewm(span=20).mean()
    df['MA_50'] = df['Close'].rolling(50).mean()
    df['Slope_MA20'] = df['EMA_20'].diff(3)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    exp12 = df['Close'].ewm(span=12).mean()
    exp26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['TR'] = np.maximum(df['High'] - df['Low'], np.abs(df['High'] - df['Close'].shift(1)))
    df['ATR'] = df['TR'].rolling(14).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    return df

def get_news(ticker):
    try:
        googlenews = GoogleNews(lang='vi', region='VN')
        googlenews.search(f"Cổ phiếu {ticker}")
        res = googlenews.result()[:5]
        return "\n".join([f"- {n['title']} ({n['date']})" for n in res])
    except: return "Không lấy được tin tức."

# =============================================================================
# AI PROMPT
# =============================================================================
def ask_wolf_ai(api_key, ticker, tech_data, news, pos_info, story):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    Bạn là "Sói già phố Wall", Trader 10 năm kinh nghiệm tại Việt Nam.
    KHÁCH HÀNG: {pos_info} (Mã: {ticker})
    
    1. DỮ LIỆU KỸ THUẬT & DÒNG TIỀN TẠO LẬP (AUTO-VSA):
    {tech_data}
    
    2. TIN TỨC & GAME:
    - Câu chuyện riêng: {story if story else "Không có thông tin đặc biệt."}
    - Tin thị trường: {news}
    
    YÊU CẦU BÁO CÁO (Markdown, In đậm lệnh và số liệu):
    ### 1. ĐỌC VỊ DÒNG TIỀN & XU HƯỚNG
    - Phân tích trạng thái Dòng tiền.
    - Trend kỹ thuật hiện tại là gì?
    - Câu chuyện vĩ mô có ủng hộ giá tăng không?

    ### 2. XỬ LÝ VỊ THẾ (Dành cho tôi)
    - Lệnh thực thi: **[NẮM GIỮ / CẮT LỖ / CHỐT LỜI / MUA THÊM]**. 
    - Kịch bản phòng thủ: Vùng giá nào vi phạm là phải BÁN?

    ### 3. CHIẾN LƯỢC TÁC CHIẾN (Cho nhịp mới)
    - Vùng Entry (Mua): **...**
    - Stoploss cứng: **...**
    - Target: **...**

    ### 4. LỜI KHUYÊN SÓI GIÀ
    - 1 câu chốt hạ.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"⚠️ Lỗi AI: {str(e)}"

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================
st.markdown("<div class='stock-header'><h1 class='header-ticker'>🐺 SÓI GIÀ PHÂN TÍCH VỊ THẾ</h1></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("1. Cấu hình AI")
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("✅ Đã kết nối Mật đạo (Secrets)!")
    else:
        api_key = st.text_input("Nhập API Key:", type="password")
    
    st.divider()
    st.header("2. Dữ liệu Đầu tư")
    ticker = st.text_input("Mã Cổ Phiếu:", "HPG").upper()
    buy_price = st.number_input("Giá Vốn Bạn Cầm:", 0.0, step=0.1)
    
    st.divider()
    st.header("3. Câu chuyện kỳ vọng")
    stock_story = st.text_area("Câu chuyện (Nếu có):")
    
    btn = st.button("🚀 PHÂN TÍCH CHUYÊN SÂU", type="primary", use_container_width=True)

if btn:
    if not api_key: st.error("Vui lòng nhập API Key.")
    else:
        with st.spinner(f"Đang bóc tách dữ liệu {ticker} (API Trực tiếp)..."):
            df, msg = load_data_auto(ticker)
            if df is None: st.error(msg)
            else:
                df = calculate_advanced_metrics(df)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                
                change_val = last['Close'] - prev['Close']
                change_pct = (change_val/prev['Close'])*100
                
                pos_info_str = ""
                pos_style_class = "pos-neutral"
                if buy_price > 0:
                    profit_pct = ((last['Close'] - buy_price) / buy_price) * 100
                    rule_msg = "(⚠️ Vi phạm Stoploss)" if profit_pct < -7 else "(🔥 Cân nhắc dời chặn lãi)" if profit_pct > 15 else ""
                    pos_info_str = f"ĐANG GIỮ. Vốn: {buy_price} | LÃI/LỖ: {profit_pct:+.2f}% {rule_msg}"
                    pos_style_class = "pos-loss" if profit_pct < 0 else "pos-green"
                else: pos_info_str = "CHƯA NẮM GIỮ (Tìm điểm mua)."
                
                ma20_slope = "Dốc lên" if last['Slope_MA20'] > 0 else "Dốc xuống"
                candle = identify_candle_pattern(last['Open'], last['High'], last['Low'], last['Close'])
                vol_stt = "NỔ VOL" if last['Vol_Ratio'] > 1.3 else "CẠN VOL" if last['Vol_Ratio'] < 0.6 else "Bình thường"
                
                smart_money_status = detect_smart_money(last['Open'], last['High'], last['Low'], last['Close'], last['Volume'], last['Vol_MA20'])
                
                tech_data = f"- Giá: {last['Close']} ({change_pct:+.2f}%)\n- Nến: {candle}\n- Trạng thái dòng tiền (VSA): {smart_money_status}\n- MA20 đang {ma20_slope}. Giá {'TRÊN' if last['Close']>last['EMA_20'] else 'DƯỚI'} MA20.\n- Vol: {vol_stt} (gấp {last['Vol_Ratio']:.1f} lần TB20)\n- RSI: {last['RSI']:.1f} | MACD: {last['MACD']:.3f} | ATR: {last['ATR']:.2f}"
                
                news = get_news(ticker)
                wolf_advice = ask_wolf_ai(api_key, ticker, tech_data, news, pos_info_str, stock_story)
                
                trade_value_billion = (last['Close'] * last['Volume']) / 1e9 * 1000 # Quy đổi ra tỷ VNĐ (do giá lưu ở đơn vị nghìn đồng)
                
                c1, c2, c3, c4 = st.columns(4)
                color = "text-green" if change_val >= 0 else "text-red"
                with c1: st.markdown(f"<div class='metric-card'><div class='metric-label'>GIÁ</div><div class='metric-value {color}'>{last['Close']:.2f}</div><div class='metric-sub'>{change_val:+.2f} ({change_pct:+.2f}%)</div></div>", unsafe_allow_html=True)
                with c2: st.markdown(f"<div class='metric-card'><div class='metric-label'>VOL</div><div class='metric-value'>{last['Volume']/1e6:.1f}M</div><div class='metric-sub'>{vol_stt}</div></div>", unsafe_allow_html=True)
                with c3: st.markdown(f"<div class='metric-card'><div class='metric-label'>RSI</div><div class='metric-value'>{last['RSI']:.1f}</div><div class='metric-sub'>Sức mạnh</div></div>", unsafe_allow_html=True)
                with c4: st.markdown(f"<div class='metric-card'><div class='metric-label'>GIAO DỊCH</div><div class='metric-value text-dark'>{trade_value_billion:.1f}</div><div class='metric-sub'>Tỷ VNĐ</div></div>", unsafe_allow_html=True)
                
                st.write("")
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
                if buy_price > 0: fig.add_hline(y=buy_price, line_dash="dash", line_color="blue", annotation_text=f"GIÁ VỐN")
                fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_50'], line=dict(color='orange'), name='MA50'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], line=dict(color='cyan'), name='EMA20'), row=1, col=1)
                colors = ['#27ae60' if c >= o else '#c0392b' for o, c in zip(df['Open'], df['Close'])]
                fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)
                fig.update_layout(height=550, xaxis_rangeslider_visible=False, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                if buy_price > 0: st.markdown(f"<div class='pos-badge {pos_style_class}'>{pos_info_str}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='wolf-box'><h2 style='color:#d4af37; text-align:center;'>📜 CHIẾN LƯỢC SÓI GIÀ</h2>{wolf_advice}</div>", unsafe_allow_html=True)

