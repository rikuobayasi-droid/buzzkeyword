"""
pages/12_competitor_analysis.py — 競合分析（v2完全版）
URL: /competitor_analysis

機能:
- 競合アカウント登録・編集・削除
- 月次データ（フォロワー数・エンゲージメント・投稿頻度）
- 直近7投稿の記録（URL・投稿日・いいね・コメント）
- 地域別トレンド分析
- 市場戦略レポート（自動生成）
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_upsert, sb_update, sb_delete

st.set_page_config(page_title="競合分析 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">競合分析</div>', unsafe_allow_html=True)

# 地域・ジャンルの選択肢
REGIONS = ["東京","大阪","京都","沖縄","北海道","福岡","名古屋","広島","神戸","奈良","その他"]
GENRES  = ["観光・旅行","グルメ","文化・伝統","自然・景色","ホテル・宿","体験・アクティビティ","その他"]

tab_manage, tab_monthly, tab_posts, tab_analysis = st.tabs([
    "アカウント管理",
    "月次データ入力",
    "投稿記録",
    "分析・市場戦略",
])

# ── ヘルパー: 万人単位 → 整数変換 ────────────────────────────────────────────
def man_to_int(val_man: float) -> int:
    """12.3万 → 123000"""
    return int(val_man * 10000)

def int_to_man(val_int) -> float:
    """123000 → 12.3"""
    try:
        return round(int(val_int) / 10000, 1)
    except Exception:
        return 0.0

# ── 分析ロジック ──────────────────────────────────────────────────────────────
def calc_engagement_rate(followers: int, avg_likes: int, avg_comments: int) -> float:
    """エンゲージメント率 = (いいね+コメント) ÷ フォロワー × 100"""
    if followers <= 0: return 0.0
    return round((avg_likes + avg_comments) / followers * 100, 2)

def calc_growth_rate(old_followers: int, new_followers: int) -> float:
    """フォロワー増加率（%）"""
    if old_followers <= 0: return 0.0
    return round((new_followers - old_followers) / old_followers * 100, 1)

def analyze_market(df_acc: pd.DataFrame, df_hist: pd.DataFrame) -> list:
    """
    全競合データから市場戦略レポートをルールベースで自動生成。
    返値: [{level, message}]
    """
    reports = []
    if df_acc.empty or df_hist.empty:
        return reports

    # 地域別フォロワー増加率を集計
    region_growth = {}
    for _, acc in df_acc.iterrows():
        acc_id  = acc["id"]
        region  = acc.get("content_region","") or acc.get("region","") or "不明"
        acc_hist = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")
        if len(acc_hist) < 2: continue
        old_f = int(acc_hist.iloc[0]["followers"] or 0)
        new_f = int(acc_hist.iloc[-1]["followers"] or 0)
        rate  = calc_growth_rate(old_f, new_f)
        if region not in region_growth:
            region_growth[region] = []
        region_growth[region].append(rate)

    if region_growth:
        region_avg = {r: round(sum(v)/len(v), 1) for r, v in region_growth.items()}
        best_region  = max(region_avg, key=region_avg.get)
        worst_region = min(region_avg, key=region_avg.get)
        best_rate    = region_avg[best_region]
        worst_rate   = region_avg[worst_region]

        if best_rate > 5:
            reports.append({"level":"ok","message":
                f"【地域トレンド】{best_region}系コンテンツの平均フォロワー増加率が+{best_rate}%で最も高い。"
                f"{best_region}へのコンテンツシフトを推奨します。"})
        elif best_rate < 1:
            reports.append({"level":"warning","message":
                "【市場飽和】全地域でフォロワー増加率が低迷しています。"
                "現在の市場は飽和状態の可能性があります。新しい切り口や地域の検討を推奨します。"})

        if worst_rate < 0:
            reports.append({"level":"warning","message":
                f"【衰退シグナル】{worst_region}系コンテンツの成長率が{worst_rate}%と最も低い。"
                f"{worst_region}コンテンツの縮小を検討してください。"})

    # 全体のエンゲージメント率
    latest_rows = []
    for _, acc in df_acc.iterrows():
        acc_id   = acc["id"]
        acc_hist = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")
        if acc_hist.empty: continue
        latest = acc_hist.iloc[-1]
        f  = int(latest.get("followers") or 0)
        l  = int(latest.get("avg_likes") or 0)
        c  = int(latest.get("avg_comments") or 0)
        er = calc_engagement_rate(f, l, c)
        latest_rows.append({"account": acc["username"], "engagement": er, "followers": f})

    if latest_rows:
        df_latest = pd.DataFrame(latest_rows)
        avg_er    = df_latest["engagement"].mean()
        if avg_er > 3:
            reports.append({"level":"ok","message":
                f"【エンゲージメント】競合全体の平均エンゲージメント率は{avg_er:.1f}%と高水準です。"
                "コンテンツの質を高めることが差別化の鍵です。"})
        elif avg_er < 1:
            reports.append({"level":"warning","message":
                f"【エンゲージメント低下】競合全体の平均エンゲージメント率は{avg_er:.1f}%と低い。"
                "市場全体でユーザーの関心が低下している可能性があります。"})

    return reports

# ════════════════════════════════════════════════════════
# タブ1: アカウント管理
# ════════════════════════════════════════════════════════
with tab_manage:
    st.markdown('<div class="section-head">競合アカウントを登録</div>', unsafe_allow_html=True)

    with st.form(key="register_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            new_username       = st.text_input("Instagramユーザー名 *", placeholder="例: @tokyo_travel")
            new_content_region = st.selectbox("主な発信地域", ["未設定"] + REGIONS, key="reg_cr")
            new_region         = st.text_input("拠点（任意）", placeholder="例: 東京都在住")
        with rc2:
            new_content_genre = st.selectbox("コンテンツジャンル", ["未設定"] + GENRES, key="reg_cg")
            new_genre         = st.text_input("詳細ジャンル（任意）", placeholder="例: 京都グルメ特化")
            new_note          = st.text_area("メモ", height=68)

        if st.form_submit_button("アカウントを登録する"):
            if not new_username.strip():
                st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("competitor_accounts", {
                    "username":       new_username.strip(),
                    "platform":       "Instagram",
                    "content_region": new_content_region if new_content_region != "未設定" else None,
                    "region":         new_region.strip() or None,
                    "content_genre":  new_content_genre if new_content_genre != "未設定" else None,
                    "genre":          new_genre.strip() or None,
                    "note":           new_note.strip() or None,
                    "is_active":      True,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown('<div class="err-box">登録に失敗しました（同じユーザー名が既に存在する可能性があります）</div>', unsafe_allow_html=True)

    # 一覧・編集・削除
    st.markdown('<div class="section-head">登録済みアカウント一覧</div>', unsafe_allow_html=True)
    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">まだ登録されていません</div>', unsafe_allow_html=True)
    else:
        for _, row in df_acc.iterrows():
            rid    = int(row["id"])
            active = bool(row.get("is_active", True))
            cr     = row.get("content_region","") or ""
            cg     = row.get("content_genre","")  or ""

            with st.expander(f"{'🟢' if active else '⚫'} {row['username']} | {cr} | {cg}"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_uname = st.text_input("ユーザー名",    value=row.get("username",""),         key=f"e_uname_{rid}")
                    cr_idx  = (["未設定"]+REGIONS).index(cr) if cr in REGIONS else 0
                    e_cr    = st.selectbox("主な発信地域", ["未設定"]+REGIONS, index=cr_idx,         key=f"e_cr_{rid}")
                    e_region= st.text_input("拠点（任意）", value=row.get("region","") or "",       key=f"e_region_{rid}")
                with ec2:
                    cg_idx  = (["未設定"]+GENRES).index(cg) if cg in GENRES else 0
                    e_cg    = st.selectbox("コンテンツジャンル", ["未設定"]+GENRES, index=cg_idx,   key=f"e_cg_{rid}")
                    e_genre = st.text_input("詳細ジャンル",  value=row.get("genre","") or "",       key=f"e_genre_{rid}")
                    e_note  = st.text_area("メモ",           value=row.get("note","") or "", height=68, key=f"e_note_{rid}")

                bc1, bc2, bc3 = st.columns([2,2,2])
                with bc1:
                    if st.button("更新する", key=f"upd_{rid}"):
                        sb_update("competitor_accounts", {
                            "username":       e_uname.strip(),
                            "content_region": e_cr if e_cr != "未設定" else None,
                            "region":         e_region.strip() or None,
                            "content_genre":  e_cg if e_cg != "未設定" else None,
                            "genre":          e_genre.strip() or None,
                            "note":           e_note.strip() or None,
                        }, {"id": rid})
                        st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                        st.rerun()
                with bc2:
                    if st.button("無効化する" if active else "有効化する", key=f"toggle_{rid}"):
                        sb_update("competitor_accounts", {"is_active": not active}, {"id": rid})
                        st.rerun()
                with bc3:
                    if st.button("削除する", key=f"del_{rid}"):
                        sb_delete("competitor_accounts", {"id": rid})
                        st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: 月次データ入力
# ════════════════════════════════════════════════════════
with tab_monthly:
    st.markdown('<div class="section-head">月次データを入力（月1回）</div>', unsafe_allow_html=True)
    st.caption("フォロワー数はXX.X万人形式で入力してください。例: 12.3万人 → 12.3")

    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">先にアカウント管理タブでアカウントを登録してください</div>', unsafe_allow_html=True)
    else:
        with st.form(key="monthly_form"):
            mc1, mc2 = st.columns(2)
            with mc1:
                sel_acc  = st.selectbox("アカウントを選択", df_acc["username"].tolist())
                rec_date = st.date_input("記録日", value=date.today())
                followers_man  = st.number_input("フォロワー数（万人）", min_value=0.0, value=0.0, step=0.1, format="%.1f",
                                                  help="例: 12.3万人なら 12.3 と入力")
            with mc2:
                avg_likes    = st.number_input("直近7投稿 平均いいね数",    min_value=0, value=0, step=10)
                avg_comments = st.number_input("直近7投稿 平均コメント数",  min_value=0, value=0, step=1)
                weekly_posts = st.number_input("週間投稿数",                 min_value=0, value=0, step=1)
            monthly_note = st.text_input("メモ（任意）")

            if st.form_submit_button("保存する"):
                acc_id     = int(df_acc[df_acc["username"] == sel_acc]["id"].values[0])
                followers  = man_to_int(followers_man)
                er         = calc_engagement_rate(followers, avg_likes, avg_comments)
                res = sb_upsert("competitor_history", {
                    "account_id":    acc_id,
                    "recorded_date": str(rec_date),
                    "followers":     followers,
                    "followers_raw": followers_man,
                    "avg_views":     0,
                    "avg_likes":     avg_likes,
                    "avg_comments":  avg_comments,
                    "weekly_posts":  weekly_posts,
                    "note":          monthly_note or None,
                })
                if res:
                    st.markdown(
                        f'<div class="success-box">保存しました &nbsp; '
                        f'エンゲージメント率: <strong>{er}%</strong></div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown('<div class="err-box">保存に失敗しました</div>', unsafe_allow_html=True)

        # 入力済み履歴
        st.markdown('<div class="section-head">入力済み履歴</div>', unsafe_allow_html=True)
        rows_hist = sb_select("competitor_history", order="-recorded_date")
        df_hist   = to_df(rows_hist)
        if not df_hist.empty and not df_acc.empty:
            df_hist = df_hist.merge(
                df_acc[["id","username"]].rename(columns={"id":"account_id"}),
                on="account_id", how="left"
            )
            f_acc = st.selectbox("絞り込み", ["全体"] + df_acc["username"].tolist(), key="hist_filter")
            df_show = df_hist if f_acc == "全体" else df_hist[df_hist["username"] == f_acc]
            for col in ["followers","avg_likes","avg_comments","weekly_posts"]:
                if col in df_show.columns:
                    df_show[col] = pd.to_numeric(df_show[col], errors="coerce").fillna(0).astype(int)
            if "followers_raw" in df_show.columns:
                df_show["フォロワー(万)"] = df_show["followers_raw"].apply(
                    lambda x: f"{float(x):.1f}万" if x else ""
                )
            cols_show = ["username","recorded_date","フォロワー(万)","avg_likes","avg_comments","weekly_posts"]
            cols_show = [c for c in cols_show if c in df_show.columns]
            st.dataframe(
                df_show[cols_show].rename(columns={
                    "username":"アカウント","recorded_date":"記録日",
                    "avg_likes":"平均いいね","avg_comments":"平均コメント","weekly_posts":"週投稿数"
                }).head(20),
                use_container_width=True, hide_index=True
            )

# ════════════════════════════════════════════════════════
# タブ3: 投稿記録（直近7投稿）
# ════════════════════════════════════════════════════════
with tab_posts:
    st.markdown('<div class="section-head">直近投稿を記録</div>', unsafe_allow_html=True)
    st.caption("直近7投稿程度を記録してください。同じURLで再入力すると上書きされます。")

    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">先にアカウント管理タブでアカウントを登録してください</div>', unsafe_allow_html=True)
    else:
        with st.form(key="post_form"):
            pc1, pc2 = st.columns(2)
            with pc1:
                p_acc      = st.selectbox("アカウントを選択", df_acc["username"].tolist(), key="p_acc")
                p_url      = st.text_input("投稿URL *", placeholder="https://www.instagram.com/p/...")
                p_date     = st.date_input("投稿日", value=date.today())
            with pc2:
                p_likes    = st.number_input("いいね数",    min_value=0, value=0, step=10)
                p_comments = st.number_input("コメント数",  min_value=0, value=0, step=1)
                p_note     = st.text_input("メモ（任意）")

            if st.form_submit_button("投稿を記録する"):
                if not p_url.strip():
                    st.markdown('<div class="err-box">投稿URLは必須です</div>', unsafe_allow_html=True)
                else:
                    acc_id = int(df_acc[df_acc["username"] == p_acc]["id"].values[0])
                    res = sb_upsert("competitor_posts", {
                        "account_id":    acc_id,
                        "post_url":      p_url.strip(),
                        "post_date":     str(p_date),
                        "likes":         p_likes,
                        "comments":      p_comments,
                        "recorded_date": str(date.today()),
                        "note":          p_note.strip() or None,
                    })
                    if res:
                        st.markdown('<div class="success-box">記録しました</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="err-box">記録に失敗しました</div>', unsafe_allow_html=True)

        # 記録済み投稿一覧
        st.markdown('<div class="section-head">記録済み投稿一覧</div>', unsafe_allow_html=True)
        rows_posts = sb_select("competitor_posts", order="-post_date")
        df_posts   = to_df(rows_posts)

        if not df_posts.empty and not df_acc.empty:
            df_posts = df_posts.merge(
                df_acc[["id","username"]].rename(columns={"id":"account_id"}),
                on="account_id", how="left"
            )
            pf_acc = st.selectbox("アカウントで絞り込み", ["全体"] + df_acc["username"].tolist(), key="post_filter")
            df_ps  = df_posts if pf_acc == "全体" else df_posts[df_posts["username"] == pf_acc]

            for _, row in df_ps.head(30).iterrows():
                pid = int(row["id"])
                with st.expander(
                    f"{row.get('username','')} | {row.get('post_date','')} | "
                    f"❤️ {int(row.get('likes',0)):,} 💬 {int(row.get('comments',0)):,}"
                ):
                    st.markdown(f"**URL:** [{row.get('post_url','')}]({row.get('post_url','')})")
                    st.markdown(f"**投稿日:** {row.get('post_date','')} &nbsp; **記録日:** {row.get('recorded_date','')}")
                    st.markdown(f"**いいね:** {int(row.get('likes',0)):,} &nbsp; **コメント:** {int(row.get('comments',0)):,}")
                    if row.get("note"):
                        st.markdown(f"**メモ:** {row.get('note','')}")

                    # 編集
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    with ec1:
                        new_likes = st.number_input("いいね数", value=int(row.get("likes",0)), step=10, key=f"pl_{pid}")
                    with ec2:
                        new_comments = st.number_input("コメント数", value=int(row.get("comments",0)), step=1, key=f"pc_{pid}")
                    with ec3:
                        if st.button("更新", key=f"pu_{pid}"):
                            sb_update("competitor_posts", {"likes": new_likes, "comments": new_comments}, {"id": pid})
                            st.rerun()
                    with ec4:
                        if st.button("削除", key=f"pd_{pid}"):
                            sb_delete("competitor_posts", {"id": pid})
                            st.rerun()

# ════════════════════════════════════════════════════════
# タブ4: 分析・市場戦略
# ════════════════════════════════════════════════════════
with tab_analysis:
    rows_acc   = sb_select("competitor_accounts", order="username")
    rows_hist  = sb_select("competitor_history",  order="recorded_date")
    rows_posts = sb_select("competitor_posts",     order="-post_date")
    df_acc     = to_df(rows_acc)
    df_hist    = to_df(rows_hist)
    df_posts   = to_df(rows_posts)

    if df_acc.empty:
        st.markdown('<div class="info-box">競合アカウントが登録されていません</div>', unsafe_allow_html=True)
        st.stop()

    if df_hist.empty:
        st.markdown('<div class="info-box">月次データがありません。「月次データ入力」タブからデータを入力してください</div>', unsafe_allow_html=True)
        st.stop()

    # 数値型変換
    for col in ["followers","avg_likes","avg_comments","weekly_posts","followers_raw"]:
        if col in df_hist.columns:
            df_hist[col] = pd.to_numeric(df_hist[col], errors="coerce").fillna(0)

    # アカウント名結合
    df_hist = df_hist.merge(
        df_acc[["id","username","content_region","content_genre"]].rename(columns={"id":"account_id"}),
        on="account_id", how="left"
    )

    # ── 市場戦略レポート（自動生成）────────────────────────────────────────
    st.markdown('<div class="section-head">市場戦略レポート（自動生成）</div>', unsafe_allow_html=True)
    reports = analyze_market(df_acc, df_hist)
    if reports:
        for r in reports:
            if r["level"] == "ok":
                st.markdown(f'<div class="success-box">✅ {r["message"]}</div>', unsafe_allow_html=True)
            elif r["level"] == "warning":
                st.markdown(f'<div class="err-box">⚠️ {r["message"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="info-box">{r["message"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box">複数のアカウントのデータが2件以上になると自動レポートが生成されます</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── 地域別フォロワー増加率 ────────────────────────────────────────────
    st.markdown('<div class="section-head">地域別 フォロワー増加率</div>', unsafe_allow_html=True)
    region_data = []
    for _, acc in df_acc.iterrows():
        acc_id  = int(acc["id"])
        region  = acc.get("content_region","") or "不明"
        ah = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")
        if len(ah) < 2: continue
        old_f = int(ah.iloc[0]["followers"])
        new_f = int(ah.iloc[-1]["followers"])
        rate  = calc_growth_rate(old_f, new_f)
        region_data.append({"地域": region, "アカウント": acc["username"], "増加率(%)": rate, "最新フォロワー": new_f})

    if region_data:
        df_region = pd.DataFrame(region_data)
        region_avg = df_region.groupby("地域")["増加率(%)"].mean().round(1).sort_values(ascending=False).reset_index()
        region_avg.columns = ["地域","平均増加率(%)"]
        st.dataframe(region_avg, use_container_width=True, hide_index=True)
        st.bar_chart(region_avg.set_index("地域")["平均増加率(%)"])

    # ── エンゲージメント率比較 ────────────────────────────────────────────
    st.markdown('<div class="section-head">エンゲージメント率比較</div>', unsafe_allow_html=True)
    er_data = []
    for _, acc in df_acc.iterrows():
        acc_id = int(acc["id"])
        ah = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")
        if ah.empty: continue
        latest   = ah.iloc[-1]
        f        = int(latest.get("followers",0))
        l        = int(latest.get("avg_likes",0))
        c        = int(latest.get("avg_comments",0))
        er       = calc_engagement_rate(f, l, c)
        fw_man   = float(latest.get("followers_raw",0))
        er_data.append({
            "アカウント":     acc["username"],
            "地域":          acc.get("content_region","") or "",
            "フォロワー(万)": f"{fw_man:.1f}万" if fw_man > 0 else f"{f:,}",
            "平均いいね":     l,
            "平均コメント":   c,
            "エンゲージメント率(%)": er,
        })

    if er_data:
        df_er = pd.DataFrame(er_data).sort_values("エンゲージメント率(%)", ascending=False)
        st.dataframe(df_er, use_container_width=True, hide_index=True)
        st.bar_chart(df_er.set_index("アカウント")["エンゲージメント率(%)"])

    # ── フォロワー数推移（個別）──────────────────────────────────────────
    st.markdown('<div class="section-head">フォロワー数推移（アカウント別）</div>', unsafe_allow_html=True)
    sel_acc_a = st.selectbox("アカウントを選択", df_acc["username"].tolist(), key="anal_sel")
    acc_row   = df_acc[df_acc["username"] == sel_acc_a].iloc[0]
    acc_id    = int(acc_row["id"])
    df_single = df_hist[df_hist["account_id"] == acc_id].sort_values("recorded_date")

    if not df_single.empty:
        latest = df_single.iloc[-1]
        fw_man = float(latest.get("followers_raw",0))
        er     = calc_engagement_rate(
            int(latest.get("followers",0)),
            int(latest.get("avg_likes",0)),
            int(latest.get("avg_comments",0))
        )
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{fw_man:.1f}万</div><div class="lbl">フォロワー数</div></div>
          <div class="metric-card"><div class="val">{er}%</div><div class="lbl">エンゲージメント率</div></div>
          <div class="metric-card"><div class="val">{int(latest.get('weekly_posts',0))}</div><div class="lbl">週間投稿数</div></div>
        </div>""", unsafe_allow_html=True)

        st.line_chart(df_single.set_index("recorded_date")["followers"])

    # ── 直近投稿分析 ─────────────────────────────────────────────────────
    if not df_posts.empty:
        st.markdown('<div class="section-head">直近投稿 いいね・コメント分析</div>', unsafe_allow_html=True)
        df_posts_acc = df_posts[df_posts["account_id"] == acc_id].copy()
        if not df_posts_acc.empty:
            for col in ["likes","comments"]:
                df_posts_acc[col] = pd.to_numeric(df_posts_acc[col], errors="coerce").fillna(0).astype(int)
            df_posts_acc["エンゲージメント"] = df_posts_acc["likes"] + df_posts_acc["comments"]
            st.dataframe(
                df_posts_acc[["post_date","likes","comments","エンゲージメント","post_url"]]\
                    .rename(columns={"post_date":"投稿日","likes":"いいね","comments":"コメント","post_url":"URL"})\
                    .sort_values("投稿日", ascending=False),
                use_container_width=True, hide_index=True
            )
            st.bar_chart(df_posts_acc.set_index("post_date")["エンゲージメント"])
