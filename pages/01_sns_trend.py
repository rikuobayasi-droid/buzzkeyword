"""
pages/01_sns_trend.py — SNS トレンドキーワード
URL: /sns_trend

修正内容:
- buzz_status を common.py から正しくimport (NameError修正)
- 全選択・全解除を session_state 直接操作方式に変更
- 絵文字を削除
"""
import streamlit as st
import pandas as pd
import os, time
from datetime import datetime, date
from collections import Counter
from common import (
    inject_css, setup_sidebar, to_df,
    classify, clean_tokens, make_bigrams, peak_estimate, compute_score,
    render_kw_card, buzz_status,  # buzz_status を明示的にimport — NameError修正
    SNS_PLATFORMS,
)
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="SNS トレンド | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">SNS トレンドキーワード</div>', unsafe_allow_html=True)

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
        yt_boost = round((yt_term_views.get(tl,0)/max_views)*100,1)
        prev = prev_scores.get(tl, gt_score)
        growth = max(0.0, round(gt_score-prev,1))
        score = compute_score(gt_score, growth, yt_boost)
        if score < 5: continue
        rows.append({"keyword":term,"score":score,"status":classify(score),
                     "viral_soon":growth>15 and tl in yt_set and gt_score>30,
                     "peak_est":peak_estimate(growth),"gt_score":gt_score,
                     "yt_boost":yt_boost,"growth":growth,"in_gt":gt_score>0,"in_yt":tl in yt_set})
    df = pd.DataFrame(rows)
    if df.empty: return df
    return df.sort_values("score",ascending=False).head(50).reset_index(drop=True)

def demo_keywords():
    s = [("japan hidden spots",91,"hot",True,"1-3 hours",88,75,42),("tokyo free spots",86,"hot",True,"1-3 hours",82,70,38),("wabi sabi living",82,"hot",False,"6-12 hours",79,68,20),("japan morning routine",77,"trending",True,"6-12 hours",74,62,35),("shibuya hidden cafe",73,"trending",False,"6-12 hours",70,58,15),("tokyo street food",68,"trending",False,"12-24 hours",65,55,10),("japan life vlog",63,"trending",False,"12-24 hours",60,50,8),("tokyo budget travel",58,"rising",True,"12-24 hours",55,45,22),("japan apartment tour",52,"rising",False,"24-72 hours",49,40,3),("tokyo night walk",47,"niche",False,"24-72 hours",44,38,2)]
    return pd.DataFrame([{"keyword":k,"score":sc,"status":st,"viral_soon":vr,"peak_est":pk,"gt_score":gt,"yt_boost":yt,"growth":gr,"in_gt":True,"in_yt":yt>0} for k,sc,st,vr,pk,gt,yt,gr in s])

for k,v in [("kw_df",pd.DataFrame()),("kw_checked",{}),("hist_checked",{}),("last_updated",None)]:
    if k not in st.session_state: st.session_state[k] = v

tab_fetch, tab_approve, tab_history, tab_post = st.tabs(["キーワード取得","チェック・承認","履歴","再生数"])

