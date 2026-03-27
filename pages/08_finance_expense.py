"""
pages/08_finance_expense.py — 経費管理
URL: /finance_expense

改修内容:
- 経費一覧表示
- 年・日で検索可能
- 絵文字を削除
"""
import streamlit as st
import base64
from datetime import date
from common import inject_css, setup_sidebar, to_df, ACCOUNTS, TAX_TYPES
from db import sb_select, sb_insert, sb_delete

st.set_page_config(page_title="経費 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">経費管理</div>', unsafe_allow_html=True)

tab_input, tab_list, tab_graph = st.tabs(["新規入力", "経費一覧・検索", "グラフ分析"])

# ── 新規入力 ──────────────────────────────────────────────────────────────────
with tab_input:
    st.markdown('<div class="section-head">経費情報を入力</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        exp_no      = st.text_input("入力番号", placeholder="例: EXP-001")
        exp_date    = st.date_input("取引日", value=date.today())
        exp_account = st.selectbox("勘定科目", ACCOUNTS)
        exp_tax     = st.selectbox("税区分", TAX_TYPES)
    with fc2:
        exp_store   = st.text_input("負担店舗", placeholder="例: 東京店")
        exp_out     = st.number_input("出金（¥）", min_value=0, value=0, step=100)
        exp_in      = st.number_input("入金（¥）", min_value=0, value=0, step=100)
        exp_balance = st.number_input("残高（¥）", min_value=0, value=0, step=100)
    with fc3:
        exp_purpose = st.text_input("経費名・目的 *")
        exp_user    = st.text_input("使用者")
        exp_partner = st.text_input("取引先")
        exp_month   = st.text_input("対象月", value=date.today().strftime("%Y-%m"))

    exp_note = st.text_area("備考", height=60)

    st.markdown('<div class="section-head">領収書（PDF）</div>', unsafe_allow_html=True)
    uploaded    = st.file_uploader("PDFをアップロード", type=["pdf"])
    receipt_b64 = None
    if uploaded:
        receipt_b64 = base64.b64encode(uploaded.read()).decode()
        st.markdown('<div class="success-box">PDFアップロード済み</div>', unsafe_allow_html=True)
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{receipt_b64}" '
            f'width="100%" height="380px" style="border:1px solid #e5e7eb;border-radius:8px;"></iframe>',
            unsafe_allow_html=True
        )
        if st.button("PDFを削除"):
            uploaded = None; receipt_b64 = None; st.rerun()

    st.markdown("---")
    col_save, col_clear = st.columns([4, 1])
    with col_save:
        if st.button("確定して保存"):
            if not exp_purpose:
                st.markdown('<div class="err-box">経費名・目的は必須です</div>', unsafe_allow_html=True)
            else:
                sb_insert("expenses", {
                    "exp_no":       exp_no,
                    "exp_date":     str(exp_date),
                    "account":      exp_account,
                    "tax_type":     exp_tax,
                    "store":        exp_store,
                    "amount_out":   exp_out,
                    "amount_in":    exp_in,
                    "balance":      exp_balance,
                    "purpose":      exp_purpose,
                    "user_name":    exp_user,
                    "partner":      exp_partner,
                    "note":         exp_note,
                    "target_month": exp_month,
                    "receipt_pdf":  receipt_b64,
                })
                st.markdown('<div class="success-box">経費を保存しました</div>', unsafe_allow_html=True)
    with col_clear:
        if st.button("全消去"): st.rerun()

# ── 経費一覧・検索 ────────────────────────────────────────────────────────────
with tab_list:
    st.markdown('<div class="section-head">経費を検索</div>', unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns(3)
    with sc1: s_year    = st.text_input("年で検索 (YYYY)",          placeholder="例: 2026")
    with sc2: s_date    = st.text_input("日で検索 (YYYY-MM-DD)",    placeholder="例: 2026-03-27")
    with sc3: s_account = st.selectbox("勘定科目", ["すべて"] + ACCOUNTS)

    rows   = sb_select("expenses", order="-exp_date")
    df_exp = to_df(rows)

    if df_exp.empty:
        st.markdown('<div class="info-box">経費データがありません</div>', unsafe_allow_html=True)
    else:
        for col in ["amount_out","amount_in","balance"]:
            if col not in df_exp.columns: df_exp[col] = 0

        df_show = df_exp.copy()
        if s_year:
            df_show = df_show[df_show["exp_date"].astype(str).str.startswith(s_year)]
        if s_date:
            df_show = df_show[df_show["exp_date"].astype(str).str.startswith(s_date)]
        if s_account != "すべて":
            df_show = df_show[df_show["account"] == s_account]

        # サマリー
        total_out = int(df_show["amount_out"].sum())
        st.markdown(f"""<div class="metric-row">
          <div class="metric-card"><div class="val">¥{total_out:,}</div><div class="lbl">総出金</div></div>
          <div class="metric-card"><div class="val">¥{int(df_show["amount_in"].sum()):,}</div><div class="lbl">総入金</div></div>
          <div class="metric-card"><div class="val">{len(df_show)}</div><div class="lbl">件数</div></div>
        </div>""", unsafe_allow_html=True)
        st.caption(f"{len(df_show)}件")

        for _, row in df_show.iterrows():
            with st.expander(
                f"{row.get('exp_date','')}  {row.get('account','')}  "
                f"{row.get('purpose','')}  ¥{int(row.get('amount_out',0)):,}"
            ):
                ec1, ec2 = st.columns(2)
                with ec1:
                    st.markdown(f"**番号:** {row.get('exp_no','')}")
                    st.markdown(f"**勘定科目:** {row.get('account','')}")
                    st.markdown(f"**税区分:** {row.get('tax_type','')}")
                    st.markdown(f"**使用者:** {row.get('user_name','')}")
                    st.markdown(f"**対象月:** {row.get('target_month','')}")
                with ec2:
                    st.markdown(f"**出金:** ¥{int(row.get('amount_out',0)):,}")
                    st.markdown(f"**入金:** ¥{int(row.get('amount_in',0)):,}")
                    st.markdown(f"**残高:** ¥{int(row.get('balance',0)):,}")
                    st.markdown(f"**取引先:** {row.get('partner','')}")
                    st.markdown(f"**備考:** {row.get('note','')}")
                if row.get("receipt_pdf"):
                    st.markdown("**領収書プレビュー:**")
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{row["receipt_pdf"]}" '
                        f'width="100%" height="300px" style="border:1px solid #e5e7eb;border-radius:8px;"></iframe>',
                        unsafe_allow_html=True
                    )
                if st.button("削除", key=f"edel_{row['id']}"):
                    sb_delete("expenses", {"id": row["id"]})
                    st.rerun()

# ── グラフ分析 ────────────────────────────────────────────────────────────────
with tab_graph:
    rows   = sb_select("expenses", order="-exp_date")
    df_exp = to_df(rows)
    if df_exp.empty:
        st.markdown('<div class="info-box">経費データがありません</div>', unsafe_allow_html=True)
    else:
        if "amount_out" not in df_exp.columns: df_exp["amount_out"] = 0
        st.markdown('<div class="section-head">勘定科目別 経費合計</div>', unsafe_allow_html=True)
        acc_agg = df_exp.groupby("account")["amount_out"].sum().sort_values(ascending=False).reset_index()
        acc_agg.columns = ["勘定科目","金額（¥）"]
        st.bar_chart(acc_agg.set_index("勘定科目"))
        for _, row in acc_agg.iterrows():
            st.markdown(f"**{row['勘定科目']}**: ¥{int(row['金額（¥）']):,}")
