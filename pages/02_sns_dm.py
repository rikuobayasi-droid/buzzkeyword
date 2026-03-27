"""
pages/02_sns_dm.py — SNS DM トラッキング
URL: /sns_dm

修正2: 時間帯別×月別×プラットフォーム別 DM
修正3: 日別×プラットフォーム別 DM
分析: 国籍推定・ヒートマップ・日別推移
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

# ── 国籍推定ロジック（JST基準）────────────────────────────────────────────────
# 各時間帯に活発なユーザーの居住地域を逆算
# 例: JST 19-22時 → UTC 10-13時 → 西ヨーロッパの夕方 / 東アジアの夜
TIMEZONE_MAP = {
    range(0,  4):  ["アメリカ東海岸", "ブラジル", "カナダ"],
    range(4,  7):  ["アメリカ西海岸", "メキシコ", "カナダ西部"],
    range(7,  10): ["イギリス", "ドイツ", "フランス", "スペイン"],
    range(10, 13): ["ドイツ", "ロシア西部", "サウジアラビア", "インド"],
    range(13, 16): ["インド", "タイ", "ベトナム", "シンガポール"],
    range(16, 19): ["日本", "韓国", "中国", "台湾", "オーストラリア"],
    range(19, 22): ["日本（夜）", "韓国（夜）", "オーストラリア"],
    range(22, 24): ["アメリカ東海岸（朝）", "ブラジル（朝）"],
}

def get_nationality(hour: int) -> list[str]:
    for r, nations in TIMEZONE_MAP.items():
        if hour in r:
            return nations
    return []

tab_monthly, tab_daily, tab_analysis = st.tabs([
    "時間帯×月別入力",
    "日別入力",
    "分析・可視化"
])

# ════════════════════════════════════════════════════════
# 修正2: 時間帯 × 月別 × プラットフォーム別 入力
# ════════════════════════════════════════════════════════
with tab_monthly:
    st.markdown('<div class="section-head">プラットフォーム × 月 × 時間帯 別 DM数を入力</div>', unsafe_allow_html=True)

    mc1, mc2 = st.columns(2)
    with mc1:
        m_year_month = st.text_input(
            "対象月 (YYYY-MM)",
            value=date.today().strftime("%Y-%m"),
            placeholder="例: 2026-03"
        )
    with mc2:
        m_platform = st.selectbox("プラットフォーム", ALL_DM_PLATFORMS, key="m_plat")

    st.markdown(f"**{m_year_month} / {m_platform}** の時間帯別DM数を入力してください（0〜23時）")

    # 既存データを取得してデフォルト値に反映
    existing_rows = sb_select("dm_hourly_monthly")
    df_exist = to_df(existing_rows)
    def get_existing(ym, pl, hr):
        if df_exist.empty: return 0
        match = df_exist[(df_exist["year_month"]==ym) & (df_exist["platform"]==pl) & (df_exist["hour"]==hr)]
        return int(match["count"].values[0]) if not match.empty else 0

    # 6列 × 4行で0〜23時を表示
    hourly_vals = {}
    for row_start in range(0, 24, 6):
        cols = st.columns(6)
        for i, col in enumerate(cols):
            hour = row_start + i
            with col:
                default_val = get_existing(m_year_month, m_platform, hour)
                hourly_vals[hour] = st.number_input(
                    f"{hour:02d}時",
                    min_value=0,
                    value=default_val,
                    step=1,
                    key=f"hm_{hour}"
                )

    total_h  = sum(hourly_vals.values())
    peak_h   = max(hourly_vals, key=hourly_vals.get) if total_h > 0 else 0
    peak_cnt = hourly_vals.get(peak_h, 0)

    st.markdown(
        f'<div class="info-box">'
        f'合計: <strong>{total_h}件</strong> &nbsp; '
        f'ピーク時間帯: <strong>{peak_h:02d}時</strong>（{peak_cnt}件）'
        f'</div>',
        unsafe_allow_html=True
    )

    if st.button("時間帯データを保存", key="m_save"):
        if not m_year_month or len(m_year_month) != 7:
            st.markdown('<div class="err-box">対象月をYYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
        else:
            saved = 0
            for hour, count in hourly_vals.items():
                res = sb_upsert("dm_hourly_monthly", {
                    "year_month": m_year_month,
                    "platform":   m_platform,
                    "hour":       hour,
                    "count":      count,
                })
                if res: saved += 1
            st.markdown(f'<div class="success-box">保存しました（{saved}件）</div>', unsafe_allow_html=True)

    # 入力済みサマリー
    st.markdown('<div class="section-head">入力済みデータ（月別合計）</div>', unsafe_allow_html=True)
    if not df_exist.empty:
        summary = df_exist.groupby(["year_month","platform"])["count"].sum().reset_index()
        pivot   = summary.pivot(index="year_month", columns="platform", values="count").fillna(0).astype(int)
        st.dataframe(pivot, use_container_width=True)
    else:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 修正3: 日別 × プラットフォーム別 入力
# ════════════════════════════════════════════════════════
with tab_daily:
    st.markdown('<div class="section-head">日別 × プラットフォーム別 DM数を入力</div>', unsafe_allow_html=True)

    d_date = st.date_input("日付", value=date.today(), key="d_date")

    st.markdown(f"**{d_date}** のプラットフォーム別DM数を入力してください")

    # 既存データを取得
    existing_daily = sb_select("dm_daily")
    df_daily_exist = to_df(existing_daily)
    def get_daily_existing(dt, pl):
        if df_daily_exist.empty: return 0
        match = df_daily_exist[(df_daily_exist["date"]==str(dt)) & (df_daily_exist["platform"]==pl)]
        return int(match["count"].values[0]) if not match.empty else 0

    daily_vals = {}
    for pl_row in [
        ("Instagram", "Facebook", "TikTok"),
        ("YouTube",   "Threads",  "X"),
        ("LINE",      "WhatsApp", "Gmail"),
    ]:
        cols = st.columns(3)
        for col, pl in zip(cols, pl_row):
            with col:
                default_val = get_daily_existing(d_date, pl)
                daily_vals[pl] = st.number_input(
                    f"{pl}",
                    min_value=0,
                    value=default_val,
                    step=1,
                    key=f"daily_{pl}"
                )

    daily_total = sum(daily_vals.values())
    st.markdown(
        f'<div class="info-box">本日合計: <strong>{daily_total:,}件</strong></div>',
        unsafe_allow_html=True
    )

    if st.button("日別データを保存", key="d_save"):
        saved = 0
        for pl, count in daily_vals.items():
            res = sb_upsert("dm_daily", {
                "date":     str(d_date),
                "platform": pl,
                "count":    count,
            })
            if res: saved += 1
        st.markdown(f'<div class="success-box">保存しました（{saved}件）</div>', unsafe_allow_html=True)

    # 直近の日別データを表示
    st.markdown('<div class="section-head">直近の日別データ</div>', unsafe_allow_html=True)
    if not df_daily_exist.empty:
        daily_pivot = df_daily_exist.groupby(["date","platform"])["count"].sum().reset_index()
        daily_wide  = daily_pivot.pivot(index="date", columns="platform", values="count").fillna(0).astype(int)
        daily_wide["合計"] = daily_wide.sum(axis=1)
        st.dataframe(daily_wide.sort_index(ascending=False).head(30), use_container_width=True)
    else:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 分析・可視化
# ════════════════════════════════════════════════════════
with tab_analysis:
    # データ読み込み
    rows_h  = sb_select("dm_hourly_monthly", order="hour")
    df_h    = to_df(rows_h)
    rows_d  = sb_select("dm_daily", order="date")
    df_d    = to_df(rows_d)
    rows_m  = sb_select("dm_monthly", order="year_month")
    df_m    = to_df(rows_m)

    has_data = not df_h.empty or not df_d.empty or not df_m.empty

    if not has_data:
        st.markdown('<div class="info-box">まだデータがありません。時間帯×月別入力・日別入力タブからデータを入力してください。</div>', unsafe_allow_html=True)
        st.stop()

    # ── 月間目標進捗 ──────────────────────────────────────────────────────────
    current_month = date.today().strftime("%Y-%m")
    if not df_d.empty:
        df_d["date_dt"] = pd.to_datetime(df_d["date"], errors="coerce")
        df_cur_month    = df_d[df_d["date_dt"].dt.strftime("%Y-%m") == current_month]
        month_total     = int(df_cur_month["count"].sum())
    elif not df_m.empty:
        df_cur_m   = df_m[df_m["year_month"] == current_month]
        month_total = int(df_cur_m["count"].sum())
    else:
        month_total = 0

    progress = round(month_total / DM_GOAL * 100, 1)
    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{month_total:,}</div><div class="lbl">今月合計DM</div></div>
      <div class="metric-card"><div class="val">{progress}%</div><div class="lbl">月間目標進捗</div></div>
      <div class="metric-card"><div class="val">{DM_GOAL:,}</div><div class="lbl">月間目標</div></div>
    </div>
    <div style="margin:.5rem 0 .2rem;font-size:.78rem;color:#6b7280;">月間目標進捗 {month_total:,} / {DM_GOAL:,}件</div>
    <div class="progress-wrap"><div class="progress-fill" style="width:{min(progress,100)}%"></div></div>
    """, unsafe_allow_html=True)

    # ── 分析1: 国籍推定（時間帯別データ使用） ─────────────────────────────────
    if not df_h.empty:
        st.markdown('<div class="section-head">国籍分析（推定）— 時間帯別データより</div>', unsafe_allow_html=True)
        st.caption("ロジック: JST時間帯のDM数から逆算して、その時間帯に活発な地域・国籍を推定します")

        # フィルター
        h_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="h_nat_filter")
        df_hf    = df_h if h_filter == "全体" else df_h[df_h["platform"] == h_filter]

        if not df_hf.empty:
            hourly_agg = df_hf.groupby("hour")["count"].sum().reset_index()
            hourly_agg.columns = ["時間（JST）", "DM数"]
            hourly_agg = hourly_agg.sort_values("時間（JST）")

            # 時間帯分布グラフ
            st.bar_chart(hourly_agg.set_index("時間（JST）"))

            # ピーク時間帯と推定国籍
            top3 = hourly_agg.nlargest(3, "DM数")
            st.markdown('<div class="section-head">ゴールデンタイム TOP3 と推定国籍</div>', unsafe_allow_html=True)
            for _, r in top3.iterrows():
                h       = int(r["時間（JST）"])
                nations = get_nationality(h)
                st.markdown(
                    f'<div class="metric-card" style="margin-bottom:.5rem;">'
                    f'<div style="font-size:1rem;font-weight:700;color:#1e3a5f;">'
                    f'{h:02d}:00〜{h+1:02d}:00 &nbsp; <span style="color:#6b7280;font-size:.85rem;">{int(r["DM数"])}件</span>'
                    f'</div>'
                    f'<div style="font-size:.82rem;color:#374151;margin-top:.3rem;">'
                    f'推定国籍: {" / ".join(nations)}'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            # プラットフォーム別時間帯トレンド
            st.markdown('<div class="section-head">プラットフォーム別 時間帯トレンド</div>', unsafe_allow_html=True)
            pivot_plat = df_h.groupby(["hour","platform"])["count"].sum().reset_index()
            if not pivot_plat.empty:
                pivot_wide = pivot_plat.pivot(index="hour", columns="platform", values="count").fillna(0)
                st.line_chart(pivot_wide)

    # ── 分析2: DM数分析（日別×時間帯） ──────────────────────────────────────
    st.markdown('<div class="section-head">DM数分析 — 日別推移</div>', unsafe_allow_html=True)

    if not df_d.empty:
        # 日別DM数推移グラフ
        df_d["date_dt"] = pd.to_datetime(df_d["date"], errors="coerce")
        daily_total_df  = df_d.groupby("date")["count"].sum().reset_index()
        daily_total_df.columns = ["日付","合計DM"]
        daily_total_df = daily_total_df.sort_values("日付")
        st.line_chart(daily_total_df.set_index("日付"))

        # 日別 × プラットフォーム別
        st.markdown('<div class="section-head">日別 × プラットフォーム別 DM数</div>', unsafe_allow_html=True)
        daily_pivot = df_d.groupby(["date","platform"])["count"].sum().reset_index()
        daily_wide  = daily_pivot.pivot(index="date", columns="platform", values="count").fillna(0)
        st.bar_chart(daily_wide)

    # ── ヒートマップ（時間帯 × 日付） ────────────────────────────────────────
    if not df_h.empty:
        st.markdown('<div class="section-head">時間帯別ヒートマップ（月×時間帯）</div>', unsafe_allow_html=True)
        st.caption("各セルの数値が大きいほど、その時間帯のDMが多いことを示します")
        hm_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="hm_filter")
        df_hm     = df_h if hm_filter == "全体" else df_h[df_h["platform"] == hm_filter]
        if not df_hm.empty:
            hmap = df_hm.groupby(["year_month","hour"])["count"].sum().reset_index()
            hmap_wide = hmap.pivot(index="year_month", columns="hour", values="count").fillna(0).astype(int)
            hmap_wide.columns = [f"{h:02d}時" for h in hmap_wide.columns]
            st.dataframe(hmap_wide, use_container_width=True)

    # ── 月別集計 ──────────────────────────────────────────────────────────────
    if not df_m.empty or not df_h.empty:
        st.markdown('<div class="section-head">月別 × プラットフォーム別 DM数</div>', unsafe_allow_html=True)
        use_df = df_m if not df_m.empty else df_h.rename(columns={"year_month":"year_month"})
        if not df_m.empty:
            m_pivot = df_m.groupby(["year_month","platform"])["count"].sum().reset_index()
            m_wide  = m_pivot.pivot(index="year_month", columns="platform", values="count").fillna(0).astype(int)
            st.bar_chart(m_wide)
