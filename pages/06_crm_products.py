"""
pages/06_crm_products.py — 商品関連（商品マスタ）
URL: /crm_products

新機能:
- 商品登録（Tour / Guidebook / Patreon）
- カテゴリー別項目
- 商品検索・一覧
- 商品詳細・編集
"""
import streamlit as st
from datetime import date
from common import inject_css, setup_sidebar, to_df, PRODUCT_CATEGORIES
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="商品関連 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">商品管理</div>', unsafe_allow_html=True)

tab_register, tab_list, tab_detail = st.tabs(["商品登録", "商品一覧・検索", "商品詳細・編集"])

# ── 商品登録 ──────────────────────────────────────────────────────────────────
with tab_register:
    st.markdown('<div class="section-head">商品を登録</div>', unsafe_allow_html=True)

    pc1, pc2 = st.columns(2)
    with pc1:
        p_name     = st.text_input("商品名 *")
        p_category = st.selectbox("カテゴリー", PRODUCT_CATEGORIES)
    with pc2:
        p_note = st.text_area("備考", height=80)

    # カテゴリー別項目
    p_price = p_duration = p_per_person = p_extra = p_plan = 0
    p_gb_name = ""

    if p_category == "Tour":
        st.markdown('<div class="section-head">ツアー詳細</div>', unsafe_allow_html=True)
        tc1, tc2 = st.columns(2)
        with tc1:
            p_price      = st.number_input("料金（¥）", min_value=0, value=0, step=1000)
            p_duration   = st.number_input("所要時間（分）", min_value=0, value=120, step=30)
        with tc2:
            p_per_person = st.number_input("1名料金（¥）", min_value=0, value=0, step=500)
            p_extra      = st.number_input("追加人数料金（¥/人）", min_value=0, value=0, step=500)

    elif p_category == "Guidebook":
        st.markdown('<div class="section-head">ガイドブック詳細</div>', unsafe_allow_html=True)
        gb1, gb2 = st.columns(2)
        with gb1:
            p_gb_name = st.text_input("ガイドブック名称")
        with gb2:
            p_price   = st.number_input("金額（¥）", min_value=0, value=0, step=100)

    elif p_category == "Patreon":
        st.markdown('<div class="section-head">Patreon詳細</div>', unsafe_allow_html=True)
        pa1, pa2 = st.columns(2)
        with pa1:
            p_plan  = st.text_input("プラン名")
        with pa2:
            p_price = st.number_input("金額（¥/月）", min_value=0, value=0, step=100)

    if st.button("商品を登録する"):
        if not p_name:
            st.markdown('<div class="err-box">商品名は必須です</div>', unsafe_allow_html=True)
        else:
            res = sb_insert("products", {
                "name":        p_name,
                "category":    p_category,
                "price":       p_price,
                "duration":    p_duration,
                "per_person":  p_per_person,
                "extra_price": p_extra,
                "plan_name":   p_plan,
                "gb_name":     p_gb_name,
                "note":        p_note,
            })
            if res:
                st.markdown('<div class="success-box">商品を登録しました</div>', unsafe_allow_html=True)

