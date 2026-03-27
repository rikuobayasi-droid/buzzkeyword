"""
pages/13_patreon_management.py — Patreonサブスク管理（修正6）
URL: /patreon_management

- purchasesと完全分離
- プランマスタから選択
- MRR（月次売上）計算
- ステータス: end_date IS NULL → 契約中 / NOT NULL → 解約済み
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="Patreon管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">Patreon サブスク管理</div>', unsafe_allow_html=True)

# ── MRR計算ロジック ──────────────────────────────────────────────────────────
def calc_mrr(df_subs: pd.DataFrame, target_month: str) -> int:
    """
    target_month: 'YYYY-MM' 形式
    ロジック:
      - start_date <= target_month の末日
      - end_date IS NULL または end_date >= target_month の初日
    → 上記を満たすサブスクの monthly_price を合計
    """
    if df_subs.empty:
        return 0
    total = 0
    ym_start = f"{target_month}-01"
    # 月末を計算（翌月1日 - 1日）
    y, m  = int(target_month[:4]), int(target_month[5:7])
    if m == 12:
        ym_end = f"{y+1}-01-01"
    else:
        ym_end = f"{y}-{m+1:02d}-01"

    for _, row in df_subs.iterrows():
        s_date  = str(row.get("start_date","") or "")
        e_date  = str(row.get("end_date","") or "")
        price   = int(row.get("monthly_price",0) or 0)
        if not s_date:
            continue
        # start_date が対象月末以前
        if s_date > ym_end:
            continue
        # end_date が NULL か、対象月初日以降
        if e_date and e_date < ym_start:
            continue
        total += price
    return total

def next_billing(start_date_str: str) -> str:
    """start_date + 1ヶ月 を返す"""
    try:
        d = date.fromisoformat(start_date_str[:10])
        d = d + relativedelta(months=1)
        return str(d)
    except Exception:
        return ""

# ── プランマスタ取得 ──────────────────────────────────────────────────────────
def get_plans() -> pd.DataFrame:
    rows = sb_select("patreon_plans", order="price")
    return to_df(rows)

tab_sub, tab_plan, tab_mrr = st.tabs(["サブスク管理", "プランマスタ", "MRR（月次売上）"])

# ════════════════════════════════════════════════════════
# タブ1: サブスク管理
# ════════════════════════════════════════════════════════
with tab_sub:
    # 顧客一覧・プラン一覧取得
    rows_c   = sb_select("customers", order="name")
    df_c     = to_df(rows_c)
    df_plans = get_plans()

    if df_c.empty:
        st.markdown('<div class="info-box">顧客データがありません。顧客管理ページから先に登録してください。</div>', unsafe_allow_html=True)
    elif df_plans.empty:
        st.markdown('<div class="info-box">プランマスタがありません。「プランマスタ」タブから先に登録してください。</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-head">サブスクを登録</div>', unsafe_allow_html=True)

        with st.form("sub_form"):
            sc1, sc2 = st.columns(2)
            with sc1:
                sel_cust    = st.selectbox("顧客", df_c["name"].tolist(), key="sub_cust")
                plan_names  = df_plans["plan_name"].tolist()
                sel_plan    = st.selectbox("プラン", plan_names, key="sub_plan")
                start_date  = st.date_input("開始日", value=date.today(), key="sub_start")
            with sc2:
                # プランの価格を自動表示
                plan_row    = df_plans[df_plans["plan_name"] == sel_plan]
                default_price = int(plan_row.iloc[0]["price"]) if not plan_row.empty else 0
                monthly_price = st.number_input("月額（¥）", min_value=0, value=default_price, step=100, key="sub_price")
                payment_method = st.selectbox("支払方法", ["クレジットカード","PayPal","銀行振込","その他"], key="sub_pay")
                sub_note = st.text_input("備考", key="sub_note")

            submitted = st.form_submit_button("登録する")
            if submitted:
                cust_id = int(df_c[df_c["name"] == sel_cust]["id"].values[0])
                plan_id = int(plan_row.iloc[0]["id"]) if not plan_row.empty else None
                next_b  = next_billing(str(start_date))
                res = sb_insert("patreon_subscriptions", {
                    "customer_id":       cust_id,
                    "plan_id":           plan_id,
                    "plan_name":         sel_plan,
                    "monthly_price":     monthly_price,
                    "start_date":        str(start_date),
                    "next_billing_date": next_b,
                    "end_date":          None,
                    "payment_method":    payment_method,
                    "note":              sub_note,
                })
                if res:
                    st.success("登録しました")
                    st.rerun()
                else:
                    st.error("登録に失敗しました")

    # サブスク一覧
    st.markdown('<div class="section-head">サブスク一覧</div>', unsafe_allow_html=True)
    rows_s  = sb_select("patreon_subscriptions", order="-start_date")
    df_subs = to_df(rows_s)

    if df_subs.empty:
        st.markdown('<div class="info-box">サブスクデータがありません</div>', unsafe_allow_html=True)
    else:
        # 顧客名を結合
        rows_c  = sb_select("customers", order="name")
        df_c    = to_df(rows_c)
        if not df_c.empty:
            df_subs = df_subs.merge(
                df_c[["id","name"]].rename(columns={"id":"customer_id","name":"cust_name"}),
                on="customer_id", how="left"
            )
        else:
            df_subs["cust_name"] = "不明"

        # ステータス判定: end_date IS NULL → 契約中
        df_subs["status"] = df_subs["end_date"].apply(
            lambda x: "契約中" if (x is None or str(x) == "" or str(x) == "None") else "解約済み"
        )

        # フィルター
        f_status = st.radio("表示", ["すべて","契約中のみ","解約済みのみ"], horizontal=True)
        df_show  = df_subs.copy()
        if f_status == "契約中のみ":   df_show = df_show[df_show["status"] == "契約中"]
        elif f_status == "解約済みのみ": df_show = df_show[df_show["status"] == "解約済み"]

        active_count = len(df_subs[df_subs["status"] == "契約中"])
        active_mrr   = int(df_subs[df_subs["status"] == "契約中"]["monthly_price"].sum())
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">{active_count}</div><div class="lbl">契約中</div></div>
          <div class="metric-card"><div class="val">¥{active_mrr:,}</div><div class="lbl">現在MRR</div></div>
          <div class="metric-card"><div class="val">{len(df_subs)}</div><div class="lbl">総契約数</div></div>
        </div>""", unsafe_allow_html=True)

        for _, row in df_show.iterrows():
            sid     = int(row["id"])
            status  = row["status"]
            s_color = "#15803d" if status == "契約中" else "#9ca3af"

            with st.expander(
                f"{row.get('cust_name','')}  {row.get('plan_name','')}  "
                f"¥{int(row.get('monthly_price',0)):,}/月  "
                f"[{status}]"
            ):
                ec1, ec2 = st.columns(2)
                with ec1:
                    st.markdown(f"**顧客:** {row.get('cust_name','')}")
                    st.markdown(f"**プラン:** {row.get('plan_name','')}")
                    st.markdown(f"**月額:** ¥{int(row.get('monthly_price',0)):,}")
                    st.markdown(f"**支払方法:** {row.get('payment_method','')}")
                with ec2:
                    st.markdown(f"**開始日:** {row.get('start_date','')}")
                    st.markdown(f"**次回請求日:** {row.get('next_billing_date','')}")
                    st.markdown(
                        f"**ステータス:** <span style='color:{s_color};font-weight:600;'>{status}</span>",
                        unsafe_allow_html=True
                    )
                    if row.get("end_date"):
                        st.markdown(f"**解約日:** {row.get('end_date','')}")

                # 解約処理
                if status == "契約中":
                    end_d = st.date_input("解約日を設定", value=date.today(), key=f"end_{sid}")
                    if st.button("解約する", key=f"cancel_{sid}"):
                        sb_update("patreon_subscriptions", {"end_date": str(end_d)}, {"id": sid})
                        st.rerun()
                else:
                    if st.button("契約を再開する", key=f"reopen_{sid}"):
                        nb = next_billing(str(date.today()))
                        sb_update("patreon_subscriptions", {
                            "end_date":          None,
                            "start_date":        str(date.today()),
                            "next_billing_date": nb,
                        }, {"id": sid})
                        st.rerun()

                if st.button("削除", key=f"sub_del_{sid}"):
                    sb_delete("patreon_subscriptions", {"id": sid})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: プランマスタ
