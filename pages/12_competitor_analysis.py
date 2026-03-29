"""
pages/12_competitor_analysis.py — 競合分析（v3完全版）

構成:
  一覧画面: 検索・比較表 → アカウントをクリックで詳細へ
  詳細画面: 基本情報タブ / 月次データタブ
  分析画面: 全体・地域別・アカウント比較
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_upsert, sb_update, sb_delete

st.set_page_config(page_title="競合分析 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

# ── 定数 ─────────────────────────────────────────────────────────────────────
LOCATIONS  = ["東京","大阪","京都","沖縄","北海道","福岡","名古屋","広島","神戸","奈良","海外","その他"]
CATEGORIES = ["観光・旅行","グルメ","文化・伝統","自然・景色","ホテル・宿","体験・アクティビティ","ライフスタイル","その他"]

# ── ヘルパー関数 ──────────────────────────────────────────────────────────────
def man_to_int(val: float) -> int:
    return int(val * 10000)

def int_to_man(val) -> float:
    try:    return round(int(val) / 10000, 1)
    except: return 0.0

def calc_er(followers: int, likes: int, comments: int) -> float:
    if followers <= 0: return 0.0
    return round((likes + comments) / followers * 100, 2)

def calc_growth(old_f: int, new_f: int) -> float:
    if old_f <= 0: return 0.0
    return round((new_f - old_f) / old_f * 100, 1)

def calc_weekly_posts(df_posts_sorted: pd.DataFrame) -> float:
    """直近7投稿の期間から週間投稿数を推定"""
    top7 = df_posts_sorted.head(7)
    if len(top7) < 2: return float(len(top7))
    try:
        newest = date.fromisoformat(str(top7.iloc[0]["post_date"])[:10])
        oldest = date.fromisoformat(str(top7.iloc[-1]["post_date"])[:10])
        span   = max((newest - oldest).days, 1)
        return round(len(top7) / span * 7, 1)
    except Exception:
        return 0.0

def get_latest_metrics(acc_id: int, df_hist: pd.DataFrame, df_posts: pd.DataFrame) -> dict:
    """アカウントの最新メトリクスを一括取得"""
    result = {"followers": 0, "followers_raw": 0.0, "avg_likes": 0,
              "avg_comments": 0, "weekly_posts": 0.0, "er": 0.0, "growth": None}
    if not df_hist.empty:
        ah = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")
        if not ah.empty:
            latest = ah.iloc[-1]
            f   = int(latest.get("followers",0) or 0)
            l   = int(latest.get("avg_likes",0) or 0)
            c   = int(latest.get("avg_comments",0) or 0)
            fw  = float(latest.get("followers_raw",0) or 0)
            result.update({"followers": f, "followers_raw": fw,
                           "avg_likes": l, "avg_comments": c, "er": calc_er(f,l,c)})
            if len(ah) >= 2:
                result["growth"] = calc_growth(int(ah.iloc[0]["followers"] or 0), f)
    if not df_posts.empty:
        ap = df_posts[df_posts["account_id"] == acc_id].sort_values("post_date", ascending=False)
        if not ap.empty:
            ap["likes"]    = pd.to_numeric(ap["likes"],    errors="coerce").fillna(0)
            ap["comments"] = pd.to_numeric(ap["comments"], errors="coerce").fillna(0)
            top7 = ap.head(7)
            result["avg_likes"]    = int(top7["likes"].mean())
            result["avg_comments"] = int(top7["comments"].mean())
            result["weekly_posts"] = calc_weekly_posts(ap)
            f = result["followers"]
            result["er"] = calc_er(f, result["avg_likes"], result["avg_comments"])
    return result

@st.cache_data(ttl=120)
def load_all_data():
    return (
        to_df(sb_select("competitor_accounts", order="username")),
        to_df(sb_select("competitor_history",  order="recorded_date")),
        to_df(sb_select("competitor_posts",    order="-post_date")),
    )

# ════════════════════════════════════════════════════════
# メインルーティング
# ════════════════════════════════════════════════════════
sel_id = st.session_state.get("selected_competitor_id")

if sel_id:
    # ── 詳細ページ ────────────────────────────────────────────────────────────
    df_acc, df_hist, df_posts = load_all_data()
    if df_acc.empty or sel_id not in df_acc["id"].values:
        st.session_state.pop("selected_competitor_id", None); st.rerun()

    row = df_acc[df_acc["id"] == sel_id].iloc[0]
    cid = int(row["id"])

    col_back, col_title = st.columns([1,6])
    with col_back:
        if st.button("← 一覧に戻る", key="back"):
            st.session_state.pop("selected_competitor_id", None)
            st.cache_data.clear()
            st.rerun()
    with col_title:
        st.markdown(f'<div class="page-title">{row["username"]}</div>', unsafe_allow_html=True)

    tab_info, tab_monthly, tab_posts_tab = st.tabs(["基本情報", "月次データ", "投稿記録"])

    # ── タブ1: 基本情報 ───────────────────────────────────────────────────────
    with tab_info:
        m = get_latest_metrics(cid, df_hist, df_posts)
        loc = row.get("location","") or row.get("content_region","") or ""
        cat = row.get("category","") or row.get("content_genre","") or ""

        # メトリクスカード
        growth_str = f"{m['growth']:+.1f}%" if m["growth"] is not None else "—"
        growth_col = "#15803d" if (m["growth"] or 0) >= 0 else "#dc2626"
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{m['followers_raw']:.1f}万</div><div class="lbl">フォロワー数</div></div>
          <div class="metric-card"><div class="val" style="color:{growth_col};">{growth_str}</div><div class="lbl">フォロワー増加率</div></div>
          <div class="metric-card"><div class="val">{m['er']}%</div><div class="lbl">エンゲージメント率</div></div>
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
            e_note  = st.text_area("メモ", value=row.get("note","") or "", height=80, key=f"e_note_{cid}")

        bc1, bc2, bc3 = st.columns([2,2,2])
        with bc1:
            if st.button("更新する", key=f"upd_{cid}"):
                sb_update("competitor_accounts", {
                    "username": e_uname.strip(),
                    "location": e_loc if e_loc != "未設定" else None,
                    "content_region": e_loc if e_loc != "未設定" else None,
                    "region":   e_region.strip() or None,
                    "category": e_cat if e_cat != "未設定" else None,
                    "content_genre": e_cat if e_cat != "未設定" else None,
                    "genre":    e_genre.strip() or None,
                    "note":     e_note.strip() or None,
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
        st.caption("フォロワー数はXX.X万人形式で入力。平均いいね・コメント・投稿頻度は投稿記録から自動計算されます。")

        # 次回入力予定日を表示
        if not df_hist.empty:
            ah = df_hist[df_hist["account_id"] == cid].sort_values("recorded_date")
            if not ah.empty:
                try:
                    last_d   = date.fromisoformat(str(ah.iloc[-1]["recorded_date"])[:10])
                    next_m   = last_d.replace(month=last_d.month % 12 + 1,
                                              year=last_d.year + (1 if last_d.month == 12 else 0))
                    days_left = (next_m - date.today()).days
                    color     = "#15803d" if days_left <= 0 else "#1e3a5f"
                    msg       = f"次回入力予定: <strong>{next_m}</strong>" + (
                        f" &nbsp; ✅ 入力日になりました" if days_left <= 0
                        else f" &nbsp; （あと{days_left}日）"
                    )
                    st.markdown(f'<div class="info-box" style="border-color:{color};">{msg}</div>', unsafe_allow_html=True)
                except Exception:
                    pass

        # 投稿記録から自動計算
        auto_likes = auto_comments = 0
        auto_wp    = 0.0
        if not df_posts.empty:
            ap = df_posts[df_posts["account_id"] == cid].sort_values("post_date", ascending=False).copy()
            if not ap.empty:
                ap["likes"]    = pd.to_numeric(ap["likes"],    errors="coerce").fillna(0)
                ap["comments"] = pd.to_numeric(ap["comments"], errors="coerce").fillna(0)
                top7        = ap.head(7)
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
                rec_ym        = st.text_input("年月 (YYYY-MM)", value=date.today().strftime("%Y-%m"),
                                              placeholder="例: 2026-03", key=f"m_ym_{cid}")
                followers_man = st.number_input("フォロワー数（万人）",
                                                min_value=0.0, value=0.0, step=0.1, format="%.1f",
                                                key=f"m_fw_{cid}")
            with mc2:
                latest_post = st.text_area("直近投稿内容（任意）",
                                           placeholder="例: 大阪城の夕景リール",
                                           height=80, key=f"m_lp_{cid}")
                m_note = st.text_input("メモ（任意）", key=f"m_note_{cid}")

            if st.form_submit_button("保存する"):
                if not rec_ym or len(rec_ym) != 7:
                    st.markdown('<div class="err-box">年月をYYYY-MM形式で入力してください</div>', unsafe_allow_html=True)
                else:
                    followers  = man_to_int(followers_man)
                    engagement = auto_likes + auto_comments
                    er_val     = calc_er(followers, auto_likes, auto_comments)
                    rec_date   = f"{rec_ym}-01"
                    res = sb_upsert("competitor_history", {
                        "account_id":    cid,
                        "recorded_date": rec_date,
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
                        st.markdown(
                            f'<div class="success-box">保存しました &nbsp; '
                            f'ER: <strong>{er_val}%</strong> &nbsp; '
                            f'エンゲージメント: <strong>{engagement:,}</strong></div>',
                            unsafe_allow_html=True
                        )
                        st.cache_data.clear()
                    else:
                        st.markdown('<div class="err-box">保存に失敗しました</div>', unsafe_allow_html=True)

        # 月次データ履歴
        st.markdown('<div class="section-head">月次データ履歴</div>', unsafe_allow_html=True)
        if not df_hist.empty:
            ah = df_hist[df_hist["account_id"] == cid].copy().sort_values("recorded_date", ascending=False)
            if not ah.empty:
                for col in ["followers","avg_likes","avg_comments","engagement"]:
                    if col in ah.columns:
                        ah[col] = pd.to_numeric(ah[col], errors="coerce").fillna(0).astype(int)
                if "followers_raw" in ah.columns:
                    ah["フォロワー(万)"] = ah["followers_raw"].apply(
                        lambda x: f"{float(x):.1f}万" if x else ""
                    )
                ah["ER(%)"] = ah.apply(lambda r: calc_er(
                    int(r.get("followers",0)), int(r.get("avg_likes",0)), int(r.get("avg_comments",0))
                ), axis=1)
                ah["投稿頻度"] = ah["weekly_posts"].apply(
                    lambda x: f"{float(x):.1f}本/週" if x else ""
                )
                show_cols = ["year_month","フォロワー(万)","avg_likes","avg_comments","ER(%)","投稿頻度","latest_post"]
                show_cols = [c for c in show_cols if c in ah.columns]
                st.dataframe(
                    ah[show_cols].rename(columns={
                        "year_month":"年月","avg_likes":"平均いいね",
                        "avg_comments":"平均コメント","latest_post":"直近投稿"
                    }),
                    use_container_width=True, hide_index=True
                )

                # フォロワー推移グラフ
                if len(ah) >= 2:
                    st.markdown('<div class="section-head">フォロワー推移</div>', unsafe_allow_html=True)
                    chart_df = ah.sort_values("recorded_date")[["recorded_date","followers_raw"]].copy()
                    chart_df["followers_raw"] = pd.to_numeric(chart_df["followers_raw"], errors="coerce").fillna(0)
                    st.line_chart(chart_df.set_index("recorded_date")["followers_raw"])

    # ── タブ3: 投稿記録 ────────────────────────────────────────────────────────
    with tab_posts_tab:
        st.markdown('<div class="section-head">投稿を記録</div>', unsafe_allow_html=True)
        with st.form(key=f"post_form_{cid}"):
            pc1, pc2 = st.columns(2)
            with pc1:
                p_url  = st.text_input("投稿URL *", placeholder="https://www.instagram.com/p/...")
                p_date = st.date_input("投稿日", value=date.today())
            with pc2:
                p_likes    = st.number_input("いいね数",   min_value=0, value=0, step=10)
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
                    else:
                        st.markdown('<div class="err-box">記録に失敗しました</div>', unsafe_allow_html=True)

        # 投稿一覧
        st.markdown('<div class="section-head">投稿一覧</div>', unsafe_allow_html=True)
        if not df_posts.empty:
            ap = df_posts[df_posts["account_id"] == cid].sort_values("post_date", ascending=False).copy()
            if not ap.empty:
                for col in ["likes","comments"]:
                    ap[col] = pd.to_numeric(ap[col], errors="coerce").fillna(0).astype(int)
                ap["エンゲージメント"] = ap["likes"] + ap["comments"]
                for _, pr in ap.iterrows():
                    pid = int(pr["id"])
                    with st.expander(
                        f"{pr['post_date']} | ❤️ {int(pr['likes']):,} 💬 {int(pr['comments']):,} | {str(pr['post_url'])[:40]}..."
                    ):
                        st.markdown(f"**URL:** [{pr['post_url']}]({pr['post_url']})")
                        ec1, ec2, ec3, ec4 = st.columns(4)
                        with ec1:
                            new_l = st.number_input("いいね", value=int(pr["likes"]), step=10, key=f"pl_{pid}")
                        with ec2:
                            new_c = st.number_input("コメント", value=int(pr["comments"]), step=1, key=f"pc_{pid}")
                        with ec3:
                            if st.button("更新", key=f"pu_{pid}"):
                                sb_update("competitor_posts", {"likes": new_l, "comments": new_c}, {"id": pid})
                                st.cache_data.clear(); st.rerun()
                        with ec4:
                            if st.button("削除", key=f"pd_{pid}"):
                                sb_delete("competitor_posts", {"id": pid})
                                st.cache_data.clear(); st.rerun()

else:
    # ════════════════════════════════════════════════════════
    # 一覧・分析画面
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="page-title">競合分析</div>', unsafe_allow_html=True)
    tab_list, tab_register, tab_analysis = st.tabs(["アカウント一覧", "新規登録", "分析・市場戦略"])

    df_acc, df_hist, df_posts = load_all_data()

    # ── タブ1: アカウント一覧（検索・比較表）─────────────────────────────────
    with tab_list:
        st.markdown('<div class="section-head">検索・絞り込み</div>', unsafe_allow_html=True)
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1: s_name = st.text_input("アカウント名", key="s_name")
        with sc2: s_loc  = st.selectbox("発信地", ["すべて"]+LOCATIONS, key="s_loc")
        with sc3: s_cat  = st.selectbox("カテゴリー", ["すべて"]+CATEGORIES, key="s_cat")
        with sc4: s_date = st.text_input("登録日 (YYYY-MM-DD)", placeholder="例: 2026-01-01", key="s_date")

        if df_acc.empty:
            st.markdown('<div class="info-box">まだ登録されていません。「新規登録」タブからアカウントを追加してください。</div>', unsafe_allow_html=True)
        else:
            df_show = df_acc.copy()
            if s_name:
                df_show = df_show[df_show["username"].str.contains(s_name, case=False, na=False)]
            if s_loc != "すべて":
                loc_mask = (
                    df_show["location"].fillna("").str.contains(s_loc, na=False) |
                    df_show["content_region"].fillna("").str.contains(s_loc, na=False)
                )
                df_show = df_show[loc_mask]
            if s_cat != "すべて":
                cat_mask = (
                    df_show["category"].fillna("").str.contains(s_cat, na=False) |
                    df_show["content_genre"].fillna("").str.contains(s_cat, na=False)
                )
                df_show = df_show[cat_mask]
            if s_date:
                df_show = df_show[df_show["created_at"].astype(str).str.startswith(s_date)]

            st.caption(f"{len(df_show)}件")

            # メトリクスを付与して比較テーブルを生成
            rows = []
            for _, row in df_show.iterrows():
                aid = int(row["id"])
                m   = get_latest_metrics(aid, df_hist, df_posts)
                loc = row.get("location","") or row.get("content_region","") or ""
                cat = row.get("category","") or row.get("content_genre","") or ""
                rows.append({
                    "_id":         aid,
                    "アカウント":   row["username"],
                    "発信地":       loc,
                    "カテゴリー":   cat,
                    "フォロワー(万)": f"{m['followers_raw']:.1f}万" if m['followers_raw'] > 0 else "—",
                    "増加率(%)":    f"{m['growth']:+.1f}%" if m["growth"] is not None else "—",
                    "ER(%)":        m["er"],
                    "平均いいね":   m["avg_likes"],
                    "平均コメント": m["avg_comments"],
                    "投稿頻度":     f"{m['weekly_posts']:.1f}本/週" if m["weekly_posts"] > 0 else "—",
                })

            # テーブル + クリックで詳細へ
            for row_d in rows:
                aid = row_d["_id"]
                c1,c2,c3,c4,c5,c6,c7,c8,c9,c10 = st.columns([2.5,1.5,2,1.2,1.2,1,1,1,1.5,0.8])
                with c1:
                    if st.button(row_d["アカウント"], key=f"go_{aid}"):
                        st.session_state["selected_competitor_id"] = aid; st.rerun()
                with c2:  st.caption(row_d["発信地"])
                with c3:  st.caption(row_d["カテゴリー"])
                with c4:  st.caption(row_d["フォロワー(万)"])
                with c5:  st.caption(row_d["増加率(%)"])
                with c6:  st.caption(f"ER {row_d['ER(%)']}%")
                with c7:  st.caption(f"❤️{row_d['平均いいね']:,}")
                with c8:  st.caption(f"💬{row_d['平均コメント']:,}")
                with c9:  st.caption(row_d["投稿頻度"])
                with c10:
                    if st.button("詳細", key=f"det_{aid}"):
                        st.session_state["selected_competitor_id"] = aid; st.rerun()

    # ── タブ2: 新規登録 ───────────────────────────────────────────────────────
    with tab_register:
        st.markdown('<div class="section-head">新規アカウントを登録</div>', unsafe_allow_html=True)
        with st.form(key="register_form"):
            rc1, rc2 = st.columns(2)
            with rc1:
                new_uname = st.text_input("Instagramユーザー名 *", placeholder="例: @tokyo_travel")
                new_loc   = st.selectbox("発信地", ["未設定"]+LOCATIONS, key="reg_loc")
                new_region= st.text_input("拠点詳細（任意）", placeholder="例: 東京都在住")
            with rc2:
                new_cat   = st.selectbox("カテゴリー", ["未設定"]+CATEGORIES, key="reg_cat")
                new_genre = st.text_input("詳細ジャンル（任意）")
                new_note  = st.text_area("メモ", height=68)

            if st.form_submit_button("登録する"):
                if not new_uname.strip():
                    st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
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
                        "note":           new_note.strip() or None,
                        "is_active":      True,
                    })
                    if res:
                        st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.markdown('<div class="err-box">登録に失敗しました（同じユーザー名が既に存在する可能性があります）</div>', unsafe_allow_html=True)

    # ── タブ3: 分析・市場戦略 ─────────────────────────────────────────────────
    with tab_analysis:
        if df_acc.empty or df_hist.empty:
            st.markdown('<div class="info-box">データが不足しています。アカウントを登録し、月次データを入力してください。</div>', unsafe_allow_html=True)
            st.stop()

        # 数値変換
        for col in ["followers","avg_likes","avg_comments","weekly_posts","followers_raw","engagement"]:
            if col in df_hist.columns:
                df_hist[col] = pd.to_numeric(df_hist[col], errors="coerce").fillna(0)

        # アカウント名・地域・カテゴリーを結合
        df_hist = df_hist.merge(
            df_acc[["id","username","location","content_region","category","content_genre"]].rename(columns={"id":"account_id"}),
            on="account_id", how="left"
        )
        df_hist["loc_disp"] = df_hist["location"].fillna("") + df_hist["content_region"].fillna("")
        df_hist["loc_disp"] = df_hist["loc_disp"].str[:4].replace("","不明")
        df_hist["cat_disp"] = df_hist["category"].fillna("") + df_hist["content_genre"].fillna("")

        # ── 全体分析サマリー ──────────────────────────────────────────────────
        st.markdown('<div class="section-head">全体分析サマリー</div>', unsafe_allow_html=True)

        # 各アカウントの最新データを集計
        summary_rows = []
        for _, acc in df_acc.iterrows():
            aid = int(acc["id"])
            m   = get_latest_metrics(aid, df_hist, df_posts)
            if m["followers"] == 0: continue
            summary_rows.append({
                "account_id": aid,
                "username":   acc["username"],
                "location":   acc.get("location","") or acc.get("content_region","") or "不明",
                "category":   acc.get("category","") or acc.get("content_genre","") or "不明",
                "er":         m["er"],
                "avg_likes":  m["avg_likes"],
                "avg_comments": m["avg_comments"],
                "weekly_posts": m["weekly_posts"],
                "growth":     m["growth"] or 0,
            })

        if summary_rows:
            df_summary = pd.DataFrame(summary_rows)
            avg_er     = df_summary["er"].mean()
            avg_likes  = df_summary["avg_likes"].mean()
            avg_wp     = df_summary["weekly_posts"].mean()
            grow_pos   = len(df_summary[df_summary["growth"] > 0])
            grow_neg   = len(df_summary[df_summary["growth"] < 0])

            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{len(df_summary)}</div><div class="lbl">分析対象アカウント数</div></div>
              <div class="metric-card"><div class="val">{avg_er:.2f}%</div><div class="lbl">平均ER</div></div>
              <div class="metric-card"><div class="val">{avg_likes:,.0f}</div><div class="lbl">平均いいね数</div></div>
              <div class="metric-card"><div class="val">{avg_wp:.1f}本/週</div><div class="lbl">平均投稿頻度</div></div>
              <div class="metric-card"><div class="val" style="color:#15803d;">{grow_pos}社</div><div class="lbl">フォロワー増加中</div></div>
              <div class="metric-card"><div class="val" style="color:#dc2626;">{grow_neg}社</div><div class="lbl">フォロワー減少中</div></div>
            </div>""", unsafe_allow_html=True)

            # ── 発信地別分析 ──────────────────────────────────────────────────
            st.markdown('<div class="section-head">発信地別分析</div>', unsafe_allow_html=True)
            loc_group = df_summary.groupby("location").agg(
                アカウント数=("account_id","count"),
                平均ER=("er","mean"),
                平均いいね=("avg_likes","mean"),
                平均フォロワー増加率=("growth","mean"),
            ).round(2).sort_values("平均フォロワー増加率", ascending=False)

            st.dataframe(loc_group, use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**発信地別 平均フォロワー増加率(%)**")
                st.bar_chart(loc_group["平均フォロワー増加率"])
            with col_b:
                st.markdown("**発信地別 平均エンゲージメント率(%)**")
                st.bar_chart(loc_group["平均ER"])

            # 市場戦略自動レポート
            st.markdown('<div class="section-head">市場戦略レポート（自動生成）</div>', unsafe_allow_html=True)
            best_loc  = loc_group["平均フォロワー増加率"].idxmax()
            worst_loc = loc_group["平均フォロワー増加率"].idxmin()
            best_rate = loc_group.loc[best_loc,"平均フォロワー増加率"]
            worst_rate= loc_group.loc[worst_loc,"平均フォロワー増加率"]

            if best_rate > 5:
                st.markdown(f'<div class="success-box">✅ <strong>{best_loc}</strong>系コンテンツの平均フォロワー増加率が+{best_rate:.1f}%で最も高い。{best_loc}へのコンテンツシフトを推奨します。</div>', unsafe_allow_html=True)
            elif best_rate < 1:
                st.markdown('<div class="err-box">⚠️ 全地域でフォロワー増加率が低迷しています。市場全体が飽和状態の可能性があります。新しい切り口や地域の検討を推奨します。</div>', unsafe_allow_html=True)
            if worst_rate < -2:
                st.markdown(f'<div class="err-box">⚠️ <strong>{worst_loc}</strong>系コンテンツの成長率が{worst_rate:.1f}%と最も低い。{worst_loc}コンテンツの縮小を検討してください。</div>', unsafe_allow_html=True)
            if avg_er < 1:
                st.markdown('<div class="err-box">⚠️ 競合全体のエンゲージメント率が1%未満です。市場全体でユーザーの関心が低下している可能性があります。</div>', unsafe_allow_html=True)
            elif avg_er > 3:
                st.markdown(f'<div class="success-box">✅ 競合全体の平均ER {avg_er:.2f}%は高水準です。コンテンツの質向上が差別化の鍵です。</div>', unsafe_allow_html=True)

            # ── アカウント別比較 ──────────────────────────────────────────────
            st.markdown('<div class="section-head">アカウント別比較分析</div>', unsafe_allow_html=True)
            sel_accounts = st.multiselect(
                "比較するアカウントを選択（複数可）",
                df_summary["username"].tolist(),
                default=df_summary["username"].tolist()[:min(5, len(df_summary))],
                key="cmp_sel"
            )
            if sel_accounts:
                df_cmp = df_summary[df_summary["username"].isin(sel_accounts)].set_index("username")

                col_x, col_y = st.columns(2)
                with col_x:
                    st.markdown("**エンゲージメント率比較(%)**")
                    st.bar_chart(df_cmp["er"])
                with col_y:
                    st.markdown("**フォロワー増加率比較(%)**")
                    st.bar_chart(df_cmp["growth"])

                col_z, col_w = st.columns(2)
                with col_z:
                    st.markdown("**平均いいね数比較**")
                    st.bar_chart(df_cmp["avg_likes"])
                with col_w:
                    st.markdown("**投稿頻度比較（本/週）**")
                    st.bar_chart(df_cmp["weekly_posts"])

                # フォロワー推移（折れ線）
                st.markdown("**フォロワー推移（万人）**")
                pivot_fw = df_hist[df_hist["username"].isin(sel_accounts)].copy()
                if not pivot_fw.empty and "followers_raw" in pivot_fw.columns:
                    fw_wide = pivot_fw.groupby(["recorded_date","username"])["followers_raw"].mean().reset_index()
                    fw_wide = fw_wide.pivot(index="recorded_date", columns="username", values="followers_raw").fillna(0)
                    st.line_chart(fw_wide)
