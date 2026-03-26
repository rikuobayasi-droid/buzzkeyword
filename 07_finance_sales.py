"""
pages/07_finance_sales.py — 売上・経営ダッシュボード
URL: /finance_sales
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df, BUSINESSES
from db import sb_select, sb_insert, sb_delete

st.set_page_config(page_title="売上 | Tabibiyori", page_icon="💴", layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">💴 売上・経営ダッシュボード</div>', unsafe_allow_html=True)

tab_input, tab_dash = st.tabs(["売上入力", "📊 経営ダッシュボード"])

with tab_input:
    st.markdown('<div class="section-head">売上を入力</div>', unsafe_allow_html=True)
    sc1, sc2 = st.columns(2)
    with sc1:
        s_date     = st.date_input("売上日", value=date.today())
        s_business = st.selectbox("事業区分", BUSINESSES + ["その他（今後追加）"])
        s_item     = st.text_input("内容", placeholder="例：Kimono Photo Experience")
    with sc2:
        s_amount  = st.number_input("売上金額（¥）", min_value=0, value=0, step=1000)
        s_expense = st.number_input("関連経費（¥）", min_value=0, value=0, step=1000)
        s_note    = st.text_input("備考")
    if st.button("💾 売上を保存"):
        if s_amount == 0:
            st.markdown('<div class="err-box">金額を入力してください</div>', unsafe_allow_html=True)
        else:
            sb_insert("sales",{"sale_date":str(s_date),"business":s_business,"item":s_item,"amount":s_amount,"expense":s_expense,"note":s_note})
            st.markdown('<div class="success-box">✅ 売上を保存しました</div>', unsafe_allow_html=True)

    rows_s = sb_select("sales", order="-sale_date")
    df_s_list = to_df(rows_s)
    if not df_s_list.empty:
        st.markdown('<div class="section-head">売上一覧</div>', unsafe_allow_html=True)
        for _, row in df_s_list.iterrows():
            c1, c2, c3 = st.columns([3,3,0.5])
            with c1: st.markdown(f"**{row.get('sale_date','')}　{row.get('business','')}**　{row.get('item','')}")
            with c2: st.markdown(f"売上：¥{int(row.get('amount',0)):,}　経費：¥{int(row.get('expense',0)):,}")
            with c3:
                if st.button("🗑", key=f"sdel_{row['id']}"): sb_delete("sales",{"id":row["id"]}); st.rerun()

with tab_dash:
    rows_s = sb_select("sales", order="-sale_date")
    df_s   = to_df(rows_s)
    rows_e = sb_select("expenses", order="-exp_date")
    df_e   = to_df(rows_e)

    if df_s.empty:
        st.markdown('<div class="info-box">売上データがありません。「売上入力」タブからデータを追加してください。</div>', unsafe_allow_html=True)
    else:
        for col in ["amount","expense"]:
            if col not in df_s.columns: df_s[col] = 0
        total_sales   = int(df_s["amount"].sum())
        total_exp_rel = int(df_s["expense"].sum())
        total_exp_all = int(df_e["amount_out"].sum()) if not df_e.empty and "amount_out" in df_e.columns else 0
        total_expense = total_exp_rel + total_exp_all
        profit        = total_sales - total_expense
        profit_rate   = round(profit/total_sales*100,1) if total_sales else 0
        profit_color  = "#15803d" if profit >= 0 else "#dc2626"

        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">¥{total_sales:,}</div><div class="lbl">総売上</div></div>
          <div class="metric-card"><div class="val">¥{total_expense:,}</div><div class="lbl">総経費</div></div>
          <div class="metric-card"><div class="val" style="color:{profit_color};">¥{profit:,}</div><div class="lbl">利益</div></div>
          <div class="metric-card"><div class="val" style="color:{profit_color};">{profit_rate}%</div><div class="lbl">利益率</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-head">事業別 売上 vs 経費</div>', unsafe_allow_html=True)
        all_businesses = df_s["business"].unique().tolist()
        for biz in all_businesses:
            biz_df     = df_s[df_s["business"]==biz]
            biz_sales  = int(biz_df["amount"].sum())
            biz_exp    = int(biz_df["expense"].sum())
            biz_profit = biz_sales - biz_exp
            biz_rate   = round(biz_profit/biz_sales*100,1) if biz_sales else 0
            b_color    = "#15803d" if biz_profit >= 0 else "#dc2626"
            bar_pct    = min(int(biz_sales/total_sales*100),100) if total_sales else 0
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:.6rem;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                <span style="font-weight:700;font-size:1rem;color:#1e3a5f;">{biz}</span>
                <span style="font-size:.75rem;color:#9ca3af;">売上シェア {bar_pct}%</span>
              </div>
              <div style="display:flex;gap:2rem;font-size:.9rem;flex-wrap:wrap;">
                <span>売上：<strong>¥{biz_sales:,}</strong></span>
                <span>経費：<strong>¥{biz_exp:,}</strong></span>
                <span style="color:{b_color};">利益：<strong>¥{biz_profit:,}</strong>（{biz_rate}%）</span>
              </div>
              <div style="margin-top:.5rem;background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;">
                <div style="width:{bar_pct}%;height:100%;background:#1e3a5f;border-radius:4px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-head">月別売上推移</div>', unsafe_allow_html=True)
        df_s["month"] = pd.to_datetime(df_s["sale_date"]).dt.strftime("%Y-%m")
        monthly = df_s.groupby(["month","business"])["amount"].sum().reset_index()
        if not monthly.empty:
            pivot = monthly.pivot(index="month", columns="business", values="amount").fillna(0)
            st.bar_chart(pivot)

        health = "🟢 黒字" if profit >= 0 else "🔴 赤字"
        st.markdown(f"""
        <div class="metric-card" style="margin-top:1rem;">
          <div style="font-size:1.1rem;font-weight:700;color:#1e3a5f;margin-bottom:.8rem;">経営サマリー　{health}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;font-size:.9rem;">
            <div>総売上：<strong>¥{total_sales:,}</strong></div>
            <div>総経費：<strong>¥{total_expense:,}</strong></div>
            <div style="color:{profit_color};">利益：<strong>¥{profit:,}</strong></div>
            <div style="color:{profit_color};">利益率：<strong>{profit_rate}%</strong></div>
            <div>事業数：<strong>{len(all_businesses)}事業</strong></div>
            <div>売上件数：<strong>{len(df_s)}件</strong></div>
          </div>
        </div>""", unsafe_allow_html=True)
