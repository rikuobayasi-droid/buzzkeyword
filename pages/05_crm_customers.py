"""
pages/05_crm_customers.py — 顧客管理
URL: /crm_customers

修正2: 購入保存処理を確実に実装
  - sb_insert 後に st.rerun() を確実に呼び出す
  - 商品マスタとの紐付けを正確に行う
  - 保存後即座に一覧へ反映

修正3: 初回問い合わせ日時を追加
  - contact_date, contact_time カラムを顧客テーブルに追加
  - 登録・編集・詳細表示に対応
  - 未入力でもエラーにならない（None許容）
"""
import streamlit as st
import pandas as pd
from datetime import date, time as time_type, datetime
from common import (inject_css, setup_sidebar, to_df,
                    TOUR_TYPES, TOUR_STATUSES, PAYMENT_TYPES)
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="顧客管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

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
    cid  = int(cust["id"])  # 一意キー生成用

    col_back, col_title = st.columns([1, 6])
    with col_back:
        if st.button("一覧に戻る", key="detail_back"):
            st.session_state.pop("selected_customer_id", None)
            st.rerun()
    with col_title:
        st.markdown(f'<div class="page-title">{cust["name"]}</div>', unsafe_allow_html=True)

    tab_hist, tab_info = st.tabs(["購入履歴", "顧客情報"])

    # ── 購入履歴タブ ──────────────────────────────────────────────────────────
    with tab_hist:
        # 商品マスタ取得
        rows_p   = sb_select("products", order="name")
        df_prods = to_df(rows_p)
        prod_names = df_prods["name"].tolist() if not df_prods.empty else []

        st.markdown('<div class="section-head">購入を追加</div>', unsafe_allow_html=True)

        with st.form(key=f"purchase_form_{cid}"):
            # 商品選択
            if not prod_names:
                st.markdown('<div class="err-box">商品マスタにデータがありません。商品管理ページから先に登録してください。</div>', unsafe_allow_html=True)
                st.form_submit_button("保存する", disabled=True)
            else:
                fc1, fc2 = st.columns(2)
                with fc1:
                    h_prod_name = st.selectbox("商品を選択 *", prod_names, key=f"h_prod_{cid}")
                    h_date      = st.date_input("購入日", value=date.today(),    key=f"h_date_{cid}")
                with fc2:
                    h_amount    = st.number_input("支払額（¥）", min_value=0, value=0, step=100, key=f"h_amt_{cid}")
                    h_note      = st.text_input("備考",          key=f"h_note_{cid}")

                # 選択した商品のカテゴリーを確認してTour項目を表示
                matched_prod = df_prods[df_prods["name"] == h_prod_name] if not df_prods.empty else pd.DataFrame()
                is_tour = not matched_prod.empty and matched_prod.iloc[0].get("category","") == "Tour"

                h_tour_status = h_guide = h_meet = h_receptionist = h_order_note = ""
                h_participants = 1
                h_payment      = "現金"
                h_confirmed    = False

                if is_tour:
                    st.markdown("**ツアー詳細**")
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        h_tour_status  = st.selectbox("予約ステータス", TOUR_STATUSES, key=f"h_status_{cid}")
                        h_meet         = st.text_input("合流場所",       key=f"h_meet_{cid}")
                        h_guide        = st.text_input("ガイド名",       key=f"h_guide_{cid}")
                        h_receptionist = st.text_input("受付担当者名",   key=f"h_recep_{cid}")
                    with tc2:
                        h_participants = st.number_input("参加人数", min_value=1, value=1, key=f"h_pax_{cid}")
                        h_payment      = st.selectbox("支払方法", PAYMENT_TYPES,           key=f"h_pay_{cid}")
                        h_confirmed    = st.checkbox("内容確認（お客様サイン済み）",        key=f"h_conf_{cid}")
                    h_order_note = st.text_area("オーダーメモ", height=60, key=f"h_order_{cid}")

                submitted = st.form_submit_button("保存する")

                # 修正2: フォーム送信時に確実に保存→rerun
                if submitted:
                    prod_id  = int(matched_prod.iloc[0]["id"]) if not matched_prod.empty else None
                    category = matched_prod.iloc[0]["category"] if not matched_prod.empty else ""

                    res = sb_insert("purchases", {
                        "customer_id":   cid,
                        "product_id":    prod_id,
                        "product_type":  category,
                        "purchase_date": str(h_date),
                        "amount":        h_amount,
                        "note":          h_note,
                        "tour_status":   h_tour_status   if is_tour else None,
                        "meet_place":    h_meet           if is_tour else None,
                        "guide_name":    h_guide          if is_tour else None,
                        "receptionist":  h_receptionist   if is_tour else None,
                        "participants":  h_participants    if is_tour else 1,
                        "payment_type":  h_payment,
                        "confirmed":     h_confirmed      if is_tour else False,
                        "order_note":    h_order_note     if is_tour else None,
                    })

                    if res:
                        st.success("保存しました")
                        st.rerun()  # 修正2: 保存後に確実に再描画して一覧に反映
                    else:
                        st.error("保存に失敗しました。もう一度お試しください。")

        # 購入履歴一覧（保存後に最新データを取得）
        st.markdown('<div class="section-head">購入履歴一覧</div>', unsafe_allow_html=True)
        rows_pur = sb_select("purchases", filters={"customer_id": cid}, order="-purchase_date")
        df_pur   = to_df(rows_pur)

        if df_pur.empty:
            st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
        else:
            # 商品名を結合
            if not df_prods.empty:
                df_pur = df_pur.merge(
                    df_prods[["id","name","category"]].rename(columns={
                        "id":"product_id", "name":"product_name", "category":"product_category"
                    }),
                    on="product_id", how="left"
                )
            else:
                df_pur["product_name"]     = df_pur.get("product_type","")
                df_pur["product_category"] = df_pur.get("product_type","")

            for col in ["amount","participants"]:
                if col not in df_pur.columns: df_pur[col] = 0

            for _, row in df_pur.iterrows():
                rid         = int(row["id"])
                prod_disp   = row.get("product_name")  or row.get("product_type","")
                cat_disp    = row.get("product_category","")
                amount_disp = int(row.get("amount",0))

                with st.expander(
                    f"{row.get('purchase_date','')}  {prod_disp}  ¥{amount_disp:,}"
                ):
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(f"**商品:** {prod_disp}")
                        st.markdown(f"**カテゴリー:** {cat_disp}")
                        st.markdown(f"**支払額:** ¥{amount_disp:,}")
                        st.markdown(f"**支払方法:** {row.get('payment_type','')}")
                    with rc2:
                        if cat_disp == "Tour":
                            sc = row.get("tour_status","")
                            status_color = {
                                "仮予約":"#d97706","ガイド手配中":"#2563eb",
                                "カメラマン手配中":"#7c3aed","確定":"#15803d",
                                "料金回収済み":"#059669","キャンセル":"#dc2626"
                            }.get(sc,"#6b7280")
                            st.markdown(
                                f"**ステータス:** <span style='color:{status_color};font-weight:600;'>{sc}</span>",
                                unsafe_allow_html=True
                            )
                            st.markdown(f"**合流場所:** {row.get('meet_place','')}")
                            st.markdown(f"**ガイド名:** {row.get('guide_name','')}")
                            st.markdown(f"**参加人数:** {int(row.get('participants',1))}名")
                            st.markdown(f"**内容確認:** {'サイン済み' if row.get('confirmed') else '未確認'}")

                    if row.get("note"):
                        st.markdown(f"**備考:** {row.get('note','')}")

                    # Tour ステータス更新
                    if cat_disp == "Tour":
                        cur_s  = row.get("tour_status","仮予約")
                        idx_s  = TOUR_STATUSES.index(cur_s) if cur_s in TOUR_STATUSES else 0
                        new_s  = st.selectbox(
                            "ステータス変更",
                            TOUR_STATUSES,
                            index=idx_s,
                            key=f"ts_{rid}"
                        )
                        uc1, uc2 = st.columns([1,6])
                        with uc1:
                            if st.button("更新", key=f"tsu_{rid}"):
                                sb_update("purchases", {"tour_status": new_s}, {"id": rid})
                                st.rerun()

                    if st.button("削除", key=f"pur_del_{rid}"):
                        sb_delete("purchases", {"id": rid})
                        st.rerun()

    # ── 顧客情報タブ ──────────────────────────────────────────────────────────
    with tab_info:
        st.markdown('<div class="section-head">顧客情報</div>', unsafe_allow_html=True)
        ic1, ic2 = st.columns(2)
        with ic1:
            new_name     = st.text_input("名前",          value=cust.get("name",""),     key=f"inf_name_{cid}")
            new_email    = st.text_input("メール",        value=cust.get("email","") or "",  key=f"inf_email_{cid}")
            new_phone    = st.text_input("電話番号",      value=cust.get("phone","") or "",  key=f"inf_phone_{cid}")
            new_username = st.text_input("SNSユーザー名", value=cust.get("username","") or "", key=f"inf_uname_{cid}")
        with ic2:
            plat_list  = ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"]
            plat_val   = cust.get("platform","その他")
            plat_idx   = plat_list.index(plat_val) if plat_val in plat_list else len(plat_list)-1
            new_platform = st.selectbox("流入プラットフォーム", plat_list, index=plat_idx, key=f"inf_plat_{cid}")
            new_address  = st.text_input("住所", value=cust.get("address","") or "", key=f"inf_addr_{cid}")

        # 修正3: 初回問い合わせ日時
        st.markdown('<div class="section-head">初回お問い合わせ日時</div>', unsafe_allow_html=True)
        ct1, ct2 = st.columns(2)
        with ct1:
            # 既存値がNoneでも安全にデフォルト値を設定
            existing_cdate = cust.get("contact_date")
            default_cdate  = date.today()
            if existing_cdate:
                try:
                    default_cdate = date.fromisoformat(str(existing_cdate)[:10])
                except Exception:
                    default_cdate = date.today()
            contact_date = st.date_input(
                "初回お問い合わせ日",
                value=default_cdate,
                key=f"inf_cdate_{cid}"
            )
        with ct2:
            existing_ctime = cust.get("contact_time")
            default_ctime  = time_type(0, 0)
            if existing_ctime:
                try:
                    parts         = str(existing_ctime)[:5].split(":")
                    default_ctime = time_type(int(parts[0]), int(parts[1]))
                except Exception:
                    default_ctime = time_type(0, 0)
            contact_time = st.time_input(
                "初回お問い合わせ時間",
                value=default_ctime,
                key=f"inf_ctime_{cid}"
            )

        st.markdown("**備考・メモ**")
        new_note = st.text_area(
            "",
            value=cust.get("note","") or "",
            height=100,
            label_visibility="collapsed",
            key=f"inf_note_{cid}"
        )

        nc1, nc2, nc3 = st.columns([1,1,1])
        with nc1:
            if st.button("更新", key=f"inf_upd_{cid}"):
                sb_update("customers", {
                    "name":         new_name,
                    "email":        new_email,
                    "phone":        new_phone,
                    "username":     new_username,
                    "platform":     new_platform,
                    "address":      new_address,
                    "note":         new_note,
                    "contact_date": str(contact_date),
                    "contact_time": str(contact_time),
                }, {"id": cid})
                st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
        with nc2:
            if st.button("取消", key=f"inf_cancel_{cid}"):
                st.rerun()
        with nc3:
            if st.button("この顧客を削除", key=f"inf_del_{cid}"):
                sb_delete("customers", {"id": cid})
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
        rc1, rc2 = st.columns(2)
        with rc1:
            c_name     = st.text_input("名前 *",         key="new_name")
            c_email    = st.text_input("メールアドレス", key="new_email")
            c_phone    = st.text_input("電話番号",       key="new_phone")
            c_username = st.text_input("SNSユーザー名",  key="new_uname")
        with rc2:
            c_platform = st.selectbox(
                "流入プラットフォーム",
                ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"],
                key="new_plat"
            )
            c_address = st.text_input("住所（任意）", key="new_addr")
            c_note    = st.text_area("備考",  height=80, key="new_note")

        # 修正3: 初回問い合わせ日時（新規登録）
        st.markdown('<div class="section-head">初回お問い合わせ日時（任意）</div>', unsafe_allow_html=True)
        nc1, nc2 = st.columns(2)
        with nc1:
            c_contact_date = st.date_input("初回お問い合わせ日", value=date.today(), key="new_cdate")
        with nc2:
            c_contact_time = st.time_input("初回お問い合わせ時間", value=time_type(0,0), key="new_ctime")

        if st.button("顧客を登録する", key="new_submit"):
            if not c_name:
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("customers", {
                    "name":         c_name,
                    "email":        c_email,
                    "phone":        c_phone,
                    "username":     c_username,
                    "platform":     c_platform,
                    "address":      c_address,
                    "note":         c_note,
                    "contact_date": str(c_contact_date),
                    "contact_time": str(c_contact_time),
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)

    # ── 顧客一覧・検索 ────────────────────────────────────────────────────────
    with tab_list:
        st.markdown('<div class="section-head">顧客を検索</div>', unsafe_allow_html=True)
        sc1, sc2, sc3 = st.columns(3)
        with sc1: s_name = st.text_input("名前で検索", key="lst_sname")
        with sc2: s_plat = st.selectbox(
            "プラットフォーム",
            ["すべて","Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"],
            key="lst_splat"
        )
        with sc3: s_date = st.text_input("利用日 (YYYY-MM-DD)", placeholder="例: 2026-01-15", key="lst_sdate")

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
                # purchases テーブルで利用日フィルター
                rows_pur = sb_select("purchases", order="-purchase_date")
                df_pur   = to_df(rows_pur)
                if not df_pur.empty:
                    matched_cids = df_pur[
                        df_pur["purchase_date"].astype(str).str.startswith(s_date)
                    ]["customer_id"].unique()
                    df_show = df_show[df_show["id"].isin(matched_cids)]

            st.caption(f"{len(df_show)}件")
            st.markdown('<div class="section-head">顧客一覧（名前をクリックで詳細へ）</div>', unsafe_allow_html=True)

            for _, row in df_show.iterrows():
                rid = int(row["id"])
                lc1, lc2, lc3, lc4, lc5 = st.columns([3, 2, 2, 2, 1])
                with lc1:
                    if st.button(row["name"], key=f"lst_go_{rid}"):
                        st.session_state["selected_customer_id"] = rid
                        st.rerun()
                with lc2:
                    st.markdown(f"`{row.get('platform','')}`")
                with lc3:
                    st.caption(str(row.get("created_at",""))[:10])
                with lc4:
                    # 修正3: 初回問い合わせ日時を一覧にも表示
                    cdate = row.get("contact_date","")
                    ctime = row.get("contact_time","")
                    if cdate:
                        st.caption(f"問合: {str(cdate)[:10]} {str(ctime)[:5]}")
                with lc5:
                    if st.button("削除", key=f"lst_del_{rid}"):
                        sb_delete("customers", {"id": rid})
                        st.rerun()
