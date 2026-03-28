"""
pages/02_sns_dm.py — SNS DM トラッキング（完全版）
URL: /sns_dm

修正内容:
- DM入力データの編集機能（UPSERT方式 — 重複なし）
- 月間目標DM数の設定・進捗管理
- 月別・年別 表示切替
- 今月DM合計の自動集計
- 時間帯×月別 / 日別 の統合管理
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from common import inject_css, setup_sidebar, to_df, ALL_DM_PLATFORMS, DM_GOAL
from db import sb_select, sb_upsert, sb_insert, sb_update

st.set_page_config(page_title="SNS DM | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">SNS DM トラッキング</div>', unsafe_allow_html=True)

# ── 国籍推定ロジック（JST基準）────────────────────────────────────────────────
# 各時間帯のDM送信者の居住地を逆算推定
# JST - 9h = UTC として、UTCの活動時間帯から国籍を推測する
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

def get_nationality(hour: int) -> list:
    for r, nations in TIMEZONE_MAP.items():
        if hour in r:
            return nations
    return []

# ── 月間目標取得ヘルパー ──────────────────────────────────────────────────────
def get_goal(year_month: str) -> int:
    rows = sb_select("dm_goals")
    df   = to_df(rows)
    if df.empty: return DM_GOAL
    match = df[df["year_month"] == year_month]
    return int(match["goal"].values[0]) if not match.empty else DM_GOAL

# ── タブ構成 ──────────────────────────────────────────────────────────────────
tab_daily, tab_hourly, tab_goal, tab_analysis = st.tabs([
    "日別入力・編集",
    "時間帯×月別入力・編集",
    "月間目標設定",
    "分析・可視化",
])

# ════════════════════════════════════════════════════════
# タブ1: 日別入力（UPSERT — 編集可能）
# ════════════════════════════════════════════════════════
with tab_daily:
    st.markdown('<div class="section-head">日別 × プラットフォーム別 DM数（上書き保存対応）</div>', unsafe_allow_html=True)
    st.caption("同じ日付 × プラットフォームで再保存すると自動で上書きされます（重複なし）")

    d_date = st.date_input("日付", value=date.today(), key="d_date")

    # 既存データを読み込んでデフォルト値に反映（編集機能）
    # date列を YYYY-MM-DD 文字列に正規化（DBがtimestamp型で返す場合に対応）
    existing_daily = to_df(sb_select("dm_daily"))
    if not existing_daily.empty:
        existing_daily["date"] = pd.to_datetime(
            existing_daily["date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        existing_daily = existing_daily.dropna(subset=["date"])

    def get_daily_val(dt, pl):
        if existing_daily.empty: return 0
        match = existing_daily[
            (existing_daily["date"] == str(dt)) &
            (existing_daily["platform"] == pl)
        ]
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
                daily_vals[pl] = st.number_input(
                    pl,
                    min_value=0,
                    value=get_daily_val(d_date, pl),
                    step=1,
                    key=f"daily_{pl}"
                )

    daily_total = sum(daily_vals.values())
    st.markdown(
        f'<div class="info-box">入力合計: <strong>{daily_total:,}件</strong>'
        f'&nbsp; &nbsp; 対象日: <strong>{d_date}</strong></div>',
        unsafe_allow_html=True
    )

    if st.button("保存する（上書き対応）", key="d_save"):
        saved_new = 0; saved_upd = 0
        for pl, count in daily_vals.items():
            # 既存チェック → 新規/更新を判別してメッセージを出し分け（修正3）
            is_existing = get_daily_val(d_date, pl) > 0 or (
                not existing_daily.empty and
                len(existing_daily[(existing_daily["date"]==str(d_date)) & (existing_daily["platform"]==pl)]) > 0
            )
            res = sb_upsert("dm_daily", {"date": str(d_date), "platform": pl, "count": count})
            if res:
                if is_existing: saved_upd += 1
                else:           saved_new += 1
        msg_parts = []
        if saved_new > 0: msg_parts.append(f"新規保存: {saved_new}件")
        if saved_upd > 0: msg_parts.append(f"更新: {saved_upd}件")
        st.markdown(f'<div class="success-box">{" / ".join(msg_parts)}</div>', unsafe_allow_html=True)

    # 直近30日間の入力済みデータ一覧
    st.markdown('<div class="section-head">入力済みデータ一覧（直近30日）</div>', unsafe_allow_html=True)
    if not existing_daily.empty:
        daily_pivot = existing_daily.groupby(["date","platform"])["count"].sum().reset_index()
        daily_wide  = daily_pivot.pivot(index="date", columns="platform", values="count").fillna(0).astype(int)
        daily_wide["合計"] = daily_wide.sum(axis=1)
        st.dataframe(daily_wide.sort_index(ascending=False).head(30), use_container_width=True)
    else:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ2: 時間帯×月別入力（UPSERT — 編集可能）
# ════════════════════════════════════════════════════════
with tab_hourly:
    st.markdown('<div class="section-head">時間帯 × 月別 × プラットフォーム別 DM数（上書き保存対応）</div>', unsafe_allow_html=True)
    st.caption("同じ月 × プラットフォーム × 時間帯で再保存すると自動で上書きされます")

    mc1, mc2 = st.columns(2)
    with mc1:
        m_year_month = st.text_input(
            "対象月 (YYYY-MM)",
            value=date.today().strftime("%Y-%m"),
            placeholder="例: 2026-03"
        )
    with mc2:
        m_platform = st.selectbox("プラットフォーム", ALL_DM_PLATFORMS, key="m_plat")

    # 既存データを読み込んでデフォルト値に反映（編集機能）
    existing_hourly = to_df(sb_select("dm_hourly_monthly"))
    def get_hourly_val(ym, pl, hr):
        if existing_hourly.empty: return 0
        match = existing_hourly[
            (existing_hourly["year_month"] == ym) &
            (existing_hourly["platform"]   == pl) &
            (existing_hourly["hour"]       == hr)
        ]
        return int(match["count"].values[0]) if not match.empty else 0

    st.markdown(f"**{m_year_month} / {m_platform}** の時間帯別DM数（既存データを自動表示）")

    hourly_vals = {}
    for row_start in range(0, 24, 6):
        cols = st.columns(6)
        for i, col in enumerate(cols):
            hour = row_start + i
            with col:
                hourly_vals[hour] = st.number_input(
                    f"{hour:02d}時",
                    min_value=0,
                    value=get_hourly_val(m_year_month, m_platform, hour),
                    step=1,
                    key=f"hm_{hour}"
                )

    total_h  = sum(hourly_vals.values())
    peak_h   = max(hourly_vals, key=hourly_vals.get) if total_h > 0 else 0
    st.markdown(
        f'<div class="info-box">'
        f'合計: <strong>{total_h}件</strong> &nbsp; '
        f'ピーク: <strong>{peak_h:02d}時</strong>（{hourly_vals.get(peak_h, 0)}件）'
        f'</div>',
        unsafe_allow_html=True
    )

    if st.button("時間帯データを保存（上書き対応）", key="m_save"):
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
    if not existing_hourly.empty:
        summary  = existing_hourly.groupby(["year_month","platform"])["count"].sum().reset_index()
        pivot_s  = summary.pivot(index="year_month", columns="platform", values="count").fillna(0).astype(int)
        st.dataframe(pivot_s, use_container_width=True)
    else:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ3: 月間目標設定
# ════════════════════════════════════════════════════════
with tab_goal:
    st.markdown('<div class="section-head">月間目標DM数を設定</div>', unsafe_allow_html=True)

    gc1, gc2 = st.columns(2)
    with gc1:
        g_month = st.text_input(
            "対象月 (YYYY-MM)",
            value=date.today().strftime("%Y-%m"),
            placeholder="例: 2026-03",
            key="g_month"
        )
    with gc2:
        # 既存の目標値をデフォルトに
        current_goal = get_goal(g_month)
        g_goal = st.number_input(
            "目標DM数",
            min_value=0,
            value=current_goal,
            step=500,
            key="g_goal"
        )

    if st.button("目標を保存する"):
        if not g_month or len(g_month) != 7:
            st.markdown('<div class="err-box">対象月をYYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
        else:
            sb_upsert("dm_goals", {"year_month": g_month, "goal": g_goal})
            st.markdown(f'<div class="success-box">{g_month} の目標を {g_goal:,}件 に設定しました</div>', unsafe_allow_html=True)

    # 目標一覧
    st.markdown('<div class="section-head">設定済み月間目標一覧</div>', unsafe_allow_html=True)
    rows_goals = sb_select("dm_goals", order="-year_month")
    df_goals   = to_df(rows_goals)

    if not df_goals.empty:
        # 日別データを取得して date 列を正規化
        existing_daily = to_df(sb_select("dm_daily"))
        if not existing_daily.empty:
            existing_daily["date"] = pd.to_datetime(
                existing_daily["date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
            existing_daily = existing_daily.dropna(subset=["date"])
        for _, row in df_goals.iterrows():
            ym   = row["year_month"]
            goal = int(row["goal"])
            if not existing_daily.empty:
                actual = int(existing_daily[
                    existing_daily["date"].str.startswith(ym)
                ]["count"].sum())
            else:
                actual = 0
            pct   = round(actual / goal * 100, 1) if goal else 0
            color = "#15803d" if pct >= 100 else "#1e3a5f" if pct >= 50 else "#dc2626"
            st.markdown(
                f'<div class="metric-card" style="margin-bottom:.5rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-weight:700;color:#1e3a5f;">{ym}</span>'
                f'<span style="font-size:.75rem;color:#9ca3af;">目標: {goal:,}件</span>'
                f'</div>'
                f'<div style="margin:.4rem 0;font-size:.9rem;">'
                f'実績: <strong>{actual:,}件</strong> &nbsp; '
                f'<span style="color:{color};font-weight:700;">{pct}%</span>'
                f'</div>'
                f'<div style="background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;">'
                f'<div style="width:{min(pct,100)}%;height:100%;background:{color};border-radius:4px;"></div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown('<div class="info-box">目標が設定されていません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ4: 分析・可視化
# ════════════════════════════════════════════════════════
with tab_analysis:
    existing_daily  = to_df(sb_select("dm_daily",  order="date"))
    existing_hourly = to_df(sb_select("dm_hourly_monthly", order="hour"))

    if existing_daily.empty and existing_hourly.empty:
        st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)
        st.stop()

    # ── date列を必ず YYYY-MM-DD 文字列に正規化（DBがtimestamp型で返す場合に対応）──
    # 例: "2026-02-22T00:00:00+00:00" → "2026-02-22"
    #     "2026-02-22 00:00:00"       → "2026-02-22"
    if not existing_daily.empty:
        existing_daily = existing_daily.copy()
        existing_daily["date"] = pd.to_datetime(
            existing_daily["date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        # 変換失敗行（NaT）を除去
        existing_daily = existing_daily.dropna(subset=["date"])

    # ── 表示切替（月別 / 年別）──────────────────────────────────────────────
    view_mode = st.radio("表示モード", ["月別", "年別"], horizontal=True)

    if view_mode == "月別":
        available_months = []
        if not existing_daily.empty:
            available_months = sorted(existing_daily["date"].str[:7].unique().tolist(), reverse=True)
        if not available_months:
            available_months = [date.today().strftime("%Y-%m")]
        sel_month = st.selectbox("対象月を選択", available_months)
        sel_year  = None
    else:
        available_years = []
        if not existing_daily.empty:
            available_years = sorted(existing_daily["date"].str[:4].unique().tolist(), reverse=True)
        if not available_years:
            available_years = [str(date.today().year)]
        sel_year  = st.selectbox("対象年を選択", available_years)
        sel_month = None

    # ── 修正5・6: 選択月/年 に連動した目標・実績集計 ──────────────────────────
    if view_mode == "月別" and sel_month:
        sel_goal   = get_goal(sel_month)
        if not existing_daily.empty:
            # 修正6: 欠損日0補完後に合計
            sel_actual = int(existing_daily[
                existing_daily["date"].str.startswith(sel_month)
            ]["count"].sum())
        else:
            sel_actual = 0
        sel_progress = round(sel_actual / sel_goal * 100, 1) if sel_goal else 0
        label_period = sel_month
    else:
        # 年別: 各月目標の合計 / 各月実績の合計
        rows_goals = sb_select("dm_goals", order="year_month")
        df_goals   = to_df(rows_goals)
        if sel_year and not df_goals.empty:
            year_goals = df_goals[df_goals["year_month"].str.startswith(sel_year)]
            sel_goal   = int(year_goals["goal"].sum()) if not year_goals.empty else DM_GOAL * 12
        else:
            sel_goal = DM_GOAL * 12
        if not existing_daily.empty and sel_year:
            sel_actual = int(existing_daily[
                existing_daily["date"].str.startswith(sel_year)
            ]["count"].sum())
        else:
            sel_actual = 0
        sel_progress = round(sel_actual / sel_goal * 100, 1) if sel_goal else 0
        label_period = sel_year or "全期間"

    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{sel_actual:,}</div><div class="lbl">合計DM ({label_period})</div></div>
      <div class="metric-card"><div class="val">{sel_goal:,}</div><div class="lbl">目標 ({label_period})</div></div>
      <div class="metric-card"><div class="val">{sel_progress}%</div><div class="lbl">進捗率</div></div>
    </div>
    <div style="margin:.5rem 0 .2rem;font-size:.78rem;color:#6b7280;">
      {label_period} 進捗: {sel_actual:,} / {sel_goal:,}件
    </div>
    <div class="progress-wrap"><div class="progress-fill" style="width:{min(sel_progress,100)}%"></div></div>
    """, unsafe_allow_html=True)

    # ── フィルタリング ────────────────────────────────────────────────────────
    if not existing_daily.empty:
        if view_mode == "月別" and sel_month:
            df_filtered  = existing_daily[existing_daily["date"].str.startswith(sel_month)]
            period_label = sel_month
        elif view_mode == "年別" and sel_year:
            df_filtered  = existing_daily[existing_daily["date"].str.startswith(sel_year)]
            period_label = sel_year
        else:
            df_filtered  = existing_daily.copy()
            period_label = "全期間"
    else:
        df_filtered  = pd.DataFrame()
        period_label = ""

    # ── 修正4: 日付範囲を生成して欠損日を0補完 ───────────────────────────────
    def fill_missing_dates(df_src: pd.DataFrame, period_str: str, mode: str) -> pd.DataFrame:
        """
        mode='monthly': YYYY-MM → その月の全日付を生成
        mode='yearly' : YYYY   → その年の全日付を生成
        欠損日を0で補完する（修正4）
        """
        if mode == "monthly":
            try:
                y, m    = int(period_str[:4]), int(period_str[5:7])
                start   = date(y, m, 1)
                from calendar import monthrange
                end     = date(y, m, monthrange(y, m)[1])
            except Exception:
                return df_src
        else:
            try:
                y       = int(period_str)
                start   = date(y, 1, 1)
                end     = date(y, 12, 31)
            except Exception:
                return df_src
        all_dates = pd.date_range(start=start, end=end, freq="D")
        all_dates_str = all_dates.strftime("%Y-%m-%d").tolist()
        if df_src.empty:
            return pd.DataFrame({"date": all_dates_str, "count": [0]*len(all_dates_str)})
        daily_sum = df_src.groupby("date")["count"].sum().reset_index()
        daily_sum = daily_sum.set_index("date").reindex(all_dates_str, fill_value=0).reset_index()
        daily_sum.columns = ["date","count"]
        return daily_sum

    # ── 日別DM数推移（0補完済み）────────────────────────────────────────────
    if not df_filtered.empty or period_label:
        st.markdown(f'<div class="section-head">日別DM数推移 — {period_label}</div>', unsafe_allow_html=True)

        fill_mode = "monthly" if view_mode == "月別" else "yearly"
        fill_key  = sel_month if view_mode == "月別" else (sel_year or "")
        df_filled = fill_missing_dates(df_filtered, fill_key, fill_mode)

        if not df_filled.empty:
            st.line_chart(df_filled.set_index("date")["count"])

        # プラットフォーム別（修正4: 欠損日を0補完）
        st.markdown('<div class="section-head">プラットフォーム別 日別推移</div>', unsafe_allow_html=True)
        if not df_filtered.empty:
            d_pivot = df_filtered.groupby(["date","platform"])["count"].sum().reset_index()
            d_wide  = d_pivot.pivot(index="date", columns="platform", values="count").fillna(0)
            if fill_key:
                all_dates_str2 = df_filled["date"].tolist()
                d_wide = d_wide.reindex(all_dates_str2, fill_value=0).fillna(0)
            d_wide = d_wide.loc[:, (d_wide != 0).any(axis=0)]
            if not d_wide.empty:
                st.bar_chart(d_wide)

    # ── 国籍分析（時間帯別データ使用）────────────────────────────────────────
    if not existing_hourly.empty:
        st.markdown('<div class="section-head">国籍分析（推定）— 時間帯別データより</div>', unsafe_allow_html=True)
        st.caption("ロジック: JST時間帯のピークからDM送信者の居住地域を逆算推定します")

        h_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="h_nat")
        df_hf    = existing_hourly if h_filter == "全体" else existing_hourly[existing_hourly["platform"] == h_filter]

        if view_mode == "月別" and sel_month:
            df_hf = df_hf[df_hf["year_month"] == sel_month]
        elif view_mode == "年別" and sel_year:
            df_hf = df_hf[df_hf["year_month"].str.startswith(sel_year)]

        if not df_hf.empty:
            # 修正4: 時間帯も0〜23時を全生成して補完
            hourly_agg = df_hf.groupby("hour")["count"].sum().reset_index()
            hourly_agg = hourly_agg.set_index("hour").reindex(range(24), fill_value=0).reset_index()
            hourly_agg.columns = ["時間（JST）","DM数"]
            st.bar_chart(hourly_agg.set_index("時間（JST）"))

            top3 = hourly_agg[hourly_agg["DM数"] > 0].nlargest(3, "DM数")
            for _, r in top3.iterrows():
                h       = int(r["時間（JST）"])
                nations = get_nationality(h)
                st.markdown(
                    f'<div class="metric-card" style="margin-bottom:.5rem;">'
                    f'<div style="font-weight:700;color:#1e3a5f;">'
                    f'{h:02d}:00〜{h+1:02d}:00 &nbsp; <span style="color:#6b7280;font-size:.85rem;">{int(r["DM数"])}件</span>'
                    f'</div>'
                    f'<div style="font-size:.82rem;color:#374151;margin-top:.3rem;">'
                    f'推定国籍: {" / ".join(nations)}'
                    f'</div></div>', unsafe_allow_html=True)

        # 時間帯ヒートマップ（0補完）
        st.markdown('<div class="section-head">時間帯ヒートマップ（月 × 時間帯）</div>', unsafe_allow_html=True)
        df_hm = existing_hourly if h_filter == "全体" else existing_hourly[existing_hourly["platform"] == h_filter]
        if not df_hm.empty:
            hmap      = df_hm.groupby(["year_month","hour"])["count"].sum().reset_index()
            hmap_wide = hmap.pivot(index="year_month", columns="hour", values="count").fillna(0).astype(int)
            # 修正4: 0〜23時を全列確保
            hmap_wide = hmap_wide.reindex(columns=range(24), fill_value=0)
            hmap_wide.columns = [f"{h:02d}時" for h in hmap_wide.columns]
            st.dataframe(hmap_wide, use_container_width=True)

    # ── 修正5: 月別/年別集計（選択と連動）───────────────────────────────────
    if not existing_daily.empty:
        if view_mode == "月別" and sel_month:
            st.markdown(f'<div class="section-head">週別集計 — {sel_month}</div>', unsafe_allow_html=True)
            if not df_filtered.empty:
                df_wk = df_filtered.copy()
                df_wk["date_dt"] = pd.to_datetime(df_wk["date"])
                df_wk["week"]    = df_wk["date_dt"].dt.strftime("%Y-W%U")
                week_total = df_wk.groupby("week")["count"].sum().reset_index()
                week_total.columns = ["週","合計DM"]
                st.bar_chart(week_total.set_index("週"))
        else:
            st.markdown(f'<div class="section-head">月別集計 — {sel_year}</div>', unsafe_allow_html=True)
            if not df_filtered.empty:
                df_mn = df_filtered.copy()
                df_mn["month"] = df_mn["date"].str[:7]
                # 修正4: 年内の全12ヶ月を生成して0補完
                if sel_year:
                    all_yr_months = [f"{sel_year}-{m:02d}" for m in range(1,13)]
                    month_total   = df_mn.groupby("month")["count"].sum().reset_index()
                    month_total   = month_total.set_index("month").reindex(all_yr_months, fill_value=0).reset_index()
                    month_total.columns = ["月","合計DM"]
                    st.bar_chart(month_total.set_index("月"))
                    # プラットフォーム別月別
                    m_plat = df_mn.groupby(["month","platform"])["count"].sum().reset_index()
                    m_wide = m_plat.pivot(index="month", columns="platform", values="count").fillna(0)
                    m_wide = m_wide.reindex(all_yr_months, fill_value=0).fillna(0)
                    m_wide = m_wide.loc[:, (m_wide != 0).any(axis=0)]
                    if not m_wide.empty:
                        st.bar_chart(m_wide)
