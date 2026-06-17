"""
pages/15_travel_demand.py — Travel Demand Score ダッシュボード

自社シグナル（dm_daily / concierge / purchases）と
市場シグナル（competitor_posts / competitor_history）を統合し
旅行需要スコアを算出・可視化する。
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_upsert

st.set_page_config(page_title="Travel Demand | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">Travel Demand Score</div>', unsafe_allow_html=True)
st.caption("自社フォロワーの関心（自社シグナル）と市場全体の需要（市場シグナル）を統合した旅行需要指標")

# ── スコア計算ロジック ────────────────────────────────────────────────────────
def safe_growth(old, new):
    if old <= 0: return 0.0
    return round((new - old) / old * 100, 2)

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))

@st.cache_data(ttl=300)
def load_all():
    # dm_daily（dm_count → count にリネーム）
    dm_raw = to_df(sb_select("dm_daily", order="date", columns="id,date,platform,dm_count"))
    if not dm_raw.empty and "dm_count" in dm_raw.columns:
        dm_raw = dm_raw.rename(columns={"dm_count": "count"})
        dm_raw["count"] = pd.to_numeric(dm_raw["count"], errors="coerce").fillna(0).astype(int)

    comp_posts = to_df(sb_select("competitor_posts",   order="-post_date"))
    comp_hist  = to_df(sb_select("competitor_history", order="recorded_date"))
    comp_acc   = to_df(sb_select("competitor_accounts", order="username"))
    purchases  = to_df(sb_select("purchases",          order="-purchase_date"))

    # concierge（テーブルが無い場合は空）
    try:
        concierge = to_df(sb_select("concierge_sessions", order="-created_at"))
    except Exception:
        concierge = pd.DataFrame()

    return dm_raw, comp_posts, comp_hist, comp_acc, purchases, concierge

dm_df, comp_posts, comp_hist, comp_acc, purchases, concierge = load_all()

# ── 期間選択 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">分析期間</div>', unsafe_allow_html=True)
pc1, pc2 = st.columns(2)
with pc1:
    period_weeks = st.selectbox("比較期間", ["直近4週", "直近8週", "直近12週"], index=0)
    weeks_n = {"直近4週": 4, "直近8週": 8, "直近12週": 12}[period_weeks]
with pc2:
    st.caption(f"本日 {date.today()} を基準に過去{weeks_n}週を分析")

today      = date.today()
period_end = today
period_mid = today - timedelta(days=7)       # 直近1週
prev_start = today - timedelta(days=14)       # 前週

# ════════════════════════════════════════════════════════
# 自社シグナルの計算
# ════════════════════════════════════════════════════════
own_signal     = 0.0
dm_growth      = 0.0
concierge_cnt  = 0
purchase_conv  = 0.0

if not dm_df.empty:
    dm_df["date"] = dm_df["date"].astype(str)
    # 直近7日と前7日のDM数を比較
    recent_dm = dm_df[dm_df["date"] >= str(period_mid)]["count"].sum()
    prev_dm   = dm_df[(dm_df["date"] >= str(prev_start)) & (dm_df["date"] < str(period_mid))]["count"].sum()
    dm_growth = safe_growth(prev_dm, recent_dm)

# AI相談セッション数
if not concierge.empty and "created_at" in concierge.columns:
    concierge["created_at"] = concierge["created_at"].astype(str)
    concierge_cnt = len(concierge[concierge["created_at"] >= str(period_mid)])

# 購買コンバージョン（直近の購買数）
if not purchases.empty:
    purchases["purchase_date"] = purchases["purchase_date"].astype(str)
    recent_purchases = len(purchases[purchases["purchase_date"] >= str(period_mid)])
    purchase_conv    = recent_purchases

# 自社シグナルスコア（0-100に正規化）
# DM増加率を主軸に、セッション・購買を加点
own_signal = clamp(
    50  # ベースライン
    + dm_growth * 0.4       # DM増加率
    + concierge_cnt * 2     # セッション1件=2点
    + purchase_conv * 3     # 購買1件=3点
)

# ════════════════════════════════════════════════════════
# 市場シグナルの計算（競合データ）
# ════════════════════════════════════════════════════════
market_signal         = 0.0
comp_likes_growth     = 0.0
comp_comments_growth  = 0.0
comp_followers_growth = 0.0

if not comp_posts.empty:
    comp_posts["post_date"] = comp_posts["post_date"].astype(str)
    comp_posts["likes"]     = pd.to_numeric(comp_posts["likes"],    errors="coerce").fillna(0)
    comp_posts["comments"]  = pd.to_numeric(comp_posts["comments"], errors="coerce").fillna(0)

    recent_posts = comp_posts[comp_posts["post_date"] >= str(period_mid)]
    prev_posts   = comp_posts[(comp_posts["post_date"] >= str(prev_start)) & (comp_posts["post_date"] < str(period_mid))]

    if not recent_posts.empty and not prev_posts.empty:
        comp_likes_growth    = safe_growth(prev_posts["likes"].mean(),    recent_posts["likes"].mean())
        comp_comments_growth = safe_growth(prev_posts["comments"].mean(), recent_posts["comments"].mean())

# 競合フォロワー増加率
if not comp_hist.empty:
    comp_hist["recorded_date"] = comp_hist["recorded_date"].astype(str)
    comp_hist["followers"]     = pd.to_numeric(comp_hist["followers"], errors="coerce").fillna(0)
    # 最新2ヶ月を比較
    recent_months = sorted(comp_hist["recorded_date"].str[:7].unique())[-2:]
    if len(recent_months) == 2:
        old_f = comp_hist[comp_hist["recorded_date"].str[:7] == recent_months[0]]["followers"].mean()
        new_f = comp_hist[comp_hist["recorded_date"].str[:7] == recent_months[1]]["followers"].mean()
        comp_followers_growth = safe_growth(old_f, new_f)

# 市場シグナルスコア（0-100に正規化）
market_signal = clamp(
    50  # ベースライン
    + comp_likes_growth * 0.35
    + comp_comments_growth * 0.45  # コメントは高関心の指標なので重み大
    + comp_followers_growth * 0.20
)

# ════════════════════════════════════════════════════════
# 統合 Travel Demand Score
# ════════════════════════════════════════════════════════
demand_score = round(own_signal * 0.5 + market_signal * 0.5, 1)

# スコアの解釈
if demand_score >= 80:
    score_label, score_color, action = "需要急増", "#15803d", "今すぐ広告投下・在庫確保のタイミング"
elif demand_score >= 60:
    score_label, score_color, action = "需要上昇中", "#16a34a", "コンテンツ強化で需要を取り込む好機"
elif demand_score >= 40:
    score_label, score_color, action = "横ばい", "#d97706", "市場は安定。差別化施策を検討"
else:
    score_label, score_color, action = "需要低下", "#dc2626", "原因分析と施策転換が必要"

# ── メインスコア表示 ──────────────────────────────────────────────────────────
st.markdown('<div class="section-head">統合 Travel Demand Score</div>', unsafe_allow_html=True)
st.markdown(f"""
<div style="text-align:center;padding:2rem;border:2px solid {score_color};border-radius:16px;margin-bottom:1rem;">
  <div style="font-size:4rem;font-weight:800;color:{score_color};line-height:1;">{demand_score}</div>
  <div style="font-size:1.2rem;font-weight:700;color:{score_color};margin-top:.5rem;">{score_label}</div>
  <div style="font-size:.9rem;color:#6b7280;margin-top:.5rem;">{action}</div>
