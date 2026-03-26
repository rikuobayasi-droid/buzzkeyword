"""
common.py — 全ページ共通の定数・CSS・ヘルパー
"""
import streamlit as st
import pandas as pd
import os, re, time, base64
from datetime import datetime, timedelta, date
from collections import Counter

# ── 定数 ──────────────────────────────────────────────────────────────────────
SNS_PLATFORMS    = ["Instagram","Facebook","TikTok","YouTube"]
ALL_DM_PLATFORMS = ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail"]
PLATFORM_EMOJI   = {"Instagram":"📸","Facebook":"👥","TikTok":"🎵","YouTube":"▶️",
                    "Threads":"🧵","X":"✖️","LINE":"💬","WhatsApp":"📱","Gmail":"📧"}
DM_COLS = {"Instagram":"dm_instagram","Facebook":"dm_facebook","TikTok":"dm_tiktok",
           "YouTube":"dm_youtube","Threads":"dm_threads","X":"dm_x",
           "LINE":"dm_line","WhatsApp":"dm_whatsapp","Gmail":"dm_gmail"}
DM_GOAL       = 20000
STATUS_EMOJI  = {"hot":"🔥","trending":"📈","rising":"🚀","niche":"💎"}
TOUR_TYPES    = ["Kimono Photo Experience","Custom Tour","Bento Tour"]
TOUR_STATUSES = ["仮予約","ガイド手配中","カメラマン手配中","確定","料金回収済み","キャンセル"]
PAYMENT_TYPES = ["現金","キャッシュレス"]
ACCOUNTS      = ["広告費","撮影代","交通費","宿泊費","通信費","消耗品費",
                 "外注費","手数料","人件費","家賃","水道光熱費","その他"]
TAX_TYPES     = ["課税（10%）","課税（8%）","非課税","不課税"]
BUSINESSES    = ["Tour","Patreon","Guidebook"]

TIMEZONE_NATIONALITY = {
    range(0,4):  ["🇺🇸 アメリカ東海岸","🇧🇷 ブラジル","🇨🇦 カナダ"],
    range(4,7):  ["🇺🇸 アメリカ西海岸","🇲🇽 メキシコ","🇨🇦 カナダ西部"],
    range(7,10): ["🇬🇧 イギリス","🇩🇪 ドイツ","🇫🇷 フランス","🇪🇸 スペイン"],
    range(10,13):["🇩🇪 ドイツ","🇷🇺 ロシア西部","🇸🇦 サウジアラビア","🇮🇳 インド"],
    range(13,16):["🇮🇳 インド","🇹🇭 タイ","🇻🇳 ベトナム","🇸🇬 シンガポール"],
    range(16,19):["🇯🇵 日本","🇰🇷 韓国","🇨🇳 中国","🇹🇼 台湾","🇦🇺 オーストラリア"],
    range(19,22):["🇯🇵 日本（夜）","🇰🇷 韓国（夜）","🇦🇺 オーストラリア"],
    range(22,24):["🇺🇸 アメリカ東海岸（朝）","🇧🇷 ブラジル（朝）"],
}

