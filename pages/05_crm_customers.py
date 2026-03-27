"""
pages/05_crm_customers.py — 顧客管理
URL: /crm_customers

改修内容:
- 名前・利用日・プラットフォームで検索可能
- 顧客クリックで詳細ページへ遷移
- 詳細ページ: 購入履歴 / 顧客情報 タブ
- 購入履歴を商品マスタと紐付け
- 絵文字を削除
"""
import streamlit as st
from datetime import date
from common import (inject_css, setup_sidebar, to_df,
                    TOUR_TYPES, TOUR_STATUSES, PAYMENT_TYPES,
                    ALL_DM_PLATFORMS, SNS_PLATFORMS)
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="顧客管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

# セッション: selected_customer_id があれば詳細画面を表示
sel_id = st.session_state.get("selected_customer_id")

# ════════════════════════════════════════════════════════
# 詳細画面
# ════════════════════════════════════════════════════════
if sel_id:
    rows_c   = sb_select("customers", order="-created_at")
    df_all_c = to_df(rows_c)
    if df_all_c.empty or sel_id not in df_all_c["id"].values:
        st.session_state.pop("selected_customer_id", None)
        st.rerun()

    cust = df_all_c[df_all_c["id"] == sel_id].iloc[0]

    col_back, col_title = st.columns([1, 6])
    with col_back:
        if st.button("一覧に戻る"):
            st.session_state.pop("selected_customer_id", None)
            st.rerun()
    with col_title:
        st.markdown(f'<div class="page-title">{cust["name"]}</div>', unsafe_allow_html=True)

    tab_hist, tab_info = st.tabs(["購入履歴", "顧客情報"])

    # ── 購入履歴タブ ──────────────────────────────────────────────────────────
    with tab_hist:
        st.markdown('<div class="section-head">購入履歴</div>', unsafe_allow_html=True)

        # 商品マスタ取得
        rows_p   = sb_select("products", order="name")
        df_prods = to_df(rows_p)
        prod_options = ["（商品マスタから選択）"] + df_prods["name"].tolist() if not df_prods.empty else ["（商品未登録）"]

        # 購入記録フォーム
        with st.expander("購入を追加"):
            hc1, hc2 = st.columns(2)
            with hc1:
                h_prod_name = st.selectbox("商品", prod_options, key="h_prod")
                h_date      = st.date_input("購入日", value=date.today(), key="h_date")
            with hc2:
                h_amount = st.number_input("支払額（¥）", min_value=0, value=0, step=100, key="h_amt")
                h_note   = st.text_input("備考", key="h_note")

            # Tour の場合のみ追加項目
            h_tour_status = h_guide = h_meet = ""
            h_participants = 1
            h_payment = "現金"
            h_confirmed = False

            if not df_prods.empty and h_prod_name != "（商品マスタから選択）":
                matched = df_prods[df_prods["name"] == h_prod_name]
                if not matched.empty and matched.iloc[0]["category"] == "Tour":
                    st.markdown("**ツアー詳細**")
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        h_tour_status  = st.selectbox("予約ステータス", TOUR_STATUSES, key="h_status")
                        h_meet         = st.text_input("合流場所", key="h_meet")
                        h_guide        = st.text_input("ガイド名", key="h_guide")
                    with tc2:
                        h_participants = st.number_input("参加人数", min_value=1, value=1, key="h_pax")
                        h_payment      = st.selectbox("支払方法", PAYMENT_TYPES, key="h_pay")
                        h_confirmed    = st.checkbox("内容確認（お客様サイン済み）", key="h_conf")

            if st.button("購入を保存", key="h_save"):
                if h_prod_name == "（商品マスタから選択）" or h_prod_name == "（商品未登録）":
                    st.markdown('<div class="err-box">商品を選択してください</div>', unsafe_allow_html=True)
                else:
                    # product_id を取得
                    matched = df_prods[df_prods["name"] == h_prod_name] if not df_prods.empty else pd.DataFrame()
                    prod_id = int(matched.iloc[0]["id"]) if not matched.empty else None
                    category = matched.iloc[0]["category"] if not matched.empty else ""

                    sb_insert("purchases", {
                        "customer_id":   sel_id,
                        "product_id":    prod_id,
                        "product_type":  category,
                        "purchase_date": str(h_date),
                        "amount":        h_amount,
                        "note":          h_note,
                        "tour_status":   h_tour_status,
                        "meet_place":    h_meet,
                        "guide_name":    h_guide,
                        "participants":  h_participants,
                        "payment_type":  h_payment,
                        "confirmed":     h_confirmed,
                    })
                    st.markdown('<div class="success-box">保存しました</div>', unsafe_allow_html=True)
                    st.rerun()

        # 購入履歴一覧
        rows_pur = sb_select("purchases", filters={"customer_id": sel_id}, order="-purchase_date")
        df_pur   = to_df(rows_pur)

        if df_pur.empty:
            st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
        else:
            # 商品名を結合
            if not df_prods.empty:
                df_pur = df_pur.merge(df_prods[["id","name","category"]].rename(columns={"id":"product_id","name":"product_name","category":"product_category"}),
                                      on="product_id", how="left")
            else:
                df_pur["product_name"]     = df_pur.get("product_type","")
                df_pur["product_category"] = df_pur.get("product_type","")

            for col in ["amount","participants"]:
                if col not in df_pur.columns: df_pur[col] = 0

            for _, row in df_pur.iterrows():
                prod_disp = row.get("product_name") or row.get("product_type","")
                cat_disp  = row.get("product_category","")
                with st.expander(f"{row.get('purchase_date','')}  {prod_disp}  ¥{int(row.get('amount',0)):,}"):
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(f"**商品:** {prod_disp}")
                        st.markdown(f"**カテゴリー:** {cat_disp}")
                        st.markdown(f"**支払額:** ¥{int(row.get('amount',0)):,}")
                        st.markdown(f"**支払方法:** {row.get('payment_type','')}")
                    with rc2:
                        if cat_disp == "Tour":
                            status_color = {"仮予約":"#d97706","ガイド手配中":"#2563eb","カメラマン手配中":"#7c3aed","確定":"#15803d","料金回収済み":"#059669","キャンセル":"#dc2626"}.get(row.get("tour_status",""),"#6b7280")
                            st.markdown(f"**ステータス:** <span style='color:{status_color};font-weight:600;'>{row.get('tour_status','')}</span>", unsafe_allow_html=True)
                            st.markdown(f"**合流場所:** {row.get('meet_place','')}")
                            st.markdown(f"**ガイド名:** {row.get('guide_name','')}")
                            st.markdown(f"**参加人数:** {row.get('participants','')}名")
                            st.markdown(f"**内容確認:** {'サイン済み' if row.get('confirmed') else '未確認'}")
                    if row.get("note"):
                        st.markdown(f"**備考:** {row.get('note','')}")

                    # ステータス更新（Tourのみ）
                    if cat_disp == "Tour":
                        cur_status = row.get("tour_status","仮予約")
                        new_status = st.selectbox("ステータス変更", TOUR_STATUSES,
                                                   index=TOUR_STATUSES.index(cur_status) if cur_status in TOUR_STATUSES else 0,
                                                   key=f"ts_{row['id']}")
                        uc1, uc2 = st.columns([1,6])
                        with uc1:
                            if st.button("更新", key=f"tsu_{row['id']}"):
                                sb_update("purchases", {"tour_status": new_status}, {"id": row["id"]})
                                st.rerun()
                    if st.button("削除", key=f"pur_del_{row['id']}"):
                        sb_delete("purchases", {"id": row["id"]})
                        st.rerun()

    # ── 顧客情報タブ ──────────────────────────────────────────────────────────
    with tab_info:
        st.markdown('<div class="section-head">顧客情報</div>', unsafe_allow_html=True)
        ic1, ic2 = st.columns(2)
        with ic1:
            new_name     = st.text_input("名前",           value=cust.get("name",""))
            new_email    = st.text_input("メール",         value=cust.get("email","") or "")
            new_phone    = st.text_input("電話番号",       value=cust.get("phone","") or "")
            new_username = st.text_input("SNSユーザー名",  value=cust.get("username","") or "")
        with ic2:
            plat_list   = ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"]
            plat_idx    = plat_list.index(cust.get("platform","その他")) if cust.get("platform") in plat_list else len(plat_list)-1
            new_platform = st.selectbox("流入プラットフォーム", plat_list, index=plat_idx)
            new_address  = st.text_input("住所", value=cust.get("address","") or "")

        st.markdown("**備考・メモ**")
        new_note = st.text_area("", value=cust.get("note","") or "", height=100, label_visibility="collapsed")

        nc1, nc2, nc3 = st.columns([1,1,4])
        with nc1:
            if st.button("更新"):
                sb_update("customers", {
                    "name":new_name,"email":new_email,"phone":new_phone,
                    "username":new_username,"platform":new_platform,
                    "address":new_address,"note":new_note
                }, {"id": sel_id})
                st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
        with nc2:
            if st.button("取消"): st.rerun()
        with nc3:
            if st.button("この顧客を削除"):
                sb_delete("customers", {"id": sel_id})
                st.session_state.pop("selected_customer_id", None)
                st.rerun()

