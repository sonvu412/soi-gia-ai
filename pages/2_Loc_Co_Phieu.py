import streamlit as st
import pandas as pd
from vnstock import Vnstock
from datetime import datetime, timedelta
from GoogleNews import GoogleNews

st.set_page_config(page_title="Wolf Screener (Auto News)", layout="wide", page_icon="📡")
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    .screener-header { background: #fff; padding: 20px; border-radius: 12px; border-bottom: 4px solid #27ae60; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .header-title { font-size: 36px; font-weight: 900; color: #2c3e50; margin: 0; }
</style>
""", unsafe_allow_html=True)

WATCHLIST = [
    'SSI', 'VND', 'HCM', 'VCI', 'SHS', 'HPG', 'HSG', 'NKG', 
    'DIG', 'DXG', 'CEO', 'NVL', 'PDR', 'KBC', 'VHM', 'VIC', 
    'TCB', 'MBB', 'VPB', 'ACB', 'STB', 'CTG', 'BID', 
    'FPT', 'MWG', 'PNJ', 'DGC', 'VNM', 'MSN', 'GEX', 'PC1', 'VGC'
]

def get_latest_catalyst(ticker):
    try:
        googlenews = GoogleNews(lang='vi', region='VN', period='7d')
        googlenews.search(f"Cổ phiếu {ticker}")
        res = googlenews.result()
        if res: return res[0]['title']
        return "Chưa có tin mới"
    except: return "Theo dòng tiền"

@st.cache_data(ttl=1800)
def auto_scan_market(rsi_min, rsi_max, use_macd, use_ma50):
    results = []
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    progress_bar = st.progress(0)
    total = len(WATCHLIST)
    
    for i, ticker in enumerate(WATCHLIST):
        progress_bar.progress((i + 1) / total)
        try:
            # Gọi API vnstock bản mới
            stock = Vnstock().stock(symbol=ticker, source='VCI')
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or df.empty or len(df) < 50: continue
            
            mapper = {'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}
            df.rename(columns=mapper, inplace=True)
            
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            exp12 = df['Close'].ewm(span=12).mean()
            exp26 = df['Close'].ewm(span=26).mean()
            macd = exp12 - exp26
            signal = macd.ewm(span=9).mean()
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            if not (rsi_min <= last['RSI'] <= rsi_max): continue
            
            passed = True
            tags = []
            
            if use_ma50:
                if last['Close'] < last['MA50']: passed = False
                else: tags.append("Trend Tăng")
            
            if use_macd:
                if macd.iloc[-1] < signal.iloc[-1]: passed = False
                else: tags.append("MACD Cắt lên")
            
            vol_ratio = last['Volume'] / last['Vol_MA20'] if last['Vol_MA20'] > 0 else 0
            if vol_ratio > 1.3: tags.append("Nổ Vol")
            elif not (use_ma50 or use_macd): passed = False
                
            if passed:
                change_pct = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                hot_story = get_latest_catalyst(ticker)
                results.append({
                    'Mã CK': ticker,
                    'Giá': round(last['Close'], 2),
                    '% Đổi': round(change_pct, 2),
                    'RSI': round(last['RSI'], 1),
                    'Vol Ratio': f"{round(vol_ratio, 1)}x",
                    'Điểm Kỹ Thuật': " + ".join(tags) if tags else "Chuẩn Form",
                    'Tin tức nóng (7 ngày qua)': hot_story
                })
        except: continue
        
    progress_bar.progress(1.0)
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values('% Đổi', ascending=False).reset_index(drop=True)

st.markdown("<div class='screener-header'><h1 class='header-title'>📡 RADAR TÌM SIÊU CỔ PHIẾU</h1></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("1. Tiêu chí Dòng tiền")
    rsi_range = st.slider("Vùng RSI:", 20, 80, (40, 70))
    st.divider()
    st.header("2. Tiêu chí Kỹ thuật")
    use_ma50 = st.checkbox("Nằm trên MA50 (Trend dài hạn khỏe)", value=True)
    use_macd = st.checkbox("MACD cắt lên Signal (Sẵn sàng chạy)")
    btn_scan = st.button("🚀 KÍCH HOẠT RADAR", type="primary", use_container_width=True)

if btn_scan:
    with st.spinner("Đang soi Chart và Quét báo chí tìm Game..."):
        df_res = auto_scan_market(rsi_range[0], rsi_range[1], use_macd, use_ma50)
        if df_res.empty: st.warning("Thị trường hiện tại không có điểm mua đẹp. Cash is King!")
        else:
            st.success(f"🎯 Đã khóa mục tiêu {len(df_res)} mã cổ phiếu tiềm năng!")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
