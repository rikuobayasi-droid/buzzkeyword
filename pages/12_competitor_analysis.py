"""
pages/12_competitor_analysis.py — 競合分析
URL: /competitor_analysis

修正:
- アカウント登録バグを修正（keyを付与）
- 編集・更新・削除を手動で実行できるように変更
- 編集フォームをexpander内に展開して表示
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_upsert, sb_update, sb_delete

st.set_page_config(page_title="競合分析 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">競合分析</div>', unsafe_allow_html=True)

tab_manage, tab_input, tab_analysis = st.tabs([
    "競合アカウント管理",
    "データ入力",
    "分析・グラフ",
])

# ════════════════════════════════════════════════════════
# 分析ロジック（ルールベース）
# ════════════════════════════════════════════════════════
def analyze_trend(df_hist: pd.DataFrame) -> list:
    alerts = []
    if df_hist.empty or len(df_hist) < 2:
        alerts.append({"level":"info","message":"データが2件以上になると傾向分析が可能になります"})
        return alerts

    df     = df_hist.sort_values("recorded_date")
    recent = df.tail(3)

    # フォロワー増加の停滞チェック
    if len(recent) >= 2:
        old_f   = int(recent.iloc[0]["followers"])
        new_f   = int(recent.iloc[-1]["followers"])
        delta_f = new_f - old_f
        rate_f  = round((delta_f / old_f) * 100, 1) if old_f > 0 else 0
        if rate_f < 0:
            alerts.append({"level":"warning","message":f"フォロワー数が減少しています（{delta_f:+,}人 / {rate_f}%）"})
        elif rate_f < 1:
            alerts.append({"level":"warning","message":f"フォロワー増加が停滞しています（変化率: {rate_f}%）"})
        else:
            alerts.append({"level":"ok","message":f"フォロワーは順調に増加しています（+{delta_f:,}人 / +{rate_f}%）"})

    # 閲覧数の減少チェック
    if len(recent) >= 2:
        old_v   = int(recent.iloc[0]["avg_views"])
        new_v   = int(recent.iloc[-1]["avg_views"])
        delta_v = new_v - old_v
        rate_v  = round((delta_v / old_v) * 100, 1) if old_v > 0 else 0
        if rate_v < -10:
            alerts.append({"level":"warning","message":f"閲覧数が大きく減少しています（{delta_v:+,} / {rate_v}%）"})
        elif rate_v < 0:
            alerts.append({"level":"warning","message":f"閲覧数がやや減少傾向です（{delta_v:+,} / {rate_v}%）"})
        else:
            alerts.append({"level":"ok","message":f"閲覧数は安定または増加しています（{delta_v:+,} / {rate_v:+}%）"})

    # フォロワー増加 + 閲覧数減少 = エンゲージメント低下
    if len(recent) >= 2 and delta_f > 0 and delta_v < 0:
        alerts.append({"level":"warning","message":"フォロワーは増加しているが閲覧数は減少しています。エンゲージメント率の低下が疑われます。"})

    # 中期的なトレンド
    if len(df) >= 4:
        mid_views = int(df.iloc[len(df)//2]["avg_views"])
        new_views = int(df.iloc[-1]["avg_views"])
        if new_views < mid_views * 0.7:
            alerts.append({"level":"warning","message":"中期的に閲覧数が30%以上低下しています。別市場へのシフトを検討してください。"})

    return alerts

# ════════════════════════════════════════════════════════
# タブ1: 競合アカウント管理（修正: 登録・編集・更新・削除）
# ════════════════════════════════════════════════════════
with tab_manage:

    # ── 新規登録フォーム ──────────────────────────────────────────────────────
    st.markdown('<div class="section-head">競合アカウントを登録</div>', unsafe_allow_html=True)

    with st.form(key="register_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            new_username = st.text_input("Instagramユーザー名 *", placeholder="例: @tokyo_travel")
            new_region   = st.text_input("発信地",               placeholder="例: 東京, 大阪, 日本")
        with rc2:
            new_genre = st.text_input("ジャンル", placeholder="例: 旅行, グルメ, 日本文化")
            new_note  = st.text_area("メモ", height=68)

        submitted = st.form_submit_button("アカウントを登録する")
        if submitted:
            if not new_username.strip():
                st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("competitor_accounts", {
                    "username":  new_username.strip(),
                    "platform":  "Instagram",
                    "region":    new_region.strip(),
                    "genre":     new_genre.strip(),
                    "note":      new_note.strip(),
                    "is_active": True,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown('<div class="err-box">登録に失敗しました（同じユーザー名が既に存在する可能性があります）</div>', unsafe_allow_html=True)

    # ── 登録済みアカウント一覧・編集・削除 ──────────────────────────────────
    st.markdown('<div class="section-head">登録済みアカウント一覧</div>', unsafe_allow_html=True)

    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">競合アカウントが登録されていません</div>', unsafe_allow_html=True)
    else:
        for _, row in df_acc.iterrows():
            rid    = int(row["id"])
            active = bool(row.get("is_active", True))

            with st.expander(
                f"{'🟢' if active else '⚫'} {row['username']} "
                f"| {row.get('region','') or '地域未設定'} "
                f"| {row.get('genre','') or 'ジャンル未設定'}"
            ):
                # 編集フォーム
                ec1, ec2 = st.columns(2)
                with ec1:
                    edit_username = st.text_input(
                        "ユーザー名",
                        value=row.get("username",""),
                        key=f"edit_uname_{rid}"
                    )
                    edit_region = st.text_input(
                        "発信地",
                        value=row.get("region","") or "",
                        key=f"edit_region_{rid}"
                    )
                with ec2:
                    edit_genre = st.text_input(
                        "ジャンル",
                        value=row.get("genre","") or "",
                        key=f"edit_genre_{rid}"
                    )
                    edit_note = st.text_area(
                        "メモ",
                        value=row.get("note","") or "",
                        height=68,
                        key=f"edit_note_{rid}"
                    )

                # ボタン行
                bc1, bc2, bc3, bc4 = st.columns([2, 2, 2, 2])
                with bc1:
                    if st.button("更新する", key=f"upd_{rid}"):
                        if not edit_username.strip():
                            st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
                        else:
                            ok = sb_update("competitor_accounts", {
                                "username": edit_username.strip(),
                                "region":   edit_region.strip(),
                                "genre":    edit_genre.strip(),
                                "note":     edit_note.strip(),
                            }, {"id": rid})
                            if ok:
                                st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                                st.rerun()
                with bc2:
                    label = "無効化する" if active else "有効化する"
                    if st.button(label, key=f"toggle_{rid}"):
                        sb_update("competitor_accounts", {"is_active": not active}, {"id": rid})
                        st.rerun()
                with bc3:
                    st.markdown(
                        f'<div style="font-size:.8rem;color:{"#15803d" if active else "#9ca3af"};padding-top:.5rem;">'
                        f'{"✅ 有効" if active else "⚫ 無効"}</div>',
                        unsafe_allow_html=True
                    )
                with bc4:
                    if st.button("削除する", key=f"del_{rid}"):
                        sb_delete("competitor_accounts", {"id": rid})
                        st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: データ入力
# ════════════════════════════════════════════════════════
with tab_input:
    st.markdown('<div class="section-head">競合データを入力</div>', unsafe_allow_html=True)
    st.caption("同じアカウント × 日付で再入力すると上書きされます（UPSERT方式）")

    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">先に「競合アカウント管理」タブでアカウントを登録してください</div>', unsafe_allow_html=True)
    else:
        with st.form(key="data_input_form"):
            ic1, ic2 = st.columns(2)
            with ic1:
                sel_account = st.selectbox("アカウントを選択", df_acc["username"].tolist())
                rec_date    = st.date_input("記録日", value=date.today())
            with ic2:
                inp_followers = st.number_input("フォロワー数",           min_value=0, value=0, step=100)
                inp_avg_views = st.number_input("平均閲覧数（リール等）", min_value=0, value=0, step=100)

            dc1, dc2 = st.columns(2)
            with dc1:
                inp_posts = st.number_input("期間内投稿数", min_value=0, value=0, step=1)
            with dc2:
                inp_note = st.text_input("メモ（任意）")

            submitted = st.form_submit_button("データを保存する（上書き対応）")
            if submitted:
                account_id = int(df_acc[df_acc["username"] == sel_account]["id"].values[0])
                res = sb_upsert("competitor_history", {
                    "account_id":    account_id,
                    "recorded_date": str(rec_date),
                    "followers":     inp_followers,
                    "avg_views":     inp_avg_views,
                    "post_count":    inp_posts,
                    "note":          inp_note,
                })
                if res:
                    st.markdown('<div class="success-box">保存しました</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="err-box">保存に失敗しました</div>', unsafe_allow_html=True)

        # 入力履歴一覧
        st.markdown('<div class="section-head">入力済み履歴（直近10件）</div>', unsafe_allow_html=True)
        rows_hist = sb_select("competitor_history", order="-recorded_date")
        df_hist   = to_df(rows_hist)

        if not df_hist.empty and not df_acc.empty:
            # アカウント名を結合
            df_hist = df_hist.merge(
                df_acc[["id","username"]].rename(columns={"id":"account_id"}),
                on="account_id", how="left"
            )
            sel_acc_input = st.selectbox("アカウントで絞り込み", ["全体"] + df_acc["username"].tolist(), key="hist_filter")
            df_show = df_hist if sel_acc_input == "全体" else df_hist[df_hist["username"] == sel_acc_input]

            for col in ["followers","avg_views","post_count"]:
                if col in df_show.columns:
                    df_show[col] = df_show[col].fillna(0).astype(int)

            st.dataframe(
                df_show[["username","recorded_date","followers","avg_views","post_count","note"]]\
                    .rename(columns={
                        "username":"アカウント","recorded_date":"記録日",
                        "followers":"フォロワー数","avg_views":"平均閲覧数",
                        "post_count":"投稿数","note":"メモ"
                    }).head(10),
                use_container_width=True,
                hide_index=True
            )

# ════════════════════════════════════════════════════════
# タブ3: 分析・グラフ
# ════════════════════════════════════════════════════════
with tab_analysis:
    rows_acc      = sb_select("competitor_accounts", order="username")
    df_acc        = to_df(rows_acc)
    rows_hist_all = sb_select("competitor_history", order="recorded_date")
    df_hist_all   = to_df(rows_hist_all)

    if df_acc.empty:
        st.markdown('<div class="info-box">競合アカウントが登録されていません</div>', unsafe_allow_html=True)
        st.stop()

    if df_hist_all.empty:
        st.markdown('<div class="info-box">データがまだありません。「データ入力」タブから入力してください</div>', unsafe_allow_html=True)
        st.stop()

    for col in ["followers","avg_views","post_count"]:
        if col in df_hist_all.columns:
            df_hist_all[col] = pd.to_numeric(df_hist_all[col], errors="coerce").fillna(0)

    sel_account_a = st.selectbox(
        "分析するアカウント",
        ["全アカウント比較"] + df_acc["username"].tolist(),
        key="anal_sel"
    )

    if sel_account_a == "全アカウント比較":
        st.markdown('<div class="section-head">全アカウント 最新データ比較</div>', unsafe_allow_html=True)
        latest_rows = []
        for _, acc in df_acc.iterrows():
            acc_hist = df_hist_all[df_hist_all["account_id"] == acc["id"]]
            if acc_hist.empty: continue
            latest = acc_hist.sort_values("recorded_date").iloc[-1]
            latest_rows.append({
                "アカウント":   acc["username"],
                "地域":        acc.get("region",""),
                "フォロワー数": int(latest["followers"]),
                "平均閲覧数":   int(latest["avg_views"]),
                "記録日":       latest["recorded_date"],
            })
        if latest_rows:
            df_latest = pd.DataFrame(latest_rows)
            st.dataframe(df_latest, use_container_width=True, hide_index=True)
            st.markdown('<div class="section-head">フォロワー数比較</div>', unsafe_allow_html=True)
            st.bar_chart(df_latest.set_index("アカウント")["フォロワー数"])
            st.markdown('<div class="section-head">平均閲覧数比較</div>', unsafe_allow_html=True)
            st.bar_chart(df_latest.set_index("アカウント")["平均閲覧数"])
        else:
            st.markdown('<div class="info-box">データがまだありません</div>', unsafe_allow_html=True)

    else:
        acc_row   = df_acc[df_acc["username"] == sel_account_a].iloc[0]
        acc_id    = int(acc_row["id"])
        df_single = df_hist_all[df_hist_all["account_id"] == acc_id].sort_values("recorded_date")

        if df_single.empty:
            st.markdown('<div class="info-box">このアカウントのデータがありません</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'**地域:** {acc_row.get("region","未設定")} &nbsp; '
                f'**ジャンル:** {acc_row.get("genre","未設定")}'
            )

            latest = df_single.iloc[-1]
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{int(latest["followers"]):,}</div><div class="lbl">フォロワー数（最新）</div></div>
              <div class="metric-card"><div class="val">{int(latest["avg_views"]):,}</div><div class="lbl">平均閲覧数（最新）</div></div>
              <div class="metric-card"><div class="val">{len(df_single)}</div><div class="lbl">記録件数</div></div>
            </div>""", unsafe_allow_html=True)

            st.markdown('<div class="section-head">フォロワー数 推移</div>', unsafe_allow_html=True)
            st.line_chart(df_single.set_index("recorded_date")["followers"])

            st.markdown('<div class="section-head">平均閲覧数 推移</div>', unsafe_allow_html=True)
            st.line_chart(df_single.set_index("recorded_date")["avg_views"])

            st.markdown('<div class="section-head">自動分析コメント</div>', unsafe_allow_html=True)
            alerts = analyze_trend(df_single)
            for alert in alerts:
                if alert["level"] == "warning":
                    st.markdown(f'<div class="err-box">⚠️ {alert["message"]}</div>', unsafe_allow_html=True)
                elif alert["level"] == "ok":
                    st.markdown(f'<div class="success-box">✅ {alert["message"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="info-box">{alert["message"]}</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-head">履歴データ</div>', unsafe_allow_html=True)
            display_hist = df_single[["recorded_date","followers","avg_views","post_count","note"]]\
                .rename(columns={
                    "recorded_date":"記録日","followers":"フォロワー数",
                    "avg_views":"平均閲覧数","post_count":"投稿数","note":"メモ"
                }).sort_values("記録日", ascending=False)
            st.dataframe(display_hist, use_container_width=True, hide_index=True)
