"""
pages/14_concierge_whitelist.py — AI コンシェルジュ ホワイトリスト

機能:
  - お気に入りスポットを保存したユーザー一覧
  - セッション詳細・保存スポット確認
  - 顧客管理との連携（customer_id で紐付け）
  - スポット人気ランキング
"""
import streamlit as st
import pandas as pd
from datetime import date
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_update

st.set_page_config(page_title="AI コンシェルジュ | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">AI コンシェルジュ ホワイトリスト</div>', unsafe_allow_html=True)

# ── データ取得 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_data():
    df_plans    = to_df(sb_select("concierge_saved_plans",   order="-created_at"))
    df_sessions = to_df(sb_select("concierge_sessions",      order="-created_at"))
    df_feedback = to_df(sb_select("concierge_spot_feedback", order="-created_at"))
    df_custs    = to_df(sb_select("customers",               order="name"))
    return df_plans, df_sessions, df_feedback, df_custs

df_plans, df_sessions, df_feedback, df_custs = load_data()

tab_whitelist, tab_ranking, tab_sessions = st.tabs([
    "ホワイトリスト（保存ユーザー）", "スポット人気ランキング", "セッション一覧"
])

# ════════════════════════════════════════════════════════
# タブ1: ホワイトリスト（保存ユーザー一覧）
# ════════════════════════════════════════════════════════
with tab_whitelist:
    st.markdown('<div class="section-head">お気に入りスポットを保存したユーザー</div>', unsafe_allow_html=True)

    if df_plans.empty:
        st.markdown('<div class="info-box">まだ保存したユーザーはいません</div>', unsafe_allow_html=True)
    else:
        # メトリクス
        unique_emails = df_plans["email"].nunique()
        total_saves   = len(df_plans)
        notified      = int(df_plans["notified_company"].fillna(False).sum()) if "notified_company" in df_plans.columns else 0

        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{unique_emails}</div><div class="lbl">ユニークユーザー数</div></div>
          <div class="metric-card"><div class="val">{total_saves}</div><div class="lbl">保存件数（合計）</div></div>
          <div class="metric-card"><div class="val">{notified}</div><div class="lbl">連絡済み</div></div>
        </div>""", unsafe_allow_html=True)

        # 検索
        sc1, sc2 = st.columns(2)
        with sc1: s_email = st.text_input("メールで検索", key="wl_email")
        with sc2:
            save_types = ["すべて"] + df_plans["save_type"].dropna().unique().tolist()
            s_type = st.selectbox("保存タイプ", save_types, key="wl_type")

        df_show = df_plans.copy()
        if s_email:
            df_show = df_show[df_show["email"].str.contains(s_email, case=False, na=False)]
        if s_type != "すべて":
            df_show = df_show[df_show["save_type"] == s_type]

        st.caption(f"{len(df_show)}件")

        # ユーザーごとにグループ表示
        for email in df_show["email"].dropna().unique():
            user_plans = df_show[df_show["email"] == email]
            latest     = user_plans.sort_values("created_at").iloc[-1]

            # 顧客管理との紐付け確認
            cust_row  = None
            cust_name = "未登録"
            if not df_custs.empty and "email" in df_custs.columns:
                matched = df_custs[df_custs["email"] == email]
                if not matched.empty:
                    cust_row  = matched.iloc[0]
                    cust_name = str(cust_row.get("name","") or "名前未入力")

            notified_flag = bool(latest.get("notified_company", False))
            notified_icon = "✅" if notified_flag else "📩"

            with st.expander(
                f"{notified_icon} {email} | {cust_name} | {len(user_plans)}件保存 | "
                f"最終: {str(latest.get('created_at',''))[:10]}"
            ):
                ec1, ec2 = st.columns(2)
                with ec1:
                    st.markdown(f"**メール:** {email}")
                    st.markdown(f"**顧客管理:** {cust_name}")
                    if cust_row is not None:
                        pts = int(cust_row.get("total_points", 0) or 0)
                        st.markdown(f"**保有ポイント:** {pts:,}pt")
                        plat = cust_row.get("platform","")
                        if plat: st.markdown(f"**流入:** {plat}")
                with ec2:
                    st.markdown(f"**保存件数:** {len(user_plans)}件")
                    for _, plan in user_plans.iterrows():
                        s_type_v = plan.get("save_type","")
                        s_date   = str(plan.get("created_at",""))[:10]
                        title    = plan.get("plan_title","") or "無題"
                        st.caption(f"📍 {s_date} | {s_type_v} | {title}")

                # 保存スポット一覧
                for _, plan in user_plans.iterrows():
                    spots_json = plan.get("spots_json")
                    if spots_json:
                        st.markdown("**保存スポット:**")
                        try:
                            import json
                            if isinstance(spots_json, str):
                                spots = json.loads(spots_json)
                            else:
                                spots = spots_json
                            if isinstance(spots, list):
                                for spot in spots:
                                    if isinstance(spot, dict):
                                        st.caption(f"  📌 {spot.get('name', spot)}")
                                    else:
                                        st.caption(f"  📌 {spot}")
                        except Exception:
                            st.caption(str(spots_json)[:100])

                # 連絡済みフラグの更新
                st.markdown("---")
                plan_ids = user_plans["id"].tolist()
                bc1, bc2 = st.columns(2)
                with bc1:
                    if not notified_flag:
                        if st.button("✅ 連絡済みにする", key=f"notify_{email}"):
                            for pid in plan_ids:
                                sb_update("concierge_saved_plans",
                                          {"notified_company": True}, {"id": int(pid)})
                            st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                            st.cache_data.clear(); st.rerun()
                    else:
                        if st.button("📩 未連絡に戻す", key=f"unnotify_{email}"):
                            for pid in plan_ids:
                                sb_update("concierge_saved_plans",
                                          {"notified_company": False}, {"id": int(pid)})
                            st.cache_data.clear(); st.rerun()
                with bc2:
                    # 顧客管理へのリンク
                    if cust_row is not None:
                        cid = int(cust_row["id"])
                        if st.button("顧客詳細を開く", key=f"go_cust_{email}"):
                            st.session_state["selected_customer_id"] = cid
                            st.switch_page("pages/05_crm_customers.py")

# ════════════════════════════════════════════════════════
# タブ2: スポット人気ランキング
# ════════════════════════════════════════════════════════
with tab_ranking:
    st.markdown('<div class="section-head">スポット人気ランキング</div>', unsafe_allow_html=True)

    if df_feedback.empty:
        st.markdown('<div class="info-box">フィードバックデータがありません</div>', unsafe_allow_html=True)
    else:
        # 集計
        ranking = df_feedback.groupby(["spot_id","spot_name"]).agg(
            likes    = ("feedback", lambda x: (x == "like").sum()),
            dislikes = ("feedback", lambda x: (x == "dislike").sum()),
            total    = ("feedback", "count"),
        ).reset_index()
        ranking["like_rate(%)"] = (ranking["likes"] / ranking["total"] * 100).round(1)
        ranking = ranking.sort_values("likes", ascending=False).reset_index(drop=True)
        ranking.index += 1

        # メトリクス
        if not ranking.empty:
            top_spot = ranking.iloc[0]
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{len(ranking)}</div><div class="lbl">スポット数</div></div>
              <div class="metric-card"><div class="val">{top_spot['spot_name']}</div><div class="lbl">人気No.1スポット</div></div>
              <div class="metric-card"><div class="val">{int(top_spot['likes'])}</div><div class="lbl">最多いいね数</div></div>
            </div>""", unsafe_allow_html=True)

        st.dataframe(
            ranking[["spot_name","likes","dislikes","total","like_rate(%)"]].rename(columns={
                "spot_name":"スポット名","likes":"👍いいね","dislikes":"👎いまいち",
                "total":"合計","like_rate(%)":"いいね率(%)"
            }),
            use_container_width=True
        )

        # いいね数グラフ
        st.markdown('<div class="section-head">いいね数グラフ</div>', unsafe_allow_html=True)
        st.bar_chart(ranking.set_index("spot_name")["likes"])

        # dislike理由の集計
        if "dislike_reasons" in df_feedback.columns:
            reasons = df_feedback[df_feedback["feedback"] == "dislike"]["dislike_reasons"].dropna()
            if not reasons.empty:
                st.markdown('<div class="section-head">いまいちの理由（上位）</div>', unsafe_allow_html=True)
                all_reasons = []
                for r in reasons:
                    all_reasons.extend([x.strip() for x in str(r).split(",") if x.strip()])
                reason_counts = pd.Series(all_reasons).value_counts().head(10)
                st.bar_chart(reason_counts)

