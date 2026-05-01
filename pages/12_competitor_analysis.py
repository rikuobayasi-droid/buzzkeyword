"""
pages/12_competitor_analysis.py — 競合分析（v4完全版）

新機能:
  - 自社アカウントフラグ（is_own）
  - 自社 vs 競合の比較グラフ（強調表示）
  - 年別・月別タブ
  - 発信地ボタンで絞り込み
  - 差分分析（競合平均との比較）
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_upsert, sb_update, sb_delete

st.set_page_config(page_title="競合分析 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

# ── 定数 ─────────────────────────────────────────────────────────────────────
LOCATIONS  = ["東京","大阪","京都","沖縄","北海道","福岡","名古屋","広島","神戸","奈良","海外","その他"]
CATEGORIES = ["観光・旅行","グルメ","文化・伝統","自然・景色","ホテル・宿","体験・アクティビティ","ライフスタイル","その他"]

# ── ヘルパー ──────────────────────────────────────────────────────────────────
def calc_er(followers, likes, comments):
    if followers <= 0: return 0.0
    return round((likes + comments) / followers * 100, 2)

def calc_growth(old_f, new_f):
    if old_f <= 0: return 0.0
    return round((new_f - old_f) / old_f * 100, 1)

def calc_weekly_posts(df_posts_sorted):
    top7 = df_posts_sorted.head(7)
    if len(top7) < 2: return float(len(top7))
    try:
        newest = date.fromisoformat(str(top7.iloc[0]["post_date"])[:10])
        oldest = date.fromisoformat(str(top7.iloc[-1]["post_date"])[:10])
        span   = max((newest - oldest).days, 1)
        return round(len(top7) / span * 7, 1)
    except Exception:
        return 0.0

def get_metrics(acc_id, df_hist, df_posts, year=None, month=None):
    """アカウントのメトリクスを取得（年月フィルター対応）"""
    result = {"followers": 0, "followers_raw": 0.0, "avg_likes": 0,
              "avg_comments": 0, "weekly_posts": 0.0, "er": 0.0, "growth": None}
    if not df_hist.empty:
        ah = df_hist[df_hist["account_id"] == int(acc_id)].copy()
        # 年月フィルター
        if year and "recorded_date" in ah.columns:
            ah = ah[ah["recorded_date"].astype(str).str.startswith(str(year))]
        if month and "recorded_date" in ah.columns:
            ah = ah[ah["recorded_date"].astype(str).str[5:7] == f"{int(month):02d}"]
        ah = ah.sort_values("recorded_date")
        if not ah.empty:
            latest = ah.iloc[-1]
            f  = int(latest.get("followers", 0) or 0)
            l  = int(latest.get("avg_likes", 0) or 0)
            c  = int(latest.get("avg_comments", 0) or 0)
            fw = float(latest.get("followers_raw", 0) or 0)
            result.update({"followers": f, "followers_raw": fw,
                           "avg_likes": l, "avg_comments": c, "er": calc_er(f, l, c)})
            if len(ah) >= 2:
                result["growth"] = calc_growth(int(ah.iloc[0]["followers"] or 0), f)
    if not df_posts.empty:
        ap = df_posts[df_posts["account_id"] == int(acc_id)].copy()
        if year: ap = ap[ap["post_date"].astype(str).str.startswith(str(year))]
        if month: ap = ap[ap["post_date"].astype(str).str[5:7] == f"{int(month):02d}"]
        ap = ap.sort_values("post_date", ascending=False)
        if not ap.empty:
            ap["likes"]    = pd.to_numeric(ap["likes"],    errors="coerce").fillna(0)
            ap["comments"] = pd.to_numeric(ap["comments"], errors="coerce").fillna(0)
            top7 = ap.head(7)
            result["avg_likes"]    = int(top7["likes"].mean())
            result["avg_comments"] = int(top7["comments"].mean())
            result["weekly_posts"] = calc_weekly_posts(ap)
            result["er"]           = calc_er(result["followers"], result["avg_likes"], result["avg_comments"])
    return result

@st.cache_data(ttl=120)
def load_all():
    df_acc   = to_df(sb_select("competitor_accounts", order="username"))
    df_hist  = to_df(sb_select("competitor_history",  order="recorded_date"))
    df_posts = to_df(sb_select("competitor_posts",    order="-post_date"))
    # account_id を int に統一
    for df in [df_hist, df_posts]:
        if not df.empty and "account_id" in df.columns:
            df["account_id"] = pd.to_numeric(df["account_id"], errors="coerce").fillna(-1).astype(int)
    if not df_acc.empty and "id" in df_acc.columns:
        df_acc["id"] = pd.to_numeric(df_acc["id"], errors="coerce").fillna(-1).astype(int)
    return df_acc, df_hist, df_posts

# ════════════════════════════════════════════════════════
# メインルーティング
# ════════════════════════════════════════════════════════
sel_id = st.session_state.get("selected_competitor_id")

if sel_id:
    # ── 詳細ページ ────────────────────────────────────────────────────────────
    df_acc, df_hist, df_posts = load_all()
    if df_acc.empty or sel_id not in df_acc["id"].values:
        st.session_state.pop("selected_competitor_id", None); st.rerun()

    row = df_acc[df_acc["id"] == sel_id].iloc[0]
    cid = int(row["id"])
    is_own = bool(row.get("is_own", False))

    col_back, col_title = st.columns([1, 6])
    with col_back:
        if st.button("← 一覧に戻る"):
            st.session_state.pop("selected_competitor_id", None)
            st.cache_data.clear(); st.rerun()
    with col_title:
        own_badge = " 🏠 自社" if is_own else ""
        st.markdown(f'<div class="page-title">{row["username"]}{own_badge}</div>', unsafe_allow_html=True)

    tab_info, tab_monthly, tab_posts_tab = st.tabs(["基本情報", "月次データ", "投稿記録"])

    # ── タブ1: 基本情報 ───────────────────────────────────────────────────────
    with tab_info:
        m   = get_metrics(cid, df_hist, df_posts)
        loc = row.get("location","") or row.get("content_region","") or ""
        cat = row.get("category","") or row.get("content_genre","") or ""
        growth_str = f"{m['growth']:+.1f}%" if m["growth"] is not None else "—"
        growth_col = "#15803d" if (m["growth"] or 0) >= 0 else "#dc2626"

        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{m['followers_raw']:.1f}万</div><div class="lbl">フォロワー数</div></div>
          <div class="metric-card"><div class="val" style="color:{growth_col};">{growth_str}</div><div class="lbl">フォロワー増加率</div></div>
          <div class="metric-card"><div class="val">{m['er']}%</div><div class="lbl">ER</div></div>
          <div class="metric-card"><div class="val">{m['avg_likes']:,}</div><div class="lbl">平均いいね</div></div>
          <div class="metric-card"><div class="val">{m['avg_comments']:,}</div><div class="lbl">平均コメント</div></div>
          <div class="metric-card"><div class="val">{m['weekly_posts']:.1f}本/週</div><div class="lbl">投稿頻度（推定）</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-head">アカウント情報を編集</div>', unsafe_allow_html=True)
        ec1, ec2 = st.columns(2)
        with ec1:
            e_uname = st.text_input("ユーザー名", value=row.get("username",""), key=f"e_uname_{cid}")
            loc_idx = (["未設定"]+LOCATIONS).index(loc) if loc in LOCATIONS else 0
            e_loc   = st.selectbox("発信地", ["未設定"]+LOCATIONS, index=loc_idx, key=f"e_loc_{cid}")
            e_region= st.text_input("拠点詳細（任意）", value=row.get("region","") or "", key=f"e_region_{cid}")
        with ec2:
            cat_idx = (["未設定"]+CATEGORIES).index(cat) if cat in CATEGORIES else 0
            e_cat   = st.selectbox("カテゴリー", ["未設定"]+CATEGORIES, index=cat_idx, key=f"e_cat_{cid}")
            e_genre = st.text_input("詳細ジャンル（任意）", value=row.get("genre","") or "", key=f"e_genre_{cid}")
            # 自社アカウントフラグ
            e_is_own = st.checkbox("🏠 自社アカウント", value=is_own, key=f"e_own_{cid}")
            e_note   = st.text_area("メモ", value=row.get("note","") or "", height=68, key=f"e_note_{cid}")

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            if st.button("更新する", key=f"upd_{cid}"):
                sb_update("competitor_accounts", {
                    "username":       e_uname.strip(),
                    "location":       e_loc if e_loc != "未設定" else None,
                    "content_region": e_loc if e_loc != "未設定" else None,
                    "region":         e_region.strip() or None,
                    "category":       e_cat if e_cat != "未設定" else None,
                    "content_genre":  e_cat if e_cat != "未設定" else None,
                    "genre":          e_genre.strip() or None,
                    "is_own":         e_is_own,
                    "note":           e_note.strip() or None,
                }, {"id": cid})
                st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                st.cache_data.clear(); st.rerun()
        with bc2:
            active = bool(row.get("is_active", True))
            if st.button("無効化" if active else "有効化", key=f"toggle_{cid}"):
                sb_update("competitor_accounts", {"is_active": not active}, {"id": cid})
                st.cache_data.clear(); st.rerun()
        with bc3:
            if st.button("削除する", key=f"del_{cid}"):
                sb_delete("competitor_accounts", {"id": cid})
                st.session_state.pop("selected_competitor_id", None)
                st.cache_data.clear(); st.rerun()

    # ── タブ2: 月次データ ─────────────────────────────────────────────────────
    with tab_monthly:
        st.markdown('<div class="section-head">月次データを入力（月1回）</div>', unsafe_allow_html=True)

        auto_likes = auto_comments = 0; auto_wp = 0.0
        if not df_posts.empty:
            ap = df_posts[df_posts["account_id"] == cid].sort_values("post_date", ascending=False).copy()
            if not ap.empty:
                ap["likes"]    = pd.to_numeric(ap["likes"],    errors="coerce").fillna(0)
                ap["comments"] = pd.to_numeric(ap["comments"], errors="coerce").fillna(0)
                top7 = ap.head(7)
                auto_likes    = int(top7["likes"].mean())
                auto_comments = int(top7["comments"].mean())
                auto_wp       = calc_weekly_posts(ap)
                st.markdown(
                    f'<div class="info-box">直近{len(top7)}投稿より自動計算 &nbsp; '
                    f'平均いいね: <strong>{auto_likes:,}</strong> &nbsp; '
                    f'平均コメント: <strong>{auto_comments:,}</strong> &nbsp; '
                    f'投稿頻度: <strong>{auto_wp:.1f}本/週</strong></div>',
                    unsafe_allow_html=True
                )

        with st.form(key=f"monthly_form_{cid}"):
            mc1, mc2 = st.columns(2)
            with mc1:
                rec_ym        = st.text_input("年月 (YYYY-MM)", value=date.today().strftime("%Y-%m"))
                followers_man = st.number_input("フォロワー数（万人）", min_value=0.0, value=0.0, step=0.1, format="%.1f")
            with mc2:
                latest_post = st.text_area("直近投稿内容（任意）", height=80)
                m_note      = st.text_input("メモ（任意）")

            if st.form_submit_button("保存する"):
                if not rec_ym or len(rec_ym) != 7:
                    st.markdown('<div class="err-box">年月をYYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
                else:
                    followers  = int(followers_man * 10000)
                    engagement = auto_likes + auto_comments
                    res = sb_upsert("competitor_history", {
                        "account_id":    cid,
                        "recorded_date": f"{rec_ym}-01",
                        "year_month":    rec_ym,
                        "followers":     followers,
                        "followers_raw": followers_man,
                        "avg_views":     0,
                        "avg_likes":     auto_likes,
                        "avg_comments":  auto_comments,
                        "weekly_posts":  float(auto_wp),
                        "engagement":    engagement,
                        "latest_post":   latest_post.strip() or None,
                        "note":          m_note.strip() or None,
                    })
                    if res:
                        st.markdown('<div class="success-box">保存しました</div>', unsafe_allow_html=True)
                        st.cache_data.clear()
                    else:
                        st.markdown('<div class="err-box">保存に失敗しました</div>', unsafe_allow_html=True)

        # 月次データ履歴（編集・削除対応）
        st.markdown('<div class="section-head">月次データ履歴</div>', unsafe_allow_html=True)
        if not df_hist.empty:
            ah = df_hist[df_hist["account_id"] == cid].copy().sort_values("recorded_date", ascending=False)
            if not ah.empty:
                for col in ["followers","avg_likes","avg_comments","engagement"]:
                    if col in ah.columns:
                        ah[col] = pd.to_numeric(ah[col], errors="coerce").fillna(0).astype(int)
                ah["ER(%)"] = ah.apply(lambda r: calc_er(
                    int(r.get("followers",0)), int(r.get("avg_likes",0)), int(r.get("avg_comments",0))
                ), axis=1)

                for i, (_, hr) in enumerate(ah.iterrows()):
                    hid = int(hr["id"])
                    ym  = hr.get("year_month","")
                    fw  = float(hr.get("followers_raw", 0) or 0)
                    er  = hr.get("ER(%)", 0)
                    lp  = str(hr.get("latest_post","") or "")

                    with st.expander(f"📅 {ym} | {fw:.1f}万 | ER {er}% | {lp[:20] if lp else '—'}"):
                        with st.form(key=f"edit_hist_{hid}_{i}"):
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                e_ym = st.text_input("年月", value=ym, key=f"eym_{hid}_{i}")
                                e_fw = st.number_input("フォロワー（万）", min_value=0.0,
                                    value=fw, step=0.1, format="%.1f", key=f"efw_{hid}_{i}")
                            with ec2:
                                e_lp   = st.text_area("直近投稿", value=lp, height=68, key=f"elp_{hid}_{i}")
                                e_note = st.text_input("メモ", value=str(hr.get("note","") or ""), key=f"en_{hid}_{i}")
                            sc1, sc2 = st.columns(2)
                            with sc1:
                                if st.form_submit_button("✏️ 更新"):
                                    sb_update("competitor_history", {
                                        "year_month":    e_ym,
                                        "recorded_date": f"{e_ym}-01",
                                        "followers":     int(e_fw * 10000),
                                        "followers_raw": e_fw,
                                        "latest_post":   e_lp.strip() or None,
                                        "note":          e_note.strip() or None,
                                    }, {"id": hid})
                                    st.cache_data.clear(); st.rerun()
                            with sc2:
                                if st.form_submit_button("🗑️ 削除"):
                                    sb_delete("competitor_history", {"id": hid})
                                    st.cache_data.clear(); st.rerun()

                if len(ah) >= 2:
                    st.markdown('<div class="section-head">フォロワー推移</div>', unsafe_allow_html=True)
                    chart_df = ah.sort_values("recorded_date")[["recorded_date","followers_raw"]].copy()
                    chart_df["followers_raw"] = pd.to_numeric(chart_df["followers_raw"], errors="coerce").fillna(0)
                    st.line_chart(chart_df.set_index("recorded_date")["followers_raw"])

    # ── タブ3: 投稿記録 ───────────────────────────────────────────────────────
    with tab_posts_tab:
        st.markdown('<div class="section-head">投稿を記録</div>', unsafe_allow_html=True)
        with st.form(key=f"post_form_{cid}"):
            pc1, pc2 = st.columns(2)
            with pc1:
                p_url  = st.text_input("投稿URL *")
                p_date = st.date_input("投稿日", value=date.today())
            with pc2:
                p_likes    = st.number_input("いいね数", min_value=0, value=0, step=10)
                p_comments = st.number_input("コメント数", min_value=0, value=0, step=1)
                p_note     = st.text_input("メモ（任意）")
            if st.form_submit_button("記録する"):
                if not p_url.strip():
                    st.markdown('<div class="err-box">URLは必須です</div>', unsafe_allow_html=True)
                else:
                    res = sb_upsert("competitor_posts", {
                        "account_id":    cid,
                        "post_url":      p_url.strip(),
                        "post_date":     str(p_date),
                        "likes":         p_likes,
                        "comments":      p_comments,
                        "recorded_date": str(date.today()),
                        "note":          p_note.strip() or None,
                    })
                    if res:
                        st.markdown('<div class="success-box">記録しました</div>', unsafe_allow_html=True)
                        st.cache_data.clear()

        st.markdown('<div class="section-head">投稿一覧</div>', unsafe_allow_html=True)
        if not df_posts.empty:
            ap = df_posts[df_posts["account_id"] == cid].sort_values("post_date", ascending=False).copy()
            if not ap.empty:
                for col in ["likes","comments"]:
                    ap[col] = pd.to_numeric(ap[col], errors="coerce").fillna(0).astype(int)
                for _, pr in ap.iterrows():
                    pid = int(pr["id"])
                    with st.expander(f"{pr['post_date']} | ❤️{int(pr['likes']):,} 💬{int(pr['comments']):,}"):
                        st.markdown(f"**URL:** [{pr['post_url']}]({pr['post_url']})")
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1: new_l = st.number_input("いいね", value=int(pr["likes"]), step=10, key=f"pl_{pid}")
                        with ec2: new_c = st.number_input("コメント", value=int(pr["comments"]), step=1, key=f"pc_{pid}")
                        with ec3:
                            if st.button("更新", key=f"pu_{pid}"):
                                sb_update("competitor_posts", {"likes": new_l, "comments": new_c}, {"id": pid})
                                st.cache_data.clear(); st.rerun()
                        if st.button("削除", key=f"pd_{pid}"):
                            sb_delete("competitor_posts", {"id": pid})
                            st.cache_data.clear(); st.rerun()

else:
    # ════════════════════════════════════════════════════════
    # 一覧・分析画面
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="page-title">競合分析</div>', unsafe_allow_html=True)
    tab_list, tab_register, tab_compare, tab_market = st.tabs([
        "アカウント一覧", "新規登録", "自社 vs 競合比較", "市場・地域分析"
    ])

    df_acc, df_hist, df_posts = load_all()

    # 自社・競合を分離
    df_own  = df_acc[df_acc["is_own"] == True].copy()  if not df_acc.empty else pd.DataFrame()
    df_comp = df_acc[df_acc["is_own"] != True].copy()  if not df_acc.empty else pd.DataFrame()

    # ── タブ1: アカウント一覧 ──────────────────────────────────────────────────
    with tab_list:
        st.markdown('<div class="section-head">検索・絞り込み</div>', unsafe_allow_html=True)
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        with sc1: s_name = st.text_input("アカウント名", key="s_name")
        with sc2: s_loc  = st.selectbox("発信地", ["すべて"]+LOCATIONS, key="s_loc")
        with sc3: s_cat  = st.selectbox("カテゴリー", ["すべて"]+CATEGORIES, key="s_cat")
        with sc4: s_own  = st.selectbox("種別", ["すべて","自社のみ","競合のみ"], key="s_own")
        with sc5: s_date = st.text_input("登録日 (YYYY-MM-DD)", key="s_date")

        if df_acc.empty:
            st.markdown('<div class="info-box">まだ登録されていません</div>', unsafe_allow_html=True)
        else:
            df_show = df_acc.copy()
            if s_name: df_show = df_show[df_show["username"].str.contains(s_name, case=False, na=False)]
            if s_loc != "すべて":
                df_show = df_show[
                    df_show["location"].fillna("").str.contains(s_loc, na=False) |
                    df_show["content_region"].fillna("").str.contains(s_loc, na=False)
                ]
            if s_cat != "すべて":
                df_show = df_show[
                    df_show["category"].fillna("").str.contains(s_cat, na=False) |
                    df_show["content_genre"].fillna("").str.contains(s_cat, na=False)
                ]
            if s_own == "自社のみ":   df_show = df_show[df_show["is_own"] == True]
            elif s_own == "競合のみ": df_show = df_show[df_show["is_own"] != True]
            if s_date: df_show = df_show[df_show["created_at"].astype(str).str.startswith(s_date)]

            st.caption(f"{len(df_show)}件")

            for _, row in df_show.iterrows():
                aid  = int(row["id"])
                m    = get_metrics(aid, df_hist, df_posts)
                loc  = row.get("location","") or row.get("content_region","") or ""
                cat  = row.get("category","") or row.get("content_genre","") or ""
                own  = bool(row.get("is_own", False))
                badge = " 🏠" if own else " 🔍"

                c1,c2,c3,c4,c5,c6,c7,c8,c9 = st.columns([2.5,0.5,1.5,1.8,1.2,1,1,1.2,0.8])
                with c1:
                    if st.button(f"{row['username']}{badge}", key=f"go_{aid}"):
                        st.session_state["selected_competitor_id"] = aid; st.rerun()
                with c2: st.caption("自社" if own else "競合")
                with c3: st.caption(loc)
                with c4: st.caption(cat)
                with c5: st.caption(f"{m['followers_raw']:.1f}万" if m['followers_raw'] > 0 else "—")
                with c6: st.caption(f"ER {m['er']}%")
                with c7: st.caption(f"❤️{m['avg_likes']:,}")
                with c8: st.caption(f"{m['weekly_posts']:.1f}本/週" if m['weekly_posts'] > 0 else "—")
                with c9:
                    if st.button("詳細", key=f"det_{aid}"):
                        st.session_state["selected_competitor_id"] = aid; st.rerun()

    # ── タブ2: 新規登録 ───────────────────────────────────────────────────────
    with tab_register:
        st.markdown('<div class="section-head">新規アカウントを登録</div>', unsafe_allow_html=True)
        with st.form(key="register_form"):
            rc1, rc2 = st.columns(2)
            with rc1:
                new_uname  = st.text_input("Instagramユーザー名 *", placeholder="例: @tokyo_travel")
                new_loc    = st.selectbox("発信地", ["未設定"]+LOCATIONS, key="reg_loc")
                new_region = st.text_input("拠点詳細（任意）")
                new_is_own = st.checkbox("🏠 自社アカウント", value=False)
            with rc2:
                new_cat   = st.selectbox("カテゴリー", ["未設定"]+CATEGORIES, key="reg_cat")
                new_genre = st.text_input("詳細ジャンル（任意）")
                new_note  = st.text_area("メモ", height=68)

            if st.form_submit_button("登録する"):
                if not new_uname.strip():
                    st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
                else:
                    # 既存アカウントの確認
                    existing = df_acc[df_acc["username"] == new_uname.strip()] if not df_acc.empty else pd.DataFrame()
                    if not existing.empty:
                        # 既存アカウントの is_own フラグを更新
                        eid = int(existing.iloc[0]["id"])
                        sb_update("competitor_accounts", {
                            "is_own":         new_is_own,
                            "location":       new_loc if new_loc != "未設定" else None,
                            "content_region": new_loc if new_loc != "未設定" else None,
                            "region":         new_region.strip() or None,
                            "category":       new_cat if new_cat != "未設定" else None,
                            "content_genre":  new_cat if new_cat != "未設定" else None,
                            "genre":          new_genre.strip() or None,
                            "note":           new_note.strip() or None,
                        }, {"id": eid})
                        own_msg = "（自社アカウントとして更新）" if new_is_own else "（競合アカウントとして更新）"
                        st.markdown(f'<div class="success-box">既存アカウントを更新しました {own_msg}</div>', unsafe_allow_html=True)
                        st.cache_data.clear(); st.rerun()
                    else:
                        res = sb_insert("competitor_accounts", {
                            "username":       new_uname.strip(),
                            "platform":       "Instagram",
                            "location":       new_loc if new_loc != "未設定" else None,
                            "content_region": new_loc if new_loc != "未設定" else None,
                            "region":         new_region.strip() or None,
                            "category":       new_cat if new_cat != "未設定" else None,
                            "content_genre":  new_cat if new_cat != "未設定" else None,
                            "genre":          new_genre.strip() or None,
                            "is_own":         new_is_own,
                            "note":           new_note.strip() or None,
                            "is_active":      True,
                        })
                        if res:
                            own_msg = "（自社アカウント）" if new_is_own else "（競合アカウント）"
                            st.markdown(f'<div class="success-box">登録しました {own_msg}</div>', unsafe_allow_html=True)
                            st.cache_data.clear(); st.rerun()
                        else:
                            st.markdown('<div class="err-box">登録に失敗しました</div>', unsafe_allow_html=True)

    # ── タブ3: 自社 vs 競合比較 ───────────────────────────────────────────────
    with tab_compare:
        if df_own.empty:
            st.markdown('<div class="info-box">自社アカウントが登録されていません。「新規登録」タブで「自社アカウント」にチェックを入れて登録してください。</div>', unsafe_allow_html=True)
        elif df_comp.empty:
            st.markdown('<div class="info-box">競合アカウントが登録されていません。</div>', unsafe_allow_html=True)
        else:
            # 年月フィルター（session_stateで状態管理）
            st.markdown('<div class="section-head">期間を指定</div>', unsafe_allow_html=True)

            # session_stateの初期化
            if "cmp_period_mode" not in st.session_state:
                st.session_state["cmp_period_mode"] = "全期間"
            if "cmp_sel_year" not in st.session_state:
                st.session_state["cmp_sel_year"] = None
            if "cmp_sel_month" not in st.session_state:
                st.session_state["cmp_sel_month"] = None

            period_tab1, period_tab2, period_tab3 = st.tabs(["全期間", "年別", "月別"])

            with period_tab1:
                st.caption("全期間のデータを表示します")
                if st.button("全期間で表示", key="period_all"):
                    st.session_state["cmp_period_mode"] = "全期間"
                    st.session_state["cmp_sel_year"]    = None
                    st.session_state["cmp_sel_month"]   = None
                    st.rerun()

            with period_tab2:
                years = sorted(set(
                    df_hist["recorded_date"].astype(str).str[:4].dropna().tolist()
                ), reverse=True) if not df_hist.empty else []
                if years:
                    y_sel = st.selectbox("年を選択", years, key="cmp_year_sel")
                    if st.button("この年で絞り込む", key="period_year_btn"):
                        st.session_state["cmp_period_mode"] = "年別"
                        st.session_state["cmp_sel_year"]    = y_sel
                        st.session_state["cmp_sel_month"]   = None
                        st.rerun()
                else:
                    st.caption("月次データを入力すると年別絞り込みができます")

            with period_tab3:
                years2 = sorted(set(
                    df_hist["recorded_date"].astype(str).str[:4].dropna().tolist()
                ), reverse=True) if not df_hist.empty else []
                months = [f"{m:02d}" for m in range(1, 13)]
                if years2:
                    cy1, cy2 = st.columns(2)
                    with cy1: y2_sel = st.selectbox("年", years2, key="cmp_year2_sel")
                    with cy2: m2_sel = st.selectbox("月", months, key="cmp_month2_sel")
                    if st.button("この月で絞り込む", key="period_month_btn"):
                        st.session_state["cmp_period_mode"] = "月別"
                        st.session_state["cmp_sel_year"]    = y2_sel
                        st.session_state["cmp_sel_month"]   = m2_sel
                        st.rerun()
                else:
                    st.caption("月次データを入力すると月別絞り込みができます")

            # 現在の絞り込み状態を表示
            sel_year  = st.session_state["cmp_sel_year"]
            sel_month = st.session_state["cmp_sel_month"]
            mode_label = st.session_state["cmp_period_mode"]
            if sel_year and sel_month:
                st.markdown(f'<div class="info-box">絞り込み中: <strong>{sel_year}年{sel_month}月</strong></div>', unsafe_allow_html=True)
            elif sel_year:
                st.markdown(f'<div class="info-box">絞り込み中: <strong>{sel_year}年</strong></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="info-box">絞り込み: <strong>全期間</strong></div>', unsafe_allow_html=True)

            # 自社メトリクス
            own_metrics = []
            for _, row in df_own.iterrows():
                m = get_metrics(int(row["id"]), df_hist, df_posts, sel_year, sel_month)
                if m["followers"] > 0:
                    own_metrics.append({
                        "username": row["username"], "is_own": True, **m
                    })

            # 競合メトリクス
            comp_metrics = []
            for _, row in df_comp.iterrows():
                m = get_metrics(int(row["id"]), df_hist, df_posts, sel_year, sel_month)
                if m["followers"] > 0:
                    comp_metrics.append({
                        "username": row["username"], "is_own": False, **m
                    })

            if not own_metrics and not comp_metrics:
                st.markdown('<div class="info-box">月次データを入力すると比較グラフが表示されます</div>', unsafe_allow_html=True)
            else:
                all_metrics = own_metrics + comp_metrics
                df_all = pd.DataFrame(all_metrics)

                # 競合平均との差分分析
                if own_metrics and comp_metrics:
                    st.markdown('<div class="section-head">自社 vs 競合平均 差分分析</div>', unsafe_allow_html=True)
                    comp_avg_er    = pd.DataFrame(comp_metrics)["er"].mean()
                    comp_avg_fw    = pd.DataFrame(comp_metrics)["followers_raw"].mean()
                    comp_avg_growth= pd.DataFrame(comp_metrics)["growth"].dropna().mean() if any(m["growth"] is not None for m in comp_metrics) else 0

                    for om in own_metrics:
                        er_diff     = om["er"]           - comp_avg_er
                        fw_diff     = om["followers_raw"] - comp_avg_fw
                        growth_diff = (om["growth"] or 0) - comp_avg_growth
                        er_col      = "#15803d" if er_diff >= 0 else "#dc2626"
                        fw_col      = "#15803d" if fw_diff >= 0 else "#dc2626"
                        gw_col      = "#15803d" if growth_diff >= 0 else "#dc2626"

                        st.markdown(f"**🏠 {om['username']}** vs 競合平均")
                        st.markdown(f"""<div class="metric-row">
                          <div class="metric-card">
                            <div class="val" style="color:{er_col};">{er_diff:+.2f}%</div>
                            <div class="lbl">ER差（競合平均比）</div>
                            <div style="font-size:.72rem;color:#6b7280;">自社 {om['er']}% / 競合平均 {comp_avg_er:.2f}%</div>
                          </div>
                          <div class="metric-card">
                            <div class="val" style="color:{fw_col};">{fw_diff:+.1f}万</div>
                            <div class="lbl">フォロワー差（競合平均比）</div>
                            <div style="font-size:.72rem;color:#6b7280;">自社 {om['followers_raw']:.1f}万 / 競合平均 {comp_avg_fw:.1f}万</div>
                          </div>
                          <div class="metric-card">
                            <div class="val" style="color:{gw_col};">{growth_diff:+.1f}%</div>
                            <div class="lbl">増加率差（競合平均比）</div>
                            <div style="font-size:.72rem;color:#6b7280;">自社 {om['growth'] or 0:+.1f}% / 競合平均 {comp_avg_growth:.1f}%</div>
                          </div>
                        </div>""", unsafe_allow_html=True)

                        # アドバイス自動生成
                        if er_diff < -1:
                            st.markdown(f'<div class="err-box">⚠️ ERが競合平均より{abs(er_diff):.2f}%低いです。投稿内容の質向上やCTA強化を検討してください。</div>', unsafe_allow_html=True)
                        elif er_diff > 1:
                            st.markdown(f'<div class="success-box">✅ ERが競合平均より{er_diff:.2f}%高いです。この強みを維持しながらフォロワー拡大を狙いましょう。</div>', unsafe_allow_html=True)

                # 比較グラフ
                st.markdown('<div class="section-head">アカウント比較グラフ</div>', unsafe_allow_html=True)
                df_all["種別"] = df_all["is_own"].map({True:"🏠 自社", False:"🔍 競合"})
                df_all["label"] = df_all.apply(lambda r: f"{'🏠' if r['is_own'] else '🔍'} {r['username']}", axis=1)

                sel_compare = st.multiselect(
                    "比較するアカウントを選択",
                    df_all["label"].tolist(),
                    default=df_all["label"].tolist()[:min(6, len(df_all))],
                    key="cmp_sel"
                )
                if sel_compare:
                    df_cmp = df_all[df_all["label"].isin(sel_compare)].set_index("label")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**エンゲージメント率(%)**")
                        st.bar_chart(df_cmp["er"])
                    with col_b:
                        st.markdown("**フォロワー数（万人）**")
                        st.bar_chart(df_cmp["followers_raw"])
                    col_c, col_d = st.columns(2)
                    with col_c:
                        st.markdown("**フォロワー増加率(%)**")
                        growth_data = df_cmp["growth"].fillna(0)
                        st.bar_chart(growth_data)
                    with col_d:
                        st.markdown("**投稿頻度（本/週）**")
                        st.bar_chart(df_cmp["weekly_posts"])

                # フォロワー推移（折れ線）
                st.markdown('<div class="section-head">フォロワー推移（折れ線）</div>', unsafe_allow_html=True)
                if not df_hist.empty and sel_compare:
                    sel_usernames = [s.split(" ", 1)[1] for s in sel_compare]
                    df_hist_merge = df_hist.merge(
                        df_acc[["id","username","is_own"]].rename(columns={"id":"account_id"}),
                        on="account_id", how="left"
                    )
                    df_hist_merge = df_hist_merge[df_hist_merge["username"].isin(sel_usernames)]
                    df_hist_merge["label"] = df_hist_merge.apply(
                        lambda r: f"{'🏠' if r.get('is_own') else '🔍'} {r['username']}", axis=1
                    )
                    if sel_year: df_hist_merge = df_hist_merge[df_hist_merge["recorded_date"].astype(str).str.startswith(str(sel_year))]
                    if sel_month: df_hist_merge = df_hist_merge[df_hist_merge["recorded_date"].astype(str).str[5:7] == str(sel_month)]
                    if not df_hist_merge.empty:
                        fw_wide = df_hist_merge.groupby(["recorded_date","label"])["followers_raw"].mean().reset_index()
                        fw_wide = fw_wide.pivot(index="recorded_date", columns="label", values="followers_raw").fillna(0)
                        st.line_chart(fw_wide)

    # ── タブ4: 市場・地域分析 ─────────────────────────────────────────────────
    with tab_market:
        st.markdown('<div class="section-head">発信地を選択して分析</div>', unsafe_allow_html=True)

        # 発信地ボタン
        all_locs = []
        if not df_acc.empty:
            for col in ["location","content_region"]:
                if col in df_acc.columns:
                    all_locs.extend(df_acc[col].dropna().tolist())
            all_locs = sorted(set([l for l in all_locs if l]))

        if not all_locs:
            st.markdown('<div class="info-box">発信地が登録されているアカウントがありません</div>', unsafe_allow_html=True)
        else:
            # ボタンで発信地選択
            st.markdown("**発信地を選択（クリックで絞り込み）:**")
            if "sel_location" not in st.session_state:
                st.session_state["sel_location"] = "すべて"

            btn_cols = st.columns(min(len(all_locs)+1, 8))
            with btn_cols[0]:
                if st.button("すべて", key="loc_all",
                    type="primary" if st.session_state["sel_location"] == "すべて" else "secondary"):
                    st.session_state["sel_location"] = "すべて"; st.rerun()
            for j, loc_v in enumerate(all_locs):
                with btn_cols[(j+1) % min(len(all_locs)+1, 8)]:
                    is_sel = st.session_state["sel_location"] == loc_v
                    if st.button(loc_v, key=f"loc_{j}",
                        type="primary" if is_sel else "secondary"):
                        st.session_state["sel_location"] = loc_v; st.rerun()

            sel_loc = st.session_state["sel_location"]
            st.markdown(f"**選択中: {sel_loc}**")

            # フィルター
            df_loc = df_acc.copy()
            if sel_loc != "すべて":
                df_loc = df_loc[
                    df_loc["location"].fillna("").str.contains(sel_loc, na=False) |
                    df_loc["content_region"].fillna("").str.contains(sel_loc, na=False)
                ]

            if df_loc.empty:
                st.markdown(f'<div class="info-box">{sel_loc} のアカウントがありません</div>', unsafe_allow_html=True)
            else:
                # 地域のメトリクスを集計
                loc_rows = []
                for _, row in df_loc.iterrows():
                    aid = int(row["id"])
                    m   = get_metrics(aid, df_hist, df_posts)
                    if m["followers"] == 0: continue
                    loc_rows.append({
                        "username":   row["username"],
                        "is_own":     bool(row.get("is_own", False)),
                        "location":   row.get("location","") or row.get("content_region","") or "",
                        "er":         m["er"],
                        "followers":  m["followers_raw"],
                        "growth":     m["growth"] or 0,
                        "weekly_posts": m["weekly_posts"],
                    })

                if loc_rows:
                    df_loc_m = pd.DataFrame(loc_rows)
                    df_loc_m["種別"] = df_loc_m["is_own"].map({True:"🏠 自社", False:"🔍 競合"})

                    st.markdown(f'<div class="section-head">{sel_loc} のアカウント分析（{len(df_loc_m)}件）</div>', unsafe_allow_html=True)

                    # サマリー
                    avg_er  = df_loc_m["er"].mean()
                    avg_fw  = df_loc_m["followers"].mean()
                    avg_gr  = df_loc_m["growth"].mean()
                    st.markdown(f"""<div class="metric-row">
                      <div class="metric-card"><div class="val">{len(df_loc_m)}</div><div class="lbl">アカウント数</div></div>
                      <div class="metric-card"><div class="val">{avg_er:.2f}%</div><div class="lbl">平均ER</div></div>
                      <div class="metric-card"><div class="val">{avg_fw:.1f}万</div><div class="lbl">平均フォロワー</div></div>
                      <div class="metric-card"><div class="val">{avg_gr:+.1f}%</div><div class="lbl">平均増加率</div></div>
                    </div>""", unsafe_allow_html=True)

                    df_loc_m["label"] = df_loc_m.apply(
                        lambda r: f"{'🏠' if r['is_own'] else '🔍'} {r['username']}", axis=1
                    )
                    la, lb = st.columns(2)
                    with la:
                        st.markdown("**ER比較(%)**")
                        st.bar_chart(df_loc_m.set_index("label")["er"])
                    with lb:
                        st.markdown("**フォロワー増加率(%)**")
                        st.bar_chart(df_loc_m.set_index("label")["growth"])

                    st.dataframe(
                        df_loc_m[["種別","username","er","followers","growth","weekly_posts"]].rename(columns={
                            "username":"アカウント","er":"ER(%)","followers":"フォロワー(万)",
                            "growth":"増加率(%)","weekly_posts":"投稿頻度(本/週)"
                        }),
                        use_container_width=True, hide_index=True
                    )
