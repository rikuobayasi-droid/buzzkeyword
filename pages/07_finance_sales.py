"""
pages/07_finance_sales.py — 売上・経営ダッシュボード

修正1: Patreon日別売上 = start_date の日にのみ monthly_price を計上
修正2: 開始日〜終了日の期間指定で集計
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from calendar import monthrange

try:
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

from common import inject_css, setup_sidebar, to_df
from db import sb_select

st.set_page_config(page_title="売上 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">売上・経営ダッシュボード</div>', unsafe_allow_html=True)

# ── 月加算ヘルパー ────────────────────────────────────────────────────────────
def add_months(d: date, n: int) -> date:
    if HAS_DATEUTIL:
        from dateutil.relativedelta import relativedelta
        return d + relativedelta(months=n)
    import calendar
    m   = d.month - 1 + n
    y   = d.year + m // 12
    m   = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)

def month_range_list(start: date, end: date) -> list:
    months, cur, count = [], start.replace(day=1), 0
    while cur <= end.replace(day=1) and count < 25:
        months.append(cur.strftime("%Y-%m"))
        cur = add_months(cur, 1); count += 1
    return months

# ── 修正1: Patreon日別売上ロジック ───────────────────────────────────────────
def calc_patreon_daily_by_contract(df_subs: pd.DataFrame, target_date: str) -> int:
    """
    修正1: 日別Patreon売上 = start_date がその日のサブスクの monthly_price 合計
    他の日は 0 円（日割りしない）
    """
    if df_subs.empty:
        return 0
    matched = df_subs[df_subs["start_date"].astype(str).str[:10] == target_date[:10]]
    return int(matched["monthly_price"].sum()) if not matched.empty else 0

def calc_patreon_mrr(df_subs: pd.DataFrame, year_month: str) -> int:
    """
    月別: 従来通り（その月に契約中 = start_date <= 月末 かつ end_date IS NULL or >= 月初）
    未来12ヶ月を上限とする
    """
    if df_subs.empty:
        return 0
    today        = date.today()
    future_limit = add_months(today.replace(day=1), 12)
    try:
        ym_date = date(int(year_month[:4]), int(year_month[5:7]), 1)
    except Exception:
        return 0
    if ym_date > future_limit:
        return 0
    y, m     = ym_date.year, ym_date.month
    days     = monthrange(y, m)[1]
    ym_start = f"{year_month}-01"
    ym_end   = f"{year_month}-{days:02d}"
    total    = 0
    for _, row in df_subs.iterrows():
        s = str(row.get("start_date","") or "")
        e = str(row.get("end_date","")   or "")
        p = int(row.get("monthly_price", 0) or 0)
        if not s or s > ym_end:                                          continue
        if e and e.lower() not in ("none","null",""):  # "null"文字列も空扱い
            if e < ym_start: continue
        total += p
    return total

def calc_patreon_period(df_subs: pd.DataFrame, date_from: date, date_to: date) -> int:
    """
    修正2: 期間指定Patreon売上 = start_date が期間内のサブスクの monthly_price 合計
    日別ロジック（契約開始日ベース）を使用 → 二重計上なし
    """
    if df_subs.empty:
        return 0
    from_str = str(date_from)
    to_str   = str(date_to)
    matched  = df_subs[
        (df_subs["start_date"].astype(str).str[:10] >= from_str) &
        (df_subs["start_date"].astype(str).str[:10] <= to_str)
    ]
    return int(matched["monthly_price"].sum()) if not matched.empty else 0

# ── データ取得 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=180)
def load_sales_data():
    rows_p  = sb_select("purchases",             order="-purchase_date")
    rows_pr = sb_select("products",              order="name")
    rows_e  = sb_select("expenses",              order="-exp_date")
    rows_s  = sb_select("patreon_subscriptions", order="start_date")
    return to_df(rows_p), to_df(rows_pr), to_df(rows_e), to_df(rows_s)

df_p_raw, df_prods, df_e, df_subs = load_sales_data()

# patreon_subscriptions の end_date を正規化
# DBから "null" 文字列で返ってくる場合に None に統一する
if not df_subs.empty and "end_date" in df_subs.columns:
    df_subs = df_subs.copy()
    df_subs["end_date"] = df_subs["end_date"].apply(
        lambda x: None if (x is None or str(x).lower() in ("null","none","")) else str(x)
    )

# purchases 前処理
if not df_p_raw.empty:
    df_p = df_p_raw.copy()
    if "amount" not in df_p.columns: df_p["amount"] = 0
    if not df_prods.empty:
        df_p = df_p.merge(
            df_prods[["id","name","category"]].rename(columns={"id":"product_id","name":"product_name","category":"business"}),
            on="product_id", how="left"
        )
    else:
        df_p["business"] = df_p.get("product_type","")
    df_p["business"]      = df_p["business"].fillna("その他")
    df_p["amount"]        = pd.to_numeric(df_p["amount"], errors="coerce").fillna(0)
    df_p["purchase_date"] = pd.to_datetime(df_p["purchase_date"], errors="coerce")
    df_p                  = df_p.dropna(subset=["purchase_date"])
    df_p["date_str"]      = df_p["purchase_date"].dt.strftime("%Y-%m-%d")
    df_p["month_str"]     = df_p["purchase_date"].dt.strftime("%Y-%m")
    df_p["year_str"]      = df_p["purchase_date"].dt.strftime("%Y")
    df_p_excl_pat         = df_p[df_p["business"] != "Patreon"]
else:
    df_p = pd.DataFrame(); df_p_excl_pat = pd.DataFrame()

today         = date.today()
period_start  = add_months(today.replace(day=1), -12)
period_end    = add_months(today.replace(day=1), 12)
all_months    = month_range_list(period_start, period_end)
patreon_monthly = {ym: calc_patreon_mrr(df_subs, ym) for ym in all_months}

# ── 修正2: 期間指定フィルター UI ──────────────────────────────────────────────
st.markdown('<div class="section-head">期間・条件を指定</div>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    f_from = st.date_input("開始日", value=today.replace(day=1), key="f_from")
with fc2:
    f_to   = st.date_input("終了日", value=today, key="f_to")
with fc3:
    all_biz_opts = ["すべて"] + (sorted(df_p_excl_pat["business"].unique().tolist()) if not df_p_excl_pat.empty else []) + ["Patreon"]
    f_biz  = st.selectbox("事業", all_biz_opts, key="f_biz")
with fc4:
    view_by = st.selectbox("集計単位", ["日別","月別","年別"], key="view_by")

if f_from > f_to:
    st.markdown('<div class="err-box">開始日は終了日より前に設定してください</div>', unsafe_allow_html=True)
    st.stop()

from_str = str(f_from)
to_str   = str(f_to)

# ── 期間内データを絞り込む ─────────────────────────────────────────────────
def get_period_purchases() -> pd.DataFrame:
    if df_p_excl_pat.empty: return pd.DataFrame()
    df = df_p_excl_pat[
        (df_p_excl_pat["date_str"] >= from_str) &
        (df_p_excl_pat["date_str"] <= to_str)
    ].copy()
    if f_biz not in ("すべて","Patreon"):
        df = df[df["business"] == f_biz]
    return df

def get_period_expenses() -> pd.DataFrame:
    if df_e.empty or "exp_date" not in df_e.columns: return pd.DataFrame()
    de = df_e.copy()
    de["exp_date_str"] = de["exp_date"].astype(str).str[:10]
    return de[(de["exp_date_str"] >= from_str) & (de["exp_date_str"] <= to_str)]

filt_p   = get_period_purchases()
filt_e   = get_period_expenses()

# Patreon売上の計算:
#   日別・期間指定 → start_date が期間内のサブスクを合計（契約開始日ベース）
#   月別           → 期間内の各月MRRを合計（より正確な月次売上）
if f_biz in ("すべて","Patreon"):
    if view_by == "月別":
        # 月別: 期間内の各月MRRを合計
        period_months_calc = month_range_list(f_from, f_to)
        filt_pat = sum(patreon_monthly.get(ym, 0) for ym in period_months_calc)
    else:
        # 日別・年別: 契約開始日ベース
        filt_pat = calc_patreon_period(df_subs, f_from, f_to)
else:
    filt_pat = 0

filt_pur = int(filt_p["amount"].sum()) if not filt_p.empty else 0

# 検索期間に応じたMRRを計算
period_months_calc = month_range_list(f_from, f_to)
if len(period_months_calc) == 1:
    period_mrr       = patreon_monthly.get(period_months_calc[0], 0)
    period_mrr_label = f"{period_months_calc[0]} MRR"
else:
    period_mrr       = sum(patreon_monthly.get(ym, 0) for ym in period_months_calc)
    period_mrr_label = f"期間MRR合計（{len(period_months_calc)}ヶ月）"

# 修正3: 事業選択に応じて総売上を計算
# Patreon選択 → MRRのみ
# その他事業選択 → その事業のみ
# すべて → MRR + その他事業合計
if f_biz == "Patreon":
    filt_tot = period_mrr          # PatreonのみはMRRだけ
    show_patreon = True
    show_others  = False
elif f_biz == "すべて":
    filt_tot = period_mrr + filt_pur
    show_patreon = True
    show_others  = True
else:
    filt_tot = filt_pur            # 特定事業選択時はその事業のみ
    show_patreon = False
    show_others  = True

filt_exp = int(filt_e["amount_out"].sum()) if not filt_e.empty and "amount_out" in filt_e.columns else 0
filt_prf = filt_tot - filt_exp
p_color  = "#15803d" if filt_prf >= 0 else "#dc2626"
period_label = f"{from_str} 〜 {to_str}"

# メトリクスカードを事業選択に応じて表示
if f_biz == "Patreon":
    # Patreon選択時: 総売上は表示しない
    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">¥{period_mrr:,}</div><div class="lbl">{period_mrr_label}</div></div>
      <div class="metric-card"><div class="val">¥{filt_exp:,}</div><div class="lbl">経費</div></div>
      <div class="metric-card"><div class="val" style="color:{p_color};">¥{filt_prf:,}</div><div class="lbl">利益</div></div>
    </div>
    <div style="font-size:.78rem;color:#6b7280;margin:.3rem 0;">集計期間: <strong>{period_label}</strong></div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">¥{filt_tot:,}</div><div class="lbl">総売上（{'MRR+その他' if f_biz == 'すべて' else f_biz}）</div></div>
      {'<div class="metric-card"><div class="val">¥' + str(f"{period_mrr:,}") + '</div><div class="lbl">' + period_mrr_label + '</div></div>' if show_patreon else ''}
      <div class="metric-card"><div class="val">¥{filt_pur:,}</div><div class="lbl">その他事業売上</div></div>
      <div class="metric-card"><div class="val">¥{filt_exp:,}</div><div class="lbl">経費</div></div>
      <div class="metric-card"><div class="val" style="color:{p_color};">¥{filt_prf:,}</div><div class="lbl">利益</div></div>
    </div>
    <div style="font-size:.78rem;color:#6b7280;margin:.3rem 0;">集計期間: <strong>{period_label}</strong></div>
    """, unsafe_allow_html=True)

