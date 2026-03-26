"""
pages/02_sns_dm.py — SNS DM トラッキング
URL: /sns_dm
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from common import (inject_css, setup_sidebar, to_df, get_nationality,
                    ALL_DM_PLATFORMS, DM_COLS, PLATFORM_EMOJI, DM_GOAL)
from db import sb_select, sb_insert, sb_upsert

st.set_page_config(page_title="SNS DM | Tabibiyori", page_icon="💬", layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">💬 DM数トラッキング</div>', unsafe_allow_html=True)

tab_daily, tab_hourly, tab_graph = st.tabs(["日次入力", "⏰ 時間帯別入力", "グラフ・分析"])

# ── 日次入力 ──────────────────────────────────────────────────────────────────
with tab_daily:
    dm_date = st.date_input("日付", value=date.today())
    dm_vals = {}
    for pl_row in [("Instagram","Facebook","TikTok"),("YouTube","Threads","X"),("LINE","WhatsApp","Gmail")]:
        cols = st.columns(3)
        for col, pl in zip(cols, pl_row):
            with col:
                dm_vals[pl] = st.number_input(f"{PLATFORM_EMOJI.get(pl,'')} {pl}", min_value=0, value=0, step=10, key=f"dm_{pl}")
    total_input = sum(dm_vals.values())
    st.markdown(f'<div class="info-box">本日合計：<strong>{total_input:,}件</strong></div>', unsafe_allow_html=True)
    if st.button("💾 保存する", key="dm_save"):
        data = {"date": str(dm_date)}
        for pl in ALL_DM_PLATFORMS: data[DM_COLS[pl]] = dm_vals[pl]
        sb_upsert("dm_tracking", data)
        st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

# ── 時間帯別入力 ──────────────────────────────────────────────────────────────
with tab_hourly:
    st.markdown("プラットフォームと日付を選んで、0〜23時のDM数を入力してください。")
    h_date     = st.date_input("日付", value=date.today(), key="h_date")
    h_platform = st.selectbox("プラットフォーム", ALL_DM_PLATFORMS, key="h_plat")
    hourly_vals = {}
    for row_start in range(0, 24, 6):
        cols = st.columns(6)
        for i, col in enumerate(cols):
            hour = row_start + i
            with col:
                hourly_vals[hour] = st.number_input(f"{hour:02d}時", min_value=0, value=0, step=1, key=f"h_{hour}")
    total_h = sum(hourly_vals.values())
    peak_h  = max(hourly_vals, key=hourly_vals.get) if total_h > 0 else 0
    st.markdown(f'<div class="info-box">合計：<strong>{total_h}件</strong>　ピーク：<strong>{peak_h:02d}時</strong>（{hourly_vals.get(peak_h,0)}件）</div>', unsafe_allow_html=True)
    if st.button("💾 時間帯データを保存"):
        for hour, count in hourly_vals.items():
            if count > 0:
                sb_upsert("dm_hourly", {"date":str(h_date),"platform":h_platform,"hour":hour,"count":count})
        st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

# ── グラフ・分析 ──────────────────────────────────────────────────────────────
with tab_graph:
    rows_h = sb_select("dm_hourly", order="hour")
    df_h   = to_df(rows_h)

    if not df_h.empty:
        st.markdown('<div class="section-head">時間帯別DM分析</div>', unsafe_allow_html=True)
        h_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="h_filter")
        df_hf    = df_h if h_filter == "全体" else df_h[df_h["platform"]==h_filter]
        if not df_hf.empty:
            hourly_agg = df_hf.groupby("hour")["count"].sum().reset_index()
            hourly_agg.columns = ["時間（JST）","DM数"]
            st.bar_chart(hourly_agg.set_index("時間（JST）"))
            top3 = hourly_agg.nlargest(3,"DM数")
            st.markdown('<div class="section-head">ゴールデンタイム TOP3 と推定国籍</div>', unsafe_allow_html=True)
            for _, r in top3.iterrows():
                h = int(r["時間（JST）"]); nations = get_nationality(h)
                st.markdown(f"""<div class="metric-card" style="margin-bottom:.5rem;"><div style="font-size:1rem;font-weight:700;color:#1e3a5f;">{h:02d}:00〜{h+1:02d}:00　<span style="color:#6b7280;font-size:.85rem;">{int(r['DM数'])}件</span></div><div style="font-size:.82rem;color:#374151;margin-top:.3rem;">推定国籍：{"　".join(nations)}</div></div>""", unsafe_allow_html=True)
        st.markdown('<div class="section-head">プラットフォーム別 時間帯トレンド</div>', unsafe_allow_html=True)
        pivot = df_h.groupby(["hour","platform"])["count"].sum().reset_index()
        if not pivot.empty:
            pivot_wide = pivot.pivot(index="hour", columns="platform", values="count").fillna(0)
            st.line_chart(pivot_wide)

    rows = sb_select("dm_tracking", order="date")
    df_dm = to_df(rows)
    if not df_dm.empty:
        for p in ALL_DM_PLATFORMS:
            if DM_COLS[p] not in df_dm.columns: df_dm[DM_COLS[p]] = 0
        df_dm["合計"] = df_dm[[DM_COLS[p] for p in ALL_DM_PLATFORMS]].sum(axis=1)
        df_dm["date"] = pd.to_datetime(df_dm["date"])
        period = st.selectbox("集計期間",["週次","月次","年次","全期間"])
        now    = pd.Timestamp.now()
        cutoff = {"週次":7,"月次":30,"年次":365}.get(period)
        df_f   = df_dm[df_dm["date"] >= now-pd.Timedelta(days=cutoff)] if cutoff else df_dm.copy()
        if not df_f.empty:
            month_dm = int(df_dm[df_dm["date"] >= now.replace(day=1)]["合計"].sum())
            progress = round(month_dm/DM_GOAL*100,1)
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{int(df_f["合計"].sum()):,}</div><div class="lbl">期間合計DM</div></div>
              <div class="metric-card"><div class="val">{month_dm:,}</div><div class="lbl">今月合計DM</div></div>
              <div class="metric-card"><div class="val">{progress}%</div><div class="lbl">月間目標進捗</div></div>
              <div class="metric-card"><div class="val">{DM_GOAL:,}</div><div class="lbl">月間目標</div></div>
            </div>
            <div style="margin:.5rem 0 .2rem;font-size:.78rem;color:#6b7280;">月間目標進捗　{month_dm:,} / {DM_GOAL:,}件</div>
            <div class="progress-wrap"><div class="progress-fill" style="width:{min(progress,100)}%"></div></div>""", unsafe_allow_html=True)
            st.markdown('<div class="section-head">合計DM推移</div>', unsafe_allow_html=True)
            st.bar_chart(df_f.set_index("date")["合計"])
            st.markdown('<div class="section-head">プラットフォーム別シェア</div>', unsafe_allow_html=True)
            share = {p: int(df_f[DM_COLS[p]].sum()) for p in ALL_DM_PLATFORMS if DM_COLS[p] in df_f.columns}
            total_s = sum(share.values()) or 1
            for i in range(0, len(ALL_DM_PLATFORMS), 3):
                cols = st.columns(3)
                for j, pl in enumerate(ALL_DM_PLATFORMS[i:i+3]):
                    cnt = share.get(pl,0)
                    with cols[j]: st.metric(f"{PLATFORM_EMOJI.get(pl,'')} {pl}",f"{cnt:,}件",f"{round(cnt/total_s*100,1)}%")
    elif df_h.empty:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)
