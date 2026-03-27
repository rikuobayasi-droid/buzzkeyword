"""
pages/05_crm_customers.py — 顧客管理（v7完全版）
URL: /crm_customers

修正内容:
- 修正1: purchases.note カラム対応（DBスキーマと一致）
- 修正2: Tour/非Tour で入力項目を条件分岐
- 修正3: contact_time を HH:MM 形式で保存
- 修正4: platform_master テーブルから動的取得（Patreon追加）
- 修正5: 購入履歴の編集機能（UPDATE対応）
- 修正6: Patreon はパトレオン管理ページへ誘導（purchasesと分離）
"""
import streamlit as st
import pandas as pd
from datetime import date, time as time_type
from common import (inject_css, setup_sidebar, to_df,
                    TOUR_TYPES, TOUR_STATUSES, PAYMENT_TYPES)
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="顧客管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

# ── プラットフォームを動的取得（修正4）──────────────────────────────────────
def get_platforms() -> list:
    rows = sb_select("platform_master", order="name")
    df   = to_df(rows)
    if df.empty:
        return ["Instagram","Facebook","TikTok","YouTube",
                "Threads","X","LINE","WhatsApp","Gmail","Patreon","その他"]
    return df["name"].tolist()

# ── time を HH:MM 形式の文字列に変換（修正3）────────────────────────────────
def fmt_time(t) -> str:
    """time_input の値を HH:MM 文字列に変換"""
    if t is None:
        return ""
    return str(t)[:5]  # HH:MM

