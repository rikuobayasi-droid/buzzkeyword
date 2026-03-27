"""
pages/07_finance_sales.py — 売上・経営ダッシュボード
URL: /finance_sales

改修内容:
- 手動売上入力を廃止
- 顧客データ（purchases）から自動集計
- 日別・月別・年別・事業別売上表示
- 絵文字を削除
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df, BUSINESSES
from db import sb_select

st.set_page_config(page_title="売上 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">売上・経営ダッシュボード</div>', unsafe_allow_html=True)

# ── データ取得 ────────────────────────────────────────────────────────────────
rows_p   = sb_select("purchases", order="-purchase_date")
df_p     = to_df(rows_p)
rows_pr  = sb_select("products", order="name")
df_prods = to_df(rows_pr)
rows_e   = sb_select("expenses", order="-exp_date")
df_e     = to_df(rows_e)

if df_p.empty:
    st.markdown('<div class="info-box">購入データがありません。顧客管理ページから購入履歴を登録してください。</div>', unsafe_allow_html=True)
    st.stop()

# 商品情報を結合してカテゴリー（事業区分）を付与
for col in ["amount","participants"]:
    if col not in df_p.columns: df_p[col] = 0

if not df_prods.empty:
    df_p = df_p.merge(
        df_prods[["id","name","category"]].rename(columns={"id":"product_id","name":"product_name","category":"business"}),
        on="product_id", how="left"
    )
else:
    df_p["product_name"] = df_p.get("product_type","")
    df_p["business"]     = df_p.get("product_type","")

df_p["business"]       = df_p["business"].fillna("その他")
df_p["purchase_date"]  = pd.to_datetime(df_p["purchase_date"], errors="coerce")
df_p["amount"]         = pd.to_numeric(df_p["amount"], errors="coerce").fillna(0)
df_p                   = df_p.dropna(subset=["purchase_date"])
df_p["date_str"]       = df_p["purchase_date"].dt.strftime("%Y-%m-%d")
df_p["month_str"]      = df_p["purchase_date"].dt.strftime("%Y-%m")
df_p["year_str"]       = df_p["purchase_date"].dt.strftime("%Y")

total_sales   = int(df_p["amount"].sum())
total_expense = int(df_e["amount_out"].sum()) if not df_e.empty and "amount_out" in df_e.columns else 0
profit        = total_sales - total_expense
profit_rate   = round(profit/total_sales*100,1) if total_sales else 0
profit_color  = "#15803d" if profit >= 0 else "#dc2626"

# ── サマリー指標 ──────────────────────────────────────────────────────────────
st.markdown(f"""<div class="metric-row">
  <div class="metric-card"><div class="val">¥{total_sales:,}</div><div class="lbl">総売上</div></div>
  <div class="metric-card"><div class="val">¥{total_expense:,}</div><div class="lbl">総経費</div></div>
  <div class="metric-card"><div class="val" style="color:{profit_color};">¥{profit:,}</div><div class="lbl">利益</div></div>
  <div class="metric-card"><div class="val" style="color:{profit_color};">{profit_rate}%</div><div class="lbl">利益率</div></div>
  <div class="metric-card"><div class="val">{len(df_p)}</div><div class="lbl">購入件数</div></div>