</div>
""", unsafe_allow_html=True)

# 自社 vs 市場の内訳
sc1, sc2 = st.columns(2)
with sc1:
    st.markdown(f"""<div class="metric-card">
      <div class="val" style="color:#1e3a5f;">{own_signal:.1f}</div>
      <div class="lbl">自社シグナル（自分のフォロワーの関心）</div>
    </div>""", unsafe_allow_html=True)
with sc2:
    st.markdown(f"""<div class="metric-card">
      <div class="val" style="color:#7c3aed;">{market_signal:.1f}</div>
      <div class="lbl">市場シグナル（競合含む市場全体）</div>
    </div>""", unsafe_allow_html=True)

# ── 内訳詳細 ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">シグナル内訳</div>', unsafe_allow_html=True)

dc1, dc2 = st.columns(2)
with dc1:
    st.markdown("**自社シグナル**")
    dm_col = "#15803d" if dm_growth >= 0 else "#dc2626"
    st.markdown(f"""<div style="font-size:.9rem;line-height:1.8;">
      DM数増加率（前週比）: <strong style="color:{dm_col};">{dm_growth:+.1f}%</strong><br>
      AI相談セッション数（直近7日）: <strong>{concierge_cnt}件</strong><br>
      購買コンバージョン（直近7日）: <strong>{int(purchase_conv)}件</strong>
    </div>""", unsafe_allow_html=True)
with dc2:
    st.markdown("**市場シグナル（競合データ）**")
    lk_col = "#15803d" if comp_likes_growth >= 0 else "#dc2626"
    cm_col = "#15803d" if comp_comments_growth >= 0 else "#dc2626"
    fl_col = "#15803d" if comp_followers_growth >= 0 else "#dc2626"
    st.markdown(f"""<div style="font-size:.9rem;line-height:1.8;">
      競合いいね増加率: <strong style="color:{lk_col};">{comp_likes_growth:+.1f}%</strong><br>
      競合コメント増加率: <strong style="color:{cm_col};">{comp_comments_growth:+.1f}%</strong><br>
      競合フォロワー増加率: <strong style="color:{fl_col};">{comp_followers_growth:+.1f}%</strong>
    </div>""", unsafe_allow_html=True)

# ── 自動インサイト ────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">需要インサイト（自動生成）</div>', unsafe_allow_html=True)
insights = []

# 自社 vs 市場のギャップ分析
if own_signal > market_signal + 10:
    insights.append(("info", "📊 自社の関心が市場全体を上回っています。自社ブランドの一時的な人気の可能性があり、市場全体のトレンドではないかもしれません。持続性を見極めてください。"))
elif market_signal > own_signal + 10:
    insights.append(("err", "⚠️ 市場全体の需要が自社の関心を上回っています。競合が需要を取り込んでいる可能性があります。コンテンツ戦略の見直しを検討してください。"))
else:
    insights.append(("success", "✅ 自社シグナルと市場シグナルが一致しています。これは本物の需要トレンドである可能性が高く、信頼できるシグナルです。"))

# DMとコメントの両方が上昇 = 強い需要
if dm_growth > 10 and comp_comments_growth > 10:
    insights.append(("success", "🔥 自社DM・競合コメントが同時に急増しています。市場全体で旅行需要が高まっている強いシグナルです。今が広告・コンテンツ投資の好機です。"))

# コメント増加（高関心シグナル）
if comp_comments_growth > 15:
    insights.append(("success", f"💬 競合コメントが{comp_comments_growth:+.0f}%増加。コメントは「予約方法」「料金」など購買意欲の直接指標です。需要が購買段階に近づいています。"))

# 需要低下警告
if demand_score < 40:
    insights.append(("err", "📉 総合需要スコアが低下しています。シーズンオフまたは市場の関心低下が考えられます。需要喚起施策を検討してください。"))

for box_type, msg in insights:
    css = "success-box" if box_type == "success" else ("err-box" if box_type == "err" else "info-box")
    st.markdown(f'<div class="{css}">{msg}</div>', unsafe_allow_html=True)

# ── 地域別需要（competitor location活用）────────────────────────────────────
st.markdown('<div class="section-head">発信地別 需要スコア</div>', unsafe_allow_html=True)
st.caption("競合アカウントの発信地別エンゲージメントから地域需要を算出")

if not comp_acc.empty and not comp_posts.empty:
    # アカウントIDを統一
    comp_acc["id"] = pd.to_numeric(comp_acc["id"], errors="coerce").fillna(-1).astype(int)
    comp_posts["account_id"] = pd.to_numeric(comp_posts["account_id"], errors="coerce").fillna(-1).astype(int)

    # 投稿に発信地を紐付け
    posts_with_loc = comp_posts.merge(
        comp_acc[["id","location","content_region"]].rename(columns={"id":"account_id"}),
        on="account_id", how="left"
    )
    posts_with_loc["loc"] = posts_with_loc["location"].fillna("") + posts_with_loc["content_region"].fillna("")
    posts_with_loc["loc"] = posts_with_loc["loc"].str[:4].replace("", "不明")
    posts_with_loc["engagement"] = posts_with_loc["likes"] + posts_with_loc["comments"]

    # 直近の地域別エンゲージメント
    recent_loc = posts_with_loc[posts_with_loc["post_date"] >= str(period_mid)]
    if not recent_loc.empty:
        loc_demand = recent_loc.groupby("loc").agg(
            投稿数=("engagement","count"),
            平均エンゲージメント=("engagement","mean"),
            総いいね=("likes","sum"),
            総コメント=("comments","sum"),
        ).round(0).sort_values("平均エンゲージメント", ascending=False)

        if not loc_demand.empty:
            st.dataframe(loc_demand, use_container_width=True)
            st.bar_chart(loc_demand["平均エンゲージメント"])

            top_loc = loc_demand.index[0]
            st.markdown(
                f'<div class="success-box">📍 現在最も需要が高い地域: <strong>{top_loc}</strong>'
                f'（平均エンゲージメント {loc_demand.iloc[0]["平均エンゲージメント"]:.0f}）</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown('<div class="info-box">直近7日の競合投稿データがありません。競合分析ページで投稿を記録してください。</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="info-box">競合データを蓄積すると地域別需要が表示されます</div>', unsafe_allow_html=True)

# ── スコアを保存 ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">スコアを記録</div>', unsafe_allow_html=True)
st.caption("週次でスコアを保存すると、需要の推移を時系列で分析できます")

if st.button("今週のスコアを保存する"):
    week_label = today.strftime("%Y-W%V")
    res = sb_upsert("demand_scores", {
        "period_type":           "weekly",
        "period_label":          week_label,
        "period_start":          str(period_mid),
        "period_end":            str(period_end),
        "dimension_type":        "overall",
        "dimension_value":       "all",
        "demand_score":          demand_score,
        "own_signal":            own_signal,
        "dm_growth":             dm_growth,
        "concierge_count":       concierge_cnt,
        "purchase_conv":         purchase_conv,
        "market_signal":         market_signal,
        "comp_likes_growth":     comp_likes_growth,
        "comp_comments_growth":  comp_comments_growth,
        "comp_followers_growth": comp_followers_growth,
    })
    if res:
        st.markdown(f'<div class="success-box">✅ {week_label} のスコア（{demand_score}）を保存しました</div>', unsafe_allow_html=True)
        st.cache_data.clear()
    else:
        st.markdown('<div class="err-box">保存に失敗しました。demand_scoresテーブルが作成されているか確認してください。</div>', unsafe_allow_html=True)

# ── スコア推移 ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-head">需要スコア推移</div>', unsafe_allow_html=True)
try:
    df_scores = to_df(sb_select("demand_scores", order="period_start"))
    if not df_scores.empty:
        df_scores_overall = df_scores[df_scores["dimension_type"] == "overall"].copy()
        if not df_scores_overall.empty:
            df_scores_overall["demand_score"] = pd.to_numeric(df_scores_overall["demand_score"], errors="coerce")
            chart_data = df_scores_overall.set_index("period_label")[["demand_score","own_signal","market_signal"]]
            for c in ["own_signal","market_signal"]:
                chart_data[c] = pd.to_numeric(chart_data[c], errors="coerce")
            st.line_chart(chart_data)
            st.dataframe(
                df_scores_overall[["period_label","demand_score","own_signal","market_signal","dm_growth","comp_comments_growth"]].rename(columns={
                    "period_label":"週","demand_score":"総合スコア","own_signal":"自社","market_signal":"市場",
                    "dm_growth":"DM増加率(%)","comp_comments_growth":"競合コメント増加率(%)"
                }).sort_values("週", ascending=False),
                use_container_width=True, hide_index=True
            )
    else:
        st.markdown('<div class="info-box">スコアを保存すると推移グラフが表示されます</div>', unsafe_allow_html=True)
except Exception:
    st.markdown('<div class="info-box">demand_scoresテーブルを作成してください</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 既存データ活用：季節性・カテゴリー別需要分析
# ════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div class="page-title" style="font-size:1.4rem;">需要パターン分析（過去データ）</div>', unsafe_allow_html=True)
st.caption("購買履歴・DM履歴から需要の季節性・傾向を分析します")

# ── ① 月別需要パターン（季節性）──────────────────────────────────────────────
st.markdown('<div class="section-head">月別需要パターン（季節性）</div>', unsafe_allow_html=True)
if not purchases.empty:
    pur = purchases.copy()
    pur["purchase_date"] = pd.to_datetime(pur["purchase_date"], errors="coerce")
    pur = pur.dropna(subset=["purchase_date"])
    pur["amount"] = pd.to_numeric(pur["amount"], errors="coerce").fillna(0)
    # キャンセル除外
    if "tour_status" in pur.columns:
        pur = pur[pur["tour_status"] != "キャンセル"]
    # Patreon除外
    if "product_type" in pur.columns:
        pur = pur[pur["product_type"] != "Patreon"]

    pur["month"] = pur["purchase_date"].dt.month
    monthly_demand = pur.groupby("month").agg(
        購買件数=("amount", "count"),
        売上=("amount", "sum"),
        平均単価=("amount", "mean"),
    ).round(0)
    # 1-12月を網羅
    monthly_demand = monthly_demand.reindex(range(1, 13), fill_value=0)
    monthly_demand.index = [f"{m}月" for m in monthly_demand.index]

    st.bar_chart(monthly_demand["購買件数"])

    # 最需要月を特定
    if monthly_demand["購買件数"].sum() > 0:
        peak_month = monthly_demand["購買件数"].idxmax()
        low_month  = monthly_demand[monthly_demand["購買件数"] > 0]["購買件数"].idxmin() if (monthly_demand["購買件数"] > 0).any() else "—"
        st.markdown(
            f'<div class="success-box">📈 最も需要が高い月: <strong>{peak_month}</strong>'
            f'（{int(monthly_demand.loc[peak_month, "購買件数"])}件） &nbsp; '
            f'閑散期: <strong>{low_month}</strong></div>',
            unsafe_allow_html=True
        )
    st.dataframe(monthly_demand, use_container_width=True)
else:
    st.markdown('<div class="info-box">購買データが蓄積されると季節性が分析できます</div>', unsafe_allow_html=True)

# ── ② カテゴリー別需要トレンド ────────────────────────────────────────────────
st.markdown('<div class="section-head">商品カテゴリー別 需要トレンド</div>', unsafe_allow_html=True)
if not purchases.empty:
    pur2 = purchases.copy()
    pur2["purchase_date"] = pd.to_datetime(pur2["purchase_date"], errors="coerce")
    pur2 = pur2.dropna(subset=["purchase_date"])
    pur2["amount"] = pd.to_numeric(pur2["amount"], errors="coerce").fillna(0)
    if "tour_status" in pur2.columns:
        pur2 = pur2[pur2["tour_status"] != "キャンセル"]
    pur2["ym"] = pur2["purchase_date"].dt.to_period("M").astype(str)

    if "product_type" in pur2.columns and not pur2.empty:
        cat_trend = pur2.groupby(["ym", "product_type"])["amount"].count().reset_index(name="件数")
        cat_pivot = cat_trend.pivot(index="ym", columns="product_type", values="件数").fillna(0)
        if not cat_pivot.empty:
            st.line_chart(cat_pivot)
            st.caption("カテゴリー別の購買件数推移。需要がどのカテゴリーにシフトしているか把握できます。")
else:
    st.markdown('<div class="info-box">データ蓄積中</div>', unsafe_allow_html=True)

# ── ③ 時間帯別関心（最適投稿時間）────────────────────────────────────────────
st.markdown('<div class="section-head">時間帯別 関心度（最適投稿時間の推定）</div>', unsafe_allow_html=True)
try:
    hourly_raw = to_df(sb_select("dm_hourly_monthly", order="hour", columns="id,year_month,platform,hour,dm_count"))
    if not hourly_raw.empty:
        if "dm_count" in hourly_raw.columns:
            hourly_raw = hourly_raw.rename(columns={"dm_count": "count"})
        hourly_raw["hour"]  = pd.to_numeric(hourly_raw["hour"],  errors="coerce").fillna(0).astype(int)
        hourly_raw["count"] = pd.to_numeric(hourly_raw["count"], errors="coerce").fillna(0).astype(int)
        hourly_agg = hourly_raw.groupby("hour")["count"].sum().reindex(range(24), fill_value=0)
        st.bar_chart(hourly_agg)

        peak_hour = int(hourly_agg.idxmax())
        st.markdown(
            f'<div class="success-box">⏰ 最も関心が高い時間帯: <strong>{peak_hour:02d}:00</strong> &nbsp; '
            f'推奨投稿時間: <strong>{max(peak_hour-1,0):02d}:00〜{peak_hour:02d}:00</strong>（ピークの直前）</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<div class="info-box">時間帯データが蓄積されると表示されます</div>', unsafe_allow_html=True)
except Exception:
    st.markdown('<div class="info-box">時間帯データ取得中</div>', unsafe_allow_html=True)

# ── ④ 流入チャネル別 顧客分析 ────────────────────────────────────────────────
st.markdown('<div class="section-head">流入チャネル別 顧客構成</div>', unsafe_allow_html=True)
try:
    custs = to_df(sb_select("customers", order="-created_at"))
    if not custs.empty and "platform" in custs.columns:
        platform_dist = custs["platform"].fillna("不明").value_counts()
        pc1, pc2 = st.columns([1, 1])
        with pc1:
            st.bar_chart(platform_dist)
        with pc2:
            st.markdown("**チャネル別顧客数**")
            for plat, cnt in platform_dist.items():
                pct = round(cnt / len(custs) * 100, 1)
                st.markdown(f"- {plat}: **{cnt}名**（{pct}%）")
        st.markdown(
            '<div class="info-box">💡 将来的に顧客の「国籍」を記録すると、地域別の旅行需要分析が可能になります。'
            'AI Conciergeのデータ収集を開始すると自動化できます。</div>',
            unsafe_allow_html=True
        )
except Exception:
    st.markdown('<div class="info-box">顧客データ取得中</div>', unsafe_allow_html=True)
