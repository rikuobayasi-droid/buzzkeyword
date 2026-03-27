"""
pages/12_competitor_analysis.py — 競合分析
URL: /competitor_analysis

機能:
- 競合Instagramアカウント登録・管理
- データ（フォロワー数・閲覧数）の時系列保存
- 推移グラフ表示
- ルールベースの分析コメント（AI不要）
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
def analyze_trend(df_hist: pd.DataFrame) -> list[dict]:
    """
    フォロワー数・閲覧数の推移から傾向を判定するルールベース分析。
    引数: 単一アカウントの履歴DataFrame（date昇順）
    返値: [{level: 'warning'|'ok'|'info', message: str}]
    """
    alerts = []
    if df_hist.empty or len(df_hist) < 2:
        alerts.append({"level":"info","message":"データが2件以上になると傾向分析が可能になります"})
        return alerts

    df = df_hist.sort_values("recorded_date")

    # ── フォロワー増加の停滞チェック ──────────────────────────────────────────
    # 直近3件のフォロワー変化率を計算
    recent = df.tail(3)
    if len(recent) >= 2:
        old_f   = int(recent.iloc[0]["followers"])
        new_f   = int(recent.iloc[-1]["followers"])
        delta_f = new_f - old_f
        rate_f  = round((delta_f / old_f) * 100, 1) if old_f > 0 else 0
        if rate_f < 0:
            alerts.append({"level":"warning","message":f"フォロワー数が減少しています（{delta_f:+,}人 / {rate_f}%）。コンテンツ戦略の見直しを検討してください。"})
        elif rate_f < 1:
            alerts.append({"level":"warning","message":f"フォロワー増加が停滞しています（変化率: {rate_f}%）。新しい発信フォーマットの検討を推奨します。"})
        else:
            alerts.append({"level":"ok","message":f"フォロワーは順調に増加しています（+{delta_f:,}人 / +{rate_f}%）"})

    # ── 閲覧数の減少チェック ──────────────────────────────────────────────────
    if len(recent) >= 2:
        old_v   = int(recent.iloc[0]["avg_views"])
        new_v   = int(recent.iloc[-1]["avg_views"])
        delta_v = new_v - old_v
        rate_v  = round((delta_v / old_v) * 100, 1) if old_v > 0 else 0
        if rate_v < -10:
            alerts.append({"level":"warning","message":f"閲覧数が大きく減少しています（{delta_v:+,} / {rate_v}%）。トレンドの変化または投稿頻度の低下が考えられます。"})
        elif rate_v < 0:
            alerts.append({"level":"warning","message":f"閲覧数がやや減少傾向です（{delta_v:+,} / {rate_v}%）。コンテンツの見直しを検討してください。"})
        else:
            alerts.append({"level":"ok","message":f"閲覧数は安定または増加しています（{delta_v:+,} / {rate_v:+}%）"})

    # ── フォロワーと閲覧数の乖離チェック ─────────────────────────────────────
    # フォロワーが増えているのに閲覧数が減っている = エンゲージメント低下
    if len(recent) >= 2:
        if delta_f > 0 and delta_v < 0:
            alerts.append({"level":"warning","message":"フォロワーは増加しているが閲覧数は減少しています。エンゲージメント率の低下が疑われます。コンテンツの質またはアルゴリズムの変化を確認してください。"})

    # ── 全体的なトレンド判定 ──────────────────────────────────────────────────
    if len(df) >= 4:
        mid_views = int(df.iloc[len(df)//2]["avg_views"])
        new_views = int(df.iloc[-1]["avg_views"])
        if new_views < mid_views * 0.7:
            alerts.append({"level":"warning","message":"中期的に閲覧数が30%以上低下しています。このカテゴリのコンテンツへの市場需要が変化している可能性があります。別市場や新しいテーマへのシフトを検討してください。"})

    return alerts

# ════════════════════════════════════════════════════════
# タブ1: 競合アカウント管理
# ════════════════════════════════════════════════════════
with tab_manage:
    st.markdown('<div class="section-head">競合アカウントを登録</div>', unsafe_allow_html=True)

    mc1, mc2 = st.columns(2)
    with mc1:
        new_username = st.text_input("Instagramユーザー名", placeholder="例: @tokyo_travel")
        new_region   = st.text_input("発信地", placeholder="例: 東京, 大阪, 日本")
    with mc2:
        new_genre = st.text_input("ジャンル", placeholder="例: 旅行, グルメ, 日本文化")
        new_note  = st.text_area("メモ", height=60)

    if st.button("アカウントを登録する"):
        if not new_username:
            st.markdown('<div class="err-box">ユーザー名は必須です</div>', unsafe_allow_html=True)
        else:
            res = sb_insert("competitor_accounts", {
                "username": new_username,
                "platform": "Instagram",
                "region":   new_region,
                "genre":    new_genre,
                "note":     new_note,
                "is_active": True,
            })
            if res:
                st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                st.rerun()
            else:
                st.markdown('<div class="err-box">登録に失敗しました（重複の可能性があります）</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-head">登録済みアカウント一覧</div>', unsafe_allow_html=True)
    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">競合アカウントが登録されていません</div>', unsafe_allow_html=True)
    else:
        for _, row in df_acc.iterrows():
            lc1, lc2, lc3, lc4, lc5 = st.columns([3, 2, 2, 1.5, 0.8])
            with lc1:
                st.markdown(f"**{row['username']}**")
            with lc2:
                st.caption(f"地域: {row.get('region','') or '未設定'}")
            with lc3:
                st.caption(f"ジャンル: {row.get('genre','') or '未設定'}")
            with lc4:
                active = row.get("is_active", True)
                status_label = "有効" if active else "無効"
                if st.button(f"{'無効化' if active else '有効化'}", key=f"toggle_{row['id']}"):
                    sb_update("competitor_accounts", {"is_active": not active}, {"id": row["id"]})
                    st.rerun()
            with lc5:
                if st.button("削除", key=f"acc_del_{row['id']}"):
                    sb_delete("competitor_accounts", {"id": row["id"]})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: データ入力（時系列履歴として保存）
# ════════════════════════════════════════════════════════
with tab_input:
    st.markdown('<div class="section-head">競合データを入力</div>', unsafe_allow_html=True)
    st.caption("同じアカウント × 日付で再入力すると上書きされます（UPSERT方式）")

    rows_acc = sb_select("competitor_accounts", order="username")
    df_acc   = to_df(rows_acc)

    if df_acc.empty:
        st.markdown('<div class="info-box">先に「競合アカウント管理」タブでアカウントを登録してください</div>', unsafe_allow_html=True)
    else:
        ic1, ic2 = st.columns(2)
        with ic1:
            sel_account = st.selectbox("アカウントを選択", df_acc["username"].tolist())
            account_id  = int(df_acc[df_acc["username"] == sel_account]["id"].values[0])
        with ic2:
            rec_date = st.date_input("記録日", value=date.today())

        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            inp_followers = st.number_input(
                "フォロワー数",
                min_value=0, value=0, step=100
            )
        with dc2:
            inp_avg_views = st.number_input(
                "平均閲覧数（リール等）",
                min_value=0, value=0, step=100
            )
        with dc3:
            inp_posts = st.number_input(
                "期間内投稿数",
                min_value=0, value=0, step=1
            )
        inp_note = st.text_input("メモ（任意）")

        # 既存データを読み込んで表示
        rows_hist = sb_select("competitor_history")
        df_hist_all = to_df(rows_hist)
        if not df_hist_all.empty:
            existing = df_hist_all[
                (df_hist_all["account_id"] == account_id) &
                (df_hist_all["recorded_date"] == str(rec_date))
            ]
            if not existing.empty:
                ex = existing.iloc[0]
                st.markdown(
                    f'<div class="info-box">この日付のデータが既に存在します — '
                    f'フォロワー: {int(ex["followers"]):,} / '
                    f'閲覧数: {int(ex["avg_views"]):,} → 上書き保存されます</div>',
                    unsafe_allow_html=True
                )

        if st.button("データを保存する（上書き対応）", key="hist_save"):
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

        # 入力履歴一覧
        st.markdown('<div class="section-head">入力済み履歴（直近10件）</div>', unsafe_allow_html=True)
        if not df_hist_all.empty:
            acc_hist = df_hist_all[df_hist_all["account_id"] == account_id].sort_values("recorded_date", ascending=False).head(10)
            if not acc_hist.empty:
                for col in ["followers","avg_views","post_count"]:
                    if col in acc_hist.columns:
                        acc_hist[col] = acc_hist[col].fillna(0).astype(int)
                st.dataframe(
                    acc_hist[["recorded_date","followers","avg_views","post_count","note"]].rename(columns={
                        "recorded_date":"記録日","followers":"フォロワー数",
                        "avg_views":"平均閲覧数","post_count":"投稿数","note":"メモ"
                    }),
                    use_container_width=True
                )

# ════════════════════════════════════════════════════════
# タブ3: 分析・グラフ
# ════════════════════════════════════════════════════════
with tab_analysis:
    rows_acc     = sb_select("competitor_accounts", order="username")
    df_acc       = to_df(rows_acc)
    rows_hist_all = sb_select("competitor_history", order="recorded_date")
    df_hist_all  = to_df(rows_hist_all)

    if df_acc.empty:
        st.markdown('<div class="info-box">競合アカウントが登録されていません</div>', unsafe_allow_html=True)
        st.stop()

    if df_hist_all.empty:
        st.markdown('<div class="info-box">データがまだありません。「データ入力」タブから入力してください</div>', unsafe_allow_html=True)
        st.stop()

    # 数値型に変換
    for col in ["followers","avg_views","post_count"]:
        if col in df_hist_all.columns:
            df_hist_all[col] = pd.to_numeric(df_hist_all[col], errors="coerce").fillna(0)

    # ── アカウント選択 ─────────────────────────────────────────────────────────
    sel_account_a = st.selectbox("分析するアカウント", ["全アカウント比較"] + df_acc["username"].tolist(), key="anal_sel")

    if sel_account_a == "全アカウント比較":
        # 全アカウントの最新データを比較
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
            st.dataframe(df_latest, use_container_width=True)

            # 全アカウントのフォロワー比較棒グラフ
            st.markdown('<div class="section-head">フォロワー数比較</div>', unsafe_allow_html=True)
            st.bar_chart(df_latest.set_index("アカウント")["フォロワー数"])
            st.markdown('<div class="section-head">平均閲覧数比較</div>', unsafe_allow_html=True)
            st.bar_chart(df_latest.set_index("アカウント")["平均閲覧数"])

    else:
        # 単一アカウント詳細分析
        acc_row  = df_acc[df_acc["username"] == sel_account_a].iloc[0]
        acc_id   = int(acc_row["id"])
        df_single = df_hist_all[df_hist_all["account_id"] == acc_id].sort_values("recorded_date")

        if df_single.empty:
            st.markdown('<div class="info-box">このアカウントのデータがありません</div>', unsafe_allow_html=True)
        else:
            # アカウント情報
            st.markdown(
                f'**地域:** {acc_row.get("region","未設定")} &nbsp; '
                f'**ジャンル:** {acc_row.get("genre","未設定")} &nbsp; '
                f'**登録日:** {str(acc_row.get("created_at",""))[:10]}'
            )

            # ── 最新値 ────────────────────────────────────────────────────────
            latest = df_single.iloc[-1]
            st.markdown(f"""<div class="metric-row">
              <div class="metric-card"><div class="val">{int(latest["followers"]):,}</div><div class="lbl">フォロワー数（最新）</div></div>
              <div class="metric-card"><div class="val">{int(latest["avg_views"]):,}</div><div class="lbl">平均閲覧数（最新）</div></div>
              <div class="metric-card"><div class="val">{len(df_single)}</div><div class="lbl">記録件数</div></div>
            </div>""", unsafe_allow_html=True)

            # ── 推移グラフ ────────────────────────────────────────────────────
            st.markdown('<div class="section-head">フォロワー数 推移</div>', unsafe_allow_html=True)
            st.line_chart(df_single.set_index("recorded_date")["followers"])

            st.markdown('<div class="section-head">平均閲覧数 推移</div>', unsafe_allow_html=True)
            st.line_chart(df_single.set_index("recorded_date")["avg_views"])

            # ── ルールベース分析コメント ──────────────────────────────────────
            st.markdown('<div class="section-head">自動分析コメント</div>', unsafe_allow_html=True)
            alerts = analyze_trend(df_single)
            for alert in alerts:
                if alert["level"] == "warning":
                    st.markdown(f'<div class="err-box">注意: {alert["message"]}</div>', unsafe_allow_html=True)
                elif alert["level"] == "ok":
                    st.markdown(f'<div class="success-box">{alert["message"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="info-box">{alert["message"]}</div>', unsafe_allow_html=True)

            # ── 履歴テーブル ──────────────────────────────────────────────────
            st.markdown('<div class="section-head">履歴データ</div>', unsafe_allow_html=True)
            display_hist = df_single[["recorded_date","followers","avg_views","post_count","note"]].rename(columns={
                "recorded_date":"記録日","followers":"フォロワー数",
                "avg_views":"平均閲覧数","post_count":"投稿数","note":"メモ"
            }).sort_values("記録日", ascending=False)
            st.dataframe(display_hist, use_container_width=True)
