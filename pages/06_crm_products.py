"""
pages/06_crm_products.py — 商品管理
URL: /crm_products

修正1対応:
- 全ウィジェットに一意なkeyを付与
- タブ間でIDが衝突しないようにタブ名プレフィックスを使用
  例: key="reg_note", key="det_note_{id}", key="cat_edit_{id}"
"""
import streamlit as st
from datetime import date
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="商品管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">商品管理</div>', unsafe_allow_html=True)

tab_register, tab_list, tab_detail, tab_category = st.tabs([
    "商品登録", "商品一覧・検索", "商品詳細・編集", "カテゴリー管理"
])

def get_categories() -> list:
    """product_categories テーブルからカテゴリー名一覧を動的取得"""
    rows = sb_select("product_categories", order="name")
    df   = to_df(rows)
    if df.empty:
        return ["Tour", "Guidebook", "Patreon"]
    return df["name"].tolist()

# ════════════════════════════════════════════════════════
# タブ1: 商品登録
# key プレフィックス: "reg_"
# ════════════════════════════════════════════════════════
with tab_register:
    st.markdown('<div class="section-head">商品を登録</div>', unsafe_allow_html=True)
    categories = get_categories()

    rc1, rc2 = st.columns(2)
    with rc1:
        p_name     = st.text_input("商品名 *",    key="reg_name")
        p_category = st.selectbox("カテゴリー",   categories, key="reg_category")
    with rc2:
        p_note = st.text_area("備考", height=80,  key="reg_note")

    # カテゴリー別の追加入力項目
    p_price = p_duration = p_per_person = p_extra = 0
    p_plan  = p_gb_name  = ""

    if p_category == "Tour":
        st.markdown('<div class="section-head">ツアー詳細</div>', unsafe_allow_html=True)
        tc1, tc2 = st.columns(2)
        with tc1:
            p_price      = st.number_input("料金（¥）",          min_value=0, value=0, step=1000, key="reg_price")
            p_duration   = st.number_input("所要時間（分）",       min_value=0, value=120, step=30, key="reg_duration")
        with tc2:
            p_per_person = st.number_input("1名料金（¥）",        min_value=0, value=0, step=500,  key="reg_per")
            p_extra      = st.number_input("追加人数料金（¥/人）", min_value=0, value=0, step=500,  key="reg_extra")

    elif p_category == "Guidebook":
        st.markdown('<div class="section-head">ガイドブック詳細</div>', unsafe_allow_html=True)
        gb1, gb2 = st.columns(2)
        with gb1:
            p_gb_name = st.text_input("ガイドブック名称", key="reg_gb_name")
        with gb2:
            p_price   = st.number_input("金額（¥）", min_value=0, value=0, step=100, key="reg_gb_price")

    elif p_category == "Patreon":
        st.markdown('<div class="section-head">Patreon詳細</div>', unsafe_allow_html=True)
        pa1, pa2 = st.columns(2)
        with pa1:
            p_plan  = st.text_input("プラン名", key="reg_plan")
        with pa2:
            p_price = st.number_input("金額（¥/月）", min_value=0, value=0, step=100, key="reg_pa_price")

    else:
        # 動的追加カテゴリー用の汎用フォーム
        gc1, gc2 = st.columns(2)
        with gc1:
            p_price    = st.number_input("料金（¥）",        min_value=0, value=0, step=100, key="reg_gen_price")
        with gc2:
            p_duration = st.number_input("所要時間（分・任意）", min_value=0, value=0, step=30, key="reg_gen_dur")

    if st.button("商品を登録する", key="reg_submit"):
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