# ════════════════════════════════════════════════════════
with tab_plan:
    st.markdown('<div class="section-head">プランを登録</div>', unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns([3,2,1])
    with pc1:
        new_plan_name = st.text_input("プラン名", placeholder="例: Basic ($5)", key="plan_new_name")
    with pc2:
        new_plan_price = st.number_input("月額（¥）", min_value=0, value=0, step=100, key="plan_new_price")
    with pc3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("追加", key="plan_add"):
            if new_plan_name:
                res = sb_insert("patreon_plans", {"plan_name": new_plan_name, "price": new_plan_price})
                if res:
                    st.rerun()

    st.markdown('<div class="section-head">プラン一覧</div>', unsafe_allow_html=True)
    df_plans = get_plans()
    if df_plans.empty:
        st.markdown('<div class="info-box">プランがありません</div>', unsafe_allow_html=True)
    else:
        for _, row in df_plans.iterrows():
            pid = int(row["id"])
            lc1, lc2, lc3, lc4 = st.columns([3,2,1,1])
            with lc1:
                e_name = st.text_input("プラン名", value=row["plan_name"], key=f"plan_name_{pid}", label_visibility="collapsed")
            with lc2:
                e_price = st.number_input("月額（¥）", value=int(row["price"]), step=100, key=f"plan_price_{pid}", label_visibility="collapsed")
            with lc3:
                if st.button("更新", key=f"plan_upd_{pid}"):
                    sb_update("patreon_plans", {"plan_name": e_name, "price": e_price}, {"id": pid})
                    st.rerun()
            with lc4:
                if st.button("削除", key=f"plan_del_{pid}"):
                    sb_delete("patreon_plans", {"id": pid})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ3: MRR（月次売上）
# ════════════════════════════════════════════════════════
with tab_mrr:
    st.markdown('<div class="section-head">MRR（月次経常収益）</div>', unsafe_allow_html=True)
    st.caption("ロジック: 各月について、start_date以降かつend_dateがない（または end_date以前）のサブスクを合計します")

    rows_s  = sb_select("patreon_subscriptions", order="start_date")
    df_subs = to_df(rows_s)

    if df_subs.empty:
        st.markdown('<div class="info-box">サブスクデータがありません</div>', unsafe_allow_html=True)
    else:
        # 集計する月の範囲を決定（最古のstart_dateから今月まで）
        min_date_str = df_subs["start_date"].min()
        try:
            min_date = date.fromisoformat(str(min_date_str)[:10])
        except Exception:
            min_date = date.today().replace(day=1)

        today = date.today()
        months = []
        cur = min_date.replace(day=1)
        while cur <= today.replace(day=1):
            months.append(cur.strftime("%Y-%m"))
            cur = (cur + relativedelta(months=1))

        # 月別MRR計算
        mrr_data = []
        for ym in months:
            mrr = calc_mrr(df_subs, ym)
            mrr_data.append({"月": ym, "MRR（¥）": mrr})

        df_mrr = pd.DataFrame(mrr_data)

        # 現在月のMRR
        current_mrr = calc_mrr(df_subs, today.strftime("%Y-%m"))
        prev_month  = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        prev_mrr    = calc_mrr(df_subs, prev_month)
        delta_mrr   = current_mrr - prev_mrr
        delta_color = "#15803d" if delta_mrr >= 0 else "#dc2626"

        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">¥{current_mrr:,}</div><div class="lbl">今月MRR</div></div>
          <div class="metric-card"><div class="val" style="color:{delta_color};">¥{delta_mrr:+,}</div><div class="lbl">先月比</div></div>
          <div class="metric-card"><div class="val">¥{prev_mrr:,}</div><div class="lbl">先月MRR</div></div>
        </div>""", unsafe_allow_html=True)

        # MRR推移グラフ
        st.markdown('<div class="section-head">MRR月別推移</div>', unsafe_allow_html=True)
        st.line_chart(df_mrr.set_index("月")["MRR（¥）"])

        # テーブル
        st.dataframe(df_mrr.sort_values("月", ascending=False), use_container_width=True)

        # プラン別内訳（現在月）
        st.markdown('<div class="section-head">現在月のプラン別内訳</div>', unsafe_allow_html=True)
        active_subs = df_subs[
            (df_subs["start_date"] <= today.strftime("%Y-%m-%d")) &
            (df_subs["end_date"].isna() | (df_subs["end_date"] == "") | (df_subs["end_date"] == "None"))
        ]
        if not active_subs.empty:
            plan_breakdown = active_subs.groupby("plan_name").agg(
                件数=("id","count"),
                合計MRR=("monthly_price","sum")
            ).reset_index()
            plan_breakdown["合計MRR"] = plan_breakdown["合計MRR"].apply(lambda x: f"¥{int(x):,}")
            st.dataframe(plan_breakdown, use_container_width=True)