# ── time文字列からtime_typeに復元 ─────────────────────────────────────────────
def parse_time(s) -> time_type:
    try:
        parts = str(s)[:5].split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except Exception:
        return time_type(0, 0)

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
    cid  = int(cust["id"])

    col_back, col_title = st.columns([1, 6])
    with col_back:
        if st.button("一覧に戻る", key="detail_back"):
            st.session_state.pop("selected_customer_id", None)
            st.session_state.pop("editing_purchase_id", None)
            st.rerun()
    with col_title:
        st.markdown(f'<div class="page-title">{cust["name"]}</div>', unsafe_allow_html=True)

    tab_hist, tab_info = st.tabs(["購入履歴", "顧客情報"])

    # ── 購入履歴タブ ──────────────────────────────────────────────────────────
    with tab_hist:
        # 商品マスタ取得（Patreon以外を対象とする）
        rows_p   = sb_select("products", order="name")
        df_prods = to_df(rows_p)
        # Patreonは別管理なのでリストから除外（カテゴリーがPatreonの商品は除く）
        if not df_prods.empty and "category" in df_prods.columns:
            df_prods_non_pat = df_prods[df_prods["category"] != "Patreon"]
        else:
            df_prods_non_pat = df_prods
        prod_names = df_prods_non_pat["name"].tolist() if not df_prods_non_pat.empty else []

        # ── Patreonサブスク誘導バナー ─────────────────────────────────────────
        st.markdown(
            '<div class="info-box">Patreonサブスクリプションは「Patreon管理」ページで管理してください</div>',
            unsafe_allow_html=True
        )

        # ── 購入追加 / 編集フォーム ───────────────────────────────────────────
        editing_id = st.session_state.get("editing_purchase_id")

        # 編集モード: 既存データをロード
        edit_data = {}
        if editing_id:
            rows_edit = sb_select("purchases", filters={"id": editing_id})
            df_edit   = to_df(rows_edit)
            if not df_edit.empty:
                edit_data = df_edit.iloc[0].to_dict()

        form_title = f"購入を編集（ID: {editing_id}）" if editing_id else "購入を追加"
        st.markdown(f'<div class="section-head">{form_title}</div>', unsafe_allow_html=True)

        if editing_id:
            if st.button("キャンセル（追加モードに戻る）", key="cancel_edit"):
                st.session_state.pop("editing_purchase_id", None)
                st.rerun()

        if not prod_names:
            st.markdown(
                '<div class="info-box">商品マスタにデータがありません。商品管理ページから先に登録してください。</div>',
                unsafe_allow_html=True
            )
        else:
            with st.form(key=f"purchase_form_{cid}_{editing_id or 'new'}"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    # 編集時は既存商品をデフォルトに
                    default_prod_idx = 0
                    if edit_data.get("product_id"):
                        matched = df_prods_non_pat[df_prods_non_pat["id"] == edit_data["product_id"]]
                        if not matched.empty and matched.iloc[0]["name"] in prod_names:
                            default_prod_idx = prod_names.index(matched.iloc[0]["name"])

                    h_prod_name = st.selectbox(
                        "商品を選択 *",
                        prod_names,
                        index=default_prod_idx,
                        key=f"h_prod_{cid}"
                    )
                    h_date = st.date_input(
                        "購入日",
                        value=date.fromisoformat(str(edit_data.get("purchase_date",""))[:10]) if edit_data.get("purchase_date") else date.today(),
                        key=f"h_date_{cid}"
                    )
                with fc2:
                    h_amount = st.number_input(
                        "支払額（¥）",
                        min_value=0,
                        value=int(edit_data.get("amount",0) or 0),
                        step=100,
                        key=f"h_amt_{cid}"
                    )
                    h_payment = st.selectbox(
                        "支払方法",
                        PAYMENT_TYPES,
                        index=PAYMENT_TYPES.index(edit_data.get("payment_type","現金")) if edit_data.get("payment_type","") in PAYMENT_TYPES else 0,
                        key=f"h_pay_{cid}"
                    )

                # 修正2: 商品カテゴリーによる条件分岐
                matched_prod = df_prods_non_pat[df_prods_non_pat["name"] == h_prod_name]
                is_tour      = not matched_prod.empty and matched_prod.iloc[0].get("category","") == "Tour"

                h_tour_status = h_guide = h_meet = h_receptionist = ""
                h_order_note  = h_note  = ""
                h_participants = 1
                h_confirmed    = False

                if is_tour:
                    # ── Tour の場合: 参加人数・実施日・ガイド等を表示 ─────────
                    st.markdown("**ツアー詳細**")
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        h_tour_status = st.selectbox(
                            "予約ステータス",
                            TOUR_STATUSES,
                            index=TOUR_STATUSES.index(edit_data.get("tour_status","仮予約")) if edit_data.get("tour_status","") in TOUR_STATUSES else 0,
                            key=f"h_status_{cid}"
                        )
                        h_meet        = st.text_input("合流場所",   value=edit_data.get("meet_place","") or "", key=f"h_meet_{cid}")
                        h_guide       = st.text_input("ガイド名",   value=edit_data.get("guide_name","") or "", key=f"h_guide_{cid}")
                    with tc2:
                        h_participants = st.number_input("参加人数", min_value=1, value=int(edit_data.get("participants",1) or 1), key=f"h_pax_{cid}")
                        h_receptionist = st.text_input("受付担当者", value=edit_data.get("receptionist","") or "", key=f"h_recep_{cid}")
                        h_confirmed    = st.checkbox("内容確認（お客様サイン済み）", value=bool(edit_data.get("confirmed",False)), key=f"h_conf_{cid}")
                    h_order_note = st.text_area("オーダーメモ", value=edit_data.get("order_note","") or "", height=60, key=f"h_order_{cid}")

                else:
                    # ── Tour以外: 最小限の項目のみ表示（修正2）──────────────
                    h_receptionist = st.text_input("受付担当者",   value=edit_data.get("receptionist","") or "", key=f"h_recep_{cid}")
                    h_order_note   = st.text_input("オーダーメモ", value=edit_data.get("order_note","") or "",   key=f"h_order_{cid}")

                # 備考は常に表示（修正1: note カラムに対応）
                h_note = st.text_area(
                    "備考",
                    value=edit_data.get("note","") or "",
                    height=60,
                    key=f"h_note_{cid}"
                )

                btn_label = "更新する" if editing_id else "保存する"
                submitted = st.form_submit_button(btn_label)

                if submitted:
                    prod_id  = int(matched_prod.iloc[0]["id"]) if not matched_prod.empty else None
                    category = matched_prod.iloc[0].get("category","") if not matched_prod.empty else ""

                    # 修正1: DBスキーマと完全一致したデータ構造
                    payload = {
                        "customer_id":   cid,
                        "product_id":    prod_id,
                        "product_type":  category,
                        "purchase_date": str(h_date),
                        "amount":        h_amount,
                        "payment_type":  h_payment,
                        "note":          h_note,          # 修正1: note カラム
                        "order_note":    h_order_note,
                        "receptionist":  h_receptionist,
                        "tour_status":   h_tour_status   if is_tour else None,
                        "meet_place":    h_meet           if is_tour else None,
                        "guide_name":    h_guide          if is_tour else None,
                        "participants":  h_participants    if is_tour else 1,
                        "confirmed":     h_confirmed      if is_tour else False,
                    }

                    if editing_id:
                        # 修正5: UPDATE処理（INSERT ではなく UPDATE）
                        ok = sb_update("purchases", payload, {"id": editing_id})
                        if ok:
                            st.session_state.pop("editing_purchase_id", None)
                            st.rerun()
                        else:
                            st.error("更新に失敗しました")
                    else:
                        # 新規 INSERT
                        res = sb_insert("purchases", payload)
                        if res:
                            st.rerun()
                        else:
                            st.error("保存に失敗しました。もう一度お試しください。")

        # ── 購入履歴一覧 ──────────────────────────────────────────────────────
        st.markdown('<div class="section-head">購入履歴一覧</div>', unsafe_allow_html=True)
        rows_pur = sb_select("purchases", filters={"customer_id": cid}, order="-purchase_date")
        df_pur   = to_df(rows_pur)

        if df_pur.empty:
            st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
        else:
            if not df_prods.empty:
                df_pur = df_pur.merge(
                    df_prods[["id","name","category"]].rename(columns={
                        "id":"product_id","name":"product_name","category":"product_category"
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

                with st.expander(f"{row.get('purchase_date','')}  {prod_disp}  ¥{amount_disp:,}"):
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(f"**商品:** {prod_disp}")
                        st.markdown(f"**支払額:** ¥{amount_disp:,}")
                        st.markdown(f"**支払方法:** {row.get('payment_type','')}")
                        if row.get("note"):
                            st.markdown(f"**備考:** {row.get('note','')}")
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
                        if row.get("receptionist"):
                            st.markdown(f"**受付担当:** {row.get('receptionist','')}")
                        if row.get("order_note"):
                            st.markdown(f"**オーダーメモ:** {row.get('order_note','')}")

                    # Tour ステータス更新
                    if cat_disp == "Tour":
                        cur_s = row.get("tour_status","仮予約")
                        idx_s = TOUR_STATUSES.index(cur_s) if cur_s in TOUR_STATUSES else 0
                        new_s = st.selectbox("ステータス変更", TOUR_STATUSES, index=idx_s, key=f"ts_{rid}")
                        uc1, uc2, uc3 = st.columns([1,1,5])
                        with uc1:
                            if st.button("更新", key=f"tsu_{rid}"):
                                sb_update("purchases", {"tour_status": new_s}, {"id": rid})
                                st.rerun()
                    else:
                        uc2, uc3 = st.columns([1,5])

                    # 修正5: 編集ボタン
                    with uc2 if cat_disp != "Tour" else uc2:
                        if st.button("編集", key=f"pur_edit_{rid}"):
                            st.session_state["editing_purchase_id"] = rid
                            st.rerun()

                    if st.button("削除", key=f"pur_del_{rid}"):
                        sb_delete("purchases", {"id": rid})
                        st.session_state.pop("editing_purchase_id", None)
                        st.rerun()

    # ── 顧客情報タブ ──────────────────────────────────────────────────────────
    with tab_info:
        platforms = get_platforms()  # 修正4: 動的取得
        st.markdown('<div class="section-head">顧客情報</div>', unsafe_allow_html=True)
        ic1, ic2 = st.columns(2)
        with ic1:
            new_name     = st.text_input("名前",          value=cust.get("name",""),          key=f"inf_name_{cid}")
            new_email    = st.text_input("メール",        value=cust.get("email","") or "",    key=f"inf_email_{cid}")
            new_phone    = st.text_input("電話番号",      value=cust.get("phone","") or "",    key=f"inf_phone_{cid}")
            new_username = st.text_input("SNSユーザー名", value=cust.get("username","") or "", key=f"inf_uname_{cid}")
        with ic2:
            plat_val = cust.get("platform","その他")
            plat_idx = platforms.index(plat_val) if plat_val in platforms else len(platforms)-1
            new_platform = st.selectbox("流入プラットフォーム", platforms, index=plat_idx, key=f"inf_plat_{cid}")
            new_address  = st.text_input("住所", value=cust.get("address","") or "", key=f"inf_addr_{cid}")

        # 修正3: 問い合わせ日時（HH:MM形式）
        st.markdown('<div class="section-head">初回お問い合わせ日時</div>', unsafe_allow_html=True)
        ct1, ct2 = st.columns(2)
        with ct1:
            existing_cdate = cust.get("contact_date")
            try:
                default_cdate = date.fromisoformat(str(existing_cdate)[:10]) if existing_cdate else date.today()
            except Exception:
                default_cdate = date.today()
            contact_date = st.date_input("初回お問い合わせ日", value=default_cdate, key=f"inf_cdate_{cid}")
        with ct2:
            contact_time = st.time_input(
                "初回お問い合わせ時間",
                value=parse_time(cust.get("contact_time")),
                key=f"inf_ctime_{cid}"
            )

        st.markdown("**備考・メモ**")
        new_note = st.text_area("", value=cust.get("note","") or "", height=100,
                                label_visibility="collapsed", key=f"inf_note_{cid}")

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
                    "contact_time": fmt_time(contact_time),  # 修正3: HH:MM形式
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

    with tab_reg:
        st.markdown('<div class="section-head">顧客情報を登録</div>', unsafe_allow_html=True)
        platforms = get_platforms()  # 修正4: 動的取得
        rc1, rc2  = st.columns(2)
        with rc1:
            c_name     = st.text_input("名前 *",         key="new_name")
            c_email    = st.text_input("メールアドレス", key="new_email")
            c_phone    = st.text_input("電話番号",       key="new_phone")
            c_username = st.text_input("SNSユーザー名",  key="new_uname")
        with rc2:
            c_platform = st.selectbox("流入プラットフォーム", platforms, key="new_plat")
            c_address  = st.text_input("住所（任意）",   key="new_addr")
            c_note     = st.text_area("備考", height=80, key="new_note")

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
                    "contact_time": fmt_time(c_contact_time),  # 修正3: HH:MM
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)

    with tab_list:
        st.markdown('<div class="section-head">顧客を検索</div>', unsafe_allow_html=True)
        platforms = get_platforms()
        sc1, sc2, sc3 = st.columns(3)
        with sc1: s_name = st.text_input("名前で検索",                      key="lst_sname")
        with sc2: s_plat = st.selectbox("プラットフォーム", ["すべて"] + platforms, key="lst_splat")
        with sc3: s_date = st.text_input("利用日 (YYYY-MM-DD)", placeholder="例: 2026-01-15", key="lst_sdate")

        rows = sb_select("customers", order="-created_at")
        df_c = to_df(rows)

        if df_c.empty:
            st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
        else:
            df_show = df_c.copy()
            if s_name:
                df_show = df_show[df_show["name"].str.contains(s_name, case=False, na=False)]
            if s_plat != "すべて":
                df_show = df_show[df_show["platform"] == s_plat]
            if s_date:
                rows_pur = sb_select("purchases", order="-purchase_date")
                df_pur   = to_df(rows_pur)
                if not df_pur.empty:
                    matched_cids = df_pur[
                        df_pur["purchase_date"].astype(str).str.startswith(s_date)
                    ]["customer_id"].unique()
                    df_show = df_show[df_show["id"].isin(matched_cids)]

            st.caption(f"{len(df_show)}件")
            for _, row in df_show.iterrows():
                rid = int(row["id"])
                lc1, lc2, lc3, lc4, lc5 = st.columns([3,2,2,2,1])
                with lc1:
                    if st.button(row["name"], key=f"lst_go_{rid}"):
                        st.session_state["selected_customer_id"] = rid
                        st.rerun()
                with lc2:
                    st.markdown(f"`{row.get('platform','')}`")
                with lc3:
                    st.caption(str(row.get("created_at",""))[:10])
                with lc4:
                    cdate = row.get("contact_date","")
                    ctime = row.get("contact_time","")
                    if cdate:
                        st.caption(f"問合: {str(cdate)[:10]} {str(ctime)[:5]}")
                with lc5:
                    if st.button("削除", key=f"lst_del_{rid}"):
                        sb_delete("customers", {"id": rid})
                        st.rerun()