# ── キーワード取得 ─────────────────────────────────────────────────────────────
with tab_fetch:
    if st.button("データ更新"):
        with st.spinner("取得中…"):
            prev = {r["keyword"].lower():r["score"] for r in st.session_state.kw_df.to_dict("records")} if not st.session_state.kw_df.empty else {}
            gt_terms, gt_scores = fetch_google_trends()
            yt_videos = fetch_youtube_trending()
            df = extract_keywords(gt_terms, gt_scores, yt_videos, prev) if (gt_terms or yt_videos) else pd.DataFrame()
            if df.empty:
                df = demo_keywords()
                st.markdown('<div class="info-box">ライブデータなし — デモデータを表示中</div>', unsafe_allow_html=True)
            st.session_state.kw_df = df
            st.session_state.kw_checked = {row["keyword"]: False for _, row in df.iterrows()}
            st.session_state.last_updated = datetime.now()
    df = st.session_state.kw_df
    if not df.empty:
        st.markdown(f'<div class="metric-row"><div class="metric-card"><div class="val">{len(df)}</div><div class="lbl">キーワード数</div></div><div class="metric-card"><div class="val">{int((df["status"]=="hot").sum())}</div><div class="lbl">Hot</div></div><div class="metric-card"><div class="val">{int(df["viral_soon"].sum())}</div><div class="lbl">Viral予測</div></div><div class="metric-card"><div class="val">{round(df["score"].mean(),1)}</div><div class="lbl">平均スコア</div></div></div>', unsafe_allow_html=True)
        for i, row in df.iterrows(): render_kw_card(i, row)
        if st.session_state.last_updated:
            st.markdown(f'<div class="last-updated">最終更新: {st.session_state.last_updated.strftime("%Y-%m-%d %H:%M:%S")}</div>', unsafe_allow_html=True)

# ── チェック・承認 ─────────────────────────────────────────────────────────────
with tab_approve:
    df = st.session_state.kw_df
    if df.empty:
        st.markdown('<div class="info-box">先にキーワード取得タブでデータを取得してください</div>', unsafe_allow_html=True)
    else:
        st.markdown("保存したいキーワードにチェックを入れて「承認して保存」してください。")
        ca, cn, cc = st.columns([1,1,4])
        with ca:
            if st.button("全選択"):
                for _, row in df.iterrows(): st.session_state.kw_checked[row["keyword"]] = True
                st.rerun()
        with cn:
            if st.button("全解除"):
                for _, row in df.iterrows(): st.session_state.kw_checked[row["keyword"]] = False
                st.rerun()
        checked_list = []
        for _, row in df.iterrows():
            kw = row["keyword"]
            col_chk, col_info = st.columns([0.5, 9.5])
            with col_chk:
                val = st.checkbox("", value=st.session_state.kw_checked.get(kw, False), key=f"chk_{kw}")
                st.session_state.kw_checked[kw] = val
            with col_info:
                viral_label = " [VIRAL]" if row.get("viral_soon") else ""
                st.markdown(f"**{kw.title()}** スコア:`{row['score']}` [{row['status']}]{viral_label}")
            if st.session_state.kw_checked.get(kw, False): checked_list.append(row)
        with cc:
            st.markdown(f'<div style="padding:.3rem 0;font-size:.85rem;color:#6b7280;">選択中: <strong>{len(checked_list)}件</strong></div>', unsafe_allow_html=True)
        if st.button("承認して履歴に保存"):
            if not checked_list:
                st.markdown('<div class="err-box">1つ以上選択してください</div>', unsafe_allow_html=True)
            else:
                saved = 0
                for row in checked_list:
                    src = []
                    if row.get("in_gt"): src.append("GoogleTrends")
                    if row.get("in_yt"): src.append("YouTube")
                    res = sb_insert("keyword_history",{"keyword":row["keyword"],"score":row["score"],"status":row["status"],"source":",".join(src)})
                    if res: saved += 1
                st.markdown(f'<div class="success-box">{saved}件を保存しました</div>', unsafe_allow_html=True)

