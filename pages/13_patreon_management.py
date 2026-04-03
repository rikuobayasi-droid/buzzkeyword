"""
pages/13_patreon_management.py — Patreon管理（完全書き直し版）

ステータス判定:
  end_date が NULL / None / NaT / "" / "null" / "None" → 契約中
  それ以外（日付文字列）→ 解約済み
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from calendar import monthrange
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_update, sb_delete, get_client

st.set_page_config(page_title="Patreon管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">Patreon管理</div>', unsafe_allow_html=True)

# ── ヘルパー ──────────────────────────────────────────────────────────────────
def next_billing(start_str: str) -> str:
    try:
        d = date.fromisoformat(str(start_str)[:10])
        if d.month == 12:
            return str(d.replace(year=d.year+1, month=1))
        return str(d.replace(month=d.month+1))
    except Exception:
        return str(date.today() + timedelta(days=30))

def is_active(end_date_val) -> bool:
    """end_date が NULL/空 → 契約中（True）"""
    if end_date_val is None:
        return True
    try:
        if pd.isna(end_date_val):
            return True
    except Exception:
        pass
    s = str(end_date_val).strip().lower()
    return s in ("", "none", "null", "nat", "nan")

def calc_mrr(df_subs: pd.DataFrame, year_month: str) -> int:
    """指定月に契約中のサブスクのMRRを計算"""
    if df_subs.empty:
        return 0
    try:
        y, m  = int(year_month[:4]), int(year_month[5:7])
        m_end = f"{year_month}-{monthrange(y,m)[1]:02d}"
        m_start = f"{year_month}-01"
    except Exception:
        return 0
    total = 0
    for _, row in df_subs.iterrows():
        s = str(row.get("start_date","") or "")[:10]
        e = row.get("end_date")
        e_str = "" if is_active(e) else str(e)[:10]
        if not s or s > m_end:
            continue
        if e_str and e_str < m_start:
            continue
        try:
            total += int(row.get("monthly_price", 0) or 0)
        except Exception:
            pass
    return total

# ── データ取得 ────────────────────────────────────────────────────────────────
def load_data():
    df_subs  = to_df(sb_select("patreon_subscriptions", order="-start_date"))
    df_custs = to_df(sb_select("customers", order="name"))
    df_plans = to_df(sb_select("patreon_plans", order="name"))
    return df_subs, df_custs, df_plans

tab_sub, tab_plan, tab_mrr = st.tabs(["サブスク管理", "プランマスタ", "MRR分析"])

# ════════════════════════════════════════════════════════
# タブ1: サブスク管理
# ════════════════════════════════════════════════════════
with tab_sub:
    df_subs, df_custs, df_plans = load_data()

    # ── 新規登録 ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">新規サブスク登録</div>', unsafe_allow_html=True)

    if df_custs.empty:
        st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
    else:
        plan_names    = df_plans["name"].tolist() if not df_plans.empty else ["Basic ($5)"]
        customer_names = df_custs["name"].tolist()

        with st.form(key="new_sub_form"):
            nc1, nc2 = st.columns(2)
            with nc1:
                sel_cust   = st.selectbox("顧客を選択 *", customer_names)
                start_date = st.date_input("開始日", value=date.today())
                payment_method = st.selectbox("支払方法", ["クレジットカード","PayPal","銀行振込","その他"])
            with nc2:
                sel_plan = st.selectbox("プランを選択 *", plan_names)
                plan_row = df_plans[df_plans["name"] == sel_plan] if not df_plans.empty else pd.DataFrame()
                default_price = int(plan_row.iloc[0]["price"]) if not plan_row.empty and "price" in plan_row.columns else 750
                monthly_price = st.number_input("月額（¥）", min_value=0, value=default_price, step=100)
                sub_note = st.text_input("備考")

            if st.form_submit_button("登録する"):
                cust_id = int(df_custs[df_custs["name"] == sel_cust]["id"].values[0])
                plan_id = int(plan_row.iloc[0]["id"]) if not plan_row.empty else None
                res = sb_insert("patreon_subscriptions", {
                    "customer_id":       cust_id,
                    "plan_id":           plan_id,
                    "plan_name":         sel_plan,
                    "monthly_price":     monthly_price,
                    "start_date":        str(start_date),
                    "next_billing_date": next_billing(str(start_date)),
                    "end_date":          None,
                    "payment_method":    payment_method,
                    "note":              sub_note or None,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown('<div class="err-box">登録に失敗しました</div>', unsafe_allow_html=True)

    # ── サブスク一覧 ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">サブスク一覧</div>', unsafe_allow_html=True)

    # 毎回最新データを取得
    df_subs, df_custs, df_plans = load_data()

    if df_subs.empty:
        st.markdown('<div class="info-box">サブスクデータがありません</div>', unsafe_allow_html=True)
    else:
        # 顧客名を結合
        if not df_custs.empty:
            df_subs = df_subs.merge(
                df_custs[["id","name"]].rename(columns={"id":"customer_id","name":"cust_name"}),
                on="customer_id", how="left"
            )
        else:
            df_subs["cust_name"] = "不明"

        # ステータス判定（is_active関数を使用）
        df_subs["status"] = df_subs["end_date"].apply(
            lambda x: "契約中" if is_active(x) else "解約済み"
        )

        # メトリクス
        active_df    = df_subs[df_subs["status"] == "契約中"]
        active_count = len(active_df)
        active_mrr   = int(active_df["monthly_price"].fillna(0).sum())
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{active_count}</div><div class="lbl">契約中</div></div>
          <div class="metric-card"><div class="val">¥{active_mrr:,}</div><div class="lbl">現在MRR</div></div>
          <div class="metric-card"><div class="val">{len(df_subs)}</div><div class="lbl">総件数</div></div>
        </div>""", unsafe_allow_html=True)

        # フィルター
        f_status = st.radio("表示", ["すべて","契約中のみ","解約済みのみ"], horizontal=True, key="sub_filter")
        if f_status == "契約中のみ":
            df_show = df_subs[df_subs["status"] == "契約中"].copy()
        elif f_status == "解約済みのみ":
            df_show = df_subs[df_subs["status"] == "解約済み"].copy()
        else:
            df_show = df_subs.copy()

        st.caption(f"{len(df_show)}件")

        # 一覧表示
        for _, row in df_show.iterrows():
            sid     = int(row["id"])
            status  = row["status"]
            s_color = "#15803d" if status == "契約中" else "#9ca3af"
            icon    = "🟢" if status == "契約中" else "⚫"
            end_val = row.get("end_date")

            with st.expander(
                f"{icon} {row.get('cust_name','')} | {row.get('plan_name','')} | "
                f"¥{int(row.get('monthly_price',0) or 0):,}/月 | {status}"
            ):
                # 情報表示
                ic1, ic2 = st.columns(2)
                with ic1:
                    st.markdown(f"**顧客:** {row.get('cust_name','')}")
                    st.markdown(f"**プラン:** {row.get('plan_name','')}")
                    st.markdown(f"**月額:** ¥{int(row.get('monthly_price',0) or 0):,}")
                    st.markdown(f"**支払方法:** {row.get('payment_method','')}")
                with ic2:
                    st.markdown(f"**開始日:** {str(row.get('start_date',''))[:10]}")
                    st.markdown(f"**次回請求日:** {str(row.get('next_billing_date',''))[:10]}")
                    st.markdown(
                        f"**ステータス:** <span style='color:{s_color};font-weight:700;'>{status}</span>",
                        unsafe_allow_html=True
                    )
                    if not is_active(end_val):
                        st.markdown(f"**解約日:** {str(end_val)[:10]}")

                st.markdown("---")

                # 編集フォーム
                with st.form(key=f"edit_{sid}"):
                    ef1, ef2 = st.columns(2)
                    with ef1:
                        e_price = st.number_input("月額（¥）", min_value=0,
                            value=int(row.get("monthly_price",0) or 0), step=100, key=f"ep_{sid}")
                        try:
                            s_default = date.fromisoformat(str(row.get("start_date",""))[:10])
                        except Exception:
                            s_default = date.today()
                        e_start = st.date_input("開始日", value=s_default, key=f"es_{sid}")
                        e_pay   = st.selectbox("支払方法",
                            ["クレジットカード","PayPal","銀行振込","その他"],
                            index=["クレジットカード","PayPal","銀行振込","その他"].index(
                                row.get("payment_method","クレジットカード")
                            ) if row.get("payment_method") in ["クレジットカード","PayPal","銀行振込","その他"] else 0,
                            key=f"epy_{sid}")
                    with ef2:
                        e_status = st.radio("ステータス", ["契約中","解約済み"],
                            index=0 if status == "契約中" else 1,
                            horizontal=True, key=f"est_{sid}")
                        if e_status == "解約済み":
                            try:
                                e_end_default = date.fromisoformat(str(end_val)[:10]) if not is_active(end_val) else date.today()
                            except Exception:
                                e_end_default = date.today()
                            e_end = st.date_input("解約日", value=e_end_default, key=f"ee_{sid}")
                            end_date_save = str(e_end)
                        else:
                            end_date_save = None  # 契約中 → NULLを明示

                    if st.form_submit_button("更新する"):
                        try:
                            get_client().table("patreon_subscriptions").update({
                                "monthly_price":     e_price,
                                "start_date":        str(e_start),
                                "next_billing_date": next_billing(str(e_start)),
                                "payment_method":    e_pay,
                                "end_date":          end_date_save,
                            }).eq("id", sid).execute()
                            st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True)
                            st.rerun()
                        except Exception as e:
                            st.markdown(f'<div class="err-box">❌ 更新失敗: {e}</div>', unsafe_allow_html=True)

                # 削除
                if st.button("🗑️ 削除", key=f"del_{sid}"):
                    sb_delete("patreon_subscriptions", {"id": sid})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: プランマスタ
