"""
app.py — BuzKeyword 運営ダッシュボード（Supabase版）
"""
import streamlit as st
import pandas as pd
import os, re, time
from datetime import datetime, timedelta, date
from collections import Counter

st.set_page_config(page_title="BuzKeyword", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")

from db import (get_client, sb_select, sb_insert, sb_upsert, sb_update, sb_delete)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:#1a1a2e;}
.stApp{background:#f8f9fc;}
#MainMenu,footer,header{visibility:hidden;}
section[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e5e7eb;}
.buz-hero{text-align:center;padding:1.5rem 0 1rem;}
.buz-hero h1{font-family:'Inter',sans-serif;font-weight:700;font-size:clamp(1.8rem,4vw,2.8rem);color:#1e3a5f;letter-spacing:-1px;line-height:1.1;}
.buz-hero p{color:#6b7280;font-size:.8rem;letter-spacing:3px;text-transform:uppercase;margin-top:.3rem;}
.metric-row{display:flex;gap:.8rem;margin:1rem 0;flex-wrap:wrap;}
.metric-card{flex:1;min-width:130px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:1rem 1.2rem;position:relative;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.05);}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:#1e3a5f;}
.metric-card .val{font-family:'Space Mono',monospace;font-size:1.6rem;font-weight:700;color:#1e3a5f;line-height:1;}
.metric-card .lbl{font-size:.68rem;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;margin-top:.3rem;}
.section-head{font-family:'Space Mono',monospace;font-size:.65rem;letter-spacing:3px;text-transform:uppercase;color:#9ca3af;border-bottom:1px solid #e5e7eb;padding-bottom:.4rem;margin:1.2rem 0 .8rem;}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.65rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;}
.badge-hot     {background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.badge-trending{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;}
.badge-rising  {background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;}
.badge-niche   {background:#faf5ff;color:#7c3aed;border:1px solid #e9d5ff;}
.badge-used    {background:#ecfdf5;color:#059669;border:1px solid #a7f3d0;}
.badge-unused  {background:#f9fafb;color:#9ca3af;border:1px solid #e5e7eb;}
.viral-chip{display:inline-block;padding:2px 8px;background:#1e3a5f;color:#fff;border-radius:4px;font-size:.6rem;font-weight:700;letter-spacing:.5px;}
.kw-card{background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:.8rem 1rem;margin-bottom:.5rem;display:flex;align-items:center;gap:.8rem;box-shadow:0 1px 2px rgba(0,0,0,.04);transition:border-color .15s,box-shadow .15s;}
.kw-card:hover{border-color:#1e3a5f;box-shadow:0 2px 8px rgba(30,58,95,.1);}
.kw-rank{font-family:'Space Mono',monospace;font-size:.65rem;color:#d1d5db;min-width:24px;}
.kw-word{font-weight:600;font-size:.95rem;color:#1a1a2e;flex:1;min-width:100px;}
.score-bar-wrap{display:flex;align-items:center;gap:6px;flex:2;min-width:80px;}
.score-bar-bg{flex:1;height:5px;background:#e5e7eb;border-radius:3px;overflow:hidden;}
.score-bar-fill{height:100%;border-radius:3px;background:#1e3a5f;}
.score-val{font-family:'Space Mono',monospace;font-size:.7rem;color:#1e3a5f;min-width:28px;text-align:right;}
.info-box{background:#eff6ff;border:1px solid #bfdbfe;border-left:3px solid #1e3a5f;border-radius:8px;padding:.8rem 1rem;font-size:.82rem;color:#1e40af;margin:.6rem 0;}
.err-box{background:#fef2f2;border:1px solid #fecaca;border-left:3px solid #dc2626;border-radius:8px;padding:.8rem 1rem;font-size:.82rem;color:#b91c1c;margin:.5rem 0;}
.success-box{background:#f0fdf4;border:1px solid #bbf7d0;border-left:3px solid #15803d;border-radius:8px;padding:.8rem 1rem;font-size:.82rem;color:#15803d;margin:.5rem 0;}
.coming-soon{background:#f8f9fc;border:2px dashed #e5e7eb;border-radius:10px;padding:3rem;text-align:center;color:#9ca3af;}
.stButton>button{background:#1e3a5f!important;color:#ffffff!important;font-family:'Inter',sans-serif!important;font-weight:600!important;font-size:.8rem!important;border:none!important;border-radius:8px!important;padding:.5rem 1.5rem!important;}
.stButton>button:hover{background:#152d4a!important;}
.progress-wrap{background:#e5e7eb;border-radius:6px;overflow:hidden;height:12px;margin:.4rem 0;}
.progress-fill{height:100%;background:#1e3a5f;border-radius:6px;}
.last-updated{font-family:'Space Mono',monospace;font-size:.62rem;color:#9ca3af;text-align:right;margin-top:.4rem;}
</style>
""", unsafe_allow_html=True)

# ── 定数 ──────────────────────────────────────────────────────────────────────
SNS_PLATFORMS    = ["Instagram","Facebook","TikTok","YouTube"]
ALL_DM_PLATFORMS = ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail"]
PLATFORM_EMOJI   = {"Instagram":"📸","Facebook":"👥","TikTok":"🎵","YouTube":"▶️","Threads":"🧵","X":"✖️","LINE":"💬","WhatsApp":"📱","Gmail":"📧"}
DM_COLS          = {"Instagram":"dm_instagram","Facebook":"dm_facebook","TikTok":"dm_tiktok","YouTube":"dm_youtube","Threads":"dm_threads","X":"dm_x","LINE":"dm_line","WhatsApp":"dm_whatsapp","Gmail":"dm_gmail"}
DM_GOAL          = 20000
STATUS_EMOJI     = {"hot":"🔥","trending":"📈","rising":"🚀","niche":"💎"}
STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","is","it","be",
    "as","by","that","this","was","are","from","have","has","had","not","what","all","were",
    "we","when","your","can","said","there","use","each","which","she","he","they","do",
    "how","their","if","will","up","about","out","who","get","been","its","so","my","than",
    "then","now","look","only","come","over","think","also","back","after","into","see",
    "her","you","me","him","our","just","new","more","us","no","i","am","did","would",
    "could","should","one","two","three","via","vs","per","re","ft","ep","pt",
}
BUZZ_THRESHOLDS = {
    "Instagram":{"1h":1000,"6h":5000,"24h":50000,"72h":100000,"7d":200000,"30d":500000},
    "Facebook": {"1h":500, "6h":2000,"24h":10000,"72h":30000, "7d":80000, "30d":200000},
    "TikTok":   {"1h":1000,"6h":5000,"24h":20000,"72h":50000, "7d":150000,"30d":400000},
    "YouTube":  {"1h":200, "6h":800, "24h":3000, "72h":8000,  "7d":20000, "30d":80000},
}

# ── ユーティリティ ────────────────────────────────────────────────────────────
def week_start(d=None):
    d = d or date.today()
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

def buzz_status(platform, views_dict):
    thresh = BUZZ_THRESHOLDS.get(platform, {})
    max_v  = max((v for v in views_dict.values() if v), default=0)
    if max_v >= thresh.get("72h",999999)*2: return "大バズ"
    if max_v >= thresh.get("72h",999999):   return "バズ"
    if max_v >= thresh.get("24h",999999):   return "通常以上"
    return "通常"

def classify(score):
    if score >= 75: return "hot"
    if score >= 55: return "trending"
    if score >= 35: return "rising"
    return "niche"

def clean_tokens(text):
    tokens = re.findall(r"[a-z][a-z']{1,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def make_bigrams(tokens):
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens)-1)]

def peak_estimate(growth):
    if growth >= 60: return "1〜3時間"
    if growth >= 30: return "6〜12時間"
    if growth >= 10: return "12〜24時間"
    return "24〜72時間"

def compute_score(gt, growth, yt):
    return round(gt*0.5 + growth*0.3 + yt*0.2, 1)

def to_df(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()

# ── API取得 ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def fetch_google_trends():
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=0, timeout=(10,25))
        try:
            daily = pt.trending_searches(pn="united_states")
            trending_raw = daily[0].tolist()[:20]
        except Exception:
            trending_raw = []
        seeds = ["AI","technology","viral","trending","japan"]
        related_raw, score_map = [], {}
        for seed in seeds:
            try:
                pt.build_payload([seed], timeframe="now 1-d", geo="US")
                rq = pt.related_queries()
                rising = rq.get(seed,{}).get("rising")
                if rising is not None and not rising.empty:
                    for _, row in rising.iterrows():
                        q = str(row.get("query","")).strip()
                        v = row.get("value",50)
                        if q:
                            related_raw.append(q)
                            score_map[q.lower()] = 100.0 if str(v)=="Breakout" else min(float(v),100)
                time.sleep(1)
            except Exception:
                pass
        all_terms = list(dict.fromkeys(trending_raw + related_raw))
        for t in all_terms: score_map.setdefault(t.lower(), 50.0)
        return all_terms, score_map
    except Exception:
        return [], {}

@st.cache_data(ttl=600, show_spinner=False)
def fetch_youtube_trending():
    api_key = st.secrets.get("YOUTUBE_API_KEY", os.getenv("YOUTUBE_API_KEY",""))
    if not api_key: return []
    try:
        import urllib.request, json
        url = (f"https://www.googleapis.com/youtube/v3/videos"
               f"?part=snippet,statistics&chart=mostPopular&regionCode=US&maxResults=25&key={api_key}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return [{"title":i["snippet"]["title"],"views":int(i["statistics"].get("viewCount",0))} for i in data.get("items",[])]
    except Exception:
        return []

def extract_keywords(gt_terms, gt_scores, yt_videos, prev_scores):
    yt_term_views = Counter()
    yt_set = set()
    for v in yt_videos:
        toks = clean_tokens(v["title"])
        for t in toks + make_bigrams(toks):
            yt_term_views[t] += v["views"]
            yt_set.add(t)
    max_views = max(yt_term_views.values(), default=1)
    all_terms = set()
    for raw in gt_terms:
        toks = clean_tokens(raw)
        all_terms.update(toks); all_terms.update(make_bigrams(toks))
    all_terms.update(yt_set)
    rows = []
    for term in all_terms:
        if len(term) < 3: continue
        tl = term.lower()
        gt_score = gt_scores.get(tl, 0.0)
        if gt_score == 0:
            for raw_t, sc in gt_scores.items():
                if tl in raw_t or raw_t in tl: gt_score = max(gt_score, sc*0.7)
        yt_boost = round((yt_term_views.get(tl,0)/max_views)*100, 1)
        prev   = prev_scores.get(tl, gt_score)
        growth = max(0.0, round(gt_score-prev, 1))
        score  = compute_score(gt_score, growth, yt_boost)
        if score < 5: continue
        rows.append({"keyword":term,"score":score,"status":classify(score),
                     "viral_soon":growth>15 and tl in yt_set and gt_score>30,
                     "peak_est":peak_estimate(growth),"gt_score":gt_score,
                     "yt_boost":yt_boost,"growth":growth,"in_gt":gt_score>0,"in_yt":tl in yt_set})
    df = pd.DataFrame(rows)
    if df.empty: return df
    return df.sort_values("score",ascending=False).head(50).reset_index(drop=True)

def demo_keywords():
    s = [
        ("japan hidden spots",91,"hot",True,"1〜3時間",88,75,42),
        ("tokyo free spots",86,"hot",True,"1〜3時間",82,70,38),
        ("wabi sabi living",82,"hot",False,"6〜12時間",79,68,20),
        ("japan morning routine",77,"trending",True,"6〜12時間",74,62,35),
        ("shibuya hidden cafe",73,"trending",False,"6〜12時間",70,58,15),
        ("tokyo street food",68,"trending",False,"12〜24時間",65,55,10),
        ("japan life vlog",63,"trending",False,"12〜24時間",60,50,8),
        ("tokyo budget travel",58,"rising",True,"12〜24時間",55,45,22),
        ("japan apartment tour",52,"rising",False,"24〜72時間",49,40,3),
        ("tokyo night walk",47,"niche",False,"24〜72時間",44,38,2),
    ]
    return pd.DataFrame([{"keyword":k,"score":sc,"status":st,"viral_soon":vr,"peak_est":pk,
                          "gt_score":gt,"yt_boost":yt,"growth":gr,"in_gt":True,"in_yt":yt>0}
                         for k,sc,st,vr,pk,gt,yt,gr in s])

def render_kw_card(i, row, show_used=False):
    badge_cls = f"badge-{row['status']}"
    viral     = '<span class="viral-chip">⚡ VIRAL SOON</span>' if row.get("viral_soon") else ""
    src_gt    = '<span style="font-size:.6rem;padding:1px 6px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:8px;margin-left:3px;">GT</span>' if row.get("in_gt") else ""
    src_yt    = '<span style="font-size:.6rem;padding:1px 6px;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:8px;margin-left:3px;">YT</span>' if row.get("in_yt") else ""
    used_html = ('<span class="badge badge-used">✅ 使用済</span>' if row.get("used") else '<span class="badge badge-unused">未使用</span>') if show_used else ""
    st.markdown(f"""
    <div class="kw-card">
      <span class="kw-rank">#{i+1:02d}</span>
      <span class="kw-word">{row['keyword'].title()}{src_gt}{src_yt}</span>
      <div class="score-bar-wrap">
        <div class="score-bar-bg"><div class="score-bar-fill" style="width:{min(int(row['score']),100)}%"></div></div>
        <span class="score-val">{row['score']:.0f}</span>
      </div>
      <span class="badge {badge_cls}">{STATUS_EMOJI.get(row['status'],'')} {row['status']}</span>
      {viral}{used_html}
      <span style="min-width:80px;color:#9ca3af;font-size:.68rem;">⏱ {row.get('peak_est','')}</span>
    </div>""", unsafe_allow_html=True)

# ── セッション状態 ────────────────────────────────────────────────────────────
if "kw_df"        not in st.session_state: st.session_state.kw_df = pd.DataFrame()
if "prev_scores"  not in st.session_state: st.session_state.prev_scores = {}
if "last_updated" not in st.session_state: st.session_state.last_updated = None

# ── サイドバー ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:.5rem 0 1.2rem;">
      <div style="font-size:1.5rem;">🔥</div>
      <div style="font-weight:700;font-size:1.15rem;color:#1e3a5f;margin-top:.2rem;">BuzKeyword</div>
      <div style="font-size:.65rem;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;">運営ダッシュボード</div>
    </div>""", unsafe_allow_html=True)

    page = st.radio("メニュー",[
        "🔥 キーワード収集","📚 キーワード履歴","📊 再生数トラッキング",
        "💬 DM数トラッキング","🏆 競合モニタリング","💰 ROI・売上",
        "📄 週次レポート","🎯 DMシミュレーター","🔒 競合自動取得（準備中）",
    ], label_visibility="collapsed")

    st.markdown("---")
    try:
        get_client()
        st.markdown('<div style="color:#15803d;font-size:.78rem;font-weight:600;">✅ Supabase接続済み</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div style="color:#dc2626;font-size:.78rem;font-weight:600;">❌ Supabase未接続</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: キーワード収集
# ═════════════════════════════════════════════════════════════════════════════
if page == "🔥 キーワード収集":
    st.markdown('<div class="buz-hero"><h1>🔥 BuzKeyword</h1><p>Real-time keyword intelligence</p></div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1: refresh      = st.button("⟳ データ更新")
    with c2: save_to_hist = st.button("📚 履歴に保存")

    if refresh or st.session_state.kw_df.empty:
        with st.spinner("トレンドデータを取得中…"):
            prev = {r["keyword"].lower():r["score"] for r in st.session_state.kw_df.to_dict("records")} if not st.session_state.kw_df.empty else {}
            gt_terms, gt_scores = fetch_google_trends()
            yt_videos = fetch_youtube_trending()
            df = extract_keywords(gt_terms, gt_scores, yt_videos, prev) if (gt_terms or yt_videos) else pd.DataFrame()
            if df.empty:
                df = demo_keywords()
                st.markdown('<div class="info-box">⚠️ ライブデータなし — デモデータを表示中</div>', unsafe_allow_html=True)
            st.session_state.kw_df = df
            st.session_state.last_updated = datetime.now()

    df = st.session_state.kw_df

    if save_to_hist and not df.empty:
        saved = 0
        for _, row in df.iterrows():
            src = []
            if row.get("in_gt"): src.append("GoogleTrends")
            if row.get("in_yt"): src.append("YouTube")
            result = sb_insert("keyword_history", {
                "keyword":row["keyword"],"score":row["score"],
                "status":row["status"],"source":",".join(src)
            })
            if result: saved += 1
        st.markdown(f'<div class="success-box">✅ {saved}件のキーワードを保存しました</div>', unsafe_allow_html=True)

    if not df.empty:
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{len(df)}</div><div class="lbl">キーワード数</div></div>
          <div class="metric-card"><div class="val">{int((df["status"]=="hot").sum())}</div><div class="lbl">🔥 ホット</div></div>
          <div class="metric-card"><div class="val">{int(df["viral_soon"].sum())}</div><div class="lbl">⚡ バイラル予測</div></div>
          <div class="metric-card"><div class="val">{round(df["score"].mean(),1)}</div><div class="lbl">平均スコア</div></div>
        </div>""", unsafe_allow_html=True)

        tab_all, tab_hot, tab_viral, tab_tbl = st.tabs(["すべて","🔥 ホット","⚡ バイラル","📊 テーブル"])
        with tab_all:
            for i, row in df.iterrows(): render_kw_card(i, row)
        with tab_hot:
            for i, row in df[df["status"].isin(["hot","trending"])].head(15).iterrows(): render_kw_card(i, row)
        with tab_viral:
            vdf = df[df["viral_soon"]==True]
            if vdf.empty: st.markdown('<div class="info-box">現在バイラル予測なし</div>', unsafe_allow_html=True)
            for i, row in vdf.iterrows(): render_kw_card(i, row)
        with tab_tbl:
            st.dataframe(df[["keyword","score","status","viral_soon","peak_est","gt_score","yt_boost","growth"]].rename(columns={
                "keyword":"キーワード","score":"スコア","status":"ステータス","viral_soon":"バイラル?",
                "peak_est":"ピーク予測","gt_score":"GTスコア","yt_boost":"YTブースト","growth":"成長率Δ"}),
                use_container_width=True, height=400)
        if st.session_state.last_updated:
            st.markdown(f'<div class="last-updated">最終更新: {st.session_state.last_updated.strftime("%Y-%m-%d %H:%M:%S")}</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: キーワード履歴
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📚 キーワード履歴":
    st.markdown("#### 📚 キーワード履歴管理")
    rows = sb_select("keyword_history", order="-score")
    df_hist = to_df(rows)
    if df_hist.empty:
        st.markdown('<div class="info-box">📭 まだキーワードがありません。キーワード収集ページで「履歴に保存」してください。</div>', unsafe_allow_html=True)
    else:
        c1,c2 = st.columns(2)
        with c1: filter_used   = st.selectbox("表示フィルター",["すべて","未使用のみ","使用済みのみ"])
        with c2: filter_status = st.selectbox("ステータス",["すべて","hot","trending","rising","niche"])
        df_show = df_hist.copy()
        if filter_used   == "未使用のみ":   df_show = df_show[df_show["used"]==0]
        elif filter_used == "使用済みのみ": df_show = df_show[df_show["used"]==1]
        if filter_status != "すべて":       df_show = df_show[df_show["status"]==filter_status]
        st.caption(f"{len(df_show)}件表示")

        for _, row in df_show.iterrows():
            c1,c2,c3,c4,c5,c6 = st.columns([3,1,1.2,1.8,2.5,0.8])
            with c1:
                st.markdown(f"**{row['keyword'].title()}**")
                st.caption(f"保存日: {str(row.get('created_at',''))[:10]}")
            with c2: st.metric("スコア", row["score"])
            with c3: st.markdown(f'<span class="badge badge-{row["status"]}">{STATUS_EMOJI.get(row["status"],"")} {row["status"]}</span>', unsafe_allow_html=True)
            with c4:
                if row["used"] == 0:
                    if st.button("✅ 使用済にする", key=f"use_{row['id']}"):
                        sb_update("keyword_history",{"used":1,"used_date":str(date.today())},{"id":row["id"]})
                        st.rerun()
                else:
                    st.markdown(f'<span class="badge badge-used">✅ {row.get("used_date","") or ""}</span>', unsafe_allow_html=True)
                    if st.button("↩ 戻す", key=f"unuse_{row['id']}"):
                        sb_update("keyword_history",{"used":0,"used_date":None},{"id":row["id"]})
                        st.rerun()
            with c5:
                note = st.text_input("メモ", value=row.get("note","") or "", key=f"note_{row['id']}",
                                     label_visibility="collapsed", placeholder="メモを入力…")
                if note != (row.get("note","") or ""):
                    sb_update("keyword_history",{"note":note},{"id":row["id"]})
            with c6:
                if st.button("🗑", key=f"del_{row['id']}"):
                    sb_delete("keyword_history",{"id":row["id"]}); st.rerun()
            st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: 再生数トラッキング
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📊 再生数トラッキング":
    st.markdown("#### 📊 SNS再生数トラッキング")
    tab_in, tab_list = st.tabs(["新規入力","投稿一覧・分析"])

    with tab_in:
        c1,c2 = st.columns(2)
        with c1:
            platform   = st.selectbox("プラットフォーム", SNS_PLATFORMS)
            post_theme = st.text_input("投稿テーマ", placeholder="例：東京無料スポット10選")
            kw_used    = st.text_input("使用キーワード", placeholder="例：tokyo hidden spots")
        with c2:
            post_url  = st.text_input("投稿URL（任意）")
            posted_at = st.date_input("投稿日", value=date.today())
        st.markdown('<div class="section-head">再生数入力</div>', unsafe_allow_html=True)
        vc1,vc2,vc3 = st.columns(3)
        vc4,vc5,vc6 = st.columns(3)
        with vc1: v_1h  = st.number_input("1時間後",  min_value=0, value=0, step=100)
        with vc2: v_6h  = st.number_input("6時間後",  min_value=0, value=0, step=100)
        with vc3: v_24h = st.number_input("24時間後", min_value=0, value=0, step=100)
        with vc4: v_72h = st.number_input("72時間後", min_value=0, value=0, step=100)
        with vc5: v_7d  = st.number_input("7日後",    min_value=0, value=0, step=100)
        with vc6: v_30d = st.number_input("30日後",   min_value=0, value=0, step=100)
        vd = {"1h":v_1h,"6h":v_6h,"24h":v_24h,"72h":v_72h,"7d":v_7d,"30d":v_30d}
        bz = buzz_status(platform, vd)
        st.markdown(f'<div class="info-box">バズ判定プレビュー：<strong>{bz}</strong>　最大再生数：<strong>{max(vd.values()):,}</strong></div>', unsafe_allow_html=True)
        if st.button("💾 保存する"):
            if not post_theme:
                st.markdown('<div class="err-box">テーマを入力してください</div>', unsafe_allow_html=True)
            else:
                sb_insert("post_tracking",{"platform":platform,"post_url":post_url,"post_theme":post_theme,
                    "keyword_used":kw_used,"posted_at":str(posted_at),"v_1h":v_1h,"v_6h":v_6h,
                    "v_24h":v_24h,"v_72h":v_72h,"v_7d":v_7d,"v_30d":v_30d,"buzz_status":bz})
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

    with tab_list:
        rows = sb_select("post_tracking", order="-posted_at")
        df_posts = to_df(rows)
        if df_posts.empty:
            st.markdown('<div class="info-box">まだ投稿データがありません</div>', unsafe_allow_html=True)
        else:
            for col in ["v_24h","v_72h","v_7d","v_30d","v_1h"]:
                if col not in df_posts.columns: df_posts[col] = 0
            agg = df_posts.groupby("platform")[["v_24h","v_72h","v_7d","v_30d"]].mean().round(0).astype(int)
            st.markdown('<div class="section-head">プラットフォーム別 平均再生数</div>', unsafe_allow_html=True)
            st.dataframe(agg.rename(columns={"v_24h":"24h平均","v_72h":"72h平均","v_7d":"7日平均","v_30d":"30日平均"}), use_container_width=True)
            st.markdown('<div class="section-head">投稿一覧</div>', unsafe_allow_html=True)
            for _, row in df_posts.iterrows():
                c1,c2,c3,c4 = st.columns([3,4,1.5,0.5])
                with c1:
                    st.markdown(f"**{PLATFORM_EMOJI.get(row['platform'],'')} {row['post_theme']}**")
                    st.caption(f"{row['posted_at']}　KW: {row.get('keyword_used','') or '未設定'}")
                with c2: st.markdown(f"1h:`{row['v_1h']:,}` / 24h:`{row['v_24h']:,}` / 7d:`{row['v_7d']:,}` / 30d:`{row['v_30d']:,}`")
                with c3: st.markdown(f"**{row.get('buzz_status','')}**")
                with c4:
                    if st.button("🗑", key=f"pdel_{row['id']}"):
                        sb_delete("post_tracking",{"id":row["id"]}); st.rerun()
                st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: DM数トラッキング
# ═════════════════════════════════════════════════════════════════════════════
elif page == "💬 DM数トラッキング":
    st.markdown("#### 💬 DM数トラッキング")
    tab_in, tab_graph = st.tabs(["日次入力","グラフ・集計"])

    with tab_in:
        st.markdown('<div class="section-head">DM数を入力（9プラットフォーム）</div>', unsafe_allow_html=True)
        dm_date = st.date_input("日付", value=date.today())
        dm_vals = {}
        platforms_grid = [("Instagram","Facebook","TikTok"),("YouTube","Threads","X"),("LINE","WhatsApp","Gmail")]
        for pl_row in platforms_grid:
            cols = st.columns(3)
            for col, pl in zip(cols, pl_row):
                with col:
                    dm_vals[pl] = st.number_input(f"{PLATFORM_EMOJI.get(pl,'')} {pl}", min_value=0, value=0, step=10, key=f"dm_{pl}")
        total_input = sum(dm_vals.values())
        st.markdown(f'<div class="info-box">本日合計：<strong>{total_input:,}件</strong></div>', unsafe_allow_html=True)
        if st.button("💾 保存する", key="dm_save"):
            data = {"date": str(dm_date)}
            for pl in ALL_DM_PLATFORMS:
                data[DM_COLS[pl]] = dm_vals[pl]
            sb_upsert("dm_tracking", data, on_conflict="date")
            st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

    with tab_graph:
        rows = sb_select("dm_tracking", order="date")
        df_dm = to_df(rows)
        if df_dm.empty:
            st.markdown('<div class="info-box">まだDMデータがありません</div>', unsafe_allow_html=True)
        else:
            for p in ALL_DM_PLATFORMS:
                if DM_COLS[p] not in df_dm.columns: df_dm[DM_COLS[p]] = 0
            df_dm["合計"] = df_dm[[DM_COLS[p] for p in ALL_DM_PLATFORMS]].sum(axis=1)
            df_dm["date"] = pd.to_datetime(df_dm["date"])

            period = st.selectbox("集計期間",["週次","月次","年次","全期間"])
            now    = pd.Timestamp.now()
            cutoff = {"週次":7,"月次":30,"年次":365}.get(period)
            df_f   = df_dm[df_dm["date"] >= now-pd.Timedelta(days=cutoff)] if cutoff else df_dm.copy()

            if df_f.empty:
                st.markdown('<div class="info-box">選択期間にデータがありません</div>', unsafe_allow_html=True)
            else:
                month_dm = int(df_dm[df_dm["date"] >= now.replace(day=1)]["合計"].sum())
                progress = round(month_dm/DM_GOAL*100,1)
                st.markdown(f"""<div class="metric-row">
                  <div class="metric-card"><div class="val">{int(df_f["合計"].sum()):,}</div><div class="lbl">期間合計DM</div></div>
                  <div class="metric-card"><div class="val">{month_dm:,}</div><div class="lbl">今月合計DM</div></div>
                  <div class="metric-card"><div class="val">{progress}%</div><div class="lbl">月間目標進捗</div></div>
                  <div class="metric-card"><div class="val">{DM_GOAL:,}</div><div class="lbl">月間目標</div></div>
                </div>
                <div style="margin:.5rem 0 .2rem;font-size:.78rem;color:#6b7280;font-weight:500;">月間目標進捗　{month_dm:,} / {DM_GOAL:,}件</div>
                <div class="progress-wrap"><div class="progress-fill" style="width:{min(progress,100)}%"></div></div>
                """, unsafe_allow_html=True)

                st.markdown('<div class="section-head">プラットフォーム別推移</div>', unsafe_allow_html=True)
                chart_df = df_f.set_index("date")[[DM_COLS[p] for p in ALL_DM_PLATFORMS]].rename(columns={DM_COLS[p]:p for p in ALL_DM_PLATFORMS})
                chart_df = chart_df.loc[:,(chart_df!=0).any(axis=0)]
                if not chart_df.empty: st.line_chart(chart_df)

                st.markdown('<div class="section-head">合計DM推移</div>', unsafe_allow_html=True)
                st.bar_chart(df_f.set_index("date")["合計"])

                st.markdown('<div class="section-head">プラットフォーム別シェア</div>', unsafe_allow_html=True)
                share = {p: int(df_f[DM_COLS[p]].sum()) for p in ALL_DM_PLATFORMS if DM_COLS[p] in df_f.columns}
                total_s = sum(share.values()) or 1
                for i in range(0, len(ALL_DM_PLATFORMS), 3):
                    cols = st.columns(3)
                    for j, pl in enumerate(ALL_DM_PLATFORMS[i:i+3]):
                        cnt = share.get(pl, 0)
                        with cols[j]: st.metric(f"{PLATFORM_EMOJI.get(pl,'')} {pl}", f"{cnt:,}件", f"{round(cnt/total_s*100,1)}%")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: 競合モニタリング
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🏆 競合モニタリング":
    st.markdown("#### 🏆 競合モニタリング（Instagram）")
    tab_acc, tab_wk, tab_analysis = st.tabs(["アカウント管理","週次データ入力","分析"])

    with tab_acc:
        c1,c2 = st.columns(2)
        with c1:
            new_un    = st.text_input("Instagramユーザー名", placeholder="@username")
            new_genre = st.text_input("ジャンル", placeholder="例：東京観光")
        with c2:
            new_note = st.text_area("メモ（任意）", height=80)
        if st.button("➕ 登録する"):
            if new_un:
                res = sb_insert("competitor_accounts",{"username":new_un,"genre":new_genre,"note":new_note})
                if res:
                    st.markdown('<div class="success-box">✅ 登録しました</div>', unsafe_allow_html=True); st.rerun()
                else:
                    st.markdown('<div class="err-box">⚠️ すでに登録されているか、エラーが発生しました</div>', unsafe_allow_html=True)
        df_acc = to_df(sb_select("competitor_accounts", order="-created_at"))
        if not df_acc.empty:
            st.markdown('<div class="section-head">登録済みアカウント</div>', unsafe_allow_html=True)
            for _, row in df_acc.iterrows():
                c1,c2,c3 = st.columns([3,2,1])
                with c1: st.markdown(f"**{row['username']}**　`{row.get('genre','') or ''}`")
                with c2: st.caption(row.get("note","") or "")
                with c3:
                    if st.button("🗑", key=f"adel_{row['id']}"):
                        sb_delete("competitor_weekly",{"account_id":row["id"]})
                        sb_delete("competitor_accounts",{"id":row["id"]}); st.rerun()

    with tab_wk:
        df_acc = to_df(sb_select("competitor_accounts"))
        if df_acc.empty:
            st.markdown('<div class="info-box">先にアカウントを登録してください</div>', unsafe_allow_html=True)
        else:
            sel    = st.selectbox("アカウント", df_acc["username"].tolist())
            acc_id = int(df_acc[df_acc["username"]==sel]["id"].values[0])
            ws     = week_start()
            st.caption(f"対象週：{ws} 〜")
            c1,c2 = st.columns(2)
            with c1:
                followers  = st.number_input("フォロワー数", min_value=0, value=0, step=100)
                post_count = st.number_input("週間投稿数",   min_value=0, value=0, step=1)
            with c2:
                avg_views = st.number_input("平均再生数",    min_value=0, value=0, step=100)
                top_theme = st.text_input("最高再生投稿テーマ")
            if st.button("💾 保存する", key="comp_save"):
                sb_upsert("competitor_weekly",
                    {"account_id":acc_id,"week_start":ws,"followers":followers,
                     "post_count":post_count,"avg_views":avg_views,"top_post_theme":top_theme},
                    on_conflict="account_id,week_start")
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

    with tab_analysis:
        rows = sb_select("competitor_weekly", order="-week_start")
        df_cw = to_df(rows)
        df_acc = to_df(sb_select("competitor_accounts"))
        if df_cw.empty or df_acc.empty:
            st.markdown('<div class="info-box">週次データを入力してください</div>', unsafe_allow_html=True)
        else:
            df_comp = df_cw.merge(df_acc[["id","username","genre"]], left_on="account_id", right_on="id", suffixes=("","_acc"))
            my_avg  = 20000
            demand_df = df_comp.groupby("week_start")["avg_views"].mean().round(0).reset_index()
            demand_df.columns = ["週","競合平均再生数"]
            st.markdown("**東京コンテンツ 需要指数推移**")
            st.line_chart(demand_df.set_index("週"))
            latest_week = df_comp["week_start"].max()
            df_lat = df_comp[df_comp["week_start"]==latest_week]
            st.markdown(f'<div class="section-head">最新週（{latest_week}）競合比較</div>', unsafe_allow_html=True)
            rows_list = []
            for _, row in df_lat.iterrows():
                diff = row["avg_views"]-my_avg
                rows_list.append({"アカウント":row["username"],"ジャンル":row.get("genre","") or "","フォロワー":f"{row['followers']:,}","平均再生":f"{row['avg_views']:,}","自社との差":f"+{diff:,}" if diff>=0 else f"{diff:,}","週間投稿":row["post_count"],"注目テーマ":row.get("top_post_theme","") or ""})
            st.dataframe(pd.DataFrame(rows_list), use_container_width=True)
            if len(demand_df) >= 2:
                ld = demand_df.iloc[-1]["競合平均再生数"]
                pd_ = demand_df.iloc[-2]["競合平均再生数"]
                if ld > pd_*1.1:   st.markdown('<div class="success-box">📈 東京コンテンツの需要は上昇中です。投稿タイミングです！</div>', unsafe_allow_html=True)
                elif ld < pd_*0.9: st.markdown('<div class="err-box">📉 需要低下中。キーワードを見直しましょう。</div>', unsafe_allow_html=True)
                else:              st.markdown('<div class="info-box">➡️ 需要は横ばいです。安定した需要があります。</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: ROI・売上
# ═════════════════════════════════════════════════════════════════════════════
elif page == "💰 ROI・売上":
    st.markdown("#### 💰 ROI・売上紐づけ")
    tab_utm, tab_in, tab_analysis = st.tabs(["UTMリンク生成","売上データ入力","ROI分析"])

    with tab_utm:
        base_url     = st.text_input("ベースURL", placeholder="https://yoursite.com/product")
        utm_source   = st.selectbox("プラットフォーム", SNS_PLATFORMS)
        utm_campaign = st.text_input("キャンペーン名", placeholder="例：tokyo_free_spots_jan")
        utm_content  = st.text_input("コンテンツ識別子（任意）")
        if base_url and utm_campaign:
            cp  = f"&utm_content={utm_content}" if utm_content else ""
            url = f"{base_url}?utm_source={utm_source.lower()}&utm_medium=social&utm_campaign={utm_campaign}{cp}"
            st.markdown(f'<div class="success-box"><strong>UTMリンク：</strong><br><code style="font-size:.8rem;word-break:break-all;color:#1e3a5f;">{url}</code></div>', unsafe_allow_html=True)
            if st.button("💾 UTMリンクを保存"):
                sb_insert("roi_tracking",{"platform":utm_source,"utm_campaign":utm_campaign,"utm_url":url,"date":str(date.today())})
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

    with tab_in:
        rows = sb_select("roi_tracking", order="-created_at")
        df_roi = to_df(rows)
        if df_roi.empty:
            st.markdown('<div class="info-box">先にUTMリンクを生成・保存してください</div>', unsafe_allow_html=True)
        else:
            sel_c  = st.selectbox("キャンペーンを選択", df_roi["utm_campaign"].tolist())
            sel_id = int(df_roi[df_roi["utm_campaign"]==sel_c]["id"].values[0])
            c1,c2,c3 = st.columns(3)
            with c1: clicks    = st.number_input("クリック数",     min_value=0, value=0, step=1)
            with c2: purchases = st.number_input("購入件数",       min_value=0, value=0, step=1)
            with c3: revenue   = st.number_input("売上金額（円）", min_value=0, value=0, step=1000)
            if st.button("💾 更新する"):
                sb_update("roi_tracking",{"clicks":clicks,"purchases":purchases,"revenue":revenue},{"id":sel_id})
                st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True)

    with tab_analysis:
        rows = sb_select("roi_tracking", order="-revenue")
        df_roi = to_df(rows)
        if df_roi.empty:
            st.markdown('<div class="info-box">データがありません</div>', unsafe_allow_html=True)
        else:
            for col in ["clicks","purchases","revenue"]:
                if col not in df_roi.columns: df_roi[col] = 0
            tc = int(df_roi["clicks"].sum()); tp = int(df_roi["purchases"].sum()); tr = int(df_roi["revenue"].sum())
            cvr = round(tp/tc*100,1) if tc else 0
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{tc:,}</div><div class="lbl">総クリック数</div></div>
              <div class="metric-card"><div class="val">{tp:,}</div><div class="lbl">総購入件数</div></div>
              <div class="metric-card"><div class="val">¥{tr:,}</div><div class="lbl">総売上</div></div>
              <div class="metric-card"><div class="val">{cvr}%</div><div class="lbl">転換率</div></div>
            </div>""", unsafe_allow_html=True)
            disp = df_roi[["platform","utm_campaign","clicks","purchases","revenue","date"]].copy()
            disp["転換率"] = disp.apply(lambda r: f"{round(r['purchases']/r['clicks']*100,1)}%" if r["clicks"] else "－",axis=1)
            disp["revenue"] = disp["revenue"].apply(lambda x: f"¥{int(x):,}")
            st.dataframe(disp.rename(columns={"platform":"プラットフォーム","utm_campaign":"キャンペーン","clicks":"クリック","purchases":"購入","revenue":"売上","date":"日付"}), use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: 週次レポート
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📄 週次レポート":
    from report import generate_weekly_report, SAMPLE_DATA
    st.markdown("#### 📄 週次レポート生成（日本語・A4）")
    ws_str = week_start(); we_str = str(date.today())

    rows_dm   = sb_select("dm_tracking")
    df_dm_all = to_df(rows_dm)
    if not df_dm_all.empty:
        df_dm_all["date"] = pd.to_datetime(df_dm_all["date"])
        for p in ALL_DM_PLATFORMS:
            if DM_COLS[p] not in df_dm_all.columns: df_dm_all[DM_COLS[p]] = 0
        df_dm_w   = df_dm_all[df_dm_all["date"] >= pd.Timestamp(ws_str)]
        dm_total  = int(df_dm_w[[DM_COLS[p] for p in ALL_DM_PLATFORMS]].sum().sum()) if not df_dm_w.empty else 0
        prev_ws   = (date.today()-timedelta(days=7)-timedelta(days=date.today().weekday())).strftime("%Y-%m-%d")
        df_dm_p   = df_dm_all[(df_dm_all["date"] >= pd.Timestamp(prev_ws)) & (df_dm_all["date"] < pd.Timestamp(ws_str))]
        dm_prev   = int(df_dm_p[[DM_COLS[p] for p in ALL_DM_PLATFORMS]].sum().sum()) if not df_dm_p.empty else 0
    else:
        dm_total = dm_prev = 0; df_dm_w = pd.DataFrame()

    rows_posts = sb_select("post_tracking", order="-v_72h", limit=3)
    top_posts  = [{"platform":r["platform"],"theme":r["post_theme"],"views":r.get("v_72h",0),"buzz":r.get("buzz_status","")} for r in rows_posts]
    rows_kw    = sb_select("keyword_history", order="-score", limit=5)
    keywords   = [{"keyword":r["keyword"],"score":r["score"],"used":bool(r.get("used",0)),"result":r.get("note","") or "計測中"} for r in rows_kw]
    rows_roi   = sb_select("roi_tracking")
    df_roi     = to_df(rows_roi)
    roi        = {"clicks":int(df_roi["clicks"].sum()),"purchases":int(df_roi["purchases"].sum()),"revenue":float(df_roi["revenue"].sum())} if not df_roi.empty else {"clicks":0,"purchases":0,"revenue":0}
    rows_nkw   = sb_select("keyword_history", filters={"used":0}, order="-score", limit=3)
    next_kws   = [r["keyword"] for r in rows_nkw]
    has_data   = dm_total > 0 or len(top_posts) > 0 or len(keywords) > 0

    if not has_data:
        st.markdown('<div class="info-box">⚠️ 今週のデータがまだありません。サンプルデータでプレビューします。</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1: preview  = st.button("👁 サンプルでプレビュー")
    with c2: generate = st.button("📥 PDFを生成・ダウンロード")

    use_sample  = preview or not has_data
    report_data = SAMPLE_DATA if use_sample else {
        "week_start":ws_str,"week_end":we_str,
        "dm":{"instagram":int(df_dm_w["dm_instagram"].sum()) if not df_dm_w.empty and "dm_instagram" in df_dm_w.columns else 0,
              "facebook": int(df_dm_w["dm_facebook"].sum())  if not df_dm_w.empty and "dm_facebook"  in df_dm_w.columns else 0,
              "tiktok":   int(df_dm_w["dm_tiktok"].sum())    if not df_dm_w.empty and "dm_tiktok"    in df_dm_w.columns else 0,
              "youtube":  int(df_dm_w["dm_youtube"].sum())   if not df_dm_w.empty and "dm_youtube"   in df_dm_w.columns else 0,
              "total":dm_total,"prev_total":dm_prev,"goal":DM_GOAL},
        "top_posts":top_posts,"keywords":keywords,"roi":roi,"competitors":[],
        "next_keywords":next_kws,"progress_pct":round(dm_total/DM_GOAL*100,1),
    }

    if generate or use_sample:
        with st.spinner("PDF生成中…"):
            pdf_bytes = generate_weekly_report(report_data)
        label = "sample" if use_sample else ws_str
        st.download_button("📥 PDFをダウンロード", data=pdf_bytes, file_name=f"buzzkeyword_report_{label}.pdf", mime="application/pdf")
        st.markdown('<div class="success-box">✅ PDFが生成されました</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: DMシミュレーター
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🎯 DMシミュレーター":
    st.markdown("#### 🎯 DMシミュレーター")
    st.caption("目標DM数から必要な再生数・投稿数を逆算します")
    c1,c2 = st.columns(2)
    with c1:
        target_dm    = st.number_input("月間目標DM数",       min_value=100,  value=20000, step=1000)
        comment_rate = st.slider("コメント率（%）",          0.5, 5.0, 2.0, 0.1)
        dm_rate      = st.slider("コメント→DM転換率（%）",   10,  60,  30,  5)
    with c2:
        dm_reach  = st.slider("DM到達率（%）",               70, 100, 85, 5)
        avg_views = st.number_input("1投稿あたり平均再生数", min_value=1000, value=20000, step=1000)

    needed_triggers = round(target_dm/(dm_reach/100))
    needed_comments = round(needed_triggers/(dm_rate/100))
    needed_views    = round(needed_comments/(comment_rate/100))
    needed_posts    = max(1, round(needed_views/avg_views))

    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{target_dm:,}</div><div class="lbl">目標DM数/月</div></div>
      <div class="metric-card"><div class="val">{needed_views:,}</div><div class="lbl">必要月間再生数</div></div>
      <div class="metric-card"><div class="val">{needed_comments:,}</div><div class="lbl">必要コメント数</div></div>
      <div class="metric-card"><div class="val">{needed_posts}</div><div class="lbl">必要投稿数/月</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">達成シナリオ</div>', unsafe_allow_html=True)
    for name, views, desc in [("プチバズ型",50000,"安定投稿・コツコツ成長"),("バズ型",200000,"数本のバズで達成可能"),("大バズ型",1000000,"1〜2本の大バズで一気に達成")]:
        posts_n = max(1, round(needed_views/views))
        c1,c2,c3,c4 = st.columns([2,2,2,3])
        with c1: st.markdown(f"**{name}**")
        with c2: st.markdown(f"{views:,}再生/本")
        with c3: st.markdown(f"**{posts_n}本/月**")
        with c4: st.caption(desc)
        st.divider()

    current_monthly = 20000*15
    current_dm_est  = round(current_monthly*(comment_rate/100)*(dm_rate/100)*(dm_reach/100))
    gap_views = needed_views - current_monthly
    st.markdown(f"""<div class="info-box">
    現在の推定月間DM数（Instagram基準）：<strong>{current_dm_est:,}件</strong>　
    目標まで：<strong>{target_dm-current_dm_est:,}件</strong>のギャップ<br>
    必要追加再生数：<strong>{max(0,gap_views):,}</strong>　
    ≒ 追加投稿 <strong>{max(0,round(gap_views/avg_views))}本/月</strong>
    </div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: 競合自動取得（準備中）
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔒 競合自動取得（準備中）":
    st.markdown("#### 🔒 競合自動取得")
    st.markdown("""
    <div class="coming-soon">
      <div style="font-size:2.5rem;margin-bottom:1rem;">🔒</div>
      <div style="font-size:1rem;color:#6b7280;font-weight:600;margin-bottom:.5rem;">COMING SOON</div>
      <div style="font-size:.82rem;color:#9ca3af;line-height:1.9;">
        Instagram / TikTok / YouTube の競合データを<br>
        APIで自動取得する機能を準備中です。<br><br>
        現在は「競合モニタリング」ページから<br>
        手動入力でご利用ください。
      </div>
    </div>""", unsafe_allow_html=True)