# ── 集計単位ごとの表示 ────────────────────────────────────────────────────────
if view_by == "日別":
    st.markdown('<div class="section-head">日別売上（修正1: Patreonは契約開始日に計上）</div>', unsafe_allow_html=True)

    date_list = []
    cur_d = f_from
    while cur_d <= f_to and len(date_list) < 366:
        date_list.append(cur_d); cur_d += timedelta(days=1)

    rows_d = []
    for d in date_list:
        ds = d.strftime("%Y-%m-%d")
        # 修正1: 契約開始日のみに計上（日割りしない）
        pat_d = calc_patreon_daily_by_contract(df_subs, ds) if f_biz in ("すべて","Patreon") else 0
        row = {"日付": ds, "Patreon": pat_d}
        if not filt_p.empty:
            day_df = filt_p[filt_p["date_str"] == ds]
            for biz in day_df["business"].unique():
                row[biz] = int(day_df[day_df["business"]==biz]["amount"].sum())
        rows_d.append(row)

    df_d = pd.DataFrame(rows_d).set_index("日付").fillna(0)
    df_d["合計"] = df_d.sum(axis=1)
    non_zero_d   = df_d[df_d["合計"] > 0]

    if non_zero_d.empty:
        st.markdown('<div class="info-box">指定期間に売上データがありません</div>', unsafe_allow_html=True)
    else:
        # テーブル表示（Patreon欄に「契約開始日のみ」の注記）
        for idx, row in non_zero_d.iterrows():
            parts = []
            for col, val in row.items():
                if col == "合計" or val == 0: continue
                label = f"{col}（契約開始日）" if col == "Patreon" else col
                parts.append(f"{label}: ¥{int(val):,}")
            st.markdown(f"**{idx[5:]}** &nbsp; " + " &nbsp; ".join(parts) + f" &nbsp; | 合計: ¥{int(row['合計']):,}")

        st.bar_chart(non_zero_d.drop(columns=["合計"]))
        st.markdown(f'<div class="info-box">期間合計: <strong>¥{int(non_zero_d["合計"].sum()):,}</strong> &nbsp; ※Patreonは契約開始日のみ計上</div>', unsafe_allow_html=True)