# ════════════════════════════════════════════════════════
# 一覧画面
# ════════════════════════════════════════════════════════
else:
    st.markdown('<div class="page-title">顧客管理</div>', unsafe_allow_html=True)
    tab_reg, tab_list = st.tabs(["新規登録", "顧客一覧"])

    # ── 新規登録 ──────────────────────────────────────────────────────────────
    with tab_reg:
        st.markdown('<div class="section-head">顧客情報を登録</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            c_name     = st.text_input("名前 *")
            c_email    = st.text_input("メールアドレス")
            c_phone    = st.text_input("電話番号")
            c_username = st.text_input("SNSユーザー名")
        with c2:
            c_platform = st.selectbox("流入プラットフォーム",
                                      ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"])
            c_address  = st.text_input("住所（任意）")
            c_note     = st.text_area("備考", height=80)

        if st.button("顧客を登録する"):
            if not c_name:
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("customers", {
                    "name":c_name,"email":c_email,"phone":c_phone,
                    "username":c_username,"platform":c_platform,
                    "address":c_address,"note":c_note
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)

    # ── 顧客一覧・検索 ────────────────────────────────────────────────────────
    with tab_list:
        st.markdown('<div class="section-head">顧客を検索</div>', unsafe_allow_html=True)
        sc1, sc2, sc3 = st.columns(3)
        with sc1: s_name  = st.text_input("名前で検索")
        with sc2: s_plat  = st.selectbox("プラットフォーム", ["すべて"] + ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"])
        with sc3: s_date  = st.text_input("利用日 (YYYY-MM-DD)", placeholder="例: 2026-01-15")

        rows   = sb_select("customers", order="-created_at")
        df_c   = to_df(rows)

        if df_c.empty:
            st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
        else:
            df_show = df_c.copy()
            if s_name:
                df_show = df_show[df_show["name"].str.contains(s_name, case=False, na=False)]
            if s_plat != "すべて":
                df_show = df_show[df_show["platform"] == s_plat]
            if s_date:
                # 利用日（purchases.purchase_date）で絞り込む
                rows_p  = sb_select("purchases", order="-purchase_date")
                df_pur  = to_df(rows_p)
                if not df_pur.empty:
                    matched_cids = df_pur[df_pur["purchase_date"].astype(str).str.startswith(s_date)]["customer_id"].unique()
                    df_show = df_show[df_show["id"].isin(matched_cids)]

            st.caption(f"{len(df_show)}件")
            st.markdown('<div class="section-head">顧客一覧（名前をクリックで詳細へ）</div>', unsafe_allow_html=True)

            for _, row in df_show.iterrows():
                lc1, lc2, lc3, lc4 = st.columns([3,2,2,1])
                with lc1:
                    if st.button(row["name"], key=f"cust_{row['id']}"):
                        st.session_state["selected_customer_id"] = row["id"]
                        st.rerun()
                with lc2:
                    st.markdown(f"`{row.get('platform','')}`")
                with lc3:
                    st.caption(str(row.get("created_at",""))[:10])
                with lc4:
                    if st.button("削除", key=f"cdel_{row['id']}"):
                        sb_delete("customers", {"id": row["id"]})
                        st.rerun()
