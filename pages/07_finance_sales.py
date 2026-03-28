"""
pages/07_finance_sales.py — 売上・経営ダッシュボード

修正2: Patreon日別売上ロジック修正
  - 月別売上 = monthly_price をその月に1回だけ計上（実売上）
  - 日別売上 = monthly_price ÷ 月日数（表示のみ・参考値）
  - DB保存なし・動的計算のみ

修正3: 検索機能追加
  - 事業別 / 年 / 月 / 日 でフィルタリング
  - フィルタ範囲で総売上・経費・利益を動的計算
  - Patreon動的計算を含めて統合表示
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
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)

def month_range_list(start: date, end: date) -> list:
    months = []
    cur    = start.replace(day=1)
    limit  = end.replace(day=1)
    count  = 0
    while cur <= limit and count < 25:
        months.append(cur.strftime("%Y-%m"))
        cur = add_months(cur, 1)
        count += 1
    return months

# ── 修正2: Patreon月別売上（実売上 = 月に1回だけ計上）────────────────────────
def calc_patreon_mrr(df_subs: pd.DataFrame, year_month: str) -> int:
    """
    実売上ロジック:
      start_date <= 月末 AND (end_date IS NULL OR end_date >= 月初)
    → monthly_price を合計（月に1回だけ計上）
    DB保存なし・毎回動的計算
    無限データ対策: 現在日から未来12ヶ月を上限
    """
    if df_subs.empty:
        return 0
    today         = date.today()
    future_limit  = add_months(today.replace(day=1), 12)
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

    total = 0
    for _, row in df_subs.iterrows():
        s = str(row.get("start_date","") or "")
        e = str(row.get("end_date","")   or "")
        p = int(row.get("monthly_price", 0) or 0)
        if not s:                                                  continue
        if s > ym_end:                                             continue
        if e and e not in ("None","") and e < ym_start:           continue
        total += p
    return total

def calc_patreon_daily_ref(df_subs: pd.DataFrame, target_date: str) -> float:
    """
    修正2: 日別は参考値のみ（実売上ではない）
    = 月額MRR ÷ 当月日数
    """
    if df_subs.empty:
        return 0.0
    try:
        d    = date.fromisoformat(target_date[:10])
        ym   = d.strftime("%Y-%m")
        mrr  = calc_patreon_mrr(df_subs, ym)
        days = monthrange(d.year, d.month)[1]
        return mrr / days
    except Exception:
        return 0.0

# ── データ取得（3分キャッシュ）────────────────────────────────────────────────
@st.cache_data(ttl=180)
def load_sales_data():
    rows_p  = sb_select("purchases",             order="-purchase_date")
    rows_pr = sb_select("products",              order="name")
    rows_e  = sb_select("expenses",              order="-exp_date")
    rows_s  = sb_select("patreon_subscriptions", order="start_date")
    return to_df(rows_p), to_df(rows_pr), to_df(rows_e), to_df(rows_s)

df_p_raw, df_prods, df_e, df_subs = load_sales_data()

# purchases を前処理
if not df_p_raw.empty:
    df_p = df_p_raw.copy()
    for col in ["amount"]:
        if col not in df_p.columns: df_p[col] = 0
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

# 表示期間（±12ヶ月）
today         = date.today()
period_start  = add_months(today.replace(day=1), -12)
period_end    = add_months(today.replace(day=1), 12)
all_months    = month_range_list(period_start, period_end)

# Patreon月別MRR（全期間・事前計算）
patreon_monthly = {ym: calc_patreon_mrr(df_subs, ym) for ym in all_months}

# ── 修正3: 検索フィルター ─────────────────────────────────────────────────────
st.markdown('<div class="section-head">検索・絞り込み</div>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns(4)

with fc1:
    all_biz_opts = ["すべて"] + (sorted(df_p_excl_pat["business"].unique().tolist()) if not df_p_excl_pat.empty else []) + ["Patreon"]
    f_biz = st.selectbox("事業", all_biz_opts, key="f_biz")
with fc2:
    year_opts = ["すべて"] + sorted({ym[:4] for ym in all_months}, reverse=True)
    f_year    = st.selectbox("年", year_opts, key="f_year")
with fc3:
    month_opts = ["すべて"] + [f"{m:02d}" for m in range(1,13)]
    f_month    = st.selectbox("月", month_opts, key="f_month")
with fc4:
    f_date = st.text_input("日 (YYYY-MM-DD・任意)", placeholder="例: 2026-03-15", key="f_date")

# ── フィルタリング後の集計関数 ────────────────────────────────────────────────
def filtered_months() -> list:
    """フィルター条件に合う月リストを返す"""
    result = []
    for ym in all_months:
        y, m = ym[:4], ym[5:7]
        if f_year != "すべて" and y != f_year: continue
        if f_month != "すべて" and m != f_month: continue
        if f_date and not f_date[:7] == ym: continue
        result.append(ym)
    return result

def filtered_purchase_df() -> pd.DataFrame:
    """フィルター条件でpurchasesを絞り込む"""
    if df_p_excl_pat.empty: return pd.DataFrame()
    df = df_p_excl_pat.copy()
    if f_biz != "すべて" and f_biz != "Patreon": df = df[df["business"] == f_biz]
    if f_biz == "Patreon": return pd.DataFrame()  # Patreonは動的計算
    if f_year  != "すべて": df = df[df["year_str"]  == f_year]
    if f_month != "すべて": df = df[df["month_str"].str[5:7] == f_month]
    if f_date:              df = df[df["date_str"] == f_date[:10]]
    return df

def filtered_expense_df() -> pd.DataFrame:
    if df_e.empty or "amount_out" not in df_e.columns: return pd.DataFrame()
    de = df_e.copy()
    if "exp_date" not in de.columns: return de
    if f_year  != "すべて": de = de[de["exp_date"].astype(str).str[:4]  == f_year]
    if f_month != "すべて": de = de[de["exp_date"].astype(str).str[5:7] == f_month]
    if f_date:              de = de[de["exp_date"].astype(str).str[:10] == f_date[:10]]
    return de

# フィルター後の集計
filt_months  = filtered_months()
filt_df_p    = filtered_purchase_df()
filt_df_e    = filtered_expense_df()
filt_pat_sum = sum(patreon_monthly.get(ym,0) for ym in filt_months) if f_biz in ("すべて","Patreon") else 0
filt_pur_sum = int(filt_df_p["amount"].sum()) if not filt_df_p.empty else 0
filt_total   = filt_pur_sum + filt_pat_sum
filt_expense = int(filt_df_e["amount_out"].sum()) if not filt_df_e.empty else 0
filt_profit  = filt_total - filt_expense
profit_color = "#15803d" if filt_profit >= 0 else "#dc2626"

# フィルター後サマリー
filter_label = f"{f_year if f_year!='すべて' else '全期間'}{'/'+f_month+'月' if f_month!='すべて' else ''}{' '+f_biz if f_biz!='すべて' else ''}"
st.markdown(f"""<div class="metric-row">
  <div class="metric-card"><div class="val">¥{filt_total:,}</div><div class="lbl">総売上 ({filter_label})</div></div>
  <div class="metric-card"><div class="val">¥{filt_pat_sum:,}</div><div class="lbl">Patreon売上</div></div>
  <div class="metric-card"><div class="val">¥{filt_expense:,}</div><div class="lbl">経費</div></div>
  <div class="metric-card"><div class="val" style="color:{profit_color};">¥{filt_profit:,}</div><div class="lbl">利益</div></div>
