"""
app.py — Tabibiyori Dashboard ホーム
URL: /
"""
import streamlit as st
from common import inject_css, setup_sidebar

st.set_page_config(page_title="Tabibiyori Dashboard", page_icon="🌸", layout="wide", initial_sidebar_state="expanded")
inject_css()
setup_sidebar()

st.markdown("""
<div style="text-align:center;padding:2rem 0 1.5rem;">
  <div style="font-size:2.5rem;">🌸</div>
  <h1 style="font-family:Inter,sans-serif;font-weight:700;font-size:2.2rem;color:#1e3a5f;letter-spacing:-1px;margin:.3rem 0;">Tabibiyori Dashboard</h1>
  <p style="color:#6b7280;font-size:.85rem;letter-spacing:3px;text-transform:uppercase;">Japan Content Operations Dashboard</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="font-family:Space Mono,monospace;font-size:.65rem;letter-spacing:3px;text-transform:uppercase;color:#9ca3af;border-bottom:1px solid #e5e7eb;padding-bottom:.4rem;margin:1.5rem 0 1rem;">クイックアクセス</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.05);">
      <div style="font-size:1.8rem;margin-bottom:.5rem;">📱</div>
      <div style="font-weight:700;font-size:1.05rem;color:#1e3a5f;margin-bottom:.4rem;">SNS</div>
      <div style="font-size:.82rem;color:#6b7280;line-height:1.6;">トレンドキーワード<br>DM集計・時間帯分析<br>集客・広告</div>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/01_sns_trend.py", label="→ SNS トレンドを開く")

with c2:
    st.markdown("""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.05);">
      <div style="font-size:1.8rem;margin-bottom:.5rem;">👤</div>
      <div style="font-weight:700;font-size:1.05rem;color:#1e3a5f;margin-bottom:.4rem;">顧客管理</div>
      <div style="font-size:.82rem;color:#6b7280;line-height:1.6;">顧客登録・情報管理<br>Tour予約ステータス<br>Patreon・Guidebook</div>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/05_crm_customers.py", label="→ 顧客管理を開く")

with c3:
    st.markdown("""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.05);">
      <div style="font-size:1.8rem;margin-bottom:.5rem;">💴</div>
      <div style="font-weight:700;font-size:1.05rem;color:#1e3a5f;margin-bottom:.4rem;">財務経理</div>
      <div style="font-size:.82rem;color:#6b7280;line-height:1.6;">売上・経費管理<br>事業別損益分析<br>BS・PL（準備中）</div>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/07_finance_sales.py", label="→ 財務経理を開く")
