"""
app.py — Tabibiyori Dashboard ホーム画面
修正1: テキストリンクを削除、カードUIでページ遷移
"""
import streamlit as st
from common import inject_css, setup_sidebar

st.set_page_config(
    page_title="Tabibiyori Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_css()
setup_sidebar()

st.markdown("""
<style>
.home-hero{text-align:center;padding:2rem 0 1.8rem;}
.home-hero h1{font-family:'Inter',sans-serif;font-weight:700;font-size:2.2rem;color:#1e3a5f;letter-spacing:-1px;margin:.3rem 0;}
.home-hero p{color:#6b7280;font-size:.82rem;letter-spacing:3px;text-transform:uppercase;}
.cat-label{font-family:'Space Mono',monospace;font-size:.62rem;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#9ca3af;border-bottom:1px solid #e5e7eb;padding-bottom:.4rem;margin:1.8rem 0 1rem;}
/* カードボタン上書き */
div[data-testid="stButton"] button {
    background:#ffffff !important;
    color:#1e3a5f !important;
    border:1px solid #e5e7eb !important;
    border-radius:10px !important;
    padding:1.2rem 1rem !important;
    width:100% !important;
    height:auto !important;
    font-family:'Inter',sans-serif !important;
    font-size:.88rem !important;
    font-weight:600 !important;
    text-align:left !important;
    box-shadow:0 1px 3px rgba(0,0,0,.05) !important;
    transition:border-color .15s, box-shadow .15s, transform .1s !important;
    white-space:pre-wrap !important;
    line-height:1.6 !important;
}
div[data-testid="stButton"] button:hover {
    border-color:#1e3a5f !important;
    box-shadow:0 4px 12px rgba(30,58,95,.12) !important;
    transform:translateY(-1px) !important;
    background:#f8faff !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="home-hero">
  <h1>Tabibiyori Dashboard</h1>
  <p>Japan Content Operations Dashboard</p>
</div>
""", unsafe_allow_html=True)

# ── SNS ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">SNS</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("トレンド\n\nキーワード収集・スコアリング\n履歴・再生数トラッキング\n\n→ /sns_trend", key="nav_trend"):
        st.switch_page("pages/01_sns_trend.py")

with c2:
    if st.button("DM\n\n日別・時間帯別DM集計\nゴールデンタイム分析\n月間目標進捗\n\n→ /sns_dm", key="nav_dm"):
        st.switch_page("pages/02_sns_dm.py")

with c3:
    if st.button("集客\n\n集客施策の管理・分析\n（準備中）\n\n→ /sns_acquisition", key="nav_acq"):
        st.switch_page("pages/03_sns_acquisition.py")

with c4:
    if st.button("広告\n\n広告運用・効果測定\n（準備中）\n\n→ /sns_ads", key="nav_ads"):
        st.switch_page("pages/04_sns_ads.py")

# ── 顧客管理 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">顧客管理</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("顧客関係\n\n顧客登録・情報管理\n購入履歴・Tour予約\nPatreon・Guidebook\n\n→ /crm_customers", key="nav_crm"):
        st.switch_page("pages/05_crm_customers.py")

with c2:
    if st.button("商品管理\n\n商品登録・カテゴリー管理\n商品一覧・詳細編集\n\n→ /crm_products", key="nav_prod"):
        st.switch_page("pages/06_crm_products.py")

# ── 財務経理 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">財務経理</div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    if st.button("売上\n\n事業別売上\n日別・月別・年別分析\n経営ダッシュボード\n\n→ /finance_sales", key="nav_sales"):
        st.switch_page("pages/07_finance_sales.py")

with c2:
    if st.button("経費\n\n経費入力・一覧\n領収書PDF管理\n勘定科目別グラフ\n\n→ /finance_expense", key="nav_exp"):
        st.switch_page("pages/08_finance_expense.py")

with c3:
    if st.button("費用対効果\n\nROI分析\nUTMリンク管理\n（準備中）\n\n→ /finance_roi", key="nav_roi"):
        st.switch_page("pages/09_finance_roi.py")

with c4:
    if st.button("BS\n\n貸借対照表\n（準備中）\n\n→ /finance_bs", key="nav_bs"):
        st.switch_page("pages/10_finance_bs.py")

with c5:
    if st.button("PL\n\n損益計算書\n（準備中）\n\n→ /finance_pl", key="nav_pl"):
        st.switch_page("pages/11_finance_pl.py")

# ── 競合分析 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">競合分析</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("競合分析\n\nInstagram競合アカウント管理\nフォロワー・閲覧数推移\n自動トレンド分析\n\n→ /competitor_analysis", key="nav_comp"):
        st.switch_page("pages/12_competitor_analysis.py")

with c2:
    if st.button("Patreon管理\n\nサブスク登録・解約管理\nMRR（月次売上）計算\nプランマスタ管理\n\n→ /patreon_management", key="nav_patreon"):
        st.switch_page("pages/13_patreon_management.py")

st.markdown("""
<div style="text-align:center;margin-top:2.5rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;">
  <span style="font-size:.72rem;color:#d1d5db;letter-spacing:1px;">Tabibiyori Dashboard — Japan Content Operations</span>
</div>
""", unsafe_allow_html=True)