</div>""", unsafe_allow_html=True)

tab_daily, tab_monthly, tab_yearly, tab_business = st.tabs(["日別売上","月別売上","年別売上","事業別分析"])

# ── 日別売上 ──────────────────────────────────────────────────────────────────
with tab_daily:
    st.markdown('<div class="section-head">日別売上</div>', unsafe_allow_html=True)
    dc1, dc2 = st.columns(2)
    with dc1: d_from = st.date_input("開始日", value=today.replace(day=1), key="d_from")
    with dc2: d_to   = st.date_input("終了日", value=today,                key="d_to")

    date_list = []
    cur_d     = d_from
    while cur_d <= d_to and len(date_list) < 366:
        date_list.append(cur_d); cur_d += timedelta(days=1)

    if date_list:
        rows_daily = []
        for d in date_list:
            ds    = d.strftime("%Y-%m-%d")
            # 修正2: 日別Patreonは参考値として表示（実売上は月別）
            p_ref = round(calc_patreon_daily_ref(df_subs, ds)) if f_biz in ("すべて","Patreon") else 0
            row   = {"日付": ds, "Patreon（参考）": p_ref}
            if not filt_df_p.empty:
                day_df = filt_df_p[filt_df_p["date_str"] == ds]
                for biz in day_df["business"].unique():
                    row[biz] = int(day_df[day_df["business"]==biz]["amount"].sum())
            rows_daily.append(row)

        df_daily_disp = pd.DataFrame(rows_daily).set_index("日付").fillna(0)
        df_daily_disp["合計"] = df_daily_disp.sum(axis=1)

        # 表示（合計0の日は省略）
        for idx, row in df_daily_disp.iterrows():
            if row["合計"] == 0: continue
            parts = [f"{col}: ¥{int(val):,}" for col, val in row.items() if col != "合計" and val > 0]
            st.markdown(f"**{idx[5:]}** &nbsp; " + " &nbsp; ".join(parts) + f" &nbsp; | &nbsp; 合計: ¥{int(row['合計']):,}")

        non_zero = df_daily_disp[df_daily_disp["合計"] > 0]
        if not non_zero.empty:
            st.bar_chart(non_zero.drop(columns=["合計"]))

        st.markdown(
            f'<div class="info-box">期間合計: <strong>¥{int(df_daily_disp["合計"].sum()):,}</strong>'
            f'&nbsp; ※Patreonの日別は参考値（実売上は月別タブを参照）</div>',
            unsafe_allow_html=True
        )

# ── 月別売上（修正2: Patreonは月に1回だけ計上） ──────────────────────────────
with tab_monthly:
    st.markdown('<div class="section-head">月別売上（Patreonは月額を1回計上）</div>', unsafe_allow_html=True)
    rows_monthly = []
    for ym in filt_months:
        # 修正2: calc_patreon_mrr = 月額を1回だけ計上（日割りしない）
        pat_val = patreon_monthly.get(ym, 0) if f_biz in ("すべて","Patreon") else 0
        row = {"月": ym, "Patreon（月額）": pat_val}
        if not filt_df_p.empty:
            m_df = filt_df_p[filt_df_p["month_str"] == ym]
            for biz in m_df["business"].unique():
                row[biz] = int(m_df[m_df["business"]==biz]["amount"].sum())
        rows_monthly.append(row)

    if rows_monthly:
        df_m = pd.DataFrame(rows_monthly).set_index("月").fillna(0)
        df_m["合計"] = df_m.sum(axis=1)
        non_zero_m = df_m[df_m["合計"] > 0]
        if not non_zero_m.empty:
            st.bar_chart(non_zero_m.drop(columns=["合計"]))
        st.dataframe(df_m.astype(int), use_container_width=True)

# ── 年別売上 ──────────────────────────────────────────────────────────────────
with tab_yearly:
    st.markdown('<div class="section-head">年別売上</div>', unsafe_allow_html=True)
    if rows_monthly:
        df_m_tmp = pd.DataFrame(rows_monthly)
        df_m_tmp["年"] = df_m_tmp["月"].str[:4]
        year_cols = [c for c in df_m_tmp.columns if c not in ["月","年"]]
        df_y = df_m_tmp.groupby("年")[year_cols].sum().fillna(0)
        df_y["合計"] = df_y.sum(axis=1)
        if not df_y.empty:
            st.bar_chart(df_y.drop(columns=["合計"]))
            st.dataframe(df_y.astype(int), use_container_width=True)

# ── 事業別分析 ────────────────────────────────────────────────────────────────
with tab_business:
    st.markdown('<div class="section-head">事業別 売上 vs 経費</div>', unsafe_allow_html=True)

    # Patreon（動的計算・修正2）
    if f_biz in ("すべて","Patreon"):
        active_cnt = len(df_subs[
            df_subs["end_date"].isna() | (df_subs["end_date"]=="") | (df_subs["end_date"]=="None")
        ]) if not df_subs.empty else 0
        current_mrr = patreon_monthly.get(today.strftime("%Y-%m"), 0)
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:.6rem;">
          <div style="display:flex;justify-content:space-between;margin-bottom:.4rem;">
            <span style="font-weight:700;color:#1e3a5f;">Patreon</span>
            <span style="font-size:.72rem;color:#9ca3af;">動的計算 / DB保存なし / 月額1回計上</span>
          </div>
          <div style="font-size:.9rem;display:flex;gap:2rem;flex-wrap:wrap;">
            <span>今月MRR: <strong>¥{current_mrr:,}</strong></span>
            <span>契約中: <strong>{active_cnt}件</strong></span>
            <span>フィルター期間合計: <strong>¥{filt_pat_sum:,}</strong></span>
          </div>
        </div>""", unsafe_allow_html=True)

    # 他事業
    if not filt_df_p.empty:
        for biz in sorted(filt_df_p["business"].unique()):
            biz_df    = filt_df_p[filt_df_p["business"] == biz]
            biz_sales = int(biz_df["amount"].sum())
            biz_rate  = round(biz_sales / filt_total * 100, 1) if filt_total else 0
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:.6rem;">
              <div style="display:flex;justify-content:space-between;margin-bottom:.4rem;">
                <span style="font-weight:700;color:#1e3a5f;">{biz}</span>
                <span style="font-size:.75rem;color:#9ca3af;">売上シェア {biz_rate}%</span>
              </div>
              <div style="font-size:.9rem;">
                売上: <strong>¥{biz_sales:,}</strong> &nbsp; 件数: <strong>{len(biz_df)}件</strong>
              </div>
              <div style="margin-top:.4rem;background:#e5e7eb;border-radius:4px;height:5px;overflow:hidden;">
                <div style="width:{biz_rate}%;height:100%;background:#1e3a5f;border-radius:4px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

    health = "黒字" if filt_profit >= 0 else "赤字"
    st.markdown(f"""
    <div class="metric-card" style="margin-top:.8rem;">
      <div style="font-weight:700;color:#1e3a5f;margin-bottom:.5rem;">経営サマリー [{health}] — {filter_label}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.4rem;font-size:.88rem;">
        <div>総売上: <strong>¥{filt_total:,}</strong></div>
        <div>経費: <strong>¥{filt_expense:,}</strong></div>
        <div style="color:{profit_color};">利益: <strong>¥{filt_profit:,}</strong></div>
        <div style="color:{profit_color};">利益率: <strong>{round(filt_profit/filt_total*100,1) if filt_total else 0}%</strong></div>
      </div>
    </div>""", unsafe_allow_html=True)
