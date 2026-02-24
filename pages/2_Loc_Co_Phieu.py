import streamlit as st
import pandas as pd
from vnstock import Vnstock
from datetime import datetime, timedelta
from GoogleNews import GoogleNews
import time

st.set_page_config(page_title="Wolf Screener (Full Market)", layout="wide", page_icon="📡")
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    .screener-header { background: #fff; padding: 20px; border-radius: 12px; border-bottom: 4px solid #27ae60; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .header-title { font-size: 36px; font-weight: 900; color: #2c3e50; margin: 0; }
</style>
""", unsafe_allow_html=True)

# 1. Danh sách Quét Nhanh (Top 50 Cổ phiếu Quốc dân)
WATCHLIST_QUICK = [
    'SSI', 'VND', 'HCM', 'VCI', 'SHS', 'MBS', 'FTS', 'BSI',
    'HPG', 'HSG', 'NKG', 'VGS',
    'DIG', 'DXG', 'CEO', 'NVL', 'PDR', 'KBC', 'VHM', 'VIC', 'VRE', 'NLG', 'KDH',
    'TCB', 'MBB', 'VPB', 'ACB', 'STB', 'CTG', 'BID', 'VCB', 'HDB', 'SHB',
    'FPT', 'MWG', 'PNJ', 'DGC', 'VNM', 'MSN', 'GEX', 'PC1', 'VGC', 'DGW', 'FRT', 'CSV', 'DPM', 'DCM', 'HAH', 'PVT', 'PVS', 'PVD'
]

# 2. Danh sách Quét Sâu (Top ~300 Cổ phiếu đại diện 99% dòng tiền thị trường)
WATCHLIST_FULL_RAW = "SSI VND VCI HCM SHS MBS FTS BSI CTS VIX AGR ORS VDS BVS HPG HSG NKG VGS SMC TLH DIG DXG CEO NVL PDR KBC VHM VIC VRE NLG KDH NAM SJS HDC DPG TCH HQC SCR KHG CRE IJC NBB CII HUT LCG VCG HHV FCN C4G G36 KSB VLB DHA BCC HT1 PLC TCB MBB VPB ACB STB CTG BID VCB VIB MSB TPB OCB HDB SSB SHB EIB LPB NAB BAB FPT CMG ELC ITD DGC CSV DPM DCM BFC LAS DDV VNM MSN SAB KDC SBT QNS BAF DBC PAN TAR LTG TRC DRI DPR PHR GVR PTB SAV GIL TNG TCM VGT STK MSH GEX PC1 HDG REE POW NT2 QTP HND TV2 GEG ASM BCG TTA VSH VHC ANV IDI FMC CMX ASM CTR VGI FOX VTP HAH VOS PVT GMD PHP SGP VSC PVD PVS BSR OIL PLX GAS PVC PVB PSH PET MWG PNJ DGW FRT PET BWE TDM HAG HNG DTL VPI VCF"
WATCHLIST_FULL = list(set(WATCHLIST_FULL_RAW.split())) # Loại bỏ mã trùng lặp

def get_latest_catalyst(ticker):
    try:
        googlenews = GoogleNews(lang='vi', region='VN', period='7d')
        googlenews.search(f"Cổ phiếu {ticker}")
        res = googlenews.result()
        if res: return res[0]['title']
        return "Chưa có tin hot trong 7 ngày"
    except: 
        return "Theo dòng tiền kỹ thuật"

@st.cache_data(ttl=1800)
def auto_scan_market(rsi_min, rsi_max, use_macd, use_ma50, scan_mode):
    results = []
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    # Chọn tệp quét
    target_list = WATCHLIST_QUICK if scan_mode == "Nhanh (Top 50)" else WATCHLIST_FULL
    
    progress_bar = st.progress(0)
    total = len(target_list)
    status_text = st.empty()
    
    for i, ticker in enumerate(target_list):
        progress_bar.progress((i + 1) / total)
        status_text.text(f"Đang quét mã {ticker} ({i+1}/{total})...")
        try:
            stock = Vnstock().stock(symbol=ticker, source='VCI')
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or df.empty or len(df) < 50: continue
            
            mapper = {'time': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}
            df.rename(columns=mapper, inplace=True)
            
            # Lọc sơ bộ thanh khoản (Bỏ qua rác < 50k cổ/phiên)
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()
            if df['Vol_MA20'].iloc[-1] < 50000: continue
            
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            
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
                else: tags.append("Trend MA50")
            
            if use_macd:
                if macd.iloc[-1] < signal.iloc[-1]: passed = False
                else: tags.append("MACD Khỏe")
            
            vol_ratio = last['Volume'] / last['Vol_MA20'] if last['Vol_MA20'] > 0 else 0
            if vol_ratio > 1.3: tags.append("Nổ Vol")
            elif not (use_ma50 or use_macd): passed = False
                
            if passed:
                change_pct = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                hot_story = get_latest_catalyst(ticker)
                
                # Tránh bị Google chặn IP do cào tin liên tục
                time.sleep(0.5) 
                
                results.append({
                    'Mã CK': ticker,
                    'Giá': round(last['Close'], 2),
                    '% Đổi': round(change_pct, 2),
                    'RSI': round(last['RSI'], 1),
                    'Vol Ratio': f"{round(vol_ratio, 1)}x",
                    'Mô hình': " + ".join(tags) if tags else "Đạt chuẩn",
                    'Tin tức (Auto)': hot_story
                })
        except: continue
        
    status_text.empty()
    progress_bar.progress(1.0)
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values('% Đổi', ascending=False).reset_index(drop=True)

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================
st.markdown("<div class='screener-header'><h1 class='header-title'>📡 RADAR QUÉT TOÀN THỊ TRƯỜNG</h1></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("1. Chế độ Quét")
    scan_mode = st.radio("Chọn vùng radar:", ["Nhanh (Top 50)", "Sâu (Toàn thị trường ~300 mã)"], index=0)
    st.caption("Khuyên dùng: Lúc đi làm chọn Nhanh (15s). Cuối ngày chọn Sâu (2-3 phút).")
    
    st.divider()
    st.header("2. Tiêu chí Kỹ thuật")
    rsi_range = st.slider("Vùng RSI:", 20, 80, (40, 70))
    use_ma50 = st.checkbox("Nằm trên MA50 (Trend dài hạn tăng)", value=True)
    use_macd = st.checkbox("MACD cắt lên Signal (Sóng mạnh)")
    
    btn_scan = st.button("🚀 KÍCH HOẠT RADAR", type="primary", use_container_width=True)

if btn_scan:
    with st.spinner(f"Đang quét dòng tiền {scan_mode}..."):
        df_res = auto_scan_market(rsi_range[0], rsi_range[1], use_macd, use_ma50, scan_mode)
        
        if df_res.empty: st.warning("Không có cổ phiếu nào lọt vào tầm ngắm Sói Già hôm nay!")
        else:
            st.success(f"🎯 Đã khóa mục tiêu {len(df_res)} siêu cổ phiếu!")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
