"""
pages/02_sns_dm.py — SNS DM トラッキング（v8 完全版）

修正1: 2026年データ表示問題の対応
  - load_dm_daily() に件数デバッグ表示を追加
  - utc=True で timezone-aware timestamp も確実に正規化
  - available_years を正規化後データから生成（年フィルタの不一致を解消）

修正2: 月間目標の実績を dm_daily から自動集計（手動入力廃止）

修正3: 日別入力・時間帯別入力タブを削除（Sheets自動同期で不要）

修正4: 年/月/日/期間指定の検索機能を追加
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from calendar import monthrange
from common import inject_css, setup_sidebar, to_df, ALL_DM_PLATFORMS, DM_GOAL
from db import sb_select, sb_upsert

st.set_page_config(page_title="SNS DM | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">SNS DM トラッキング</div>', unsafe_allow_html=True)

# ── 国籍推定ロジック ──────────────────────────────────────────────────────────
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
        if hour in r: return nations
    return []

# ── 修正1: date列を確実に YYYY-MM-DD 文字列へ正規化 ──────────────────────────
def load_dm_daily() -> pd.DataFrame:
    """
    dm_daily を取得し date列を正規化する。
    Supabaseのdate列がtext型/date型どちらでも対応。
    """
    rows = sb_select("dm_daily", order="date")
    df   = to_df(rows)
    if df.empty:
        return df
    df = df.copy()

    def safe_to_date_str(val):
        if val is None: return None
        if pd.isna(val) if not isinstance(val, str) else val == "": return None

        s = str(val).strip()

        # すでに YYYY-MM-DD 形式なら即返す（最速パス）
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s

        # YYYY/MM/DD → YYYY-MM-DD
        if re.match(r"^\d{4}/\d{2}/\d{2}$", s):
            return s.replace("/", "-")

        # timestamp系（"2026-03-01T..." or "2026-03-01 00:00..."）
        # 先頭10文字を取り出す
        if len(s) >= 10:
            candidate = s[:10].replace("/", "-")
            if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
                return candidate

        # pandas で変換（最終手段）
        try:
            return pd.to_datetime(s, utc=False).strftime("%Y-%m-%d")
        except Exception:
            try:
                return pd.to_datetime(s, utc=True).tz_convert(None).strftime("%Y-%m-%d")
            except Exception:
                return None

    df["date"] = df["date"].apply(safe_to_date_str)
    df = df.dropna(subset=["date"])
    df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)
    return df.sort_values("date").reset_index(drop=True)

def get_goal(year_month: str) -> int:
    rows = sb_select("dm_goals")
    df   = to_df(rows)
    if df.empty: return DM_GOAL
    match = df[df["year_month"] == year_month]
    return int(match["goal"].values[0]) if not match.empty else DM_GOAL

def get_monthly_actual(df_daily: pd.DataFrame, prefix: str) -> int:
    """year_month (YYYY-MM) または year (YYYY) を prefix として実績を合計"""
    if df_daily.empty: return 0
    return int(df_daily[df_daily["date"].str.startswith(prefix)]["count"].sum())

def fill_dates(df_src: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """欠損日を0補完した日別合計を返す"""
    all_dates = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d").tolist()
    if df_src.empty:
        return pd.DataFrame({"date": all_dates, "count": [0]*len(all_dates)})
    daily_sum = df_src.groupby("date")["count"].sum()
    daily_sum = daily_sum.reindex(all_dates, fill_value=0).reset_index()
    daily_sum.columns = ["date", "count"]
    return daily_sum

def fill_dates_by_platform(df_src: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """欠損日を0補完したプラットフォーム別日別データを返す"""
    all_dates = pd.date_range(start=start, end=end, freq="D").strftime("%Y-%m-%d").tolist()
    if df_src.empty: return pd.DataFrame()
    d_pivot = df_src.groupby(["date","platform"])["count"].sum().reset_index()
    d_wide  = d_pivot.pivot(index="date", columns="platform", values="count").fillna(0)
    d_wide  = d_wide.reindex(all_dates, fill_value=0).fillna(0)
    return d_wide.loc[:, (d_wide != 0).any(axis=0)]

# ── タブ構成（修正3: 入力タブを削除） ──────────────────────────────────────
tab_goal, tab_analysis = st.tabs(["月間目標設定", "分析・可視化"])

# ════════════════════════════════════════════════════════
# タブ1: 月間目標設定（修正2: 実績を dm_daily から自動集計）
# ════════════════════════════════════════════════════════
with tab_goal:
    st.markdown('<div class="section-head">月間目標DM数を設定</div>', unsafe_allow_html=True)
    st.caption("実績はスプレッドシートから自動同期されたデータを使って集計します")

    gc1, gc2 = st.columns(2)
    with gc1:
        g_month = st.text_input(
            "対象月 (YYYY-MM)",
            value=date.today().strftime("%Y-%m"),
            key="g_month"
        )
    with gc2:
        current_goal = get_goal(g_month)
        g_goal = st.number_input("目標DM数", min_value=0, value=current_goal, step=500, key="g_goal")

    if st.button("目標を保存する"):
        if not g_month or len(g_month) != 7:
            st.markdown('<div class="err-box">YYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
        else:
            sb_upsert("dm_goals", {"year_month": g_month, "goal": g_goal})
            st.markdown(f'<div class="success-box">{g_month} の目標を {g_goal:,}件 に設定しました</div>', unsafe_allow_html=True)

    # 修正2: 実績を dm_daily から自動集計して表示
    st.markdown('<div class="section-head">設定済み月間目標と実績（自動集計）</div>', unsafe_allow_html=True)
    rows_goals = sb_select("dm_goals", order="-year_month")
    df_goals   = to_df(rows_goals)

    if not df_goals.empty:
        df_daily_goal = load_dm_daily()  # 正規化済みデータ
        for _, row in df_goals.iterrows():
            ym     = row["year_month"]
            goal   = int(row["goal"])
            # 修正2: dm_daily から該当月のデータを全プラットフォーム合算
            actual = get_monthly_actual(df_daily_goal, ym)
            pct    = round(actual / goal * 100, 1) if goal else 0
            color  = "#15803d" if pct >= 100 else "#1e3a5f" if pct >= 50 else "#dc2626"

            # プラットフォーム別内訳も表示
            if not df_daily_goal.empty:
                plat_breakdown = df_daily_goal[
                    df_daily_goal["date"].str.startswith(ym)
                ].groupby("platform")["count"].sum().sort_values(ascending=False)
                breakdown_str = " / ".join([f"{p}: {int(v):,}" for p, v in plat_breakdown.items() if v > 0])
            else:
                breakdown_str = ""

            st.markdown(
                f'<div class="metric-card" style="margin-bottom:.6rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-weight:700;color:#1e3a5f;">{ym}</span>'
                f'<span style="font-size:.75rem;color:#9ca3af;">目標: {goal:,}件</span>'
                f'</div>'
                f'<div style="font-size:.9rem;margin:.3rem 0;">'
                f'実績: <strong>{actual:,}件</strong> &nbsp; '
                f'<span style="color:{color};font-weight:700;">{pct}%</span>'
                f'</div>'
                f'<div style="background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;margin-bottom:.3rem;">'
                f'<div style="width:{min(pct,100)}%;height:100%;background:{color};border-radius:4px;"></div>'
                f'</div>'
                + (f'<div style="font-size:.72rem;color:#9ca3af;">{breakdown_str}</div>' if breakdown_str else '')
                + f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown('<div class="info-box">目標が設定されていません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ2: 分析・可視化（修正1 + 修正4: 検索機能追加）
# ════════════════════════════════════════════════════════
with tab_analysis:

    # 修正1: 正規化済みデータを取得してデバッグ情報を表示
    existing_daily  = load_dm_daily()
    existing_hourly_raw = to_df(sb_select(
        "dm_hourly_monthly",
        order="hour",
        columns="id,year_month,platform,hour,dm_count"
    ))

    if not existing_hourly_raw.empty:
        existing_hourly = existing_hourly_raw.copy()
        # dm_count → count にリネーム（以降のコードはcountで統一）
        if "dm_count" in existing_hourly.columns:
            existing_hourly = existing_hourly.rename(columns={"dm_count": "count"})
        existing_hourly["hour"] = pd.to_numeric(
            existing_hourly["hour"], errors="coerce"
        ).fillna(0).astype(int)
        if "count" in existing_hourly.columns:
            existing_hourly["count"] = pd.to_numeric(
                existing_hourly["count"], errors="coerce"
            ).fillna(0).astype(int)
        else:
            existing_hourly["count"] = 0
    else:
        existing_hourly = pd.DataFrame()

    # ── デバッグ情報（問題診断用）────────────────────────────────────────────
    with st.expander("データ取得状況を確認（問題がある場合はここを開く）"):
        # 正規化前の生データも確認
        raw_rows = sb_select("dm_daily", order="date")
        df_raw   = to_df(raw_rows)
        st.markdown(f"**Supabase取得件数（生データ）:** {len(df_raw)}件")
        if not df_raw.empty:
            st.markdown(f"**date列の型（先頭値）:** `{type(df_raw['date'].iloc[0]).__name__}` → 値: `{df_raw['date'].iloc[0]}`")
            st.markdown(f"**dateの最新値（末尾）:** `{df_raw['date'].iloc[-1]}`")

        st.markdown(f"**正規化後件数:** {len(existing_daily)}件")
        if not existing_daily.empty:
            year_counts = existing_daily["date"].str[:4].value_counts().sort_index()
            for yr, cnt in year_counts.items():
                st.markdown(f"- {yr}年: {cnt}件")
            st.markdown(f"**最古:** {existing_daily['date'].min()} / **最新:** {existing_daily['date'].max()}")
            st.markdown(f"**プラットフォーム:** {', '.join(existing_daily['platform'].unique())}")
        else:
            st.markdown('<div class="err-box">正規化後にデータが0件になっています。date列の値を上記で確認してください。</div>', unsafe_allow_html=True)
        st.markdown(f"**dm_hourly_monthly件数:** {len(existing_hourly)}件")
        if not existing_hourly.empty:
            st.markdown(f"**hourlyカラム一覧:** {list(existing_hourly.columns)}")
            st.markdown(f"**hour列の型:** `{existing_hourly['hour'].dtype}`")
            st.markdown(f"**year_month列の一意値:** {sorted(existing_hourly['year_month'].dropna().unique().tolist())}")
            # 2026-01の11時を直接確認
            test = existing_hourly[
                (existing_hourly["year_month"] == "2026-01") &
                (existing_hourly["hour"] == 11)
            ]
            cnt_sum = int(test["count"].sum()) if "count" in test.columns else "count列なし"
            st.markdown(f"**2026-01 / hour=11:** {len(test)}件 / count合計: {cnt_sum}")
            if not test.empty:
                st.markdown("**生データ（先頭5件）:**")
                show_cols = [c for c in ["year_month","platform","hour","count","dm_count"] if c in test.columns]
                st.dataframe(test[show_cols].head(5))

    if existing_daily.empty and existing_hourly.empty:
        st.markdown('<div class="info-box">まだデータがありません。スプレッドシートの「Tabibiyori 同期」→「全タブを同期する」を実行してください。</div>', unsafe_allow_html=True)
        st.stop()

    # ── 修正4: 検索・フィルター UI ────────────────────────────────────────────
    st.markdown('<div class="section-head">検索・期間指定</div>', unsafe_allow_html=True)
    search_mode = st.radio("検索方法", ["年・月・日を選択", "期間を直接指定"], horizontal=True)

    if search_mode == "年・月・日を選択":
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            available_years = sorted(
                existing_daily["date"].str[:4].unique().tolist(), reverse=True
            ) if not existing_daily.empty else [str(date.today().year)]
            sel_year = st.selectbox("年", ["すべて"] + available_years, key="sel_year")
        with sc2:
            month_opts = ["すべて"] + [f"{m:02d}" for m in range(1,13)]
            sel_month_num = st.selectbox("月", month_opts, key="sel_month_num")
        with sc3:
            sel_day = st.text_input("日（任意）", placeholder="例: 15", key="sel_day")

        # フィルター条件を構築
        f_prefix = ""
        if sel_year != "すべて":
            f_prefix = sel_year
            if sel_month_num != "すべて":
                f_prefix = f"{sel_year}-{sel_month_num}"
                if sel_day.strip():
                    day_str = sel_day.strip().zfill(2)
                    f_prefix = f"{sel_year}-{sel_month_num}-{day_str}"

        # 表示期間の決定
        # 問題③修正: p_end は「月の最終日」を使う（df_filtered.max()は欠損日に依存するため）
        if f_prefix == "":
            if not existing_daily.empty:
                p_start = date.fromisoformat(existing_daily["date"].min())
                p_end   = date.fromisoformat(existing_daily["date"].max())
            else:
                p_start = p_end = date.today()
            df_filtered  = existing_daily.copy()
            period_label = "全期間"
        else:
            df_filtered  = existing_daily[existing_daily["date"].str.startswith(f_prefix)].copy() if not existing_daily.empty else pd.DataFrame()
            period_label = f_prefix
            if sel_year != "すべて" and sel_month_num != "すべて" and sel_day.strip():
                # 特定日指定
                try:
                    p_start = p_end = date(int(sel_year), int(sel_month_num), int(sel_day.strip()))
                except Exception:
                    p_start = p_end = date.today()
            elif sel_year != "すべて" and sel_month_num != "すべて":
                # 月指定: p_start=月初、p_end=月末（欠損日に依存しない）
                y, m    = int(sel_year), int(sel_month_num)
                p_start = date(y, m, 1)
                p_end   = date(y, m, monthrange(y, m)[1])
            elif sel_year != "すべて":
                # 年指定
                p_start = date(int(sel_year), 1, 1)
                p_end   = date(int(sel_year), 12, 31)
            else:
                p_start = p_end = date.today()

    else:
        # 期間直接指定
        dc1, dc2 = st.columns(2)
        with dc1:
            p_start = st.date_input("開始日", value=date.today().replace(day=1), key="p_start")
        with dc2:
            p_end   = st.date_input("終了日", value=date.today(),                key="p_end")
        if p_start > p_end:
            st.markdown('<div class="err-box">開始日は終了日より前にしてください</div>', unsafe_allow_html=True)
            st.stop()
        from_str = str(p_start); to_str = str(p_end)
        df_filtered  = existing_daily[
            (existing_daily["date"] >= from_str) & (existing_daily["date"] <= to_str)
        ].copy() if not existing_daily.empty else pd.DataFrame()
        period_label = f"{p_start} 〜 {p_end}"

    # ── 選択期間のサマリー ────────────────────────────────────────────────────
    # デバッグ: フィルター後のデータ件数を表示
    with st.expander("フィルター結果を確認（4月が表示されない場合はここを開く）"):
        st.markdown(f"**選択条件:** year={sel_year if search_mode=='年・月・日を選択' else '期間指定'} / month={sel_month_num if search_mode=='年・月・日を選択' else '-'}")
        st.markdown(f"**f_prefix:** `{f_prefix if search_mode=='年・月・日を選択' else 'N/A'}`")
        st.markdown(f"**p_start:** `{p_start}` / **p_end:** `{p_end}`")
        st.markdown(f"**df_filtered件数:** {len(df_filtered)}件")
        if not df_filtered.empty:
            st.markdown(f"**df_filteredの日付範囲:** {df_filtered['date'].min()} 〜 {df_filtered['date'].max()}")
            st.markdown(f"**df_filteredの先頭5件:**")
            st.dataframe(df_filtered[["date","platform","count"]].head(5))
        else:
            st.markdown("**df_filtered は空です**")
            st.markdown(f"**existing_daily件数:** {len(existing_daily)}件")
            if not existing_daily.empty:
                st.markdown(f"**existing_dailyの2026-04データ件数:** {len(existing_daily[existing_daily['date'].str.startswith('2026-04')])}件")
    sel_goal   = 0
    if search_mode == "年・月・日を選択" and sel_year != "すべて" and sel_month_num != "すべて" and not sel_day.strip():
        sel_goal = get_goal(f"{sel_year}-{sel_month_num}")
    sel_progress = round(sel_actual / sel_goal * 100, 1) if sel_goal else 0

    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{sel_actual:,}</div><div class="lbl">合計DM（{period_label}）</div></div>
      {'<div class="metric-card"><div class="val">' + str(sel_goal) + '</div><div class="lbl">月間目標</div></div>' if sel_goal else ''}
      {'<div class="metric-card"><div class="val">' + str(sel_progress) + '%</div><div class="lbl">進捗率</div></div>' if sel_goal else ''}
    </div>""", unsafe_allow_html=True)
    if sel_goal:
        st.markdown(f'<div class="progress-wrap"><div class="progress-fill" style="width:{min(sel_progress,100)}%"></div></div>', unsafe_allow_html=True)

    if df_filtered.empty:
        st.markdown('<div class="info-box">選択した期間にデータがありません</div>', unsafe_allow_html=True)
        st.stop()

    # ── 日別DM数推移（欠損日0補完）────────────────────────────────────────────
    st.markdown(f'<div class="section-head">日別DM数推移 — {period_label}</div>', unsafe_allow_html=True)
    df_filled = fill_dates(df_filtered, p_start, p_end)
    if not df_filled.empty:
        st.line_chart(df_filled.set_index("date")["count"])

    # プラットフォーム別日別（欠損日0補完）
    st.markdown('<div class="section-head">プラットフォーム別 日別推移</div>', unsafe_allow_html=True)
    d_wide = fill_dates_by_platform(df_filtered, p_start, p_end)
    if not d_wide.empty:
        st.bar_chart(d_wide)

    # プラットフォーム別合計（棒グラフ + テーブル）
    st.markdown('<div class="section-head">プラットフォーム別 合計DM数（多い順）</div>', unsafe_allow_html=True)
    plat_total = df_filtered.groupby("platform")["count"].sum().reset_index(name="DM数")
    if not plat_total.empty:
        total_cnt  = int(plat_total["DM数"].sum())
        plat_total = plat_total.sort_values("DM数", ascending=False)
        plat_total["割合(%)"] = (plat_total["DM数"] / total_cnt * 100).round(1)
        st.bar_chart(plat_total.set_index("platform")["DM数"])
        st.dataframe(
            plat_total.rename(columns={"platform":"プラットフォーム"}).reset_index(drop=True),
            use_container_width=True, hide_index=True
        )

    # ── 国籍分析 ─────────────────────────────────────────────────────────────
    if not existing_hourly.empty:
        st.markdown('<div class="section-head">国籍分析（推定）</div>', unsafe_allow_html=True)
        h_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="h_nat")
        df_hf    = existing_hourly if h_filter == "全体" else existing_hourly[existing_hourly["platform"] == h_filter]

        # 期間フィルターを時間帯データにも適用
        if search_mode == "年・月・日を選択":
            if sel_year != "すべて" and sel_month_num != "すべて":
                df_hf = df_hf[df_hf["year_month"] == f"{sel_year}-{sel_month_num}"]
            elif sel_year != "すべて":
                df_hf = df_hf[df_hf["year_month"].str.startswith(sel_year)]
        else:
            from_ym = str(p_start)[:7]; to_ym = str(p_end)[:7]
            df_hf = df_hf[(df_hf["year_month"] >= from_ym) & (df_hf["year_month"] <= to_ym)]

        if not df_hf.empty:
            # hour列をintに統一してからgroupby（str/int混在で特定時間が欠落する問題を防ぐ）
            df_hf_agg = df_hf.copy()
            df_hf_agg["hour"]  = pd.to_numeric(df_hf_agg["hour"],  errors="coerce").fillna(0).astype(int)
            df_hf_agg["count"] = pd.to_numeric(df_hf_agg["count"], errors="coerce").fillna(0).astype(int)
            hourly_agg = df_hf_agg.groupby("hour")["count"].sum().reset_index()
            hourly_agg = hourly_agg.set_index("hour").reindex(range(24), fill_value=0).reset_index()
            hourly_agg.columns = ["時間（JST）","DM数"]
            st.bar_chart(hourly_agg.set_index("時間（JST）"))

            top3 = hourly_agg[hourly_agg["DM数"] > 0].nlargest(3,"DM数")
            for _, r in top3.iterrows():
                h = int(r["時間（JST）"]); nations = get_nationality(h)
                st.markdown(
                    f'<div class="metric-card" style="margin-bottom:.5rem;">'
                    f'<div style="font-weight:700;color:#1e3a5f;">{h:02d}:00〜{h+1:02d}:00'
                    f'<span style="color:#6b7280;font-size:.85rem;margin-left:.5rem;">{int(r["DM数"])}件</span></div>'
                    f'<div style="font-size:.82rem;color:#374151;margin-top:.3rem;">推定国籍: {" / ".join(nations)}</div>'
                    f'</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-head">時間帯ヒートマップ</div>', unsafe_allow_html=True)
        if not df_hf.empty:
            # pivot前にhourを必ずintに変換（str混在で特定時間が欠落する問題を防ぐ）
            df_hf_hmap = df_hf.copy()
            df_hf_hmap["hour"]  = pd.to_numeric(df_hf_hmap["hour"],  errors="coerce").fillna(0).astype(int)
            df_hf_hmap["count"] = pd.to_numeric(df_hf_hmap["count"], errors="coerce").fillna(0).astype(int)

            hmap = df_hf_hmap.groupby(["year_month","hour"])["count"].sum().reset_index()

            # pivot: hour列がintであることを保証してからreindex
            hmap["hour"] = hmap["hour"].astype(int)
            hmap_wide = hmap.pivot(index="year_month", columns="hour", values="count")

            # 0〜23時を全列確保（欠損時間をfill_value=0で補完）
            hmap_wide = hmap_wide.reindex(columns=list(range(24)), fill_value=0).fillna(0).astype(int)
            hmap_wide.columns = [f"{h:02d}時" for h in range(24)]
            st.dataframe(hmap_wide, use_container_width=True)

    # ── 月別/週別集計 ─────────────────────────────────────────────────────────
    date_range_days = (p_end - p_start).days
    if date_range_days > 60:
        # 期間が長い場合は月別
        st.markdown('<div class="section-head">月別集計</div>', unsafe_allow_html=True)
        df_mn = df_filtered.copy()
        df_mn["month"] = df_mn["date"].str[:7]
        all_months_in_range = pd.date_range(
            start=p_start.replace(day=1), end=p_end, freq="MS"
        ).strftime("%Y-%m").tolist()
        month_total = df_mn.groupby("month")["count"].sum()
        month_total = month_total.reindex(all_months_in_range, fill_value=0).reset_index()
        month_total.columns = ["月","合計DM"]
        st.bar_chart(month_total.set_index("月"))

        # プラットフォーム別月別
        m_plat = df_mn.groupby(["month","platform"])["count"].sum().reset_index()
        m_wide = m_plat.pivot(index="month", columns="platform", values="count").fillna(0)
        m_wide = m_wide.reindex(all_months_in_range, fill_value=0).fillna(0)
        m_wide = m_wide.loc[:, (m_wide != 0).any(axis=0)]
        if not m_wide.empty:
            st.bar_chart(m_wide)
    else:
        # 期間が短い場合は週別
        st.markdown('<div class="section-head">週別集計</div>', unsafe_allow_html=True)
        df_wk = df_filtered.copy()
        df_wk["date_dt"] = pd.to_datetime(df_wk["date"])
        df_wk["week"]    = df_wk["date_dt"].dt.strftime("%Y-W%U")
        week_total = df_wk.groupby("week")["count"].sum().reset_index()
        week_total.columns = ["週","合計DM"]
        if not week_total.empty:
            st.bar_chart(week_total.set_index("週"))
