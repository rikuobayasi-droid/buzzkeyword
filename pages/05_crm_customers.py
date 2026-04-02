"""
pages/05_crm_customers.py — 顧客管理
修正1: 購入済み判定を purchases + patreon_subscriptions の両方から行う
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

def get_platforms() -> list:
    rows = sb_select("platform_master", order="name")
    df   = to_df(rows)
    if df.empty:
        return ["Instagram","Facebook","TikTok","YouTube",
                "Threads","X","LINE","WhatsApp","Gmail","Patreon","その他"]
    return df["name"].tolist()

def fmt_time(t) -> str:
    if t is None: return ""
    return str(t)[:5]

def parse_time(s) -> time_type:
    try:
        parts = str(s)[:5].split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except Exception:
        return time_type(0, 0)

def time_str_to_hour(s):
    try:    return int(str(s)[:2])
    except: return None

def posting_window(peak_hour: int) -> str:
    start = (peak_hour - 3) % 24
    end   = (peak_hour - 2) % 24
    return f"{start:02d}:00〜{end:02d}:00"

def time_pattern(peak_hour: int) -> str:
    if   20 <= peak_hour or peak_hour < 3:  return "夜型（SNS活発時間帯）"
    elif 11 <= peak_hour <= 14:              return "昼型（ランチタイム）"
    elif  6 <= peak_hour <= 10:              return "朝型（通勤時間帯）"
    elif 15 <= peak_hour <= 19:              return "夕方型（帰宅時間帯）"
    else:                                    return "深夜型"

# 修正3: 曜日を英語・Sun始まりで定義
# pandas の weekday: 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
# 表示順: Sun, Mon, Tue, Wed, Thu, Fri, Sat
WEEKDAY_EN_ORDER = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
# pandas weekday(0=Mon) → 英語ラベル変換テーブル
WEEKDAY_PD_TO_EN = {0:"Mon", 1:"Tue", 2:"Wed", 3:"Thu", 4:"Fri", 5:"Sat", 6:"Sun"}

# ── 修正1: 購入済み顧客IDを両テーブルから取得 ─────────────────────────────────
def get_buyer_ids() -> set:
    """
    購入済み判定: purchases OR patreon_subscriptions に存在する顧客ID
    Patreonユーザーが「未購入」にならないようにする
    """
    buyer_ids = set()
    # purchases から
    rows_p = sb_select("purchases", order="-purchase_date")
    df_p   = to_df(rows_p)
    if not df_p.empty and "customer_id" in df_p.columns:
        buyer_ids.update(df_p["customer_id"].dropna().astype(int).tolist())
    # patreon_subscriptions から（修正1の核心）
    rows_s = sb_select("patreon_subscriptions", order="-start_date")
    df_s   = to_df(rows_s)
    if not df_s.empty and "customer_id" in df_s.columns:
        buyer_ids.update(df_s["customer_id"].dropna().astype(int).tolist())
    return buyer_ids

# ── 分析: 両テーブルを統合した仮想購入データ ─────────────────────────────────
def get_all_purchase_categories(customer_id: int, df_p: pd.DataFrame,
                                df_s: pd.DataFrame, df_prods: pd.DataFrame) -> list:
    """
    顧客の購入カテゴリー一覧を purchases + patreon_subscriptions から取得
    """
    categories = []
    if not df_p.empty and not df_prods.empty:
        cust_p = df_p[df_p["customer_id"] == customer_id]
        if not cust_p.empty:
            merged = cust_p.merge(df_prods[["id","category"]].rename(columns={"id":"product_id"}),
                                  on="product_id", how="left")
            categories.extend(merged["category"].dropna().tolist())
    if not df_s.empty:
        cust_s = df_s[df_s["customer_id"] == customer_id]
        if not cust_s.empty:
            categories.extend(["Patreon"] * len(cust_s))
    return list(set(categories))

@st.cache_data(ttl=300)
def load_analysis_data():
    rows_c  = sb_select("customers",             order="-created_at")
    rows_p  = sb_select("purchases",             order="-purchase_date")
    rows_pr = sb_select("products",              order="name")
    rows_s  = sb_select("patreon_subscriptions", order="-start_date")
    return to_df(rows_c), to_df(rows_p), to_df(rows_pr), to_df(rows_s)

def render_analysis():
    df_c, df_p, df_prods, df_s = load_analysis_data()
    if df_c.empty:
        st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
        return

    df_c = df_c.copy()
    df_c["hour"] = df_c["contact_time"].apply(time_str_to_hour)
    df_c_valid   = df_c.dropna(subset=["hour"]).copy()
    df_c_valid["hour"] = df_c_valid["hour"].astype(int)
    df_c_valid["weekday"] = pd.to_datetime(
        df_c_valid["contact_date"].astype(str).str[:10], errors="coerce"
    ).dt.weekday

    # 修正1: 購入済みIDを両テーブルから取得
    buyer_ids_p = set(df_p["customer_id"].dropna().astype(int).tolist()) if not df_p.empty else set()
    buyer_ids_s = set(df_s["customer_id"].dropna().astype(int).tolist()) if not df_s.empty else set()
    buyer_ids   = buyer_ids_p | buyer_ids_s  # 和集合

    # 顧客ごとの購入カテゴリー（purchases + patreon_subscriptions 統合）
    def get_first_category(cid):
        cats = []
        if not df_p.empty and not df_prods.empty:
            cp = df_p[df_p["customer_id"] == cid]
            if not cp.empty:
                merged = cp.merge(df_prods[["id","category"]].rename(columns={"id":"product_id"}),
                                  on="product_id", how="left")
                cats.extend(merged["category"].dropna().tolist())
        if not df_s.empty:
            cs = df_s[df_s["customer_id"] == cid]
            if not cs.empty:
                cats.extend(["Patreon"] * len(cs))
        return cats[0] if cats else "未購入"

    df_c_valid["product_category"] = df_c_valid["id"].apply(get_first_category)

    # ── グラフ① 時間帯×カテゴリー ────────────────────────────────────────────
    st.markdown('<div class="section-head">時間帯 × カテゴリー別 問い合わせ数</div>', unsafe_allow_html=True)
    hour_cat = df_c_valid.groupby(["hour","product_category"]).size().reset_index(name="count")
    if not hour_cat.empty:
        pivot_hc = hour_cat.pivot(index="hour", columns="product_category", values="count").fillna(0)
        pivot_hc = pivot_hc.reindex(range(24), fill_value=0)
        st.bar_chart(pivot_hc)

    # ── グラフ② ヒートマップ ─────────────────────────────────────────────────
    st.markdown('<div class="section-head">ヒートマップ（カテゴリー × 時間帯）</div>', unsafe_allow_html=True)
    if not hour_cat.empty:
        heatmap = hour_cat.pivot(index="product_category", columns="hour", values="count").fillna(0).astype(int)
        heatmap.columns = [f"{h:02d}時" for h in heatmap.columns]
        st.dataframe(heatmap, use_container_width=True)

    # ── カテゴリー別ピーク + 投稿推奨 ────────────────────────────────────────
    st.markdown('<div class="section-head">カテゴリー別 ピーク時間 & 投稿推奨時間</div>', unsafe_allow_html=True)
    for cat in sorted(df_c_valid["product_category"].unique()):
        df_cat = df_c_valid[df_c_valid["product_category"] == cat]
        if df_cat.empty: continue
        peak = int(df_cat["hour"].value_counts().idxmax())
        st.markdown(
            f'<div class="metric-card" style="margin-bottom:.5rem;">'
            f'<div style="font-weight:700;color:#1e3a5f;">{cat}</div>'
            f'<div style="font-size:.88rem;margin-top:.3rem;">'
            f'ピーク: <strong>{peak:02d}:00</strong> &nbsp; '
            f'投稿推奨: <strong>{posting_window(peak)}</strong> &nbsp; '
            f'分布特性: <strong>{time_pattern(peak)}</strong>'
            f'</div></div>', unsafe_allow_html=True)

    if not df_c_valid.empty:
        all_peak = int(df_c_valid["hour"].value_counts().idxmax())
        st.markdown(f'<div class="success-box">全体ピーク: <strong>{all_peak:02d}:00</strong> &nbsp; 投稿推奨: <strong>{posting_window(all_peak)}</strong></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── 曜日別 ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">曜日別 × カテゴリー別</div>', unsafe_allow_html=True)
    df_wd = df_c_valid.dropna(subset=["weekday"]).copy()
    if not df_wd.empty:
        # 修正1: pd.Categorical で Sun,Mon,...,Sat 順を強制
        df_wd["weekday_en"] = df_wd["weekday"].astype(int).map(WEEKDAY_PD_TO_EN)
        df_wd["weekday_en"] = pd.Categorical(
            df_wd["weekday_en"],
            categories=WEEKDAY_EN_ORDER,
            ordered=True
        )
        wd_cat = df_wd.groupby(["weekday_en","product_category"], observed=False).size().reset_index(name="count")
        if not wd_cat.empty:
            pivot_wd = wd_cat.pivot(index="weekday_en", columns="product_category", values="count").fillna(0)
            pivot_wd = pivot_wd.reindex(WEEKDAY_EN_ORDER).fillna(0)
            st.bar_chart(pivot_wd)

    # ── 修正4: プラットフォーム別分析（棒グラフ + テーブル）────────────────
    st.markdown('<div class="section-head">プラットフォーム別 問い合わせ数（多い順）</div>', unsafe_allow_html=True)
    plat_total = df_c_valid.groupby("platform").size().reset_index(name="DM数")
    if not plat_total.empty:
        total_cnt  = int(plat_total["DM数"].sum())
        plat_total = plat_total.sort_values("DM数", ascending=False)
        plat_total["割合(%)"] = (plat_total["DM数"] / total_cnt * 100).round(1)
        st.bar_chart(plat_total.set_index("platform")["DM数"])
        st.dataframe(
            plat_total.rename(columns={"platform":"プラットフォーム"}).reset_index(drop=True),
            use_container_width=True, hide_index=True
        )

    # ── 修正2: プラットフォーム × 商品カテゴリー クロス集計 ──────────────────
    st.markdown('<div class="section-head">プラットフォーム × 商品カテゴリー（どのSNSから何が売れているか）</div>', unsafe_allow_html=True)
    # purchases と patreon_subscriptions を統合
    cross_rows = []
    if not df_p.empty and not df_prods.empty:
        df_p_cat = df_p.merge(
            df_prods[["id","category"]].rename(columns={"id":"product_id"}),
            on="product_id", how="left"
        )
        for _, row in df_p_cat.iterrows():
            cid_val = row.get("customer_id")
            if cid_val is None: continue
            cust_match = df_c[df_c["id"] == cid_val]
            if cust_match.empty: continue
            plat = cust_match.iloc[0].get("platform","不明")
            cat  = row.get("category","その他")
            cross_rows.append({"platform": plat, "category": cat})
    if not df_s.empty:
        for _, row in df_s.iterrows():
            cid_val = row.get("customer_id")
            if cid_val is None: continue
            cust_match = df_c[df_c["id"] == cid_val]
            if cust_match.empty: continue
            plat = cust_match.iloc[0].get("platform","不明")
            cross_rows.append({"platform": plat, "category": "Patreon"})
    if cross_rows:
        df_cross = pd.DataFrame(cross_rows)
        cross_pivot = df_cross.groupby(["platform","category"]).size().reset_index(name="購入数")
        cross_table = cross_pivot.pivot(index="platform", columns="category", values="購入数").fillna(0).astype(int)
        cross_table["合計"] = cross_table.sum(axis=1)
        cross_table = cross_table.sort_values("合計", ascending=False)
        # テーブル表示
        st.dataframe(cross_table, use_container_width=True)
        # 積み上げ棒グラフ
        st.bar_chart(cross_table.drop(columns=["合計"]))
    else:
        st.caption("購入データが増えると表示されます")

    # ── 購入者ベース（修正1: buyer_ids に Patreon 含む）────────────────────
    st.markdown('<div class="section-head">購入者ベース分析（purchases + Patreon含む）</div>', unsafe_allow_html=True)
    df_buyers = df_c_valid[df_c_valid["id"].isin(buyer_ids)]
    if df_buyers.empty:
        st.caption("購入データがある顧客が増えると表示されます")
    else:
        buyer_cat = df_buyers.groupby(["hour","product_category"]).size().reset_index(name="count")
        if not buyer_cat.empty:
            pivot_bc = buyer_cat.pivot(index="hour",columns="product_category",values="count").fillna(0)
            pivot_bc = pivot_bc.reindex(range(24), fill_value=0)
            st.bar_chart(pivot_bc)
        if not df_buyers.empty:
            b_peak = int(df_buyers["hour"].value_counts().idxmax())
            st.markdown(f'<div class="success-box">購入者ピーク: <strong>{b_peak:02d}:00</strong> &nbsp; 推奨投稿: <strong>{posting_window(b_peak)}</strong></div>', unsafe_allow_html=True)

    # ── CVR（修正1: Patreon含む） ─────────────────────────────────────────────
    st.markdown('<div class="section-head">コンバージョン分析</div>', unsafe_allow_html=True)
    total_inq   = len(df_c)
    total_buyer = len(buyer_ids & set(df_c["id"].tolist()))
    cvr         = round(total_buyer / total_inq * 100, 1) if total_inq > 0 else 0
    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{total_inq}</div><div class="lbl">総問い合わせ数</div></div>
      <div class="metric-card"><div class="val">{total_buyer}</div><div class="lbl">購入顧客数（Patreon含む）</div></div>
      <div class="metric-card"><div class="val">{cvr}%</div><div class="lbl">CVR</div></div>
    </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# メインページ
# ════════════════════════════════════════════════════════
sel_id = st.session_state.get("selected_customer_id")

if sel_id:
    rows_c   = sb_select("customers", order="-created_at")
    df_all_c = to_df(rows_c)
    if df_all_c.empty or sel_id not in df_all_c["id"].values:
        st.session_state.pop("selected_customer_id", None); st.rerun()

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

    with tab_hist:
        rows_p   = sb_select("products", order="name")
        df_prods = to_df(rows_p)
        df_prods_non_pat = df_prods[df_prods["category"] != "Patreon"] if not df_prods.empty and "category" in df_prods.columns else df_prods
        prod_names = df_prods_non_pat["name"].tolist() if not df_prods_non_pat.empty else []

        st.markdown('<div class="info-box">Patreonサブスクリプションは「Patreon管理」ページで管理してください</div>', unsafe_allow_html=True)

        editing_id = st.session_state.get("editing_purchase_id")
        edit_data  = {}
        if editing_id:
            rows_edit = sb_select("purchases", filters={"id": editing_id})
            df_edit   = to_df(rows_edit)
            if not df_edit.empty: edit_data = df_edit.iloc[0].to_dict()

        form_title = f"購入を編集（ID: {editing_id}）" if editing_id else "購入を追加"
        st.markdown(f'<div class="section-head">{form_title}</div>', unsafe_allow_html=True)
        if editing_id:
            if st.button("キャンセル", key="cancel_edit"):
                st.session_state.pop("editing_purchase_id", None); st.rerun()

        if prod_names:
            with st.form(key=f"purchase_form_{cid}_{editing_id or 'new'}"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    default_prod_idx = 0
                    if edit_data.get("product_id"):
                        m = df_prods_non_pat[df_prods_non_pat["id"] == edit_data["product_id"]]
                        if not m.empty and m.iloc[0]["name"] in prod_names:
                            default_prod_idx = prod_names.index(m.iloc[0]["name"])
                    h_prod_name = st.selectbox("商品を選択 *", prod_names, index=default_prod_idx, key=f"h_prod_{cid}")
                    h_date = st.date_input("購入日",
                        value=date.fromisoformat(str(edit_data.get("purchase_date",""))[:10]) if edit_data.get("purchase_date") else date.today(),
                        key=f"h_date_{cid}")
                with fc2:
                    h_amount  = st.number_input("支払額（¥）", min_value=0, value=int(edit_data.get("amount",0) or 0), step=100, key=f"h_amt_{cid}")
                    h_payment = st.selectbox("支払方法", PAYMENT_TYPES,
                        index=PAYMENT_TYPES.index(edit_data.get("payment_type","現金")) if edit_data.get("payment_type","") in PAYMENT_TYPES else 0,
                        key=f"h_pay_{cid}")

                matched_prod = df_prods_non_pat[df_prods_non_pat["name"] == h_prod_name]
                is_tour      = not matched_prod.empty and matched_prod.iloc[0].get("category","") == "Tour"
                h_tour_status = h_guide = h_meet = h_receptionist = h_order_note = h_note = ""
                h_participants = 1; h_confirmed = False

                if is_tour:
                    st.markdown("**ツアー詳細**")
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        h_tour_status = st.selectbox("予約ステータス", TOUR_STATUSES,
                            index=TOUR_STATUSES.index(edit_data.get("tour_status","仮予約")) if edit_data.get("tour_status","") in TOUR_STATUSES else 0,
                            key=f"h_status_{cid}")
                        h_meet  = st.text_input("合流場所",  value=edit_data.get("meet_place","") or "", key=f"h_meet_{cid}")
                        h_guide = st.text_input("ガイド名",  value=edit_data.get("guide_name","") or "", key=f"h_guide_{cid}")
                    with tc2:
                        h_participants = st.number_input("参加人数", min_value=1, value=int(edit_data.get("participants",1) or 1), key=f"h_pax_{cid}")
                        h_receptionist = st.text_input("受付担当者", value=edit_data.get("receptionist","") or "", key=f"h_recep_{cid}")
                        h_confirmed    = st.checkbox("内容確認済み", value=bool(edit_data.get("confirmed",False)), key=f"h_conf_{cid}")
                    h_order_note = st.text_area("オーダーメモ", value=edit_data.get("order_note","") or "", height=60, key=f"h_order_{cid}")
                else:
                    h_receptionist = st.text_input("受付担当者",   value=edit_data.get("receptionist","") or "", key=f"h_recep_{cid}")
                    h_order_note   = st.text_input("オーダーメモ", value=edit_data.get("order_note","") or "",   key=f"h_order_{cid}")

                h_note    = st.text_area("備考", value=edit_data.get("note","") or "", height=60, key=f"h_note_{cid}")
                submitted = st.form_submit_button("更新する" if editing_id else "保存する")

                if submitted:
                    prod_id  = int(matched_prod.iloc[0]["id"]) if not matched_prod.empty else None
                    category = matched_prod.iloc[0].get("category","") if not matched_prod.empty else ""
                    payload  = {
                        "customer_id":   cid, "product_id": prod_id, "product_type": category,
                        "purchase_date": str(h_date), "amount": h_amount, "payment_type": h_payment,
                        "note": h_note, "order_note": h_order_note, "receptionist": h_receptionist,
                        "tour_status":  h_tour_status  if is_tour else None,
                        "meet_place":   h_meet         if is_tour else None,
                        "guide_name":   h_guide        if is_tour else None,
                        "participants": h_participants if is_tour else 1,
                        "confirmed":    h_confirmed    if is_tour else False,
                    }
                    if editing_id:
                        ok = sb_update("purchases", payload, {"id": editing_id})
                        if ok: st.session_state.pop("editing_purchase_id", None); st.rerun()
                        else:  st.error("更新に失敗しました")
                    else:
                        res = sb_insert("purchases", payload)
                        if res: st.rerun()
                        else:   st.error("保存に失敗しました")

        st.markdown('<div class="section-head">購入履歴一覧</div>', unsafe_allow_html=True)
        rows_pur = sb_select("purchases", filters={"customer_id": cid}, order="-purchase_date")
        df_pur   = to_df(rows_pur)
        if df_pur.empty:
            st.markdown('<div class="info-box">購入履歴がありません</div>', unsafe_allow_html=True)
        else:
            if not df_prods.empty:
                df_pur = df_pur.merge(df_prods[["id","name","category"]].rename(columns={"id":"product_id","name":"product_name","category":"product_category"}), on="product_id", how="left")
            else:
                df_pur["product_name"] = df_pur.get("product_type",""); df_pur["product_category"] = df_pur.get("product_type","")
            for col in ["amount","participants"]:
                if col not in df_pur.columns: df_pur[col] = 0
            for _, row in df_pur.iterrows():
                rid = int(row["id"]); prod_d = row.get("product_name") or row.get("product_type",""); cat_d = row.get("product_category",""); amt_d = int(row.get("amount",0))
                with st.expander(f"{row.get('purchase_date','')}  {prod_d}  ¥{amt_d:,}"):
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(f"**商品:** {prod_d}"); st.markdown(f"**支払額:** ¥{amt_d:,}"); st.markdown(f"**支払方法:** {row.get('payment_type','')}")
                        if row.get("note"): st.markdown(f"**備考:** {row.get('note','')}")
                    with rc2:
                        if cat_d == "Tour":
                            sc = row.get("tour_status","")
                            sc_col = {"仮予約":"#d97706","ガイド手配中":"#2563eb","カメラマン手配中":"#7c3aed","確定":"#15803d","料金回収済み":"#059669","キャンセル":"#dc2626"}.get(sc,"#6b7280")
                            st.markdown(f"**ステータス:** <span style='color:{sc_col};font-weight:600;'>{sc}</span>", unsafe_allow_html=True)
                            st.markdown(f"**合流場所:** {row.get('meet_place','')}"); st.markdown(f"**ガイド名:** {row.get('guide_name','')}"); st.markdown(f"**参加人数:** {int(row.get('participants',1))}名")
                        if row.get("receptionist"): st.markdown(f"**受付担当:** {row.get('receptionist','')}")
                        if row.get("order_note"):   st.markdown(f"**オーダーメモ:** {row.get('order_note','')}")
                    if cat_d == "Tour":
                        cur_s = row.get("tour_status","仮予約"); idx_s = TOUR_STATUSES.index(cur_s) if cur_s in TOUR_STATUSES else 0
                        new_s = st.selectbox("ステータス変更", TOUR_STATUSES, index=idx_s, key=f"ts_{rid}")
                        uc1, uc2, uc3 = st.columns([1,1,5])
                        with uc1:
                            if st.button("更新", key=f"tsu_{rid}"): sb_update("purchases",{"tour_status":new_s},{"id":rid}); st.rerun()
                        with uc2:
                            if st.button("編集", key=f"pur_edit_{rid}"): st.session_state["editing_purchase_id"] = rid; st.rerun()
                    else:
                        uc1, uc2 = st.columns([1,5])
                        with uc1:
                            if st.button("編集", key=f"pur_edit_{rid}"): st.session_state["editing_purchase_id"] = rid; st.rerun()
                    if st.button("削除", key=f"pur_del_{rid}"):
                        sb_delete("purchases",{"id":rid}); st.session_state.pop("editing_purchase_id",None); st.rerun()

    with tab_info:
        platforms = get_platforms()
        ic1, ic2  = st.columns(2)
        with ic1:
            new_name     = st.text_input("名前",          value=cust.get("name",""),          key=f"inf_name_{cid}")
            new_email    = st.text_input("メール",        value=cust.get("email","") or "",    key=f"inf_email_{cid}")
            new_phone    = st.text_input("電話番号",      value=cust.get("phone","") or "",    key=f"inf_phone_{cid}")
            new_username = st.text_input("SNSユーザー名", value=cust.get("username","") or "", key=f"inf_uname_{cid}")
        with ic2:
            plat_val = cust.get("platform","その他"); plat_idx = platforms.index(plat_val) if plat_val in platforms else len(platforms)-1
            new_platform = st.selectbox("流入プラットフォーム", platforms, index=plat_idx, key=f"inf_plat_{cid}")
            new_address  = st.text_input("住所", value=cust.get("address","") or "", key=f"inf_addr_{cid}")
        ct1, ct2 = st.columns(2)
        with ct1:
            try:    default_cdate = date.fromisoformat(str(cust.get("contact_date",""))[:10]) if cust.get("contact_date") else date.today()
            except: default_cdate = date.today()
            contact_date = st.date_input("初回お問い合わせ日", value=default_cdate, key=f"inf_cdate_{cid}")
        with ct2:
            contact_time = st.time_input("初回お問い合わせ時間", value=parse_time(cust.get("contact_time")), key=f"inf_ctime_{cid}")
        new_note = st.text_area("備考・メモ", value=cust.get("note","") or "", height=100, key=f"inf_note_{cid}")
        nc1, nc2, nc3 = st.columns([1,1,1])
        with nc1:
            if st.button("更新", key=f"inf_upd_{cid}"):
                sb_update("customers",{"name":new_name,"email":new_email,"phone":new_phone,"username":new_username,"platform":new_platform,"address":new_address,"note":new_note,"contact_date":str(contact_date),"contact_time":fmt_time(contact_time)},{"id":cid})
                st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
        with nc2:
            if st.button("取消", key=f"inf_cancel_{cid}"): st.rerun()
        with nc3:
            if st.button("この顧客を削除", key=f"inf_del_{cid}"):
                sb_delete("customers",{"id":cid}); st.session_state.pop("selected_customer_id",None); st.rerun()

else:
    st.markdown('<div class="page-title">顧客管理</div>', unsafe_allow_html=True)
    tab_reg, tab_list, tab_analysis, tab_points = st.tabs(["新規登録", "顧客一覧", "分析", "ポイント管理"])

    with tab_reg:
        platforms = get_platforms()
        rc1, rc2  = st.columns(2)
        with rc1:
            c_name = st.text_input("名前 *", key="new_name"); c_email = st.text_input("メールアドレス", key="new_email")
            c_phone = st.text_input("電話番号", key="new_phone"); c_username = st.text_input("SNSユーザー名", key="new_uname")
        with rc2:
            c_platform = st.selectbox("流入プラットフォーム", platforms, key="new_plat")
            c_address  = st.text_input("住所（任意）", key="new_addr"); c_note = st.text_area("備考", height=80, key="new_note")
        nc1, nc2 = st.columns(2)
        with nc1: c_contact_date = st.date_input("初回お問い合わせ日", value=date.today(), key="new_cdate")
        with nc2: c_contact_time = st.time_input("初回お問い合わせ時間", value=time_type(0,0), key="new_ctime")
        if st.button("顧客を登録する", key="new_submit"):
            if not c_name: st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("customers",{"name":c_name,"email":c_email,"phone":c_phone,"username":c_username,"platform":c_platform,"address":c_address,"note":c_note,"contact_date":str(c_contact_date),"contact_time":fmt_time(c_contact_time)})
                if res: st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)

    with tab_list:
        platforms = get_platforms()
        sc1, sc2, sc3 = st.columns(3)
        with sc1: s_name = st.text_input("名前で検索", key="lst_sname")
        with sc2: s_plat = st.selectbox("プラットフォーム", ["すべて"]+platforms, key="lst_splat")
        with sc3: s_date = st.text_input("利用日 (YYYY-MM-DD)", placeholder="例: 2026-01-15", key="lst_sdate")
        rows = sb_select("customers", order="-created_at"); df_c = to_df(rows)
        if df_c.empty:
            st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
        else:
            df_show = df_c.copy()
            if s_name: df_show = df_show[df_show["name"].str.contains(s_name,case=False,na=False)]
            if s_plat != "すべて": df_show = df_show[df_show["platform"]==s_plat]
            if s_date:
                rows_pur = sb_select("purchases",order="-purchase_date"); df_pur = to_df(rows_pur)
                if not df_pur.empty:
                    mc = df_pur[df_pur["purchase_date"].astype(str).str.startswith(s_date)]["customer_id"].unique()
                    df_show = df_show[df_show["id"].isin(mc)]
            st.caption(f"{len(df_show)}件")
            for _, row in df_show.iterrows():
                rid = int(row["id"])
                pts = int(row.get("total_points", 0) or 0)
                lc1,lc2,lc3,lc4,lc5,lc6 = st.columns([3,2,2,1.5,1.5,1])
                with lc1:
                    if st.button(row["name"], key=f"lst_go_{rid}"):
                        st.session_state["selected_customer_id"] = rid; st.rerun()
                with lc2: st.markdown(f"`{row.get('platform','')}`")
                with lc3: st.caption(str(row.get("created_at",""))[:10])
                with lc4: st.caption(f"🎯 {pts:,}pt")
                with lc5:
                    if row.get("contact_date"): st.caption(f"問合: {str(row.get('contact_date',''))[:10]}")
                with lc6:
                    if st.button("削除", key=f"lst_del_{rid}"):
                        sb_delete("customers",{"id":rid}); st.rerun()

    with tab_analysis:
        render_analysis()

    # ── ポイント管理タブ ──────────────────────────────────────────────────────
    with tab_points:
        st.markdown('<div class="section-head">ポイント管理（5%還元制度）</div>', unsafe_allow_html=True)
        st.caption("購入金額の5%をポイントとして付与。RPCを通じて安全に操作します。")

        # 顧客データ取得
        df_pts = to_df(sb_select("customers", order="name"))
        if df_pts.empty:
            st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
            st.stop()

        # total_points が存在しない場合の対応
        if "total_points" not in df_pts.columns:
            df_pts["total_points"] = 0
        df_pts["total_points"] = pd.to_numeric(df_pts["total_points"], errors="coerce").fillna(0).astype(int)

        pt_sub1, pt_sub2, pt_sub3 = st.tabs(["ポイント一覧", "ポイント付与", "ポイント譲渡"])

        # ── ポイント一覧 ──────────────────────────────────────────────────────
        with pt_sub1:
            st.markdown('<div class="section-head">顧客別ポイント残高</div>', unsafe_allow_html=True)

            # ポイントランキング表示
            df_rank = df_pts[["id","name","platform","total_points"]].copy()
            df_rank = df_rank.sort_values("total_points", ascending=False)
            df_rank.columns = ["ID","名前","プラットフォーム","ポイント残高"]
            st.dataframe(df_rank, use_container_width=True, hide_index=True)

            # トランザクション履歴
            st.markdown('<div class="section-head">ポイント取引履歴（直近50件）</div>', unsafe_allow_html=True)
            rows_tx = sb_select("point_transactions", order="-created_at", limit=50)
            df_tx   = to_df(rows_tx)
            if not df_tx.empty:
                # 顧客名を結合
                df_tx = df_tx.merge(
                    df_pts[["id","name"]].rename(columns={"id":"user_id","name":"顧客名"}),
                    on="user_id", how="left"
                )
                TYPE_MAP = {
                    "earn":         "🎁 付与",
                    "spend":        "💳 利用",
                    "transfer_out": "📤 譲渡（送信）",
                    "transfer_in":  "📥 譲渡（受取）",
                    "expire":       "⏰ 期限切れ",
                    "admin":        "⚙️ 管理者調整",
                }
                df_tx["種別"] = df_tx["transaction_type"].map(TYPE_MAP).fillna(df_tx["transaction_type"])
                df_tx["増減"] = df_tx["amount"].apply(lambda x: f"+{int(x):,}" if int(x) > 0 else f"{int(x):,}")
                show_cols = ["顧客名","種別","増減","balance_after","description","created_at"]
                show_cols = [c for c in show_cols if c in df_tx.columns]
                st.dataframe(
                    df_tx[show_cols].rename(columns={
                        "balance_after":"取引後残高",
                        "description":"説明",
                        "created_at":"日時"
                    }).head(50),
                    use_container_width=True, hide_index=True
                )
            else:
                st.markdown('<div class="info-box">取引履歴がまだありません</div>', unsafe_allow_html=True)

        # ── ポイント付与 ──────────────────────────────────────────────────────
        with pt_sub2:
            st.markdown('<div class="section-head">購入ポイント付与（購入金額 × 5%）</div>', unsafe_allow_html=True)

            customer_opts = {f"{row['name']} (ID:{row['id']}, 現在:{int(row['total_points']):,}pt)": int(row["id"])
                             for _, row in df_pts.iterrows()}

            with st.form(key="earn_form"):
                sel_cust_earn = st.selectbox("顧客を選択", list(customer_opts.keys()), key="earn_cust")
                earn_amount   = st.number_input("購入金額（円）", min_value=0, value=0, step=100)
                earn_note     = st.text_input("備考（任意）")

                # プレビュー計算
                preview_pts = int(earn_amount * 0.05)
                st.markdown(
                    f'<div class="info-box">付与予定ポイント: <strong>{preview_pts:,}pt</strong>'
                    f'（{earn_amount:,}円 × 5%）</div>',
                    unsafe_allow_html=True
                )

                if st.form_submit_button("ポイントを付与する"):
                    if earn_amount <= 0:
                        st.markdown('<div class="err-box">購入金額を入力してください</div>', unsafe_allow_html=True)
                    elif preview_pts <= 0:
                        st.markdown('<div class="err-box">ポイント付与額が0以下です（最低20円以上の購入が必要）</div>', unsafe_allow_html=True)
                    else:
                        cid = customer_opts[sel_cust_earn]
                        try:
                            from db import get_client
                            result = get_client().rpc("earn_points", {
                                "p_customer_id":    cid,
                                "p_purchase_amount": earn_amount,
                                "p_description":    earn_note or None,
                            }).execute()
                            res_data = result.data
                            if isinstance(res_data, list): res_data = res_data[0]
                            if res_data and res_data.get("success"):
                                st.markdown(
                                    f'<div class="success-box">'
                                    f'✅ {int(res_data["points_added"]):,}pt 付与しました &nbsp; '
                                    f'残高: {int(res_data["balance_before"]):,}pt → '
                                    f'<strong>{int(res_data["balance_after"]):,}pt</strong>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                st.cache_data.clear()
                            else:
                                err = res_data.get("error","不明なエラー") if res_data else "レスポンスなし"
                                st.markdown(f'<div class="err-box">❌ エラー: {err}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.markdown(f'<div class="err-box">❌ RPC呼び出しエラー: {e}</div>', unsafe_allow_html=True)

        # ── ポイント譲渡 ──────────────────────────────────────────────────────
        with pt_sub3:
            st.markdown('<div class="section-head">ポイント譲渡（顧客間）</div>', unsafe_allow_html=True)
            st.caption("送信者のポイントを減算し、受信者へ加算します。残高不足の場合は失敗します。")

            customer_opts_tr = {f"{row['name']} (ID:{row['id']}, 残高:{int(row['total_points']):,}pt)": int(row["id"])
                                for _, row in df_pts.iterrows()}

            with st.form(key="transfer_form"):
                tr1, tr2 = st.columns(2)
                with tr1:
                    sel_sender   = st.selectbox("送信者（譲渡元）", list(customer_opts_tr.keys()), key="tr_sender")
                with tr2:
                    sel_receiver = st.selectbox("受信者（譲渡先）", list(customer_opts_tr.keys()), key="tr_receiver")

                tr_amount = st.number_input("譲渡ポイント数", min_value=1, value=100, step=10)
                tr_note   = st.text_input("備考（任意）")

                sender_id   = customer_opts_tr[sel_sender]
                receiver_id = customer_opts_tr[sel_receiver]
                sender_pts  = int(df_pts[df_pts["id"] == sender_id]["total_points"].values[0])

                st.markdown(
                    f'<div class="info-box">'
                    f'送信者残高: <strong>{sender_pts:,}pt</strong> &nbsp; '
                    f'譲渡後残高: <strong>{max(sender_pts - tr_amount, 0):,}pt</strong>'
                    f'{"（❌ 残高不足）" if tr_amount > sender_pts else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                if st.form_submit_button("ポイントを譲渡する"):
                    if sender_id == receiver_id:
                        st.markdown('<div class="err-box">送信者と受信者が同じです</div>', unsafe_allow_html=True)
                    elif tr_amount > sender_pts:
                        st.markdown(f'<div class="err-box">残高不足です（保有: {sender_pts:,}pt）</div>', unsafe_allow_html=True)
                    else:
                        try:
                            from db import get_client
                            result = get_client().rpc("transfer_points", {
                                "p_sender_id":   sender_id,
                                "p_receiver_id": receiver_id,
                                "p_amount":      tr_amount,
                                "p_description": tr_note or None,
                            }).execute()
                            res_data = result.data
                            if isinstance(res_data, list): res_data = res_data[0]
                            if res_data and res_data.get("success"):
                                sender_name   = sel_sender.split(" (")[0]
                                receiver_name = sel_receiver.split(" (")[0]
                                st.markdown(
                                    f'<div class="success-box">'
                                    f'✅ {tr_amount:,}pt 譲渡完了 &nbsp; '
                                    f'{sender_name}: <strong>{int(res_data["sender_balance"]):,}pt</strong> &nbsp; '
                                    f'{receiver_name}: <strong>{int(res_data["receiver_balance"]):,}pt</strong>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                st.cache_data.clear()
                            else:
                                err = res_data.get("error","不明なエラー") if res_data else "レスポンスなし"
                                st.markdown(f'<div class="err-box">❌ エラー: {err}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.markdown(f'<div class="err-box">❌ RPC呼び出しエラー: {e}</div>', unsafe_allow_html=True)
