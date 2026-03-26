"""
app.py — Tabibiyori Dashboard v2
"""
import streamlit as st
import pandas as pd
import os, re, time
from datetime import datetime, timedelta, date
from collections import Counter

st.set_page_config(page_title="Tabibiyori Dashboard", page_icon="🌸", layout="wide", initial_sidebar_state="expanded")

from db import get_client, sb_select, sb_insert, sb_upsert, sb_update, sb_delete

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:#1a1a2e;}
.stApp{background:#f8f9fc;}
#MainMenu,footer,header{visibility:hidden;}
section[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e5e7eb;}

.buz-hero{text-align:center;padding:1.5rem 0 1rem;}
.buz-hero h1{font-family:'Inter',sans-serif;font-weight:700;font-size:clamp(1.6rem,4vw,2.4rem);color:#1e3a5f;letter-spacing:-1px;line-height:1.1;}
.buz-hero p{color:#6b7280;font-size:.8rem;letter-spacing:3px;text-transform:uppercase;margin-top:.3rem;}

/* ナビゲーション */
.nav-category{font-size:.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;padding:.8rem .5rem .3rem;margin-top:.5rem;}
.nav-item{display:block;padding:.45rem .8rem;border-radius:6px;font-size:.88rem;color:#374151;cursor:pointer;margin:.1rem 0;transition:background .15s;}
.nav-item:hover{background:#f3f4f6;}
.nav-item.active{background:#eff6ff;color:#1e3a5f;font-weight:600;}

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
.viral-chip{display:inline-block;padding:2px 8px;background:#1e3a5f;color:#fff;border-radius:4px;font-size:.6rem;font-weight:700;}

.kw-card{background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:.8rem 1rem;margin-bottom:.5rem;display:flex;align-items:center;gap:.8rem;box-shadow:0 1px 2px rgba(0,0,0,.04);transition:border-color .15s;}
.kw-card:hover{border-color:#1e3a5f;}
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

.stButton>button{background:#1e3a5f!important;color:#fff!important;font-family:'Inter',sans-serif!important;font-weight:600!important;font-size:.8rem!important;border:none!important;border-radius:8px!important;padding:.5rem 1.5rem!important;}
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

# 時間帯→推定国籍マッピング（JST基準）
TIMEZONE_NATIONALITY = {
    range(0,4):   ["🇺🇸 アメリカ東海岸","🇧🇷 ブラジル","🇨🇦 カナダ"],
    range(4,7):   ["🇺🇸 アメリカ西海岸","🇲🇽 メキシコ","🇨🇦 カナダ西部"],
    range(7,10):  ["🇬🇧 イギリス","🇩🇪 ドイツ","🇫🇷 フランス","🇪🇸 スペイン"],
    range(10,13): ["🇩🇪 ドイツ","🇷🇺 ロシア西部","🇸🇦 サウジアラビア","🇮🇳 インド"],
    range(13,16): ["🇮🇳 インド","🇹🇭 タイ","🇻🇳 ベトナム","🇸🇬 シンガポール"],
    range(16,19): ["🇯🇵 日本","🇰🇷 韓国","🇨🇳 中国","🇹🇼 台湾","🇦🇺 オーストラリア"],
    range(19,22): ["🇯🇵 日本（夜）","🇰🇷 韓国（夜）","🇦🇺 オーストラリア"],
    range(22,24): ["🇺🇸 アメリカ東海岸（朝）","🇧🇷 ブラジル（朝）"],
}

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

def to_df(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def get_nationality(hour):
    for r, nations in TIMEZONE_NATIONALITY.items():
        if hour in r:
            return nations
    return []

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
    yt_term_views = Counter(); yt_set = set()
    for v in yt_videos:
        toks = clean_tokens(v["title"])
        for t in toks + make_bigrams(toks):
            yt_term_views[t] += v["views"]; yt_set.add(t)
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
if "kw_df"           not in st.session_state: st.session_state.kw_df = pd.DataFrame()
if "kw_checked"      not in st.session_state: st.session_state.kw_checked = {}
if "prev_scores"     not in st.session_state: st.session_state.prev_scores = {}
if "last_updated"    not in st.session_state: st.session_state.last_updated = None
if "page"            not in st.session_state: st.session_state.page = "home"

# ── サイドバー ────────────────────────────────────────────────────────────────
with st.sidebar:
    # タイトル（クリックでホームへ）
    if st.button("🌸 Tabibiyori Dashboard", key="home_btn", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    st.markdown('<div style="font-size:.62rem;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;padding:.2rem .5rem .8rem;">Operations Dashboard</div>', unsafe_allow_html=True)

    # ── SNS カテゴリ
    st.markdown('<div class="nav-category">📱 SNS</div>', unsafe_allow_html=True)
    for label, key in [("トレンド","sns_trend"),("DM","sns_dm"),("集客","sns_acquire"),("広告","sns_ads")]:
        active = "active" if st.session_state.page == key else ""
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.page = key; st.rerun()

    # ── 顧客管理 カテゴリ
    st.markdown('<div class="nav-category">👤 顧客管理</div>', unsafe_allow_html=True)
    for label, key in [("顧客関係","crm_customers"),("商品関連","crm_products")]:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.page = key; st.rerun()

    # ── 財務経理 カテゴリ
    st.markdown('<div class="nav-category">💴 財務経理</div>', unsafe_allow_html=True)
    for label, key in [("売上","fin_sales"),("経費","fin_expense"),("費用対効果","fin_roi"),("BS","fin_bs"),("PL","fin_pl")]:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.page = key; st.rerun()

    st.markdown("---")
    try:
        get_client()
        st.markdown('<div style="color:#15803d;font-size:.75rem;font-weight:600;">✅ Supabase接続済み</div>', unsafe_allow_html=True)
    except Exception:
        st.markdown('<div style="color:#dc2626;font-size:.75rem;font-weight:600;">❌ Supabase未接続</div>', unsafe_allow_html=True)

page = st.session_state.page

# ═════════════════════════════════════════════════════════════════════════════
# HOME
# ═════════════════════════════════════════════════════════════════════════════
if page == "home":
    st.markdown('<div class="buz-hero"><h1>🌸 Tabibiyori Dashboard</h1><p>Japan Content Operations Dashboard</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-head">クイックアクセス</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown("### 📱 SNS")
        st.markdown("トレンドキーワード・DM集計・集客・広告")
        if st.button("SNSを開く", key="quick_sns"):
            st.session_state.page = "sns_trend"; st.rerun()
    with c2:
        st.markdown("### 👤 顧客管理")
        st.markdown("顧客登録・購入履歴・Tour予約管理")
        if st.button("顧客管理を開く", key="quick_crm"):
            st.session_state.page = "crm_customers"; st.rerun()
    with c3:
        st.markdown("### 💴 財務経理")
        st.markdown("売上・経費・PL・BS・費用対効果")
        if st.button("財務経理を開く", key="quick_fin"):
            st.session_state.page = "fin_sales"; st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# SNS: トレンド
# ═════════════════════════════════════════════════════════════════════════════
elif page == "sns_trend":
    st.markdown("#### 🔥 トレンドキーワード")

    tab_fetch, tab_approve, tab_history, tab_post = st.tabs([
        "キーワード取得", "✅ チェック・承認", "📚 履歴", "📊 再生数"
    ])

    # ── タブ1：取得
    with tab_fetch:
        if st.button("⟳ データ更新"):
            with st.spinner("取得中…"):
                prev = {r["keyword"].lower():r["score"] for r in st.session_state.kw_df.to_dict("records")} if not st.session_state.kw_df.empty else {}
                gt_terms, gt_scores = fetch_google_trends()
                yt_videos = fetch_youtube_trending()
                df = extract_keywords(gt_terms, gt_scores, yt_videos, prev) if (gt_terms or yt_videos) else pd.DataFrame()
                if df.empty:
                    df = demo_keywords()
                    st.markdown('<div class="info-box">⚠️ デモデータを表示中</div>', unsafe_allow_html=True)
                st.session_state.kw_df = df
                st.session_state.kw_checked = {row["keyword"]: False for _, row in df.iterrows()}
                st.session_state.last_updated = datetime.now()

        df = st.session_state.kw_df
        if not df.empty:
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{len(df)}</div><div class="lbl">キーワード数</div></div>
              <div class="metric-card"><div class="val">{int((df["status"]=="hot").sum())}</div><div class="lbl">🔥 ホット</div></div>
              <div class="metric-card"><div class="val">{int(df["viral_soon"].sum())}</div><div class="lbl">⚡ バイラル</div></div>
              <div class="metric-card"><div class="val">{round(df["score"].mean(),1)}</div><div class="lbl">平均スコア</div></div>
            </div>""", unsafe_allow_html=True)
            for i, row in df.iterrows(): render_kw_card(i, row)
            if st.session_state.last_updated:
                st.markdown(f'<div class="last-updated">最終更新: {st.session_state.last_updated.strftime("%Y-%m-%d %H:%M:%S")}</div>', unsafe_allow_html=True)

    # ── タブ2：チェック・承認→保存
    with tab_approve:
        df = st.session_state.kw_df
        if df.empty:
            st.markdown('<div class="info-box">先に「キーワード取得」タブでデータを取得してください</div>', unsafe_allow_html=True)
        else:
            st.markdown("保存したいキーワードにチェックを入れて「承認して保存」してください。")
            st.markdown('<div class="section-head">キーワード選択（最大50件）</div>', unsafe_allow_html=True)

            # 全選択・全解除
            col_all, col_none = st.columns(2)
            with col_all:
                if st.button("✅ すべて選択"):
                    for _, row in df.iterrows():
                        st.session_state.kw_checked[row["keyword"]] = True
                    st.rerun()
            with col_none:
                if st.button("☐ すべて解除"):
                    for _, row in df.iterrows():
                        st.session_state.kw_checked[row["keyword"]] = False
                    st.rerun()

            checked_list = []
            for _, row in df.iterrows():
                col_chk, col_info = st.columns([0.5, 9.5])
                with col_chk:
                    checked = st.checkbox("", value=st.session_state.kw_checked.get(row["keyword"], False),
                                          key=f"chk_{row['keyword']}")
                    st.session_state.kw_checked[row["keyword"]] = checked
                with col_info:
                    badge = f'<span class="badge badge-{row["status"]}">{STATUS_EMOJI.get(row["status"],"")} {row["status"]}</span>'
                    viral = '<span class="viral-chip">⚡</span>' if row.get("viral_soon") else ""
                    st.markdown(f"**{row['keyword'].title()}** &nbsp; スコア: `{row['score']}` &nbsp; {badge} {viral}", unsafe_allow_html=True)
                if checked: checked_list.append(row)

            st.markdown(f'<div class="info-box">選択中：<strong>{len(checked_list)}件</strong></div>', unsafe_allow_html=True)

            if st.button("✅ 承認して履歴に保存", key="approve_save"):
                if not checked_list:
                    st.markdown('<div class="err-box">キーワードを1つ以上選択してください</div>', unsafe_allow_html=True)
                else:
                    saved = 0
                    for row in checked_list:
                        src = []
                        if row.get("in_gt"): src.append("GoogleTrends")
                        if row.get("in_yt"): src.append("YouTube")
                        res = sb_insert("keyword_history",{
                            "keyword":row["keyword"],"score":row["score"],
                            "status":row["status"],"source":",".join(src)
                        })
                        if res: saved += 1
                    st.markdown(f'<div class="success-box">✅ {saved}件を履歴に保存しました</div>', unsafe_allow_html=True)

    # ── タブ3：履歴
    with tab_history:
        rows = sb_select("keyword_history", order="-score")
        df_hist = to_df(rows)
        if df_hist.empty:
            st.markdown('<div class="info-box">📭 履歴がありません。「チェック・承認」タブから保存してください。</div>', unsafe_allow_html=True)
        else:
            c1,c2 = st.columns(2)
            with c1: f_used   = st.selectbox("フィルター",["すべて","未使用のみ","使用済みのみ"])
            with c2: f_status = st.selectbox("ステータス",["すべて","hot","trending","rising","niche"])
            df_show = df_hist.copy()
            if f_used   == "未使用のみ":   df_show = df_show[df_show["used"]==0]
            elif f_used == "使用済みのみ": df_show = df_show[df_show["used"]==1]
            if f_status != "すべて":       df_show = df_show[df_show["status"]==f_status]
            st.caption(f"{len(df_show)}件")
            for _, row in df_show.iterrows():
                c1,c2,c3,c4,c5,c6 = st.columns([3,1,1.2,1.8,2.5,0.8])
                with c1:
                    st.markdown(f"**{row['keyword'].title()}**")
                    st.caption(str(row.get("created_at",""))[:10])
                with c2: st.metric("スコア", row["score"])
                with c3: st.markdown(f'<span class="badge badge-{row["status"]}">{STATUS_EMOJI.get(row["status"],"")} {row["status"]}</span>', unsafe_allow_html=True)
                with c4:
                    if row["used"] == 0:
                        if st.button("✅ 使用済", key=f"use_{row['id']}"):
                            sb_update("keyword_history",{"used":1,"used_date":str(date.today())},{"id":row["id"]}); st.rerun()
                    else:
                        st.markdown(f'<span class="badge badge-used">✅ {row.get("used_date","") or ""}</span>', unsafe_allow_html=True)
                        if st.button("↩ 戻す", key=f"unuse_{row['id']}"):
                            sb_update("keyword_history",{"used":0,"used_date":None},{"id":row["id"]}); st.rerun()
                with c5:
                    note = st.text_input("メモ", value=row.get("note","") or "", key=f"note_{row['id']}",
                                         label_visibility="collapsed", placeholder="メモを入力…")
                    if note != (row.get("note","") or ""):
                        sb_update("keyword_history",{"note":note},{"id":row["id"]})
                with c6:
                    if st.button("🗑", key=f"del_{row['id']}"):
                        sb_delete("keyword_history",{"id":row["id"]}); st.rerun()
                st.divider()

    # ── タブ4：再生数
    with tab_post:
        st.markdown('<div class="section-head">投稿を登録</div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            platform   = st.selectbox("プラットフォーム", SNS_PLATFORMS)
            post_theme = st.text_input("投稿テーマ")
            kw_used    = st.text_input("使用キーワード")
        with c2:
            post_url  = st.text_input("投稿URL（任意）")
            posted_at = st.date_input("投稿日", value=date.today())
        vc1,vc2,vc3 = st.columns(3); vc4,vc5,vc6 = st.columns(3)
        with vc1: v_1h  = st.number_input("1時間後",  min_value=0, value=0, step=100)
        with vc2: v_6h  = st.number_input("6時間後",  min_value=0, value=0, step=100)
        with vc3: v_24h = st.number_input("24時間後", min_value=0, value=0, step=100)
        with vc4: v_72h = st.number_input("72時間後", min_value=0, value=0, step=100)
        with vc5: v_7d  = st.number_input("7日後",    min_value=0, value=0, step=100)
        with vc6: v_30d = st.number_input("30日後",   min_value=0, value=0, step=100)
        vd = {"1h":v_1h,"6h":v_6h,"24h":v_24h,"72h":v_72h,"7d":v_7d,"30d":v_30d}
        bz = buzz_status(platform, vd)
        st.markdown(f'<div class="info-box">バズ判定：<strong>{bz}</strong>　最大：<strong>{max(vd.values()):,}</strong></div>', unsafe_allow_html=True)
        if st.button("💾 保存"):
            if post_theme:
                sb_insert("post_tracking",{"platform":platform,"post_url":post_url,"post_theme":post_theme,
                    "keyword_used":kw_used,"posted_at":str(posted_at),"v_1h":v_1h,"v_6h":v_6h,
                    "v_24h":v_24h,"v_72h":v_72h,"v_7d":v_7d,"v_30d":v_30d,"buzz_status":bz})
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

        # 一覧
        rows = sb_select("post_tracking", order="-posted_at")
        df_posts = to_df(rows)
        if not df_posts.empty:
            for col in ["v_1h","v_24h","v_7d","v_30d"]:
                if col not in df_posts.columns: df_posts[col] = 0
            st.markdown('<div class="section-head">投稿一覧</div>', unsafe_allow_html=True)
            for _, row in df_posts.iterrows():
                c1,c2,c3,c4 = st.columns([3,4,1.5,0.5])
                with c1:
                    st.markdown(f"**{PLATFORM_EMOJI.get(row['platform'],'')} {row['post_theme']}**")
                    st.caption(f"{row['posted_at']}")
                with c2: st.markdown(f"1h:`{row['v_1h']:,}` / 24h:`{row['v_24h']:,}` / 7d:`{row['v_7d']:,}` / 30d:`{row['v_30d']:,}`")
                with c3: st.markdown(f"**{row.get('buzz_status','')}**")
                with c4:
                    if st.button("🗑", key=f"pdel_{row['id']}"):
                        sb_delete("post_tracking",{"id":row["id"]}); st.rerun()
                st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# SNS: DM
# ═════════════════════════════════════════════════════════════════════════════
elif page == "sns_dm":
    st.markdown("#### 💬 DM数トラッキング")
    tab_daily, tab_hourly, tab_graph = st.tabs(["日次入力","⏰ 時間帯別入力","グラフ・分析"])

    # ── 日次入力
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

    # ── 時間帯別入力
    with tab_hourly:
        st.markdown("各プラットフォームの時間帯別DM数を入力してください（0〜23時・JST）")
        h_date    = st.date_input("日付", value=date.today(), key="h_date")
        h_platform = st.selectbox("プラットフォーム", ALL_DM_PLATFORMS, key="h_plat")

        st.markdown('<div class="section-head">時間帯別DM数入力</div>', unsafe_allow_html=True)
        hourly_vals = {}
        # 6列×4行で0〜23時
        for row_start in range(0, 24, 6):
            cols = st.columns(6)
            for i, col in enumerate(cols):
                hour = row_start + i
                with col:
                    hourly_vals[hour] = st.number_input(f"{hour:02d}時", min_value=0, value=0, step=1, key=f"h_{hour}")

        total_h = sum(hourly_vals.values())
        peak_h  = max(hourly_vals, key=hourly_vals.get)
        st.markdown(f'<div class="info-box">合計：<strong>{total_h}件</strong>　ピーク：<strong>{peak_h:02d}時</strong>（{hourly_vals[peak_h]}件）</div>', unsafe_allow_html=True)

        if st.button("💾 時間帯データを保存", key="hourly_save"):
            for hour, count in hourly_vals.items():
                if count > 0:
                    sb_upsert("dm_hourly", {
                        "date": str(h_date),
                        "platform": h_platform,
                        "hour": hour,
                        "count": count
                    })
            st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

    # ── グラフ・分析
    with tab_graph:
        rows = sb_select("dm_tracking", order="date")
        df_dm = to_df(rows)

        # 時間帯分析
        rows_h = sb_select("dm_hourly", order="hour")
        df_h   = to_df(rows_h)

        if not df_h.empty:
            st.markdown('<div class="section-head">時間帯別DM分析</div>', unsafe_allow_html=True)
            h_plat_filter = st.selectbox("プラットフォーム", ["全体"] + ALL_DM_PLATFORMS, key="h_filter")
            df_hf = df_h if h_plat_filter == "全体" else df_h[df_h["platform"]==h_plat_filter]
            if not df_hf.empty:
                hourly_agg = df_hf.groupby("hour")["count"].sum().reset_index()
                hourly_agg.columns = ["時間（JST）","DM数"]
                hourly_agg = hourly_agg.sort_values("時間（JST）")
                st.bar_chart(hourly_agg.set_index("時間（JST）"))

                # ゴールデンタイム
                if not hourly_agg.empty:
                    top3 = hourly_agg.nlargest(3,"DM数")
                    st.markdown('<div class="section-head">ゴールデンタイム TOP3 と推定国籍</div>', unsafe_allow_html=True)
                    for _, r in top3.iterrows():
                        hour_val = int(r["時間（JST）"])
                        nations  = get_nationality(hour_val)
                        nations_str = "　".join(nations) if nations else "不明"
                        st.markdown(f"""
                        <div class="metric-card" style="margin-bottom:.5rem;">
                          <div style="font-size:1.1rem;font-weight:700;color:#1e3a5f;">{hour_val:02d}:00〜{hour_val+1:02d}:00　<span style="color:#6b7280;font-size:.9rem;">{int(r['DM数'])}件</span></div>
                          <div style="font-size:.82rem;color:#374151;margin-top:.3rem;">推定国籍：{nations_str}</div>
                        </div>""", unsafe_allow_html=True)

                # プラットフォーム別トレンド
                st.markdown('<div class="section-head">プラットフォーム別 時間帯トレンド</div>', unsafe_allow_html=True)
                pivot = df_h.groupby(["hour","platform"])["count"].sum().reset_index()
                if not pivot.empty:
                    pivot_wide = pivot.pivot(index="hour", columns="platform", values="count").fillna(0)
                    st.line_chart(pivot_wide)

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
                <div class="progress-wrap"><div class="progress-fill" style="width:{min(progress,100)}%"></div></div>
                """, unsafe_allow_html=True)
                st.bar_chart(df_f.set_index("date")["合計"])

                share = {p: int(df_f[DM_COLS[p]].sum()) for p in ALL_DM_PLATFORMS if DM_COLS[p] in df_f.columns}
                total_s = sum(share.values()) or 1
                for i in range(0, len(ALL_DM_PLATFORMS), 3):
                    cols = st.columns(3)
                    for j, pl in enumerate(ALL_DM_PLATFORMS[i:i+3]):
                        cnt = share.get(pl,0)
                        with cols[j]: st.metric(f"{PLATFORM_EMOJI.get(pl,'')} {pl}",f"{cnt:,}件",f"{round(cnt/total_s*100,1)}%")
        elif df_h.empty:
            st.markdown('<div class="info-box">まだデータがありません</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# SNS: 集客・広告（準備中）
# ═════════════════════════════════════════════════════════════════════════════
elif page in ["sns_acquire","sns_ads"]:
    label = "集客" if page == "sns_acquire" else "広告"
    st.markdown(f"#### 📱 SNS {label}")
    st.markdown(f'<div class="coming-soon"><div style="font-size:2rem;margin-bottom:1rem;">🔒</div><div style="font-size:1rem;color:#6b7280;font-weight:600;">COMING SOON</div><div style="font-size:.82rem;color:#9ca3af;margin-top:.5rem;">{label}機能は準備中です</div></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# 顧客管理：顧客関係
# ═════════════════════════════════════════════════════════════════════════════
elif page == "crm_customers":
    st.markdown("#### 👤 顧客管理")

    tab_reg, tab_list, tab_purchase = st.tabs(["新規登録","顧客一覧","購入履歴"])

    # ── 新規登録
    with tab_reg:
        st.markdown('<div class="section-head">顧客情報を登録</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            c_name     = st.text_input("名前")
            c_email    = st.text_input("メールアドレス")
            c_phone    = st.text_input("電話番号")
            c_username = st.text_input("SNSユーザー名")
        with c2:
            c_platform = st.selectbox("流入プラットフォーム", ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"])
            c_address  = st.text_input("住所（任意）")
            c_note     = st.text_area("備考", height=80)

        if st.button("💾 顧客を登録する"):
            if not c_name:
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("customers", {
                    "name":c_name, "email":c_email, "phone":c_phone,
                    "username":c_username, "platform":c_platform,
                    "address":c_address, "note":c_note
                })
                if res: st.markdown('<div class="success-box">✅ 登録しました</div>', unsafe_allow_html=True)

    # ── 顧客一覧
    with tab_list:
        rows = sb_select("customers", order="-created_at")
        df_c = to_df(rows)
        if df_c.empty:
            st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
        else:
            search = st.text_input("🔍 検索（名前・メール・ユーザー名）", placeholder="検索キーワード")
            if search:
                mask = df_c.apply(lambda r: search.lower() in str(r.get("name","")).lower()
                                  or search.lower() in str(r.get("email","")).lower()
                                  or search.lower() in str(r.get("username","")).lower(), axis=1)
                df_c = df_c[mask]
            st.caption(f"{len(df_c)}件")
            for _, row in df_c.iterrows():
                with st.expander(f"👤 {row['name']}　{PLATFORM_EMOJI.get(row.get('platform',''),'')} {row.get('platform','')}　📅 {str(row.get('created_at',''))[:10]}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        st.markdown(f"**メール：** {row.get('email','') or '未登録'}")
                        st.markdown(f"**電話：** {row.get('phone','') or '未登録'}")
                        st.markdown(f"**SNS：** {row.get('username','') or '未登録'}")
                    with ec2:
                        st.markdown(f"**住所：** {row.get('address','') or '未登録'}")
                        st.markdown(f"**流入元：** {row.get('platform','')}")
                    st.markdown("**備考：**")
                    new_note = st.text_area("", value=row.get("note","") or "", key=f"cn_{row['id']}", height=80, label_visibility="collapsed")
                    nc1, nc2, nc3 = st.columns([1,1,4])
                    with nc1:
                        if st.button("💾 更新", key=f"cu_{row['id']}"):
                            sb_update("customers",{"note":new_note},{"id":row["id"]})
                            st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True)
                    with nc2:
                        if st.button("↩ 取消", key=f"cc_{row['id']}"):
                            st.rerun()
                    with nc3:
                        if st.button("🗑 削除", key=f"cd_{row['id']}"):
                            sb_delete("customers",{"id":row["id"]}); st.rerun()

    # ── 購入履歴
    with tab_purchase:
        rows_c = sb_select("customers", order="-created_at")
        df_all_c = to_df(rows_c)
        if df_all_c.empty:
            st.markdown('<div class="info-box">先に顧客を登録してください</div>', unsafe_allow_html=True)
        else:
            sel_c = st.selectbox("顧客を選択", df_all_c["name"].tolist(), key="pur_c")
            c_id  = int(df_all_c[df_all_c["name"]==sel_c]["id"].values[0])

            prod_type = st.selectbox("商品カテゴリ", ["Tour","Patreon","Guidebook"])

            if prod_type == "Tour":
                st.markdown('<div class="section-head">Tour 予約情報</div>', unsafe_allow_html=True)
                tc1, tc2 = st.columns(2)
                with tc1:
                    tour_type   = st.selectbox("Tourの種類", ["Kimono Photo Experience","Custom Tour","Bento Tour"])
                    tour_status = st.selectbox("予約ステータス", ["仮予約","ガイド手配中","カメラマン手配中","確定","料金回収済み","キャンセル"])
                    tour_date   = st.date_input("ツアー日時", value=date.today())
                    meet_place  = st.text_input("合流場所")
                    guide_name  = st.text_input("ガイド名")
                with tc2:
                    participants = st.number_input("参加人数", min_value=1, value=1, step=1)
                    price        = st.number_input("料金（¥）", min_value=0, value=0, step=1000)
                    discount     = st.number_input("割引額（¥）", min_value=0, value=0, step=500)
                    payment_type = st.selectbox("支払方法", ["現金","キャッシュレス"])
                    receptionist = st.text_input("受付担当者名")
                    confirmed    = st.checkbox("内容確認（お客様サイン済み）")

                if st.button("💾 Tour予約を保存"):
                    sb_insert("purchases", {
                        "customer_id":c_id, "product_type":"Tour",
                        "tour_type":tour_type, "tour_status":tour_status,
                        "tour_date":str(tour_date), "meet_place":meet_place,
                        "guide_name":guide_name, "participants":participants,
                        "price":price, "discount":discount,
                        "payment_type":payment_type, "receptionist":receptionist,
                        "confirmed":confirmed
                    })
                    st.markdown('<div class="success-box">✅ Tour予約を保存しました</div>', unsafe_allow_html=True)

            elif prod_type == "Patreon":
                st.markdown('<div class="section-head">Patreon 情報</div>', unsafe_allow_html=True)
                pc1, pc2 = st.columns(2)
                with pc1:
                    join_date = st.date_input("入会日", value=date.today())
                    plan      = st.text_input("プラン名")
                with pc2:
                    cancel_date = st.date_input("解約日（任意）", value=None)
                if st.button("💾 Patreon情報を保存"):
                    sb_insert("purchases", {
                        "customer_id":c_id, "product_type":"Patreon",
                        "join_date":str(join_date), "plan":plan,
                        "cancel_date":str(cancel_date) if cancel_date else None
                    })
                    st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

            elif prod_type == "Guidebook":
                st.markdown('<div class="section-head">Guidebook 情報</div>', unsafe_allow_html=True)
                gc1, gc2 = st.columns(2)
                with gc1:
                    gb_name  = st.text_input("ガイドブック名")
                    gb_date  = st.date_input("購入日", value=date.today())
                with gc2:
                    gb_price  = st.number_input("金額（¥）", min_value=0, value=0, step=100)
                    gb_cancel = st.checkbox("キャンセル済み")
                if st.button("💾 Guidebook購入を保存"):
                    sb_insert("purchases", {
                        "customer_id":c_id, "product_type":"Guidebook",
                        "guidebook_name":gb_name, "purchase_date":str(gb_date),
                        "price":gb_price, "cancelled":gb_cancel
                    })
                    st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

            # 購入履歴一覧
            st.markdown('<div class="section-head">購入履歴一覧</div>', unsafe_allow_html=True)
            rows_p = sb_select("purchases", filters={"customer_id":c_id}, order="-created_at")
            df_p   = to_df(rows_p)
            if df_p.empty:
                st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
            else:
                for _, row in df_p.iterrows():
                    pt = row.get("product_type","")
                    if pt == "Tour":
                        label_str = f"🗺 {row.get('tour_type','')}　{row.get('tour_date','')}　{row.get('tour_status','')}　¥{int(row.get('price',0)):,}"
                    elif pt == "Patreon":
                        label_str = f"🎁 Patreon　{row.get('plan','')}　入会:{row.get('join_date','')}"
                    else:
                        label_str = f"📖 {row.get('guidebook_name','')}　{row.get('purchase_date','')}　¥{int(row.get('price',0)):,}"
                    pc1, pc2 = st.columns([8,1])
                    with pc1: st.markdown(label_str)
                    with pc2:
                        if st.button("🗑", key=f"pd_{row['id']}"):
                            sb_delete("purchases",{"id":row["id"]}); st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# 顧客管理：商品関連（準備中）
# ─────────────────────────────────────────────────────────────────────────────
elif page == "crm_products":
    st.markdown("#### 📦 商品関連")
    st.markdown('<div class="coming-soon"><div style="font-size:2rem;margin-bottom:1rem;">🔒</div><div style="font-size:1rem;color:#6b7280;font-weight:600;">COMING SOON</div><div style="font-size:.82rem;color:#9ca3af;margin-top:.5rem;">準備中です</div></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# 財務経理：経費
# ═════════════════════════════════════════════════════════════════════════════
elif page == "fin_expense":
    st.markdown("#### 🧾 経費入力")

    tab_input, tab_list, tab_graph = st.tabs(["新規入力","経費一覧","グラフ分析"])

    ACCOUNTS = ["広告費","撮影代","交通費","宿泊費","通信費","消耗品費","外注費","手数料","その他"]
    TAX_TYPES = ["課税（10%）","課税（8%）","非課税","不課税"]

    with tab_input:
        st.markdown('<div class="section-head">経費を入力</div>', unsafe_allow_html=True)
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            exp_no      = st.text_input("入力番号", placeholder="例：EXP-001")
            exp_date    = st.date_input("取引日", value=date.today())
            exp_account = st.selectbox("勘定科目", ACCOUNTS)
            exp_tax     = st.selectbox("税区分", TAX_TYPES)
        with fc2:
            exp_store   = st.text_input("負担店舗", placeholder="例：東京店")
            exp_out     = st.number_input("出金（¥）", min_value=0, value=0, step=100)
            exp_in      = st.number_input("入金（¥）", min_value=0, value=0, step=100)
            exp_balance = st.number_input("残高（¥）", min_value=0, value=0, step=100)
        with fc3:
            exp_purpose = st.text_input("経費名・目的")
            exp_user    = st.text_input("使用者")
            exp_partner = st.text_input("取引先")
            exp_month   = st.text_input("対象月", value=date.today().strftime("%Y-%m"))

        exp_note = st.text_area("備考", height=60)

        # 領収書アップロード
        st.markdown('<div class="section-head">領収書（PDF）</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("PDFをアップロード", type=["pdf"], key="exp_pdf")

        receipt_b64 = None
        if uploaded:
            import base64
            receipt_b64 = base64.b64encode(uploaded.read()).decode()
            st.markdown('<div class="success-box">✅ PDFアップロード済み</div>', unsafe_allow_html=True)
            # プレビュー
            pdf_display = f'<iframe src="data:application/pdf;base64,{receipt_b64}" width="100%" height="400px"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            if st.button("🗑 PDFを削除", key="del_pdf"):
                uploaded = None
                receipt_b64 = None
                st.rerun()

        st.markdown("---")
        col_save, col_clear = st.columns([3,1])
        with col_save:
            if st.button("✅ 確定して保存", key="exp_save"):
                if not exp_purpose:
                    st.markdown('<div class="err-box">経費名・目的は必須です</div>', unsafe_allow_html=True)
                else:
                    sb_insert("expenses", {
                        "exp_no":exp_no, "exp_date":str(exp_date),
                        "account":exp_account, "tax_type":exp_tax,
                        "store":exp_store, "amount_out":exp_out,
                        "amount_in":exp_in, "balance":exp_balance,
                        "purpose":exp_purpose, "user":exp_user,
                        "partner":exp_partner, "note":exp_note,
                        "target_month":exp_month, "receipt_pdf":receipt_b64
                    })
                    st.markdown('<div class="success-box">✅ 経費を保存しました</div>', unsafe_allow_html=True)
        with col_clear:
            if st.button("🗑 全消去", key="exp_clear"):
                st.rerun()

    with tab_list:
        rows = sb_select("expenses", order="-exp_date")
        df_exp = to_df(rows)
        if df_exp.empty:
            st.markdown('<div class="info-box">経費データがありません</div>', unsafe_allow_html=True)
        else:
            for col in ["amount_out","amount_in","balance"]:
                if col not in df_exp.columns: df_exp[col] = 0
            total_out = int(df_exp["amount_out"].sum())
            total_in  = int(df_exp["amount_in"].sum())
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">¥{total_out:,}</div><div class="lbl">総出金</div></div>
              <div class="metric-card"><div class="val">¥{total_in:,}</div><div class="lbl">総入金</div></div>
              <div class="metric-card"><div class="val">{len(df_exp)}</div><div class="lbl">件数</div></div>
            </div>""", unsafe_allow_html=True)

            for _, row in df_exp.iterrows():
                with st.expander(f"🧾 {row.get('exp_date','')}　{row.get('account','')}　{row.get('purpose','')}　¥{int(row.get('amount_out',0)):,}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        st.markdown(f"**番号：** {row.get('exp_no','')}")
                        st.markdown(f"**勘定科目：** {row.get('account','')}")
                        st.markdown(f"**税区分：** {row.get('tax_type','')}")
                        st.markdown(f"**使用者：** {row.get('user','')}")
                    with ec2:
                        st.markdown(f"**出金：** ¥{int(row.get('amount_out',0)):,}")
                        st.markdown(f"**入金：** ¥{int(row.get('amount_in',0)):,}")
                        st.markdown(f"**取引先：** {row.get('partner','')}")
                        st.markdown(f"**対象月：** {row.get('target_month','')}")
                    if row.get("receipt_pdf"):
                        st.markdown("**領収書：**")
                        st.markdown(f'<iframe src="data:application/pdf;base64,{row["receipt_pdf"]}" width="100%" height="300px"></iframe>', unsafe_allow_html=True)
                    if st.button("🗑 削除", key=f"edel_{row['id']}"):
                        sb_delete("expenses",{"id":row["id"]}); st.rerun()

    with tab_graph:
        rows = sb_select("expenses", order="-exp_date")
        df_exp = to_df(rows)
        if df_exp.empty:
            st.markdown('<div class="info-box">経費データがありません</div>', unsafe_allow_html=True)
        else:
            if "amount_out" not in df_exp.columns: df_exp["amount_out"] = 0
            st.markdown('<div class="section-head">勘定科目別 経費合計</div>', unsafe_allow_html=True)
            acc_agg = df_exp.groupby("account")["amount_out"].sum().sort_values(ascending=False)
            acc_df  = acc_agg.reset_index()
            acc_df.columns = ["勘定科目","金額（¥）"]
            st.bar_chart(acc_df.set_index("勘定科目"))
            for _, row in acc_df.iterrows():
                st.markdown(f"**{row['勘定科目']}**　¥{int(row['金額（¥）']):,}")

# ═════════════════════════════════════════════════════════════════════════════
# 財務経理：売上
# ═════════════════════════════════════════════════════════════════════════════
elif page == "fin_sales":
    st.markdown("#### 💴 売上管理")

    tab_input, tab_dash = st.tabs(["売上入力","経営ダッシュボード"])

    BUSINESSES = ["Tour","Patreon","Guidebook"]

    with tab_input:
        st.markdown('<div class="section-head">売上を入力</div>', unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)
        with sc1:
            s_date     = st.date_input("売上日", value=date.today())
            s_business = st.selectbox("事業区分", BUSINESSES)
            s_item     = st.text_input("内容", placeholder="例：Kimono Photo Experience")
        with sc2:
            s_amount   = st.number_input("売上金額（¥）", min_value=0, value=0, step=1000)
            s_expense  = st.number_input("関連経費（¥）", min_value=0, value=0, step=1000)
            s_note     = st.text_input("備考")

        if st.button("💾 売上を保存"):
            if s_amount == 0:
                st.markdown('<div class="err-box">金額を入力してください</div>', unsafe_allow_html=True)
            else:
                sb_insert("sales", {
                    "sale_date":str(s_date), "business":s_business,
                    "item":s_item, "amount":s_amount,
                    "expense":s_expense, "note":s_note
                })
                st.markdown('<div class="success-box">✅ 売上を保存しました</div>', unsafe_allow_html=True)

    with tab_dash:
        rows = sb_select("sales", order="-sale_date")
        df_s = to_df(rows)
        rows_e = sb_select("expenses", order="-exp_date")
        df_e   = to_df(rows_e)

        if df_s.empty:
            st.markdown('<div class="info-box">売上データがありません</div>', unsafe_allow_html=True)
        else:
            if "amount"  not in df_s.columns: df_s["amount"]  = 0
            if "expense" not in df_s.columns: df_s["expense"] = 0
            total_sales   = int(df_s["amount"].sum())
            total_expense = int(df_s["expense"].sum()) + (int(df_e["amount_out"].sum()) if not df_e.empty and "amount_out" in df_e.columns else 0)
            profit        = total_sales - total_expense

            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">¥{total_sales:,}</div><div class="lbl">総売上</div></div>
              <div class="metric-card"><div class="val">¥{total_expense:,}</div><div class="lbl">総経費</div></div>
              <div class="metric-card"><div class="val">¥{profit:,}</div><div class="lbl">利益</div></div>
              <div class="metric-card"><div class="val">{round(profit/total_sales*100,1) if total_sales else 0}%</div><div class="lbl">利益率</div></div>
            </div>""", unsafe_allow_html=True)

            st.markdown('<div class="section-head">事業別 売上 vs 経費</div>', unsafe_allow_html=True)
            for biz in BUSINESSES:
                biz_sales = int(df_s[df_s["business"]==biz]["amount"].sum()) if not df_s.empty else 0
                biz_exp   = int(df_s[df_s["business"]==biz]["expense"].sum()) if not df_s.empty else 0
                biz_profit = biz_sales - biz_exp
                color = "#15803d" if biz_profit >= 0 else "#dc2626"
                st.markdown(f"""
                <div class="metric-card" style="margin-bottom:.5rem;">
                  <div style="font-weight:700;font-size:1rem;color:#1e3a5f;margin-bottom:.4rem;">{biz}</div>
                  <div style="display:flex;gap:1.5rem;font-size:.88rem;">
                    <span>売上：<strong>¥{biz_sales:,}</strong></span>
                    <span>経費：<strong>¥{biz_exp:,}</strong></span>
                    <span style="color:{color};">利益：<strong>¥{biz_profit:,}</strong></span>
                  </div>
                </div>""", unsafe_allow_html=True)

            st.markdown('<div class="section-head">月別売上推移</div>', unsafe_allow_html=True)
            df_s["month"] = pd.to_datetime(df_s["sale_date"]).dt.strftime("%Y-%m")
            monthly = df_s.groupby(["month","business"])["amount"].sum().reset_index()
            if not monthly.empty:
                pivot = monthly.pivot(index="month",columns="business",values="amount").fillna(0)
                st.bar_chart(pivot)

# ═════════════════════════════════════════════════════════════════════════════
# 財務経理：費用対効果・BS・PL（準備中）
# ═════════════════════════════════════════════════════════════════════════════
elif page in ["fin_roi","fin_bs","fin_pl"]:
    labels = {"fin_roi":"📊 費用対効果","fin_bs":"📋 BS（貸借対照表）","fin_pl":"📈 PL（損益計算書）"}
    st.markdown(f"#### {labels.get(page,'')}")
    st.markdown('<div class="coming-soon"><div style="font-size:2rem;margin-bottom:1rem;">🔒</div><div style="font-size:1rem;color:#6b7280;font-weight:600;">COMING SOON</div><div style="font-size:.82rem;color:#9ca3af;margin-top:.5rem;">この機能は現在開発中です。<br>次のアップデートで実装予定です。</div></div>', unsafe_allow_html=True)

else:
    st.markdown('<div class="info-box">左メニューからページを選択してください</div>', unsafe_allow_html=True)