# ════════════════════════════════════════════════════════
# タブ2: 商品一覧・検索
# key プレフィックス: "lst_"
# ════════════════════════════════════════════════════════
with tab_list:
    st.markdown('<div class="section-head">商品を検索</div>', unsafe_allow_html=True)
    categories = get_categories()

    sc1, sc2, sc3 = st.columns(3)
    with sc1: s_name     = st.text_input("商品名で検索",           key="lst_name")
    with sc2: s_category = st.selectbox("カテゴリー", ["すべて"] + categories, key="lst_cat")
    with sc3: s_date_str = st.text_input("登録日 (YYYY-MM-DD)",    key="lst_date", placeholder="例: 2026-01-01")

    rows     = sb_select("products", order="-created_at")
    df_prods = to_df(rows)

    if df_prods.empty:
        st.markdown('<div class="info-box">商品データがありません</div>', unsafe_allow_html=True)
    else:
        df_show = df_prods.copy()
        if s_name:
            df_show = df_show[df_show["name"].str.contains(s_name, case=False, na=False)]
        if s_category != "すべて":
            df_show = df_show[df_show["category"] == s_category]
        if s_date_str:
            df_show = df_show[df_show["created_at"].astype(str).str.startswith(s_date_str)]

        st.caption(f"{len(df_show)}件")
        for _, row in df_show.iterrows():
            lc1, lc2, lc3, lc4 = st.columns([4, 2, 2, 1])
            with lc1:
                if st.button(row["name"], key=f"lst_link_{row['id']}"):
                    st.session_state["selected_product_id"] = row["id"]
                    st.rerun()
            with lc2:
                st.markdown(f"`{row.get('category','')}`")
            with lc3:
                st.caption(f"¥{int(row.get('price',0) or 0):,}")
            with lc4:
                if st.button("削除", key=f"lst_del_{row['id']}"):
                    sb_delete("products", {"id": row["id"]})
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ3: 商品詳細・編集
# key プレフィックス: "det_"
# ════════════════════════════════════════════════════════
with tab_detail:
    categories = get_categories()
    rows       = sb_select("products", order="-created_at")
    df_prods   = to_df(rows)

    if df_prods.empty:
        st.markdown('<div class="info-box">商品データがありません</div>', unsafe_allow_html=True)
    else:
        prod_names  = df_prods["name"].tolist()
        default_idx = 0
        prod_id     = st.session_state.get("selected_product_id")
        if prod_id:
            matched = df_prods[df_prods["id"] == prod_id]
            if not matched.empty:
                idx = prod_names.index(matched.iloc[0]["name"])
                default_idx = idx

        sel_name = st.selectbox("商品を選択", prod_names, index=default_idx, key="det_sel")
        prod_row = df_prods[df_prods["name"] == sel_name].iloc[0]
        pid      = int(prod_row["id"])  # 一意キー生成用

        st.markdown('<div class="section-head">商品情報</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)
        with dc1:
            new_name = st.text_input(
                "商品名",
                value=prod_row.get("name", ""),
                key=f"det_name_{pid}"
            )
            cat_idx = categories.index(prod_row.get("category","")) if prod_row.get("category","") in categories else 0
            new_category = st.selectbox(
                "カテゴリー",
                categories,
                index=cat_idx,
                key=f"det_cat_{pid}"
            )
        with dc2:
            new_note = st.text_area(
                "備考",
                value=prod_row.get("note","") or "",
                height=80,
                key=f"det_note_{pid}"   # <-- 一意なkey（修正1対応）
            )

        # カテゴリー別の編集フォーム
        new_price = new_duration = new_per = new_extra = 0
        new_plan  = new_gb = ""

        if new_category == "Tour":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_price    = st.number_input("料金（¥）",          value=int(prod_row.get("price",0) or 0),       step=1000, key=f"det_price_{pid}")
                new_duration = st.number_input("所要時間（分）",       value=int(prod_row.get("duration",120) or 120), step=30,   key=f"det_dur_{pid}")
            with ec2:
                new_per   = st.number_input("1名料金（¥）",          value=int(prod_row.get("per_person",0) or 0),  step=500,  key=f"det_per_{pid}")
                new_extra = st.number_input("追加人数料金（¥/人）",   value=int(prod_row.get("extra_price",0) or 0), step=500,  key=f"det_extra_{pid}")

        elif new_category == "Guidebook":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_gb    = st.text_input("ガイドブック名称",     value=prod_row.get("gb_name","") or "",  key=f"det_gb_{pid}")
            with ec2:
                new_price = st.number_input("金額（¥）",          value=int(prod_row.get("price",0) or 0), step=100, key=f"det_gb_price_{pid}")

        elif new_category == "Patreon":
            ec1, ec2 = st.columns(2)
            with ec1:
                new_plan  = st.text_input("プラン名",              value=prod_row.get("plan_name","") or "", key=f"det_plan_{pid}")
            with ec2:
                new_price = st.number_input("金額（¥/月）",        value=int(prod_row.get("price",0) or 0), step=100, key=f"det_pa_price_{pid}")

        else:
            ec1, ec2 = st.columns(2)
            with ec1:
                new_price    = st.number_input("料金（¥）",        value=int(prod_row.get("price",0) or 0),    step=100, key=f"det_gen_price_{pid}")
            with ec2:
                new_duration = st.number_input("所要時間（分）",   value=int(prod_row.get("duration",0) or 0), step=30,  key=f"det_gen_dur_{pid}")

        if st.button("更新する", key=f"det_submit_{pid}"):
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
            }, {"id": pid})
            st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
            st.rerun()

# ════════════════════════════════════════════════════════
# タブ4: カテゴリー管理
# key プレフィックス: "cat_"
# ════════════════════════════════════════════════════════
with tab_category:
    st.markdown('<div class="section-head">カテゴリーを管理</div>', unsafe_allow_html=True)

    cc1, cc2 = st.columns([3, 1])
    with cc1:
        new_cat_name = st.text_input(
            "新しいカテゴリー名",
            placeholder="例: Workshop, Online Tour",
            key="cat_new_name"
        )
    with cc2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("追加する", key="cat_add"):
            if not new_cat_name.strip():
                st.markdown('<div class="err-box">カテゴリー名を入力してください</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("product_categories", {"name": new_cat_name.strip()})
                if res:
                    st.markdown('<div class="success-box">カテゴリーを追加しました</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown('<div class="err-box">追加に失敗しました（重複の可能性があります）</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-head">カテゴリー一覧</div>', unsafe_allow_html=True)
    rows_cat = sb_select("product_categories", order="name")
    df_cat   = to_df(rows_cat)

    if df_cat.empty:
        st.markdown('<div class="info-box">カテゴリーがありません。上から追加してください。</div>', unsafe_allow_html=True)
    else:
        for _, row in df_cat.iterrows():
            lc1, lc2, lc3 = st.columns([4, 2, 1])
            with lc1:
                edited_name = st.text_input(
                    "カテゴリー名",
                    value=row["name"],
                    key=f"cat_edit_{row['id']}",   # ループ内でidを使い一意に
                    label_visibility="collapsed"
                )
            with lc2:
                if st.button("更新", key=f"cat_upd_{row['id']}"):
                    if edited_name.strip():
                        sb_update("product_categories", {"name": edited_name.strip()}, {"id": row["id"]})
                        st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                        st.rerun()
            with lc3:
                if st.button("削除", key=f"cat_del_{row['id']}"):
                    sb_delete("product_categories", {"id": row["id"]})
                    st.rerun()