# ════════════════════════════════════════════════════════
# タブ3: セッション一覧
# ════════════════════════════════════════════════════════
with tab_sessions:
    st.markdown('<div class="section-head">AIコンシェルジュ セッション一覧</div>', unsafe_allow_html=True)

    if df_sessions.empty:
        st.markdown('<div class="info-box">セッションデータがありません</div>', unsafe_allow_html=True)
    else:
        # 検索
        ss1, ss2, ss3 = st.columns(3)
        with ss1: s_sess_email = st.text_input("メールで検索", key="sess_email")
        with ss2:
            vibes = ["すべて"] + df_sessions["vibe"].dropna().unique().tolist() if "vibe" in df_sessions.columns else ["すべて"]
            s_vibe = st.selectbox("スタイル", vibes, key="sess_vibe")
        with ss3:
            s_wa = st.checkbox("WhatsApp クリックのみ", key="sess_wa")

        df_sess_show = df_sessions.copy()
        if s_sess_email:
            df_sess_show = df_sess_show[df_sess_show["email"].str.contains(s_sess_email, case=False, na=False)]
        if s_vibe != "すべて":
            df_sess_show = df_sess_show[df_sess_show["vibe"] == s_vibe]
        if s_wa and "wa_clicked" in df_sess_show.columns:
            df_sess_show = df_sess_show[df_sess_show["wa_clicked"] == True]

        # メトリクス
        wa_cnt = int(df_sess_show["wa_clicked"].fillna(False).sum()) if "wa_clicked" in df_sess_show.columns else 0
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{len(df_sess_show)}</div><div class="lbl">セッション数</div></div>
          <div class="metric-card"><div class="val">{df_sess_show['email'].nunique()}</div><div class="lbl">ユニークユーザー</div></div>
          <div class="metric-card"><div class="val">{wa_cnt}</div><div class="lbl">WhatsAppクリック</div></div>
        </div>""", unsafe_allow_html=True)

        st.caption(f"{len(df_sess_show)}件")

        # 表示カラムを絞る
        show_cols = [c for c in ["created_at","email","vibe","style","time_slot",
                                  "priority","first_time","pro_request","wa_clicked"]
                     if c in df_sess_show.columns]
        st.dataframe(
            df_sess_show[show_cols].rename(columns={
                "created_at":"日時","email":"メール","vibe":"スタイル",
                "style":"撮影","time_slot":"時間帯","priority":"優先",
                "first_time":"初回","pro_request":"プロ依頼","wa_clicked":"WA"
            }).sort_values("日時", ascending=False),
            use_container_width=True, hide_index=True
        )