elif view_by == "月別":
    st.markdown('<div class="section-head">月別売上</div>', unsafe_allow_html=True)

    # 対象月を期間から生成
    period_months = month_range_list(f_from, f_to)
    rows_m = []
    for ym in period_months:
        pat_m = patreon_monthly.get(ym, 0) if f_biz in ("すべて","Patreon") else 0
        row = {"月": ym, "Patreon（月額）": pat_m}
        if not filt_p.empty:
            m_df = filt_p[filt_p["month_str"] == ym]
            for biz in m_df["business"].unique():
                row[biz] = int(m_df[m_df["business"]==biz]["amount"].sum())
        rows_m.append(row)

    if rows_m:
        df_m = pd.DataFrame(rows_m).set_index("月").fillna(0)
        df_m["合計"] = df_m.sum(axis=1)
        non_zero_m   = df_m[df_m["合計"] > 0]
        if not non_zero_m.empty:
            st.bar_chart(non_zero_m.drop(columns=["合計"]))
            st.dataframe(df_m.astype(int), use_container_width=True)
        else:
            st.markdown('<div class="info-box">指定期間に売上データがありません</div>', unsafe_allow_html=True)

elif view_by == "年別":
    st.markdown('<div class="section-head">年別売上</div>', unsafe_allow_html=True)

    period_months = month_range_list(f_from, f_to)
    rows_m2 = []
    for ym in period_months:
        pat_m = patreon_monthly.get(ym, 0) if f_biz in ("すべて","Patreon") else 0
        row = {"月": ym, "Patreon（月額）": pat_m}
        if not filt_p.empty:
            m_df = filt_p[filt_p["month_str"] == ym]
            for biz in m_df["business"].unique():
                row[biz] = int(m_df[m_df["business"]==biz]["amount"].sum())
        rows_m2.append(row)

    if rows_m2:
        df_m2 = pd.DataFrame(rows_m2)
        df_m2["年"] = df_m2["月"].str[:4]
        year_cols   = [c for c in df_m2.columns if c not in ["月","年"]]
        df_y        = df_m2.groupby("年")[year_cols].sum().fillna(0)
        df_y["合計"]= df_y.sum(axis=1)
        if not df_y[df_y["合計"] > 0].empty:
            st.bar_chart(df_y.drop(columns=["合計"]))
            st.dataframe(df_y.astype(int), use_container_width=True)
        else:
            st.markdown('<div class="info-box">指定期間に売上データがありません</div>', unsafe_allow_html=True)