# ════════════════════════════════════════════════════════
with tab_plan:
    st.markdown('<div class="section-head">プランを登録</div>', unsafe_allow_html=True)
    _, df_custs, df_plans = load_data()

    with st.form(key="new_plan_form"):
        pc1, pc2, pc3 = st.columns([3,2,1])
        with pc1: p_name  = st.text_input("プラン名 *", placeholder="例: Basic ($5)")
        with pc2: p_price = st.number_input("月額（¥）", min_value=0, value=750, step=100)
        with pc3: p_note  = st.text_input("備考")
        if st.form_submit_button("登録する"):
            if not p_name:
                st.markdown('<div class="err-box">プラン名は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("patreon_plans", {"name": p_name, "price": p_price, "note": p_note or None})
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.rerun()

    st.markdown('<div class="section-head">登録済みプラン</div>', unsafe_allow_html=True)
    if df_plans.empty:
        st.markdown('<div class="info-box">プランがありません</div>', unsafe_allow_html=True)
    else:
        for _, row in df_plans.iterrows():
            c1, c2, c3 = st.columns([4, 2, 1])
            with c1: st.markdown(f"**{row['name']}**")
            with c2: st.caption(f"¥{int(row.get('price',0)):,}/月")
            with c3:
                if st.button("削除", key=f"plan_del_{row['id']}"):
                    sb_delete("patreon_plans", {"id": int(row["id"])})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ3: MRR分析
# ════════════════════════════════════════════════════════
with tab_mrr:
    st.markdown('<div class="section-head">月別MRR推移</div>', unsafe_allow_html=True)
    st.caption("各月に契約中のサブスクのMRRを計算します")

    df_subs, _, _ = load_data()

    if df_subs.empty:
        st.markdown('<div class="info-box">データがありません</div>', unsafe_allow_html=True)
    else:
        # 表示月数を選択
        n_months = st.slider("表示月数", min_value=3, max_value=24, value=12, step=1)

        # 月リストを生成（過去n_months月）
        months = []
        d = date.today().replace(day=1)
        for _ in range(n_months):
            months.append(d.strftime("%Y-%m"))
            if d.month == 1:
                d = d.replace(year=d.year-1, month=12)
            else:
                d = d.replace(month=d.month-1)
        months = list(reversed(months))

        # 各月のMRRを計算
        mrr_data = []
        for ym in months:
            mrr = calc_mrr(df_subs, ym)
            mrr_data.append({"月": ym, "MRR(¥)": mrr})

        df_mrr = pd.DataFrame(mrr_data)
        if not df_mrr.empty and df_mrr["MRR(¥)"].sum() > 0:
            st.line_chart(df_mrr.set_index("月")["MRR(¥)"])
            st.dataframe(df_mrr, use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="info-box">MRRデータがありません。サブスクを登録してください。</div>', unsafe_allow_html=True)

        # 現在の契約中サブスク一覧
        st.markdown('<div class="section-head">現在の契約中サブスク</div>', unsafe_allow_html=True)
        df_subs["is_active_flag"] = df_subs["end_date"].apply(is_active)
        df_active = df_subs[df_subs["is_active_flag"]].copy()

        if not df_active.empty and not df_custs.empty:
            df_active = df_active.merge(
                df_custs[["id","name"]].rename(columns={"id":"customer_id","name":"顧客名"}),
                on="customer_id", how="left"
            )
            st.dataframe(
                df_active[["顧客名","plan_name","monthly_price","start_date"]].rename(columns={
                    "plan_name":"プラン","monthly_price":"月額(¥)","start_date":"開始日"
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown(f"**契約中合計MRR: ¥{int(df_active['monthly_price'].fillna(0).sum()):,}**")
        else:
            st.markdown('<div class="info-box">契約中のサブスクがありません</div>', unsafe_allow_html=True)
