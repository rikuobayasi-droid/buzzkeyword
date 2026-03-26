"""
pages/05_crm_customers.py — 顧客管理
URL: /crm_customers
"""
import streamlit as st
from datetime import date
from common import (inject_css, setup_sidebar, to_df,
                    PLATFORM_EMOJI, TOUR_TYPES, TOUR_STATUSES, PAYMENT_TYPES, BUSINESSES)
from db import sb_select, sb_insert, sb_update, sb_delete

st.set_page_config(page_title="顧客管理 | Tabibiyori", page_icon="👤", layout="wide")
inject_css()
setup_sidebar()
st.markdown('<div class="page-title">👤 顧客管理</div>', unsafe_allow_html=True)

tab_reg, tab_list, tab_purchase = st.tabs(["新規登録", "顧客一覧・情報", "購入履歴"])

# ── 新規登録 ──────────────────────────────────────────────────────────────────
with tab_reg:
    st.markdown('<div class="section-head">顧客情報を登録</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        c_name     = st.text_input("名前 *")
        c_email    = st.text_input("メールアドレス")
        c_phone    = st.text_input("電話番号")
        c_username = st.text_input("SNSユーザー名")
    with c2:
        c_platform = st.selectbox("流入プラットフォーム", ["Instagram","Facebook","TikTok","YouTube","Threads","X","LINE","WhatsApp","Gmail","その他"])
        c_address  = st.text_input("住所（任意）")
        c_note     = st.text_area("備考", height=100)
    if st.button("💾 顧客を登録する"):
        if not c_name:
            st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
        else:
            res = sb_insert("customers",{"name":c_name,"email":c_email,"phone":c_phone,"username":c_username,"platform":c_platform,"address":c_address,"note":c_note})
            if res: st.markdown('<div class="success-box">✅ 登録しました</div>', unsafe_allow_html=True)

# ── 顧客一覧・情報 ────────────────────────────────────────────────────────────
with tab_list:
    rows = sb_select("customers", order="-created_at")
    df_c = to_df(rows)
    if df_c.empty:
        st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
    else:
        search = st.text_input("🔍 検索（名前・メール・ユーザー名）")
        if search:
            mask = df_c.apply(lambda r: search.lower() in str(r.get("name","")).lower()
                              or search.lower() in str(r.get("email","")).lower()
                              or search.lower() in str(r.get("username","")).lower(), axis=1)
            df_c = df_c[mask]
        st.caption(f"{len(df_c)}件")
        for _, row in df_c.iterrows():
            with st.expander(f"👤 {row['name']}　{PLATFORM_EMOJI.get(row.get('platform',''),'')} {row.get('platform','')}　📅 {str(row.get('created_at',''))[:10]}"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    st.markdown(f"**名前：** {row.get('name','')}")
                    st.markdown(f"**メール：** {row.get('email','') or '未登録'}")
                    st.markdown(f"**電話：** {row.get('phone','') or '未登録'}")
                    st.markdown(f"**SNSユーザー名：** {row.get('username','') or '未登録'}")
                with ec2:
                    st.markdown(f"**流入元：** {PLATFORM_EMOJI.get(row.get('platform',''),'')} {row.get('platform','')}")
                    st.markdown(f"**住所：** {row.get('address','') or '未登録'}")
                st.markdown("---")
                st.markdown("**📝 備考・メモ**")
                new_note = st.text_area("", value=row.get("note","") or "", key=f"cn_{row['id']}", height=100, label_visibility="collapsed")
                nc1, nc2, nc3, _ = st.columns([1,1,1,4])
                with nc1:
                    if st.button("💾 更新", key=f"cu_{row['id']}"):
                        sb_update("customers",{"note":new_note},{"id":row["id"]})
                        st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True)
                with nc2:
                    if st.button("↩ 取消", key=f"cc_{row['id']}"): st.rerun()
                with nc3:
                    if st.button("🗑 削除", key=f"cd_{row['id']}"): sb_delete("customers",{"id":row["id"]}); st.rerun()

# ── 購入履歴 ──────────────────────────────────────────────────────────────────
with tab_purchase:
    rows_c   = sb_select("customers", order="-created_at")
    df_all_c = to_df(rows_c)
    if df_all_c.empty:
        st.markdown('<div class="info-box">先に顧客を登録してください</div>', unsafe_allow_html=True)
    else:
        sel_c = st.selectbox("顧客を選択", df_all_c["name"].tolist(), key="pur_c")
        c_id  = int(df_all_c[df_all_c["name"]==sel_c]["id"].values[0])
        prod_type = st.selectbox("商品カテゴリ", BUSINESSES + ["（今後追加予定）"])

        # Tour
        if prod_type == "Tour":
            st.markdown('<div class="section-head">Tour 予約情報</div>', unsafe_allow_html=True)
            tc1, tc2 = st.columns(2)
            with tc1:
                tour_type    = st.selectbox("Tourの種類", TOUR_TYPES)
                tour_status  = st.selectbox("予約ステータス", TOUR_STATUSES)
                tour_date    = st.date_input("ツアー日時", value=date.today())
                meet_place   = st.text_input("合流場所")
                guide_name   = st.text_input("ガイド名")
            with tc2:
                participants = st.number_input("参加人数", min_value=1, value=1, step=1)
                price        = st.number_input("料金（¥）", min_value=0, value=0, step=1000)
                discount     = st.number_input("割引額（¥）", min_value=0, value=0, step=500)
                payment_type = st.selectbox("支払方法", PAYMENT_TYPES)
                receptionist = st.text_input("受付担当者名（予約者）")
                confirmed    = st.checkbox("✅ 内容確認（お客様サイン済み）")
            order_note = st.text_area("オーダーメモ・備考", height=60)
            if st.button("💾 Tour予約を保存"):
                sb_insert("purchases",{"customer_id":c_id,"product_type":"Tour","tour_type":tour_type,"tour_status":tour_status,"tour_date":str(tour_date),"meet_place":meet_place,"guide_name":guide_name,"participants":participants,"price":price,"discount":discount,"payment_type":payment_type,"receptionist":receptionist,"confirmed":confirmed,"order_note":order_note})
                st.markdown('<div class="success-box">✅ Tour予約を保存しました</div>', unsafe_allow_html=True)

        # Patreon
        elif prod_type == "Patreon":
            st.markdown('<div class="section-head">Patreon 情報</div>', unsafe_allow_html=True)
            pc1, pc2 = st.columns(2)
            with pc1:
                join_date   = st.date_input("入会日", value=date.today())
                plan        = st.text_input("プラン名")
            with pc2:
                cancel_date = st.date_input("解約日（未解約の場合は空欄）", value=None)
            if st.button("💾 Patreon情報を保存"):
                sb_insert("purchases",{"customer_id":c_id,"product_type":"Patreon","join_date":str(join_date),"plan":plan,"cancel_date":str(cancel_date) if cancel_date else None})
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

        # Guidebook
        elif prod_type == "Guidebook":
            st.markdown('<div class="section-head">Guidebook 情報</div>', unsafe_allow_html=True)
            gc1, gc2 = st.columns(2)
            with gc1:
                gb_name  = st.text_input("購入したガイドブック名")
                gb_date  = st.date_input("購入日", value=date.today())
            with gc2:
                gb_price  = st.number_input("金額（¥）", min_value=0, value=0, step=100)
                gb_cancel = st.checkbox("キャンセル済み")
            if st.button("💾 Guidebook購入を保存"):
                sb_insert("purchases",{"customer_id":c_id,"product_type":"Guidebook","guidebook_name":gb_name,"purchase_date":str(gb_date),"price":gb_price,"cancelled":gb_cancel})
                st.markdown('<div class="success-box">✅ 保存しました</div>', unsafe_allow_html=True)

        # 購入履歴一覧
        st.markdown('<div class="section-head">購入履歴一覧</div>', unsafe_allow_html=True)
        rows_p = sb_select("purchases", filters={"customer_id":c_id}, order="-created_at")
        df_p   = to_df(rows_p)
        if df_p.empty:
            st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
        else:
            for _, row in df_p.iterrows():
                pt = row.get("product_type","")
                if pt == "Tour":
                    status_color = {"仮予約":"#d97706","ガイド手配中":"#2563eb","カメラマン手配中":"#7c3aed","確定":"#15803d","料金回収済み":"#059669","キャンセル":"#dc2626"}.get(row.get("tour_status",""),"#6b7280")
                    with st.expander(f"🗺 {row.get('tour_type','')}　{row.get('tour_date','')}　¥{int(row.get('price',0)):,}（割引:¥{int(row.get('discount',0)):,}）　{row.get('participants','')}名"):
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            st.markdown(f"**予約ステータス：** <span style='color:{status_color};font-weight:600;'>{row.get('tour_status','')}</span>", unsafe_allow_html=True)
                            st.markdown(f"**合流場所：** {row.get('meet_place','')}")
                            st.markdown(f"**ガイド名：** {row.get('guide_name','')}")
                        with dc2:
                            st.markdown(f"**支払方法：** {row.get('payment_type','')}")
                            st.markdown(f"**受付担当：** {row.get('receptionist','')}")
                            st.markdown(f"**内容確認：** {'✅ サイン済み' if row.get('confirmed') else '⬜ 未確認'}")
                        if row.get("order_note"):
                            st.markdown(f"**メモ：** {row.get('order_note','')}")
                        new_status = st.selectbox("ステータスを変更", TOUR_STATUSES,
                            index=TOUR_STATUSES.index(row.get("tour_status","仮予約")) if row.get("tour_status","") in TOUR_STATUSES else 0,
                            key=f"ts_{row['id']}")
                        us1, us2 = st.columns([1,6])
                        with us1:
                            if st.button("更新", key=f"tsu_{row['id']}"):
                                sb_update("purchases",{"tour_status":new_status},{"id":row["id"]})
                                st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True); st.rerun()
                        with us2:
                            if st.button("🗑 削除", key=f"pd_{row['id']}"): sb_delete("purchases",{"id":row["id"]}); st.rerun()
                elif pt == "Patreon":
                    with st.expander(f"🎁 Patreon　{row.get('plan','')}　入会:{row.get('join_date','')}　解約:{row.get('cancel_date','') or '継続中'}"):
                        if st.button("🗑 削除", key=f"pd_{row['id']}"): sb_delete("purchases",{"id":row["id"]}); st.rerun()
                else:
                    with st.expander(f"📖 {row.get('guidebook_name','')}　{row.get('purchase_date','')}　¥{int(row.get('price',0)):,}　{'キャンセル済み' if row.get('cancelled') else ''}"):
                        if st.button("🗑 削除", key=f"pd_{row['id']}"): sb_delete("purchases",{"id":row["id"]}); st.rerun()