# ── 事業別サマリー ────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">事業別サマリー</div>', unsafe_allow_html=True)

# Patreon: 検索期間のMRRを表示
if f_biz in ("すべて","Patreon"):
    active_cnt = 0
    if not df_subs.empty:
        active_cnt = len(df_subs[
            df_subs["end_date"].apply(lambda x: x is None or str(x) in ("","None"))
        ])

    # 検索期間内の月別MRRを集計（今月固定ではなく選択期間に連動）
    period_months_for_mrr = month_range_list(f_from, f_to)
    period_mrr_list = {ym: patreon_monthly.get(ym, 0) for ym in period_months_for_mrr}

    # 単月選択の場合はその月のMRR、複数月の場合は月平均MRRを表示
    if len(period_mrr_list) == 1:
        # 単月: そのままMRRを表示
        display_mrr       = list(period_mrr_list.values())[0]
        display_mrr_label = f"{list(period_mrr_list.keys())[0]} MRR"
    else:
        # 複数月: 平均MRRと合計を両方表示
        mrr_values        = [v for v in period_mrr_list.values() if v > 0]
        display_mrr       = int(sum(mrr_values) / len(mrr_values)) if mrr_values else 0
        display_mrr_label = f"期間平均MRR（{len(period_mrr_list)}ヶ月）"

    # 参考: 今月のMRR
    current_mrr = patreon_monthly.get(today.strftime("%Y-%m"), 0)

    st.markdown(f"""
    <div class="metric-card" style="margin-bottom:.6rem;">
      <div style="display:flex;justify-content:space-between;margin-bottom:.4rem;">
        <span style="font-weight:700;color:#1e3a5f;">Patreon</span>
        <span style="font-size:.72rem;color:#9ca3af;">DB保存なし・動的計算</span>
      </div>
      <div style="font-size:.9rem;display:flex;gap:2rem;flex-wrap:wrap;">
        <span>{display_mrr_label}: <strong>¥{display_mrr:,}</strong></span>
        <span>期間合計: <strong>¥{filt_pat:,}</strong></span>
        <span>今月MRR（参考）: <strong>¥{current_mrr:,}</strong></span>
        <span>契約中: <strong>{active_cnt}件</strong></span>
      </div>
    </div>""", unsafe_allow_html=True)

