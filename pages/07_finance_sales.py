"""
pages/07_finance_sales.py — 売上・経営ダッシュボード（Patreon動的計算版）
URL: /finance_sales

修正2: Patreon売上を動的計算・二重計上なし
  - patreon_subscriptions から毎回計算
  - DBに保存しない
  - 表示期間: 現在日から±12ヶ月
  - purchases（Tour/Guidebook等）+ Patreon動的計算を統合表示
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

# ── Patreon動的計算ロジック ────────────────────────────────────────────────────
def month_range_months(start: date, end: date) -> list:
    """start月からend月までの YYYY-MM リストを返す（最大24ヶ月）"""
    months = []
    cur = start.replace(day=1)
    limit = end.replace(day=1)
    count = 0
    while cur <= limit and count < 24:
        months.append(cur.strftime("%Y-%m"))
        if HAS_DATEUTIL:
            cur = cur + relativedelta(months=1)
        else:
            if cur.month == 12:
                cur = cur.replace(year=cur.year+1, month=1)
            else:
                cur = cur.replace(month=cur.month+1)
        count += 1
    return months

def calc_patreon_mrr(df_subs: pd.DataFrame, year_month: str) -> int:
    """
    対象月のPatreon売上を動的計算（DBに保存しない）
    条件:
      start_date <= 月末
      end_date IS NULL または end_date >= 月初
    無限データ対策: 現在日から未来12ヶ月を上限とする
    """
    if df_subs.empty:
        return 0

    today = date.today()
    max_future = today.replace(day=1)
    # 未来12ヶ月上限チェック
    for _ in range(12):
        if max_future.strftime("%Y-%m") == year_month:
            break
        if HAS_DATEUTIL:
            max_future = max_future + relativedelta(months=1)
        else:
            if max_future.month == 12:
                max_future = max_future.replace(year=max_future.year+1, month=1)
            else:
                max_future = max_future.replace(month=max_future.month+1)
    else:
        # 12ヶ月を超えた未来月は計上しない
        y, m = int(year_month[:4]), int(year_month[5:7])
        future_limit = today.replace(day=1)
        for _ in range(12):
            if HAS_DATEUTIL:
                future_limit = future_limit + relativedelta(months=1)
            else:
                if future_limit.month == 12:
                    future_limit = future_limit.replace(year=future_limit.year+1, month=1)
                else:
                    future_limit = future_limit.replace(month=future_limit.month+1)
        if date(y, m, 1) > future_limit:
            return 0

    y, m      = int(year_month[:4]), int(year_month[5:7])
    days      = monthrange(y, m)[1]
    ym_start  = f"{year_month}-01"
    ym_end    = f"{year_month}-{days:02d}"

    total = 0
    for _, row in df_subs.iterrows():
        s = str(row.get("start_date","") or "")
        e = str(row.get("end_date","")   or "")
        p = int(row.get("monthly_price", 0) or 0)
        if not s: continue
        if s > ym_end:  continue      # まだ開始していない
        if e and e != "None" and e < ym_start: continue  # 解約済み
        total += p
    return total

def calc_patreon_daily(df_subs: pd.DataFrame, target_date: str) -> float:
    """
    日別Patreon売上 = 月額 ÷ 当月日数（小数点以下切り捨て）
    """
    if df_subs.empty: return 0.0
    try:
        d   = date.fromisoformat(target_date[:10])
        ym  = d.strftime("%Y-%m")
        mrr = calc_patreon_mrr(df_subs, ym)
        days_in_month = monthrange(d.year, d.month)[1]
        return mrr / days_in_month
    except Exception:
        return 0.0

# ── データ取得 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=180)
def load_sales_data():
    rows_p   = sb_select("purchases",             order="-purchase_date")
    rows_pr  = sb_select("products",              order="name")
    rows_e   = sb_select("expenses",              order="-exp_date")
    rows_s   = sb_select("patreon_subscriptions", order="start_date")
    return to_df(rows_p), to_df(rows_pr), to_df(rows_e), to_df(rows_s)

df_p, df_prods, df_e, df_subs = load_sales_data()

# 商品カテゴリーを付与（purchases）
if not df_p.empty:
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
    # Patreonカテゴリーは除外（動的計算で別途加算）
    df_p_excl_pat = df_p[df_p["business"] != "Patreon"]
else:
    df_p_excl_pat = pd.DataFrame()

# ── 表示期間（現在日 ± 12ヶ月）─────────────────────────────────────────────
today      = date.today()
if HAS_DATEUTIL:
    period_start = (today.replace(day=1) + relativedelta(months=-12))
    period_end   = (today.replace(day=1) + relativedelta(months=+12))
else:
    period_start = today.replace(day=1, month=today.month, year=today.year-1)
    period_end   = today.replace(day=1)
    for _ in range(12):
        if period_end.month == 12:
            period_end = period_end.replace(year=period_end.year+1, month=1)
        else:
            period_end = period_end.replace(month=period_end.month+1)

all_months = month_range_months(period_start, period_end)

# ── Patreon月別売上を全期間で計算（動的・DB保存なし）──────────────────────────
patreon_monthly = {}
for ym in all_months:
    patreon_monthly[ym] = calc_patreon_mrr(df_subs, ym)

# 今月サマリー
current_month_str = today.strftime("%Y-%m")
patreon_mrr_now   = patreon_monthly.get(current_month_str, 0)
purchase_sales    = int(df_p_excl_pat["amount"].sum()) if not df_p_excl_pat.empty else 0
patreon_total_all = sum(patreon_monthly.values())
total_sales       = purchase_sales + patreon_total_all
total_expense     = int(df_e["amount_out"].sum()) if not df_e.empty and "amount_out" in df_e.columns else 0
profit            = total_sales - total_expense
profit_color      = "#15803d" if profit >= 0 else "#dc2626"

st.markdown(f"""<div class="metric-row">
  <div class="metric-card"><div class="val">¥{total_sales:,}</div><div class="lbl">総売上（全期間）</div></div>
  <div class="metric-card"><div class="val">¥{patreon_mrr_now:,}</div><div class="lbl">今月Patreon MRR</div></div>
  <div class="metric-card"><div class="val">¥{total_expense:,}</div><div class="lbl">総経費</div></div>
  <div class="metric-card"><div class="val" style="color:{profit_color};">¥{profit:,}</div><div class="lbl">利益</div></div>