</div>""", unsafe_allow_html=True)

tab_daily, tab_monthly, tab_yearly, tab_business = st.tabs([
    "日別売上", "月別売上", "年別売上", "事業別分析"
])

# ── 日別売上 ──────────────────────────────────────────────────────────────────
with tab_daily:
    st.markdown('<div class="section-head">日別 x 事業別 売上</div>', unsafe_allow_html=True)

    # 期間フィルター
    dc1, dc2 = st.columns(2)
    with dc1: d_from = st.date_input("開始日", value=date.today().replace(day=1))
    with dc2: d_to   = st.date_input("終了日", value=date.today())

    df_day = df_p[(df_p["purchase_date"] >= pd.Timestamp(d_from)) &
                  (df_p["purchase_date"] <= pd.Timestamp(d_to))]

    if df_day.empty:
        st.markdown('<div class="info-box">選択期間にデータがありません</div>', unsafe_allow_html=True)
    else:
        # 日別 × 事業別 ピボット
        daily_pivot = df_day.groupby(["date_str","business"])["amount"].sum().reset_index()
        daily_wide  = daily_pivot.pivot(index="date_str", columns="business", values="amount").fillna(0)
        daily_wide["合計"] = daily_wide.sum(axis=1)

        # テーブル表示（仕様: 03/27 ツアー 100000 Patreon 500 Guidebook 20000）
        for idx, row in daily_wide.iterrows():
            date_label = idx[5:]  # MM-DD
            parts      = [f"{biz}: ¥{int(row.get(biz,0)):,}" for biz in daily_wide.columns if biz != "合計" and row.get(biz,0) > 0]
            st.markdown(
                f"**{date_label}** &nbsp; "
                + " &nbsp; ".join(parts)
                + f" &nbsp; | &nbsp; 合計: ¥{int(row['合計']):,}"
            )

        st.markdown('<div class="section-head">日別売上グラフ</div>', unsafe_allow_html=True)
        st.bar_chart(daily_wide.drop(columns=["合計"]))

        st.markdown(f'<div class="info-box">期間合計: <strong>¥{int(df_day["amount"].sum()):,}</strong></div>', unsafe_allow_html=True)

# ── 月別売上 ──────────────────────────────────────────────────────────────────
with tab_monthly:
    st.markdown('<div class="section-head">月別 x 事業別 売上</div>', unsafe_allow_html=True)
    monthly_pivot = df_p.groupby(["month_str","business"])["amount"].sum().reset_index()
    monthly_wide  = monthly_pivot.pivot(index="month_str", columns="business", values="amount").fillna(0)
    monthly_wide["合計"] = monthly_wide.sum(axis=1)

    st.bar_chart(monthly_wide.drop(columns=["合計"]))
    st.dataframe(monthly_wide.astype(int).rename(columns={"合計":"合計（¥）"}), use_container_width=True)

# ── 年別売上 ──────────────────────────────────────────────────────────────────
with tab_yearly:
    st.markdown('<div class="section-head">年別 x 事業別 売上</div>', unsafe_allow_html=True)
    yearly_pivot = df_p.groupby(["year_str","business"])["amount"].sum().reset_index()
    yearly_wide  = yearly_pivot.pivot(index="year_str", columns="business", values="amount").fillna(0)
    yearly_wide["合計"] = yearly_wide.sum(axis=1)

    st.bar_chart(yearly_wide.drop(columns=["合計"]))
    st.dataframe(yearly_wide.astype(int).rename(columns={"合計":"合計（¥）"}), use_container_width=True)

# ── 事業別分析 ────────────────────────────────────────────────────────────────
with tab_business:
    st.markdown('<div class="section-head">事業別 売上 vs 経費</div>', unsafe_allow_html=True)
    all_biz = df_p["business"].unique().tolist()

    for biz in all_biz:
        biz_df     = df_p[df_p["business"] == biz]
        biz_sales  = int(biz_df["amount"].sum())
        biz_exp    = int(df_e[df_e.get("account","") == biz]["amount_out"].sum()) if not df_e.empty and "amount_out" in df_e.columns else 0
        biz_profit = biz_sales - biz_exp
        b_color    = "#15803d" if biz_profit >= 0 else "#dc2626"
        bar_pct    = min(int(biz_sales/total_sales*100),100) if total_sales else 0
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:.6rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
            <span style="font-weight:700;font-size:1rem;color:#1e3a5f;">{biz}</span>
            <span style="font-size:.75rem;color:#9ca3af;">売上シェア {bar_pct}%</span>
          </div>
          <div style="display:flex;gap:2rem;font-size:.9rem;flex-wrap:wrap;">
            <span>売上: <strong>¥{biz_sales:,}</strong></span>
            <span>経費: <strong>¥{biz_exp:,}</strong></span>
            <span style="color:{b_color};">利益: <strong>¥{biz_profit:,}</strong></span>
            <span>件数: <strong>{len(biz_df)}件</strong></span>
          </div>
          <div style="margin-top:.5rem;background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;">
            <div style="width:{bar_pct}%;height:100%;background:#1e3a5f;border-radius:4px;"></div>
          </div>
        </div>""", unsafe_allow_html=True)

    # 全体サマリー
    health = "黒字" if profit >= 0 else "赤字"
    st.markdown(f"""
    <div class="metric-card" style="margin-top:1rem;">
      <div style="font-size:1.1rem;font-weight:700;color:#1e3a5f;margin-bottom:.8rem;">経営サマリー [{health}]</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;font-size:.9rem;">
        <div>総売上: <strong>¥{total_sales:,}</strong></div>
        <div>総経費: <strong>¥{total_expense:,}</strong></div>
        <div style="color:{profit_color};">利益: <strong>¥{profit:,}</strong></div>
        <div style="color:{profit_color};">利益率: <strong>{profit_rate}%</strong></div>
        <div>事業数: <strong>{len(all_biz)}事業</strong></div>
        <div>購入件数: <strong>{len(df_p)}件</strong></div>
      </div>
    </div>""", unsafe_allow_html=True)