# 他事業
if not filt_p.empty:
    for biz in sorted(filt_p["business"].unique()):
        biz_df    = filt_p[filt_p["business"] == biz]
        biz_sales = int(biz_df["amount"].sum())
        biz_rate  = round(biz_sales / filt_tot * 100, 1) if filt_tot else 0
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:.6rem;">
          <div style="display:flex;justify-content:space-between;margin-bottom:.4rem;">
            <span style="font-weight:700;color:#1e3a5f;">{biz}</span>
            <span style="font-size:.75rem;color:#9ca3af;">売上シェア {biz_rate}%</span>
          </div>
          <div style="font-size:.9rem;">売上: <strong>¥{biz_sales:,}</strong> &nbsp; 件数: <strong>{len(biz_df)}件</strong></div>
          <div style="margin-top:.4rem;background:#e5e7eb;border-radius:4px;height:5px;overflow:hidden;">
            <div style="width:{min(biz_rate,100)}%;height:100%;background:#1e3a5f;border-radius:4px;"></div>
          </div>
        </div>""", unsafe_allow_html=True)

health = "黒字" if filt_prf >= 0 else "赤字"
st.markdown(f"""
<div class="metric-card" style="margin-top:.8rem;">
  <div style="font-weight:700;color:#1e3a5f;margin-bottom:.5rem;">経営サマリー [{health}]</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:.4rem;font-size:.88rem;">
    <div>総売上: <strong>¥{filt_tot:,}</strong></div>
    <div>経費: <strong>¥{filt_exp:,}</strong></div>
    <div style="color:{p_color};">利益: <strong>¥{filt_prf:,}</strong></div>
    <div style="color:{p_color};">利益率: <strong>{round(filt_prf/filt_tot*100,1) if filt_tot else 0}%</strong></div>
  </div>
</div>""", unsafe_allow_html=True)