# ── 履歴 ──────────────────────────────────────────────────────────────────────
with tab_history:
    rows = sb_select("keyword_history", order="-score")
    df_hist = to_df(rows)
    if df_hist.empty:
        st.markdown('<div class="info-box">履歴がありません</div>', unsafe_allow_html=True)
    else:
        fc1, fc2 = st.columns(2)
        with fc1: f_used = st.selectbox("フィルター",["すべて","未使用のみ","使用済みのみ"])
        with fc2: f_st   = st.selectbox("ステータス",["すべて","hot","trending","rising","niche"])
        df_show = df_hist.copy()
        if f_used == "未使用のみ":    df_show = df_show[df_show["used"]==0]
        elif f_used == "使用済みのみ": df_show = df_show[df_show["used"]==1]
        if f_st != "すべて":          df_show = df_show[df_show["status"]==f_st]
        st.caption(f"{len(df_show)}件")

        ha, hn = st.columns([1,1])
        with ha:
            if st.button("全選択 (履歴)"):
                for _, row in df_show.iterrows(): st.session_state.hist_checked[row["id"]] = True
                st.rerun()
        with hn:
            if st.button("全解除 (履歴)"):
                for _, row in df_show.iterrows(): st.session_state.hist_checked[row["id"]] = False
                st.rerun()

        for _, row in df_show.iterrows():
            c0,c1,c2,c3,c4,c5 = st.columns([0.4,2.5,1,1.2,1.8,2.5])
            with c0:
                chk = st.checkbox("", value=st.session_state.hist_checked.get(row["id"],False), key=f"hchk_{row['id']}")
                st.session_state.hist_checked[row["id"]] = chk
            with c1:
                st.markdown(f"**{row['keyword'].title()}**")
                st.caption(str(row.get("created_at",""))[:10])
            with c2: st.metric("スコア", row["score"])
            with c3: st.markdown(f'<span class="badge badge-{row["status"]}">{row["status"]}</span>', unsafe_allow_html=True)
            with c4:
                if row["used"] == 0:
                    if st.button("使用済にする", key=f"use_{row['id']}"): sb_update("keyword_history",{"used":1,"used_date":str(date.today())},{"id":row["id"]}); st.rerun()
                else:
                    st.markdown(f'<span class="badge badge-used">使用済 {row.get("used_date","") or ""}</span>', unsafe_allow_html=True)
                    if st.button("戻す", key=f"unuse_{row['id']}"): sb_update("keyword_history",{"used":0,"used_date":None},{"id":row["id"]}); st.rerun()
            with c5:
                note = st.text_input("メモ", value=row.get("note","") or "", key=f"note_{row['id']}", label_visibility="collapsed", placeholder="メモを入力…")
                if note != (row.get("note","") or ""): sb_update("keyword_history",{"note":note},{"id":row["id"]})
            st.divider()

# ── 再生数 ─────────────────────────────────────────────────────────────────────
with tab_post:
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
    bz = buzz_status(platform, vd)  # common からimport済み — エラーなし
    st.markdown(f'<div class="info-box">バズ判定: <strong>{bz}</strong> / 最大: <strong>{max(vd.values()):,}</strong></div>', unsafe_allow_html=True)
    if st.button("保存"):
        if post_theme:
            sb_insert("post_tracking",{"platform":platform,"post_url":post_url,"post_theme":post_theme,"keyword_used":kw_used,"posted_at":str(posted_at),"v_1h":v_1h,"v_6h":v_6h,"v_24h":v_24h,"v_72h":v_72h,"v_7d":v_7d,"v_30d":v_30d,"buzz_status":bz})
            st.markdown('<div class="success-box">保存しました</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="err-box">投稿テーマを入力してください</div>', unsafe_allow_html=True)
    rows = sb_select("post_tracking", order="-posted_at")
    df_posts = to_df(rows)
    if not df_posts.empty:
        for col in ["v_1h","v_24h","v_7d","v_30d"]:
            if col not in df_posts.columns: df_posts[col] = 0
        for _, row in df_posts.iterrows():
            pc1,pc2,pc3,pc4 = st.columns([3,4,1.5,0.5])
            with pc1:
                st.markdown(f"**{row.get('platform','')} / {row.get('post_theme','')}**")
                st.caption(str(row.get("posted_at","")))
            with pc2: st.markdown(f"1h:`{row['v_1h']:,}` / 24h:`{row['v_24h']:,}` / 7d:`{row['v_7d']:,}` / 30d:`{row['v_30d']:,}`")
            with pc3: st.markdown(f"**{row.get('buzz_status','')}**")
            with pc4:
                if st.button("削除", key=f"pdel_{row['id']}"): sb_delete("post_tracking",{"id":row["id"]}); st.rerun()
            st.divider()
