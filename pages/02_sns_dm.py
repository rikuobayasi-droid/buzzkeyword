"""
pages/02_sns_dm.py — SNS DM トラッキング（月別管理）
URL: /sns_dm

変更内容:
- 時間帯別 → 月別管理に変更
- プラットフォーム × 月別 入力・グラフ化
- 絵文字を削除
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df, ALL_DM_PLATFORMS, DM_GOAL
from db import sb_select, sb_upsert

st.set_page_config(page_title="SNS DM | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">SNS DM トラッキング</div>', unsafe_allow_html=True)

tab_input, tab_graph = st.tabs(["月別入力", "グラフ・分析"])

# ── 月別入力 ──────────────────────────────────────────────────────────────────
with tab_input:
    st.markdown('<div class="section-head">プラットフォーム × 月別 DM数を入力</div>', unsafe_allow_html=True)

    col_ym, col_plat = st.columns(2)
    with col_ym:
        year_month = st.text_input("対象月 (YYYY-MM)", value=date.today().strftime("%Y-%m"),
                                    placeholder="例: 2026-01")
    with col_plat:
        platform = st.selectbox("プラットフォーム", ALL_DM_PLATFORMS)

    dm_count = st.number_input("DM数", min_value=0, value=0, step=10)
    st.caption("※ 同じ月・プラットフォームで再度保存すると上書きされます")

    if st.button("保存する"):
        if not year_month or len(year_month) != 7:
            st.markdown('<div class="err-box">対象月をYYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
        else:
            sb_upsert("dm_monthly", {
                "year_month": year_month,
                "platform":   platform,
                "count":      dm_count,
            })
            st.markdown('<div class="success-box">保存しました</div>', unsafe_allow_html=True)

    # 入力済みデータ一覧
    st.markdown('<div class="section-head">入力済みデータ</div>', unsafe_allow_html=True)
    rows   = sb_select("dm_monthly", order="-year_month")
    df_all = to_df(rows)
    if df_all.empty:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)
    else:
        filter_plat = st.selectbox("絞り込み（プラットフォーム）", ["すべて"] + ALL_DM_PLATFORMS, key="inp_filter")
        df_show = df_all if filter_plat == "すべて" else df_all[df_all["platform"]==filter_plat]
        st.dataframe(
            df_show[["year_month","platform","count"]].rename(columns={
                "year_month":"月", "platform":"プラットフォーム", "count":"DM数"
            }),
            use_container_width=True, height=300
        )

# ── グラフ・分析 ──────────────────────────────────────────────────────════════
with tab_graph:
    rows   = sb_select("dm_monthly", order="year_month")
    df_dm  = to_df(rows)

    if df_dm.empty:
        st.markdown('<div class="info-box">まだデータがありません。月別入力タブからデータを入力してください。</div>', unsafe_allow_html=True)
    else:
        # 月間目標進捗
        current_month = date.today().strftime("%Y-%m")
        df_cur = df_dm[df_dm["year_month"] == current_month]
        month_total = int(df_cur["count"].sum()) if not df_cur.empty else 0
        progress    = round(month_total / DM_GOAL * 100, 1)

        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{month_total:,}</div><div class="lbl">今月合計DM</div></div>
          <div class="metric-card"><div class="val">{progress}%</div><div class="lbl">月間目標進捗</div></div>
          <div class="metric-card"><div class="val">{DM_GOAL:,}</div><div class="lbl">月間目標</div></div>
          <div class="metric-card"><div class="val">{df_dm["year_month"].nunique()}</div><div class="lbl">記録月数</div></div>
        </div>
        <div style="margin:.5rem 0 .2rem;font-size:.78rem;color:#6b7280;">月間目標進捗 {month_total:,} / {DM_GOAL:,}件</div>
        <div class="progress-wrap"><div class="progress-fill" style="width:{min(progress,100)}%"></div></div>
        """, unsafe_allow_html=True)

        # ── 月別 × プラットフォーム別 ───────────────────────────────────────
        st.markdown('<div class="section-head">月別 x プラットフォーム別 DM数</div>', unsafe_allow_html=True)
        pivot = df_dm.pivot_table(index="year_month", columns="platform", values="count", aggfunc="sum").fillna(0)
        st.bar_chart(pivot)

        # ── プラットフォーム別合計（全期間） ──────────────────────────────────
        st.markdown('<div class="section-head">プラットフォーム別 合計DM数（全期間）</div>', unsafe_allow_html=True)
        plat_agg = df_dm.groupby("platform")["count"].sum().sort_values(ascending=False).reset_index()
        plat_agg.columns = ["プラットフォーム","DM数"]
        st.bar_chart(plat_agg.set_index("プラットフォーム"))

        # ── 月別合計推移 ──────────────────────────────────────────────────────
        st.markdown('<div class="section-head">月別 合計DM推移</div>', unsafe_allow_html=True)
        monthly_total = df_dm.groupby("year_month")["count"].sum().reset_index()
        monthly_total.columns = ["月","合計DM"]
        st.line_chart(monthly_total.set_index("月"))

        # ── 数値テーブル ──────────────────────────────────────────────────────
        st.markdown('<div class="section-head">月別 × プラットフォーム別 詳細テーブル</div>', unsafe_allow_html=True)
        st.dataframe(pivot.astype(int), use_container_width=True)
