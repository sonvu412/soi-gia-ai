import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# =============================================================================
# CẤU HÌNH GIAO DIỆN
# =============================================================================
st.set_page_config(page_title="Wolf Portfolio - Quản lý vị thế", layout="wide", page_icon="💼")
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    .portfolio-header { background: #fff; padding: 20px; border-radius: 12px; border-bottom: 4px solid #3498db; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .header-title { font-size: 32px; font-weight: 900; color: #2c3e50; margin: 0; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# HÀM LẤY GIÁ REAL-TIME
# =============================================================================
def get_current_price(ticker):
    if not ticker: return 0
    try:
        url = f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={ticker.upper()}&resolution=D&from={int((datetime.now()-timedelta(days=7)).timestamp())}&to={int(datetime.now().timestamp())}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5).json()
        return res['c'][-1] if res.get('s') == 'ok' else 0
    except: return 0

def get_action_recommendation(current_price, buy_price):
    if current_price == 0 or buy_price == 0: return "⌛ Đang theo dõi..."
    profit_pct = ((current_price - buy_price) / buy_price) * 100
    if profit_pct <= -7: return "❌ CẮT LỖ KHẨN CẤP"
    if profit_pct >= 15: return "💰 CHỐT LỜI TỪNG PHẦN"
    if -3 <= profit_pct <= 3: return "💎 TIẾP TỤC NẮM GIỮ"
    return "⚖️ Theo dõi sát"

# =============================================================================
# KHỞI TẠO DỮ LIỆU TRONG SESSION (BỘ NHỚ TẠM)
# =============================================================================
if 'portfolio_df' not in st.session_state:
    # Dữ liệu mặc định ban đầu
    st.session_state.portfolio_df = pd.DataFrame([
        {"Mã CP": "HPG", "Giá vốn": 28.5, "Mục tiêu": 35.0, "Cắt lỗ": 26.5},
        {"Mã CP": "SSI", "Giá vốn": 34.0, "Mục tiêu": 42.0, "Cắt lỗ": 31.0}
    ])

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================
st.markdown("<div class='portfolio-header'><h1 class='header-title'>💼 QUẢN LÝ DANH MỤC THỰC CHIẾN</h1></div>", unsafe_allow_html=True)

st.info("💡 **Hướng dẫn:** Bạn có thể nhấn trực tiếp vào ô để sửa, hoặc nhấn vào dòng cuối cùng để thêm mã mới. Để xóa, hãy chọn dòng đó và nhấn phím **Delete**.")

# Ô NHẬP LIỆU THÔNG MINH (Data Editor)
edited_df = st.data_editor(
    st.session_state.portfolio_df,
    num_rows="dynamic", # Cho phép thêm/bớt dòng
    use_container_width=True,
    column_config={
        "Mã CP": st.column_config.TextColumn("Mã CP", help="Nhập mã chứng khoán (VD: VCB, HPG)", max_chars=10),
        "Giá vốn": st.column_config.NumberColumn("Giá vốn", format="%.2f"),
        "Mục tiêu": st.column_config.NumberColumn("Kỳ vọng", format="%.2f"),
        "Cắt lỗ": st.column_config.NumberColumn("Cắt lỗ", format="%.2f"),
    }
)

# Nút cập nhật trạng thái
if st.button("🔄 CẬP NHẬT GIÁ VÀ KHUYẾN NGHỊ REAL-TIME"):
    st.session_state.portfolio_df = edited_df
    
    with st.spinner("Sói già đang check bảng điện..."):
        # Tính toán các cột tự động
        current_prices = []
        recommendations = []
        profits = []

        for ticker, buy_p in zip(edited_df["Mã CP"], edited_df["Giá vốn"]):
            curr = get_current_price(ticker)
            current_prices.append(curr)
            recommendations.append(get_action_recommendation(curr, buy_p))
            if buy_p > 0 and curr > 0:
                profits.append(f"{((curr - buy_p) / buy_p * 100):+.2f}%")
            else:
                profits.append("0%")

        # Hiển thị bảng kết quả cuối cùng
        final_df = edited_df.copy()
        final_df["Giá hiện tại"] = current_prices
        final_df["% Lãi/Lỗ"] = profits
        final_df["KHUYẾN NGHỊ"] = recommendations

        st.divider()
        st.subheader("📊 Bảng Theo Dõi Chuyên Sâu")
        st.dataframe(
            final_df,
            use_container_width=True,
            column_config={
                "KHUYẾN NGHỊ": st.column_config.TextColumn("KHUYẾN NGHỊ", help="Hành động dựa trên biến động real-time")
            }
        )
        
        # Thống kê nhanh
        c1, c2 = st.columns(2)
        total_items = len(final_df)
        with c1: st.metric("Tổng số mã", total_items)
        with c2: st.success("Dữ liệu đã được cập nhật mới nhất từ sàn!")
