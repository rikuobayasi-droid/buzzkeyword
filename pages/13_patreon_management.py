"""
pages/13_patreon_management.py — Patreon管理（完全修正版）

修正1: patreon_plans.name → plan_name に修正
修正2: DB取得エラー解消
修正3: サブスク管理項目追加（cancel_date対応）
修正4: MRR分析機能（検索・前月比・前年比）
修正5: DuplicateElementKey 解消（keyにenumerate indexを付与）

MRR計算ロジック:
  - start_date <= 対象月末
  - cancel_date が NULL または cancel_date の翌月以降が対象月
  例: cancel_date=2026-03-15 → 2026-04以降はMRRに含めない
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

PAYMENT_METHODS = ["クレジットカード", "PayPal", "銀行振込", "その他"]

# ── ヘルパー ──────────────────────────────────────────────────────────────────
def next_billing(start_str: str) -> str:
    try:
        d = date.fromisoformat(str(start_str)[:10])
        return str(d.replace(month=d.month % 12 + 1,
                              year=d.year + (1 if d.month == 12 else 0)))
    except Exception:
        return str(date.today() + timedelta(days=30))

def safe_date(val) -> str:
    """任意の値を YYYY-MM-DD 文字列に変換。失敗したら空文字"""
    if val is None: return ""
    try:
        import pandas as pd
        if pd.isna(val): return ""
    except Exception:
        pass
    s = str(val).strip().lower()
    if s in ("", "none", "null", "nat", "nan"): return ""
    return str(val)[:10]

def is_active_sub(row) -> bool:
    """
    契約中判定:
      cancel_date が NULL/空 → 契約中
      cancel_date がある    → end_date（後方互換）も確認
    """
    cancel = safe_date(row.get("cancel_date"))
    end    = safe_date(row.get("end_date"))
    # cancel_date が優先、なければ end_date を参照
    effective_end = cancel or end
    return effective_end == ""

def calc_mrr(df_subs: pd.DataFrame, year_month: str) -> int:
    """
    指定月のMRRを計算
    ロジック:
      - start_date <= 対象月末日
      - cancel_date が空 OR cancel_dateの翌月以降が対象月
        例: cancel_date=2026-03-15 → 2026-03まではMRRに含む、2026-04以降は除外
    """
    if df_subs.empty: return 0
    try:
        y, m    = int(year_month[:4]), int(year_month[5:7])
        m_start = f"{year_month}-01"
        m_end   = f"{year_month}-{monthrange(y, m)[1]:02d}"
    except Exception:
        return 0

    total = 0
    for _, row in df_subs.iterrows():
        s = safe_date(row.get("start_date"))
        if not s or s > m_end:
            continue

        # cancel_dateがある場合: 翌月から除外
        cancel = safe_date(row.get("cancel_date")) or safe_date(row.get("end_date"))
        if cancel:
            try:
                cd = date.fromisoformat(cancel)
                # 翌月の1日を計算
                next_m = cd.replace(
                    year=cd.year + (1 if cd.month == 12 else 0),
                    month=cd.month % 12 + 1,
                    day=1
                )
                # 対象月の1日が翌月以降なら除外
                if date.fromisoformat(m_start) >= next_m:
                    continue
            except Exception:
                pass

        try:
            total += int(row.get("monthly_price", 0) or 0)
        except Exception:
            pass
    return total

def add_months(d: date, n: int) -> date:
    m = d.month + n
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return d.replace(year=y, month=m, day=1)

@st.cache_data(ttl=60)
def load_all():
    df_subs  = to_df(sb_select("patreon_subscriptions", order="-start_date"))
    df_custs = to_df(sb_select("customers",             order="name"))
    df_plans = to_df(sb_select("patreon_plans",         order="plan_name"))  # 修正1: plan_name
    return df_subs, df_custs, df_plans

# ── タブ ──────────────────────────────────────────────────────────────────────
tab_sub, tab_plan, tab_mrr = st.tabs(["サブスク管理", "プランマスタ", "MRR分析"])

# ════════════════════════════════════════════════════════
# タブ1: サブスク管理
# ════════════════════════════════════════════════════════
with tab_sub:
    df_subs, df_custs, df_plans = load_all()

    # ── 新規登録 ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">新規サブスク登録</div>', unsafe_allow_html=True)

    if df_custs.empty:
        st.markdown('<div class="info-box">顧客データがありません</div>', unsafe_allow_html=True)
    else:
        # 修正1: plan_name を使用
        plan_names = df_plans["plan_name"].tolist() if not df_plans.empty else ["Basic ($5)"]

        with st.form(key="new_sub_form"):
            nc1, nc2 = st.columns(2)
            with nc1:
                sel_cust   = st.selectbox("顧客を選択 *", df_custs["name"].tolist())
                start_date = st.date_input("開始日", value=date.today())
                payment_method = st.selectbox("支払方法", PAYMENT_METHODS)
            with nc2:
                sel_plan   = st.selectbox("プランを選択 *", plan_names)
                plan_row   = df_plans[df_plans["plan_name"] == sel_plan] if not df_plans.empty else pd.DataFrame()
                def_price  = int(plan_row.iloc[0]["price"]) if not plan_row.empty else 750
                monthly_price = st.number_input("月額（¥）", min_value=0, value=def_price, step=100)
                sub_note   = st.text_input("備考")
                # 解約済みチェックボックス（新規登録時は通常OFFで運用）
                is_cancelled_new = st.checkbox("解約済み", value=False, key="new_cancelled")
                cancel_date_new  = None
                if is_cancelled_new:
                    cancel_date_new = st.date_input("解約日", value=date.today(), key="new_cancel_date")

            if st.form_submit_button("登録する"):
                cust_id  = int(df_custs[df_custs["name"] == sel_cust]["id"].values[0])
                plan_id  = int(plan_row.iloc[0]["id"]) if not plan_row.empty else None
                cancel_v = str(cancel_date_new) if (is_cancelled_new and cancel_date_new) else None
                res = sb_insert("patreon_subscriptions", {
                    "customer_id":       cust_id,
                    "plan_id":           plan_id,
                    "plan_name":         sel_plan,
                    "monthly_price":     monthly_price,
                    "start_date":        str(start_date),
                    "next_billing_date": next_billing(str(start_date)),
                    "end_date":          None,
                    "cancel_date":       cancel_v,
                    "payment_method":    payment_method,
                    "note":              sub_note or None,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.markdown('<div class="err-box">登録に失敗しました</div>', unsafe_allow_html=True)

    # ── サブスク一覧 ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">サブスク一覧</div>', unsafe_allow_html=True)
    df_subs, df_custs, df_plans = load_all()

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

        # ステータス判定
        df_subs["status"] = df_subs.apply(
            lambda r: "契約中" if is_active_sub(r) else "解約済み", axis=1
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
        f_status = st.radio("表示", ["すべて","契約中のみ","解約済みのみ"], horizontal=True)
        if f_status == "契約中のみ":
            df_show = df_subs[df_subs["status"] == "契約中"].copy()
        elif f_status == "解約済みのみ":
            df_show = df_subs[df_subs["status"] == "解約済み"].copy()
        else:
            df_show = df_subs.copy()

        st.caption(f"{len(df_show)}件")

        # 修正5: enumerate で一意なキーを生成
        for i, (_, row) in enumerate(df_show.iterrows()):
            sid    = int(row["id"])
            status = row["status"]
            icon   = "🟢" if status == "契約中" else "⚫"
            c_date = safe_date(row.get("cancel_date")) or safe_date(row.get("end_date"))

            with st.expander(
                f"{icon} {row.get('cust_name','')} | {row.get('plan_name','')} | "
                f"¥{int(row.get('monthly_price',0) or 0):,}/月 | {status}"
            ):
                ic1, ic2 = st.columns(2)
                with ic1:
                    st.markdown(f"**顧客:** {row.get('cust_name','')}")
                    st.markdown(f"**プラン:** {row.get('plan_name','')}")
                    st.markdown(f"**月額:** ¥{int(row.get('monthly_price',0) or 0):,}")
                    st.markdown(f"**支払方法:** {row.get('payment_method','')}")
                with ic2:
                    st.markdown(f"**開始日:** {safe_date(row.get('start_date'))}")
                    st.markdown(f"**次回請求日:** {safe_date(row.get('next_billing_date'))}")
                    s_color = "#15803d" if status == "契約中" else "#9ca3af"
                    st.markdown(
                        f"**ステータス:** <span style='color:{s_color};font-weight:700;'>{status}</span>",
                        unsafe_allow_html=True
                    )
                    if c_date:
                        st.markdown(f"**解約日:** {c_date}")
                        st.caption(f"※ {c_date[:7]} まで MRR に含まれます")

                st.markdown("---")

                # 編集フォーム（修正5: key に i を付与して重複回避）
                with st.form(key=f"edit_{sid}_{i}"):
                    ef1, ef2 = st.columns(2)
                    with ef1:
                        e_price = st.number_input("月額（¥）", min_value=0,
                            value=int(row.get("monthly_price", 0) or 0),
                            step=100, key=f"ep_{sid}_{i}")
                        try:
                            s_def = date.fromisoformat(safe_date(row.get("start_date")) or str(date.today()))
                        except Exception:
                            s_def = date.today()
                        e_start = st.date_input("開始日", value=s_def, key=f"es_{sid}_{i}")
                        e_pay   = st.selectbox("支払方法", PAYMENT_METHODS,
                            index=PAYMENT_METHODS.index(row.get("payment_method","クレジットカード"))
                                  if row.get("payment_method") in PAYMENT_METHODS else 0,
                            key=f"epy_{sid}_{i}")
                    with ef2:
                        # 解約済みチェックボックス
                        is_cancelled = st.checkbox(
                            "解約済み",
                            value=bool(c_date),
                            key=f"cancel_{sid}_{i}"
                        )
                        if is_cancelled:
                            # チェックON: 解約日入力欄を表示
                            try:
                                c_def = date.fromisoformat(c_date) if c_date else date.today()
                            except Exception:
                                c_def = date.today()
                            e_cancel = st.date_input(
                                "解約日",
                                value=c_def,
                                key=f"cancel_date_{sid}_{i}"
                            )
                            cancel_save = str(e_cancel)
                            try:
                                excl_from = add_months(e_cancel, 1).strftime("%Y-%m")
                                st.caption(f"⚠️ {excl_from} 以降 MRR から除外")
                            except Exception:
                                pass
                        else:
                            # チェックOFF: NULL（契約中に戻す）
                            cancel_save = None

                    if st.form_submit_button("更新する", key=f"upd_{sid}_{i}"):
                        try:
                            get_client().table("patreon_subscriptions").update({
                                "monthly_price":     e_price,
                                "start_date":        str(e_start),
                                "next_billing_date": next_billing(str(e_start)),
                                "payment_method":    e_pay,
                                "cancel_date":       cancel_save,
                                "end_date":          cancel_save,  # 後方互換
                            }).eq("id", sid).execute()
                            st.markdown('<div class="success-box">✅ 更新しました</div>', unsafe_allow_html=True)
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.markdown(f'<div class="err-box">❌ 更新失敗: {e}</div>', unsafe_allow_html=True)

                if st.button("🗑️ 削除", key=f"del_{sid}_{i}"):
                    sb_delete("patreon_subscriptions", {"id": sid})
                    st.cache_data.clear()
                    st.rerun()

# ════════════════════════════════════════════════════════
# タブ2: プランマスタ
# ════════════════════════════════════════════════════════
with tab_plan:
    _, _, df_plans = load_all()
    st.markdown('<div class="section-head">プランを登録</div>', unsafe_allow_html=True)

    with st.form(key="new_plan_form"):
        pc1, pc2, pc3 = st.columns([3, 2, 2])
        with pc1: p_name  = st.text_input("プラン名 *", placeholder="例: Basic ($5)")
        with pc2: p_price = st.number_input("月額（¥）", min_value=0, value=750, step=100)
        with pc3: p_note  = st.text_input("備考（任意）")
        if st.form_submit_button("登録する"):
            if not p_name.strip():
                st.markdown('<div class="err-box">プラン名は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("patreon_plans", {
                    "plan_name": p_name.strip(),  # 修正1: plan_name
                    "price":     p_price,
                    "note":      p_note.strip() or None,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear(); st.rerun()
                else:
                    st.markdown('<div class="err-box">登録に失敗しました</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-head">登録済みプラン</div>', unsafe_allow_html=True)
    if df_plans.empty:
        st.markdown('<div class="info-box">プランがありません</div>', unsafe_allow_html=True)
    else:
        for j, (_, row) in enumerate(df_plans.iterrows()):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1: st.markdown(f"**{row['plan_name']}**")
            with c2: st.caption(f"¥{int(row.get('price', 0)):,}/月")
            with c3: st.caption(row.get("note", "") or "")
            with c4:
                if st.button("削除", key=f"plan_del_{row['id']}_{j}"):
                    sb_delete("patreon_plans", {"id": int(row["id"])})
                    st.cache_data.clear(); st.rerun()

# ════════════════════════════════════════════════════════
# タブ3: MRR分析
# ════════════════════════════════════════════════════════
with tab_mrr:
    st.markdown('<div class="section-head">MRR分析</div>', unsafe_allow_html=True)
    df_subs, df_custs, _ = load_all()

    if df_subs.empty:
        st.markdown('<div class="info-box">データがありません</div>', unsafe_allow_html=True)
        st.stop()

    # ── 検索・期間指定 ────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">期間指定</div>', unsafe_allow_html=True)
    search_mode = st.radio("検索方法", ["月数で指定", "期間を直接指定"], horizontal=True)

    if search_mode == "月数で指定":
        n_months = st.slider("表示月数", min_value=3, max_value=36, value=12)
        months = []
        d = date.today().replace(day=1)
        for _ in range(n_months):
            months.append(d.strftime("%Y-%m"))
            d = add_months(d, -1)
        months = list(reversed(months))
    else:
        dc1, dc2 = st.columns(2)
        with dc1:
            from_date = st.date_input("開始月", value=date(date.today().year, 1, 1))
        with dc2:
            to_date   = st.date_input("終了月", value=date.today())
        months = []
        d = from_date.replace(day=1)
        end_d = to_date.replace(day=1)
        while d <= end_d:
            months.append(d.strftime("%Y-%m"))
            d = add_months(d, 1)

    # ── MRR計算 ────────────────────────────────────────────────────────────────
    mrr_data = []
    for ym in months:
        mrr = calc_mrr(df_subs, ym)
        mrr_data.append({"月": ym, "MRR": mrr})

    df_mrr = pd.DataFrame(mrr_data)

    # 前月比・前年比を計算
    df_mrr["前月比(¥)"]  = df_mrr["MRR"].diff().fillna(0).astype(int)
    df_mrr["前月比(%)"]  = (df_mrr["MRR"].pct_change() * 100).round(1).fillna(0)
    df_mrr["前年同月MRR"] = df_mrr["MRR"].shift(12).fillna(0).astype(int)
    df_mrr["前年比(%)"]   = ((df_mrr["MRR"] - df_mrr["前年同月MRR"]) /
                              df_mrr["前年同月MRR"].replace(0, float("nan")) * 100).round(1).fillna(0)

    # ── グラフ ────────────────────────────────────────────────────────────────
    if df_mrr["MRR"].sum() > 0:
        st.markdown('<div class="section-head">MRR推移</div>', unsafe_allow_html=True)
        st.line_chart(df_mrr.set_index("月")["MRR"])

        # 前月比グラフ
        if len(df_mrr) > 1:
            st.markdown('<div class="section-head">前月比（¥）</div>', unsafe_allow_html=True)
            st.bar_chart(df_mrr.set_index("月")["前月比(¥)"])
    else:
        st.markdown('<div class="info-box">MRRデータがありません</div>', unsafe_allow_html=True)

    # ── 表形式 ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">MRR詳細テーブル</div>', unsafe_allow_html=True)

    def fmt_diff(v):
        if v > 0:   return f"🟢 +¥{int(v):,}"
        elif v < 0: return f"🔴 ¥{int(v):,}"
        return "―"

    def fmt_pct(v):
        if v > 0:   return f"+{v:.1f}%"
        elif v < 0: return f"{v:.1f}%"
        return "―"

    df_display = df_mrr.copy()
    df_display["MRR"]      = df_display["MRR"].apply(lambda x: f"¥{int(x):,}")
    df_display["前月比"]   = df_display["前月比(¥)"].apply(fmt_diff)
    df_display["前月比率"] = df_display["前月比(%)"].apply(fmt_pct)
    df_display["前年比率"] = df_display["前年比(%)"].apply(fmt_pct)

    st.dataframe(
        df_display[["月","MRR","前月比","前月比率","前年比率"]],
        use_container_width=True, hide_index=True
    )

    # ── 現在の契約中サブスク ──────────────────────────────────────────────────
    st.markdown('<div class="section-head">現在の契約中サブスク</div>', unsafe_allow_html=True)
    df_subs["is_active_flag"] = df_subs.apply(is_active_sub, axis=1)
    df_active = df_subs[df_subs["is_active_flag"]].copy()

    if not df_active.empty:
        if not df_custs.empty:
            df_active = df_active.merge(
                df_custs[["id","name"]].rename(columns={"id":"customer_id","name":"顧客名"}),
                on="customer_id", how="left"
            )
        df_active["月額(¥)"] = df_active["monthly_price"].fillna(0).astype(int)
        st.dataframe(
            df_active[["顧客名","plan_name","月額(¥)","start_date"]].rename(columns={
                "plan_name":"プラン","start_date":"開始日"
            }),
            use_container_width=True, hide_index=True
        )
        st.markdown(f"**契約中MRR合計: ¥{int(df_active['月額(¥)'].sum()):,}**")
    else:
        st.markdown('<div class="info-box">契約中のサブスクがありません</div>', unsafe_allow_html=True)