BUZZ_THRESHOLDS = {
    "Instagram":{"1h":1000,"6h":5000,"24h":50000,"72h":100000,"7d":200000,"30d":500000},
    "Facebook": {"1h":500, "6h":2000,"24h":10000,"72h":30000, "7d":80000, "30d":200000},
    "TikTok":   {"1h":1000,"6h":5000,"24h":20000,"72h":50000, "7d":150000,"30d":400000},
    "YouTube":  {"1h":200, "6h":800, "24h":3000, "72h":8000,  "7d":20000, "30d":80000},
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

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:#1a1a2e;}
.stApp{background:#f8f9fc;}
#MainMenu,footer,header{visibility:hidden;}
section[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e5e7eb;}
.page-title{font-family:'Inter',sans-serif;font-weight:700;font-size:1.6rem;color:#1e3a5f;margin-bottom:1rem;}
.metric-row{display:flex;gap:.8rem;margin:1rem 0;flex-wrap:wrap;}
.metric-card{flex:1;min-width:130px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:1rem 1.2rem;position:relative;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.05);}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:#1e3a5f;}
.metric-card .val{font-family:'Space Mono',monospace;font-size:1.6rem;font-weight:700;color:#1e3a5f;line-height:1;}
.metric-card .lbl{font-size:.68rem;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;margin-top:.3rem;}
.section-head{font-family:'Space Mono',monospace;font-size:.65rem;letter-spacing:3px;text-transform:uppercase;color:#9ca3af;border-bottom:1px solid #e5e7eb;padding-bottom:.4rem;margin:1.2rem 0 .8rem;}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.65rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;}
.badge-hot{background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.badge-trending{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;}
.badge-rising{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;}
.badge-niche{background:#faf5ff;color:#7c3aed;border:1px solid #e9d5ff;}
.badge-used{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0;}
.badge-unused{background:#f9fafb;color:#9ca3af;border:1px solid #e5e7eb;}
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
"""

# ── ヘルパー ──────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)

def setup_sidebar():
    with st.sidebar:
        # ❌ 完全に削除
        # st.page_link("app", label="🌸 Tabibiyori Dashboard")

        # ✅ 代わりにこれ
        if st.button("🌸 Tabibiyori Dashboard"):
            st.switch_page("app.py")

        st.markdown(
            '<div style="font-size:.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;padding:.8rem .5rem .3rem;">📱 SNS</div>',
            unsafe_allow_html=True
        )

        st.page_link("pages/01_sns_trend.py",       label="トレンド")
        st.page_link("pages/02_sns_dm.py",          label="DM")
        st.page_link("pages/03_sns_acquisition.py", label="集客")
        st.page_link("pages/04_sns_ads.py",         label="広告")

        st.markdown(
            '<div style="font-size:.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;padding:.8rem .5rem .3rem;">👤 顧客管理</div>',
            unsafe_allow_html=True
        )

        st.page_link("pages/05_crm_customers.py", label="顧客関係")
        st.page_link("pages/06_crm_products.py",  label="商品関連")

        st.markdown(
            '<div style="font-size:.62rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;padding:.8rem .5rem .3rem;">💴 財務経理</div>',
            unsafe_allow_html=True
        )

        st.page_link("pages/07_finance_sales.py",   label="売上")
        st.page_link("pages/08_finance_expense.py", label="経費")
        st.page_link("pages/09_finance_roi.py",     label="費用対効果")
        st.page_link("pages/10_finance_bs.py",      label="BS")
        st.page_link("pages/11_finance_pl.py",      label="PL")

        st.markdown("---")

        from db import get_client
        try:
            get_client()
            st.markdown(
                '<div style="color:#15803d;font-size:.75rem;font-weight:600;">✅ Supabase接続済み</div>',
                unsafe_allow_html=True
            )
        except Exception:
            st.markdown(
                '<div style="color:#dc2626;font-size:.75rem;font-weight:600;">❌ Supabase未接続</div>',
                unsafe_allow_html=True
            )

def to_df(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()

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

def get_nationality(hour):
    for r, nations in TIMEZONE_NATIONALITY.items():
        if hour in r: return nations
    return []

def render_kw_card(i, row, show_used=False):
    badge_cls = f"badge-{row['status']}"
    viral = '<span class="viral-chip">⚡ VIRAL SOON</span>' if row.get("viral_soon") else ""
    src_gt = '<span style="font-size:.6rem;padding:1px 6px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:8px;margin-left:3px;">GT</span>' if row.get("in_gt") else ""
    src_yt = '<span style="font-size:.6rem;padding:1px 6px;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:8px;margin-left:3px;">YT</span>' if row.get("in_yt") else ""
    used_html = ('<span class="badge badge-used">✅ 使用済</span>' if row.get("used") else '<span class="badge badge-unused">未使用</span>') if show_used else ""
    st.markdown(f"""<div class="kw-card"><span class="kw-rank">#{i+1:02d}</span><span class="kw-word">{row['keyword'].title()}{src_gt}{src_yt}</span><div class="score-bar-wrap"><div class="score-bar-bg"><div class="score-bar-fill" style="width:{min(int(row['score']),100)}%"></div></div><span class="score-val">{row['score']:.0f}</span></div><span class="badge {badge_cls}">{STATUS_EMOJI.get(row['status'],'')} {row['status']}</span>{viral}{used_html}<span style="min-width:80px;color:#9ca3af;font-size:.68rem;">⏱ {row.get('peak_est','')}</span></div>""", unsafe_allow_html=True)

def coming_soon_page(title):
    inject_css()
    setup_sidebar()
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="coming-soon"><div style="font-size:2.5rem;margin-bottom:1rem;">🔒</div><div style="font-size:1rem;color:#6b7280;font-weight:600;margin-bottom:.5rem;">COMING SOON</div><div style="font-size:.82rem;color:#9ca3af;line-height:1.9;">この機能は現在開発中です。<br>次のアップデートで実装予定です。</div></div>', unsafe_allow_html=True)