</div>""", unsafe_allow_html=True)

tab_daily, tab_monthly, tab_yearly, tab_business = st.tabs(["日別売上","月別売上","年別売上","事業別分析"])

# ── 日別売上 ──────────────────────────────────────────────────────────────────
with tab_daily:
    st.markdown('<div class="section-head">日別 × 事業別 売上</div>', unsafe_allow_html=True)
    dc1, dc2 = st.columns(2)
    with dc1: d_from = st.date_input("開始日", value=today.replace(day=1), key="d_from")
    with dc2: d_to   = st.date_input("終了日", value=today,                key="d_to")

    # 対象日付リスト生成
    date_list = []
    cur_d     = d_from
    while cur_d <= d_to:
        date_list.append(cur_d)
        cur_d += timedelta(days=1)

    if not date_list:
        st.markdown('<div class="info-box">期間を正しく設定してください</div>', unsafe_allow_html=True)
    else:
        rows_daily = []
        for d in date_list:
            ds    = d.strftime("%Y-%m-%d")
            p_day = calc_patreon_daily(df_subs, ds)
            row   = {"日付": ds, "Patreon": round(p_day)}
            if not df_p_excl_pat.empty:
                day_df = df_p_excl_pat[df_p_excl_pat["date_str"] == ds]
                for biz in day_df["business"].unique():
                    row[biz] = int(day_df[day_df["business"]==biz]["amount"].sum())
            rows_daily.append(row)

        df_daily_disp = pd.DataFrame(rows_daily).set_index("日付").fillna(0)
        df_daily_disp["合計"] = df_daily_disp.sum(axis=1)

        # テーブル表示
        for idx, row in df_daily_disp.iterrows():
            if row["合計"] == 0: continue
            parts = [f"{col}: ¥{int(val):,}" for col, val in row.items() if col != "合計" and val > 0]
            st.markdown(f"**{idx[5:]}** &nbsp; " + " &nbsp; ".join(parts) + f" &nbsp; | &nbsp; 合計: ¥{int(row['合計']):,}")

        st.markdown('<div class="section-head">日別売上グラフ</div>', unsafe_allow_html=True)
        st.bar_chart(df_daily_disp.drop(columns=["合計"]))
        st.markdown(f'<div class="info-box">期間合計: <strong>¥{int(df_daily_disp["合計"].sum()):,}</strong></div>', unsafe_allow_html=True)

# ── 月別売上 ──────────────────────────────────────────────────────────────────
with tab_monthly:
    st.markdown('<div class="section-head">月別 × 事業別 売上（表示期間: ±12ヶ月）</div>', unsafe_allow_html=True)

    rows_monthly = []
    for ym in all_months:
        row = {"月": ym, "Patreon": patreon_monthly.get(ym, 0)}
        if not df_p_excl_pat.empty:
            m_df = df_p_excl_pat[df_p_excl_pat["month_str"] == ym]
            for biz in m_df["business"].unique():
                row[biz] = int(m_df[m_df["business"]==biz]["amount"].sum())
        rows_monthly.append(row)

    df_monthly_disp = pd.DataFrame(rows_monthly).set_index("月").fillna(0)
    df_monthly_disp["合計"] = df_monthly_disp.sum(axis=1)
    st.bar_chart(df_monthly_disp.drop(columns=["合計"]))
    st.dataframe(df_monthly_disp.astype(int), use_container_width=True)

# ── 年別売上 ──────────────────────────────────────────────────────────────────
with tab_yearly:
    st.markdown('<div class="section-head">年別 × 事業別 売上</div>', unsafe_allow_html=True)

    # 月別データから年別に集計
    df_m_tmp = pd.DataFrame(rows_monthly) if rows_monthly else pd.DataFrame()
    if not df_m_tmp.empty:
        df_m_tmp["年"] = df_m_tmp["月"].str[:4]
        year_cols = [c for c in df_m_tmp.columns if c not in ["月","年"]]
        df_yearly_disp = df_m_tmp.groupby("年")[year_cols].sum().fillna(0)
        df_yearly_disp["合計"] = df_yearly_disp.sum(axis=1)
        st.bar_chart(df_yearly_disp.drop(columns=["合計"]))
        st.dataframe(df_yearly_disp.astype(int), use_container_width=True)

# ── 事業別分析 ────────────────────────────────────────────────────────────────
with tab_business:
    st.markdown('<div class="section-head">事業別 売上 vs 経費</div>', unsafe_allow_html=True)

    # Patreon
    pat_total = sum(patreon_monthly.values())
    active_subs = len(df_subs[
        df_subs["end_date"].isna() | (df_subs["end_date"]=="") | (df_subs["end_date"]=="None")
    ]) if not df_subs.empty else 0

    st.markdown(f"""
    <div class="metric-card" style="margin-bottom:.6rem;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
        <span style="font-weight:700;font-size:1rem;color:#1e3a5f;">Patreon（動的計算）</span>
        <span style="font-size:.75rem;color:#9ca3af;">契約中: {active_subs}件</span>
      </div>
      <div style="display:flex;gap:2rem;font-size:.9rem;flex-wrap:wrap;">
        <span>今月MRR: <strong>¥{patreon_mrr_now:,}</strong></span>
        <span>期間合計: <strong>¥{pat_total:,}</strong></span>
        <span style="font-size:.75rem;color:#9ca3af;">※DB保存なし・毎回動的計算</span>
      </div>
    </div>""", unsafe_allow_html=True)

    # 他事業
    if not df_p_excl_pat.empty:
        all_biz = df_p_excl_pat["business"].unique().tolist()
        for biz in all_biz:
            biz_df    = df_p_excl_pat[df_p_excl_pat["business"] == biz]
            biz_sales = int(biz_df["amount"].sum())
            biz_rate  = round(biz_sales / total_sales * 100, 1) if total_sales else 0
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:.6rem;">
              <div style="display:flex;justify-content:space-between;margin-bottom:.4rem;">
                <span style="font-weight:700;color:#1e3a5f;">{biz}</span>
                <span style="font-size:.75rem;color:#9ca3af;">売上シェア {biz_rate}%</span>
              </div>
              <div style="font-size:.9rem;">
                売上: <strong>¥{biz_sales:,}</strong> &nbsp; 件数: <strong>{len(biz_df)}件</strong>
              </div>
              <div style="margin-top:.4rem;background:#e5e7eb;border-radius:4px;height:5px;">
                <div style="width:{biz_rate}%;height:100%;background:#1e3a5f;border-radius:4px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

    health = "黒字" if profit >= 0 else "赤字"
    st.markdown(f"""
    <div class="metric-card" style="margin-top:1rem;">
      <div style="font-size:1rem;font-weight:700;color:#1e3a5f;margin-bottom:.6rem;">経営サマリー [{health}]</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;font-size:.88rem;">
        <div>総売上: <strong>¥{total_sales:,}</strong></div>
        <div>総経費: <strong>¥{total_expense:,}</strong></div>
        <div style="color:{profit_color};">利益: <strong>¥{profit:,}</strong></div>
        <div>今月MRR: <strong>¥{patreon_mrr_now:,}</strong></div>
      </div>
    </div>""", unsafe_allow_html=True)