# ── 商品一覧・検索 ────────────────────────────────────────────────────────────
with tab_list:
    st.markdown('<div class="section-head">商品を検索</div>', unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns(3)
    with sc1: s_name     = st.text_input("商品名で検索")
    with sc2: s_category = st.selectbox("カテゴリー", ["すべて"] + PRODUCT_CATEGORIES, key="s_cat")
    with sc3: s_date     = st.text_input("登録日 (YYYY-MM-DD)", placeholder="例: 2026-01-01")

    rows     = sb_select("products", order="-created_at")
    df_prods = to_df(rows)

    if df_prods.empty:
        st.markdown('<div class="info-box">商品データがありません</div>', unsafe_allow_html=True)
    else:
        # フィルタリング
        df_show = df_prods.copy()
        if s_name:
            df_show = df_show[df_show["name"].str.contains(s_name, case=False, na=False)]
        if s_category != "すべて":
            df_show = df_show[df_show["category"] == s_category]
        if s_date:
            df_show = df_show[df_show["created_at"].astype(str).str.startswith(s_date)]

        st.caption(f"{len(df_show)}件")

        for _, row in df_show.iterrows():
            pc1, pc2, pc3, pc4 = st.columns([4, 2, 2, 1])
            with pc1:
                # 商品名クリックで詳細タブへ遷移（session_state経由）
                if st.button(f"{row['name']}", key=f"prod_link_{row['id']}"):
                    st.session_state["selected_product_id"] = row["id"]
                    st.rerun()
            with pc2:
                st.markdown(f"`{row.get('category','')}`")
            with pc3:
                st.caption(str(row.get("created_at",""))[:10])
            with pc4:
                if st.button("削除", key=f"prod_del_{row['id']}"):
                    sb_delete("products", {"id": row["id"]})
                    st.rerun()

# ── 商品詳細・編集 ────────────────────────────────────────────────────────────
with tab_detail:
    prod_id = st.session_state.get("selected_product_id")
    rows    = sb_select("products", order="-created_at")
    df_prods = to_df(rows)

    if df_prods.empty:
        st.markdown('<div class="info-box">商品データがありません</div>', unsafe_allow_html=True)
    else:
        # セレクトボックスでも選択できるようにする
        prod_names = df_prods["name"].tolist()
        default_idx = 0
        if prod_id:
            matched = df_prods[df_prods["id"] == prod_id]
            if not matched.empty:
                default_idx = prod_names.index(matched.iloc[0]["name"])

        sel_name = st.selectbox("商品を選択", prod_names, index=default_idx, key="detail_sel")
        prod_row = df_prods[df_prods["name"] == sel_name].iloc[0]

        st.markdown('<div class="section-head">商品情報</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)
        with dc1:
            new_name     = st.text_input("商品名", value=prod_row.get("name",""))
            new_category = st.selectbox("カテゴリー", PRODUCT_CATEGORIES,
                                         index=PRODUCT_CATEGORIES.index(prod_row.get("category","Tour"))
                                         if prod_row.get("category") in PRODUCT_CATEGORIES else 0,
                                         key="edit_cat")
        with dc2:
            new_note = st.text_area("備考", value=prod_row.get("note","") or "", height=80)

        new_price = new_duration = new_per = new_extra = 0
        new_plan  = new_gb = ""

        if new_category == "Tour":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_price    = st.number_input("料金（¥）",          value=int(prod_row.get("price",0) or 0), step=1000)
                new_duration = st.number_input("所要時間（分）",       value=int(prod_row.get("duration",120) or 120), step=30)
            with ec2:
                new_per      = st.number_input("1名料金（¥）",        value=int(prod_row.get("per_person",0) or 0), step=500)
                new_extra    = st.number_input("追加人数料金（¥/人）", value=int(prod_row.get("extra_price",0) or 0), step=500)
        elif new_category == "Guidebook":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_gb    = st.text_input("ガイドブック名称", value=prod_row.get("gb_name","") or "")
            with ec2:
                new_price = st.number_input("金額（¥）", value=int(prod_row.get("price",0) or 0), step=100)
        elif new_category == "Patreon":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_plan  = st.text_input("プラン名", value=prod_row.get("plan_name","") or "")
            with ec2:
                new_price = st.number_input("金額（¥/月）", value=int(prod_row.get("price",0) or 0), step=100)

        if st.button("更新する"):
            sb_update("products", {
                "name":        new_name,
                "category":    new_category,
                "price":       new_price,
                "duration":    new_duration,
                "per_person":  new_per,
                "extra_price": new_extra,
                "plan_name":   new_plan,
                "gb_name":     new_gb,
                "note":        new_note,
            }, {"id": int(prod_row["id"])})
            st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
            st.rerun()
