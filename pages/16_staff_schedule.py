"""
pages/16_staff_schedule.py — スタッフ・スケジュール管理システム（v2）

変更点:
  - 通常勤務時間（曜日別）を廃止 → 出勤日ごとに日付+勤務時間を登録
  - 日別タイムラインに横並び日付セレクター
  - 設定タブに業務種類の更新（編集）+削除ボタン
"""
import streamlit as st
import pandas as pd
import json
from datetime import date, time as time_type, datetime, timedelta
from common import inject_css, setup_sidebar, to_df
from db import sb_select, sb_insert, sb_update, sb_delete, get_client

st.set_page_config(page_title="スタッフ管理 | Tabibiyori", page_icon=None, layout="wide")
inject_css()
setup_sidebar()

# ── 定数 ─────────────────────────────────────────────────────────────────────
WEEKDAY_JP = {0:"月",1:"火",2:"水",3:"木",4:"金",5:"土",6:"日"}
STATUS_MAP = {
    "confirmed":   ("🟢 確定",       "#15803d"),
    "adjusting":   ("🟡 調整中",     "#d97706"),
    "need_sub":    ("🟠 代替要",     "#ea580c"),
    "need_action": ("🔴 要対応",     "#dc2626"),
    "cancelled":   ("⚪ キャンセル",  "#9ca3af"),
}
HOURS = list(range(8, 22))  # 8:00〜21:00表示

# ── ヘルパー ──────────────────────────────────────────────────────────────────
def parse_json_field(val, default):
    if val is None: return default
    if isinstance(val, (list, dict)): return val
    try: return json.loads(val)
    except Exception: return default

def time_to_float(t):
    if t is None: return None
    if isinstance(t, str):
        try:
            h, m = map(int, t[:5].split(":")); return h + m / 60
        except Exception: return None
    try: return t.hour + t.minute / 60
    except Exception: return None

def fmt_time(t):
    if t is None: return ""
    if isinstance(t, str): return t[:5]
    try: return t.strftime("%H:%M")
    except Exception: return str(t)[:5]

def calc_end_time(start_t, hours_dur):
    start_f = time_to_float(start_t)
    if start_f is None: return None
    end_f = start_f + hours_dur
    h = int(end_f) % 24
    m = int(round((end_f - int(end_f)) * 60))
    if m == 60: h += 1; m = 0
    return f"{h:02d}:{m:02d}"

@st.cache_data(ttl=60)
def load_all():
    tasks    = to_df(sb_select("staff_task_types", order="sort_order"))
    staff    = to_df(sb_select("staff_members",    order="name"))
    events   = to_df(sb_select("staff_events",     order="event_date"))
    workdays = to_df(sb_select("staff_work_days",  order="work_date"))
    try:
        breaks = to_df(sb_select("staff_breaks", order="break_date"))
    except Exception:
        breaks = pd.DataFrame()
    try:
        holidays = to_df(sb_select("staff_holidays", order="holiday_date"))
    except Exception:
        holidays = pd.DataFrame()
    return tasks, staff, events, workdays, breaks, holidays

def get_event_breaks(event_id, breaks_df):
    """指定予定の休憩リストを返す"""
    if breaks_df.empty: return pd.DataFrame()
    return breaks_df[breaks_df["event_id"] == event_id]

def hour_in_break(h, event_id, breaks_df):
    """指定時刻hがその予定の休憩時間内か判定"""
    eb = get_event_breaks(event_id, breaks_df)
    if eb.empty: return False
    for _, br in eb.iterrows():
        bs = time_to_float(br.get("start_time"))
        be = time_to_float(br.get("end_time"))
        if bs is not None and be is None and bool(br.get("is_ongoing", False)):
            if h >= bs: return True
        elif bs is not None and be is not None:
            if bs <= h < be: return True
    return False

def get_workday_v2(staff_row, target_date, workdays_df, holidays_df):
    """
    雇用形態を考慮した出勤判定。
    戻り: (出勤か, 開始, 終了)

    parttime（アルバイト・業務委託）: staff_work_days に登録があれば出勤
    fulltime（契約社員・正社員）: staff_holidays に休日登録がなければ出勤（デフォルト勤務時間）
                                  ただし staff_work_days に個別登録があればそれを優先
    """
    sid = int(staff_row["id"])
    emp_type = staff_row.get("employment_type", "parttime") or "parttime"

    # まず staff_work_days の個別登録を確認（両形態共通で優先）
    if not workdays_df.empty:
        wd = workdays_df[
            (workdays_df["staff_id"] == sid) &
            (workdays_df["work_date"].astype(str) == str(target_date))
        ]
        if not wd.empty:
            row = wd.iloc[0]
            return True, row.get("start_time"), row.get("end_time")

    if emp_type == "fulltime":
        # 正社員: 休日登録がなければ出勤
        is_holiday = False
        if not holidays_df.empty:
            hd = holidays_df[
                (holidays_df["staff_id"] == sid) &
                (holidays_df["holiday_date"].astype(str) == str(target_date))
            ]
            is_holiday = not hd.empty
        if is_holiday:
            return False, None, None
        # 出勤（デフォルト勤務時間）
        d_start = staff_row.get("default_start", "10:00") or "10:00"
        d_end   = staff_row.get("default_end", "19:00") or "19:00"
        return True, d_start, d_end
    else:
        # アルバイト・業務委託: staff_work_days に登録がなければ休み
        return False, None, None

def get_task_color(task_name, tasks_df):
    if not tasks_df.empty:
        m = tasks_df[tasks_df["name"] == task_name]
        if not m.empty: return m.iloc[0].get("color", "#3b82f6")
    return "#3b82f6"

# ════════════════════════════════════════════════════════
tasks_df, staff_df, events_df, workdays_df, breaks_df, holidays_df = load_all()

# 後方互換: 旧 get_workday を新ロジックにブリッジ
def get_workday(staff_id, target_date, workdays_df):
    if staff_df.empty: return False, None, None
    sr = staff_df[staff_df["id"] == staff_id]
    if sr.empty: return False, None, None
    return get_workday_v2(sr.iloc[0], target_date, workdays_df, holidays_df)

st.markdown('<div class="page-title">スタッフ・スケジュール管理</div>', unsafe_allow_html=True)

tab_dash, tab_timeline, tab_calendar, tab_staff, tab_events, tab_settings = st.tabs([
    "ダッシュボード", "日別タイムライン", "月別カレンダー", "従業員管理", "予定管理", "設定"
])

if "sched_date" not in st.session_state:
    st.session_state["sched_date"] = date.today()
if "cal_month" not in st.session_state:
    st.session_state["cal_month"] = date.today().replace(day=1)

# ════════════════════════════════════════════════════════
# タブ1: ダッシュボード
# ════════════════════════════════════════════════════════
with tab_dash:
    today = date.today()
    st.markdown(f'<div class="section-head">本日 {today}（{WEEKDAY_JP[today.weekday()]}）の状況</div>', unsafe_allow_html=True)

    today_events = pd.DataFrame()
    if not events_df.empty:
        today_events = events_df[events_df["event_date"].astype(str) == str(today)].copy()
        today_events = today_events[today_events["status"] != "cancelled"]

    # 本日出勤スタッフ数（staff_work_days ベース）
    working_staff = 0
    if not workdays_df.empty:
        working_staff = workdays_df[workdays_df["work_date"].astype(str) == str(today)]["staff_id"].nunique()

    total_events = len(today_events)
    need_action  = len(today_events[today_events["status"] == "need_action"]) if not today_events.empty else 0
    adjusting    = len(today_events[today_events["status"] == "adjusting"]) if not today_events.empty else 0
    need_sub     = len(today_events[today_events["status"] == "need_sub"]) if not today_events.empty else 0

    st.markdown(f"""<div class="metric-row">
      <div class="metric-card"><div class="val">{working_staff}</div><div class="lbl">本日の出勤人数</div></div>
      <div class="metric-card"><div class="val">{total_events}</div><div class="lbl">本日の予定数</div></div>
      <div class="metric-card"><div class="val" style="color:#dc2626;">{need_action}</div><div class="lbl">要対応</div></div>
      <div class="metric-card"><div class="val" style="color:#d97706;">{adjusting}</div><div class="lbl">調整中</div></div>
      <div class="metric-card"><div class="val" style="color:#ea580c;">{need_sub}</div><div class="lbl">代替スタッフ要</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-head">⚠️ 要対応一覧</div>', unsafe_allow_html=True)
    if not events_df.empty:
        upcoming = events_df[
            (events_df["event_date"].astype(str) >= str(today)) &
            (events_df["status"].isin(["need_action","adjusting","need_sub"]))
        ].copy().sort_values(["event_date","planned_start"])
        if upcoming.empty:
            st.markdown('<div class="success-box">✅ 対応が必要な予定はありません</div>', unsafe_allow_html=True)
        else:
            for _, ev in upcoming.iterrows():
                staff_name = "不明"
                if not staff_df.empty:
                    sm = staff_df[staff_df["id"] == ev["staff_id"]]
                    if not sm.empty: staff_name = sm.iloc[0]["name"]
                status_label, status_color = STATUS_MAP.get(ev["status"], ("", "#000"))
                reason = ev.get("adjust_reason","") or ""
                st.markdown(
                    f'<div class="err-box"><strong>{staff_name}</strong> | {ev["event_date"]} '
                    f'{fmt_time(ev["planned_start"])}〜{fmt_time(ev["planned_end"])} | '
                    f'{ev["task_type"]} | <span style="color:{status_color};">{status_label}</span>'
                    f'{"<br>理由: " + reason if reason else ""}</div>',
                    unsafe_allow_html=True
                )
    else:
        st.markdown('<div class="info-box">予定データがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ2: 日別タイムライン
# ════════════════════════════════════════════════════════
with tab_timeline:
    view_date = st.session_state["sched_date"]

    # ── 表示モード切り替え ────────────────────────────────────────────────────
    view_mode = st.radio("表示モード", ["タイムライン（PC向け）", "リスト（スマホ向け）"],
                          horizontal=True, key="view_mode")

    # ── 日付ナビゲーション（前日/今日/翌日）────────────────────────────────────
    nc1, nc2, nc3, nc4 = st.columns([1, 1, 1, 2])
    with nc1:
        if st.button("← 前日", use_container_width=True):
            st.session_state["sched_date"] -= timedelta(days=1); st.rerun()
    with nc2:
        if st.button("今日", type="primary", use_container_width=True):
            st.session_state["sched_date"] = date.today(); st.rerun()
    with nc3:
        if st.button("翌日 →", use_container_width=True):
            st.session_state["sched_date"] += timedelta(days=1); st.rerun()
    with nc4:
        picked = st.date_input("日付", value=view_date, key="date_picker", label_visibility="collapsed")
        if picked != view_date:
            st.session_state["sched_date"] = picked; st.rerun()

    view_date = st.session_state["sched_date"]
    wd_jp = WEEKDAY_JP[view_date.weekday()]
    st.markdown(f'<div class="section-head">{view_date}（{wd_jp}）のスケジュール</div>', unsafe_allow_html=True)

    if staff_df.empty:
        st.markdown('<div class="info-box">従業員が登録されていません</div>', unsafe_allow_html=True)
    else:
        day_events = pd.DataFrame()
        if not events_df.empty:
            day_events = events_df[events_df["event_date"].astype(str) == str(view_date)].copy()

        is_mobile = (view_mode == "リスト（スマホ向け）")

        if not is_mobile:
            # ── タイムライン表示（PC向け）────────────────────────────────────
            header_html = '<div style="display:flex;border-bottom:2px solid #1e3a5f;padding-bottom:4px;margin-bottom:4px;">'
            header_html += '<div style="width:80px;flex-shrink:0;font-weight:700;font-size:.8rem;">従業員</div>'
            for h in HOURS:
                header_html += f'<div style="flex:1;text-align:center;font-size:.7rem;color:#6b7280;">{h}:00</div>'
            header_html += '</div>'
            st.markdown(header_html, unsafe_allow_html=True)

            for _, s in staff_df.iterrows():
                if not s.get("is_active", True): continue
                sid   = int(s["id"])
                sname = s["name"]
                is_work, w_start, w_end = get_workday(sid, view_date, workdays_df)
                s_events = day_events[day_events["staff_id"] == sid] if not day_events.empty else pd.DataFrame()
                s_events = s_events[s_events["status"] != "cancelled"] if not s_events.empty else s_events

                row_html = '<div style="display:flex;align-items:center;border-bottom:1px solid #e5e7eb;min-height:44px;">'
                row_html += f'<div style="width:80px;flex-shrink:0;font-weight:600;font-size:.85rem;">{sname}</div>'
                row_html += '<div style="flex:1;display:flex;height:36px;">'

                if not is_work and (s_events.empty):
                    row_html += '<div style="flex:1;background:#f3f4f6;color:#9ca3af;text-align:center;line-height:36px;font-size:.8rem;border-radius:4px;">休日</div>'
                else:
                    w_start_f = time_to_float(w_start) if w_start else HOURS[0]
                    w_end_f   = time_to_float(w_end) if w_end else HOURS[-1]+1
                    for h in HOURS:
                        slot_events = []
                        if not s_events.empty:
                            for _, ev in s_events.iterrows():
                                ps = time_to_float(ev["planned_start"]); pe = time_to_float(ev["planned_end"])
                                if ps is not None and pe is not None and ps <= h < pe:
                                    slot_events.append(ev)
                        if slot_events:
                            ev = slot_events[0]
                            eid_check = int(ev["id"])
                            # この時刻が休憩時間内かチェック（休憩テーブルベース）
                            if hour_in_break(h, eid_check, breaks_df):
                                row_html += '<div style="flex:1;background:#f59e0b;color:white;text-align:center;line-height:36px;font-size:.65rem;overflow:hidden;white-space:nowrap;" title="休憩中">🍽️休憩</div>'
                            else:
                                color = get_task_color(ev["task_type"], tasks_df)
                                # 複数人予定は👥アイコン付き+枠線で強調
                                if bool(ev.get("is_group", False)):
                                    row_html += f'<div style="flex:1;background:{color};color:white;text-align:center;line-height:34px;font-size:.62rem;overflow:hidden;white-space:nowrap;border:2px solid #7c3aed;box-sizing:border-box;" title="複数人予定: {ev["task_type"]}">👥{ev["task_type"][:3]}</div>'
                                else:
                                    row_html += f'<div style="flex:1;background:{color};color:white;text-align:center;line-height:36px;font-size:.65rem;overflow:hidden;white-space:nowrap;" title="{ev["task_type"]}">{ev["task_type"][:4]}</div>'
                        elif is_work and w_start_f <= h < w_end_f:
                            row_html += '<div style="flex:1;background:#ecfdf5;border:1px dashed #a7f3d0;" title="空き"></div>'
                        else:
                            row_html += '<div style="flex:1;background:#fafafa;"></div>'
                row_html += '</div></div>'
                st.markdown(row_html, unsafe_allow_html=True)

            st.markdown('<div style="margin-top:12px;font-size:.75rem;color:#6b7280;">凡例: '
                        '<span style="background:#ecfdf5;border:1px dashed #a7f3d0;padding:2px 8px;">空き</span> '
                        '<span style="background:#f3f4f6;padding:2px 8px;">休日</span> '
                        '<span style="background:#f59e0b;color:white;padding:2px 8px;">🍽️休憩</span> '
                        '<span style="border:2px solid #7c3aed;padding:1px 8px;">👥複数人予定</span> '
                        '各色=業務種類</div>', unsafe_allow_html=True)
        else:
            # ── リスト表示（スマホ向け）──────────────────────────────────────
            for _, s in staff_df.iterrows():
                if not s.get("is_active", True): continue
                sid   = int(s["id"])
                sname = s["name"]
                is_work, w_start, w_end = get_workday(sid, view_date, workdays_df)
                s_events = day_events[day_events["staff_id"] == sid] if not day_events.empty else pd.DataFrame()
                s_events = s_events[s_events["status"] != "cancelled"].sort_values("planned_start") if not s_events.empty else s_events

                # スタッフ名ヘッダー
                if not is_work and s_events.empty:
                    st.markdown(f'<div style="padding:8px 12px;background:#f3f4f6;border-radius:8px;margin:6px 0;"><strong>{sname}</strong> <span style="color:#9ca3af;">休日</span></div>', unsafe_allow_html=True)
                else:
                    work_info = f'{fmt_time(w_start)}〜{fmt_time(w_end)} 勤務' if is_work else '休日出勤あり'
                    st.markdown(f'<div style="padding:8px 12px;background:#eff6ff;border-radius:8px;margin:6px 0 2px;"><strong>{sname}</strong> <span style="color:#1e3a5f;font-size:.8rem;">{work_info}</span></div>', unsafe_allow_html=True)
                    if not s_events.empty:
                        for _, ev in s_events.iterrows():
                            color = get_task_color(ev["task_type"], tasks_df)
                            loc = f' 📍{ev["location"]}' if ev.get("location") else ''
                            is_grp = bool(ev.get("is_group", False))
                            grp_icon = "👥 " if is_grp else ""
                            border_color = "#7c3aed" if is_grp else color
                            grp_label = ' <span style="background:#7c3aed;color:white;padding:1px 6px;border-radius:4px;font-size:.7rem;">研修</span>' if is_grp else ''
                            st.markdown(
                                f'<div style="display:flex;align-items:center;padding:6px 12px;margin:2px 0 2px 16px;border-left:4px solid {border_color};background:#fafafa;">'
                                f'<span style="font-weight:600;color:{color};min-width:90px;">{fmt_time(ev["planned_start"])}〜{fmt_time(ev["planned_end"])}</span>'
                                f'<span style="margin-left:8px;">{grp_icon}{ev["task_type"]}{loc}{grp_label}</span></div>',
                                unsafe_allow_html=True
                            )
                            # この予定の休憩を表示
                            ev_breaks = get_event_breaks(int(ev["id"]), breaks_df)
                            if not ev_breaks.empty:
                                for _, br in ev_breaks.iterrows():
                                    bs = fmt_time(br.get("start_time"))
                                    be = fmt_time(br.get("end_time")) if br.get("end_time") else "（休憩中）"
                                    st.markdown(
                                        f'<div style="display:flex;align-items:center;padding:4px 12px;margin:2px 0 2px 32px;border-left:4px solid #f59e0b;background:#fffbeb;">'
                                        f'<span style="font-weight:600;color:#f59e0b;min-width:90px;">{bs}〜{be}</span>'
                                        f'<span style="margin-left:8px;">🍽️ 休憩</span></div>',
                                        unsafe_allow_html=True
                                    )
                    else:
                        st.markdown('<div style="padding:4px 12px 4px 16px;color:#9ca3af;font-size:.8rem;">予定なし（終日空き）</div>', unsafe_allow_html=True)

        # ── この日にクイック予定追加 ──────────────────────────────────────────
        with st.expander(f"＋ {view_date} に予定を追加"):
            q_staff_options = {s["name"]: int(s["id"]) for _, s in staff_df.iterrows() if s.get("is_active", True)}
            q_task_names = tasks_df["name"].tolist() if not tasks_df.empty else []
            with st.form(key=f"quick_add_{view_date}"):
                qc1, qc2, qc3 = st.columns(3)
                with qc1:
                    q_staff = st.selectbox("担当者", list(q_staff_options.keys()), key="q_staff")
                    q_task  = st.selectbox("業務", q_task_names, key="q_task")
                with qc2:
                    q_start = st.time_input("開始", value=time_type(10,0), key="q_start")
                    q_dur   = st.number_input("所要時間", min_value=0.5, value=2.0, step=0.5, key="q_dur")
                with qc3:
                    q_loc  = st.text_input("📍場所", key="q_loc")
                    q_calc_end = calc_end_time(q_start, q_dur)
                    st.caption(f"終了: {q_calc_end}")
                if st.form_submit_button("追加する"):
                    qsid = q_staff_options[q_staff]
                    qstaff_row = staff_df[staff_df["id"] == qsid].iloc[0]
                    qskills = parse_json_field(qstaff_row.get("skills"), [])
                    q_is_work, q_ws, q_we = get_workday(qsid, view_date, workdays_df)
                    q_status = "confirmed"; q_reasons = []; q_holiday = False
                    if not q_is_work:
                        q_status = "need_action"; q_reasons.append("出勤日ではありません"); q_holiday = True
                    if qskills and q_task not in qskills:
                        q_status = "need_action"; q_reasons.append(f"「{q_task}」を担当できません")
                    sb_insert("staff_events", {
                        "staff_id":        qsid,
                        "task_type":       q_task,
                        "event_date":      str(view_date),
                        "planned_start":   fmt_time(q_start),
                        "planned_end":     q_calc_end,
                        "location":        q_loc.strip() or None,
                        "status":          q_status,
                        "is_holiday_work": q_holiday,
                        "adjust_reason":   " / ".join(q_reasons) if q_reasons else None,
                    })
                    st.cache_data.clear(); st.rerun()

        # 予定詳細・実績記録
        st.markdown('<div class="section-head">予定詳細・実績記録</div>', unsafe_allow_html=True)
        if not day_events.empty:
            day_events_show = day_events[day_events["status"] != "cancelled"].sort_values("planned_start")
            for i, (_, ev) in enumerate(day_events_show.iterrows()):
                eid = int(ev["id"])
                staff_name = "不明"
                if not staff_df.empty:
                    sm = staff_df[staff_df["id"] == ev["staff_id"]]
                    if not sm.empty: staff_name = sm.iloc[0]["name"]
                status_label, status_color = STATUS_MAP.get(ev.get("status","confirmed"), ("", "#000"))
                actual_s = fmt_time(ev.get("actual_start")) if ev.get("actual_start") else "—"
                actual_e = fmt_time(ev.get("actual_end")) if ev.get("actual_end") else "—"

                # この予定の休憩を取得
                ev_breaks = get_event_breaks(eid, breaks_df)
                ongoing_break = ev_breaks[ev_breaks["is_ongoing"] == True] if not ev_breaks.empty else pd.DataFrame()
                is_on_break = not ongoing_break.empty
                break_badge = " 🍽️休憩中" if is_on_break else ""

                with st.expander(f'{staff_name} | {ev["task_type"]} | {fmt_time(ev["planned_start"])}〜{fmt_time(ev["planned_end"])} | {status_label}{break_badge}'):
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.markdown(f"**担当:** {staff_name}")
                        st.markdown(f"**業務:** {ev['task_type']}")
                        st.markdown(f"**予定:** {fmt_time(ev['planned_start'])}〜{fmt_time(ev['planned_end'])}")
                        if ev.get("location"): st.markdown(f"**📍 場所:** {ev['location']}")
                        if ev.get("memo"): st.markdown(f"**メモ:** {ev['memo']}")
                    with dc2:
                        st.markdown(f"**実績開始:** {actual_s}")
                        st.markdown(f"**実績終了:** {actual_e}")
                        st.markdown(f"**ステータス:** <span style='color:{status_color};'>{status_label}</span>", unsafe_allow_html=True)
                        if is_on_break:
                            st.markdown('<span style="color:#f59e0b;font-weight:700;">🍽️ 現在休憩中</span>', unsafe_allow_html=True)

                    # 登録済み休憩の一覧
                    if not ev_breaks.empty:
                        st.markdown("**休憩記録:**")
                        for _, br in ev_breaks.iterrows():
                            brid = int(br["id"])
                            bs = fmt_time(br.get("start_time"))
                            be = fmt_time(br.get("end_time")) if br.get("end_time") else "（休憩中）"
                            brc1, brc2 = st.columns([4, 1])
                            with brc1:
                                st.caption(f"🍽️ {bs} 〜 {be}")
                            with brc2:
                                if st.button("削除", key=f"delbrk_{brid}_{i}"):
                                    sb_delete("staff_breaks", {"id": brid})
                                    st.cache_data.clear(); st.rerun()

                    # 開始・終了ボタン
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("▶ 開始", key=f"start_{eid}_{i}", use_container_width=True):
                            sb_update("staff_events", {"actual_start": datetime.now().isoformat()}, {"id": eid})
                            st.cache_data.clear(); st.rerun()
                    with bc2:
                        if st.button("■ 終了", key=f"end_{eid}_{i}", use_container_width=True):
                            sb_update("staff_events", {"actual_end": datetime.now().isoformat()}, {"id": eid})
                            st.cache_data.clear(); st.rerun()

                    # 休憩ボタン（自動記録）
                    st.markdown("**休憩（ボタンで自動記録）**")
                    if is_on_break:
                        if st.button("🍽️ 休憩終了", key=f"brkend_{eid}_{i}", use_container_width=True):
                            brid = int(ongoing_break.iloc[0]["id"])
                            now_time = datetime.now().strftime("%H:%M")
                            sb_update("staff_breaks", {
                                "end_time": now_time, "is_ongoing": False
                            }, {"id": brid})
                            st.cache_data.clear(); st.rerun()
                    else:
                        if st.button("🍽️ 休憩開始", key=f"brkstart_{eid}_{i}", use_container_width=True):
                            now_time = datetime.now().strftime("%H:%M")
                            sb_insert("staff_breaks", {
                                "event_id":   eid,
                                "staff_id":   int(ev["staff_id"]),
                                "break_date": str(ev["event_date"]),
                                "start_time": now_time,
                                "end_time":   None,
                                "is_ongoing": True,
                            })
                            st.cache_data.clear(); st.rerun()

                    # 休憩ボタン（手動入力）
                    with st.form(key=f"manual_break_{eid}_{i}"):
                        st.markdown("**休憩を手動で追加**")
                        mbc1, mbc2, mbc3 = st.columns([2, 2, 1])
                        with mbc1: mb_start = st.time_input("休憩開始", value=time_type(12,0), key=f"mbs_{eid}_{i}")
                        with mbc2: mb_end   = st.time_input("休憩終了", value=time_type(13,0), key=f"mbe_{eid}_{i}")
                        with mbc3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.form_submit_button("追加"):
                                sb_insert("staff_breaks", {
                                    "event_id":   eid,
                                    "staff_id":   int(ev["staff_id"]),
                                    "break_date": str(ev["event_date"]),
                                    "start_time": fmt_time(mb_start),
                                    "end_time":   fmt_time(mb_end),
                                    "is_ongoing": False,
                                })
                                st.cache_data.clear(); st.rerun()

                    # 状態変更・削除
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        new_status = st.selectbox("状態", list(STATUS_MAP.keys()),
                            index=list(STATUS_MAP.keys()).index(ev.get("status","confirmed")),
                            format_func=lambda x: STATUS_MAP[x][0], key=f"st_{eid}_{i}")
                        if st.button("状態更新", key=f"stupd_{eid}_{i}", use_container_width=True):
                            sb_update("staff_events", {"status": new_status}, {"id": eid})
                            st.cache_data.clear(); st.rerun()
                    with sc2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑️ 削除", key=f"del_ev_{eid}_{i}", use_container_width=True):
                            sb_delete("staff_events", {"id": eid})
                            st.cache_data.clear(); st.rerun()

                    # ── 予定内容を編集 ──────────────────────────────────────
                    st.markdown("---")
                    st.markdown("**予定内容を編集**")
                    with st.form(key=f"edit_ev_{eid}_{i}"):
                        task_names_e = tasks_df["name"].tolist() if not tasks_df.empty else []
                        staff_opts_e = {s["name"]: int(s["id"]) for _, s in staff_df.iterrows()}

                        efc1, efc2 = st.columns(2)
                        with efc1:
                            # 担当者
                            cur_staff_name = staff_name
                            staff_idx = list(staff_opts_e.keys()).index(cur_staff_name) if cur_staff_name in staff_opts_e else 0
                            e_staff = st.selectbox("担当者", list(staff_opts_e.keys()), index=staff_idx, key=f"ev_staff_{eid}_{i}")
                            # 業務種類
                            task_idx = task_names_e.index(ev["task_type"]) if ev["task_type"] in task_names_e else 0
                            e_task = st.selectbox("業務種類", task_names_e, index=task_idx, key=f"ev_task_{eid}_{i}")
                            # 日付
                            try:
                                cur_date = pd.to_datetime(ev["event_date"]).date()
                            except Exception:
                                cur_date = date.today()
                            e_date = st.date_input("日付", value=cur_date, key=f"ev_date_{eid}_{i}")
                        with efc2:
                            # 開始時刻
                            try:
                                ps_parts = fmt_time(ev["planned_start"]).split(":")
                                cur_start = time_type(int(ps_parts[0]), int(ps_parts[1]))
                            except Exception:
                                cur_start = time_type(10, 0)
                            e_start = st.time_input("開始時刻", value=cur_start, key=f"ev_start_{eid}_{i}")
                            # 終了時刻
                            try:
                                pe_parts = fmt_time(ev["planned_end"]).split(":")
                                cur_end = time_type(int(pe_parts[0]), int(pe_parts[1]))
                            except Exception:
                                cur_end = time_type(12, 0)
                            e_end = st.time_input("終了時刻", value=cur_end, key=f"ev_end_{eid}_{i}")

                        e_location = st.text_input("📍 場所", value=ev.get("location","") or "", key=f"ev_loc_{eid}_{i}")
                        e_memo     = st.text_input("メモ", value=ev.get("memo","") or "", key=f"ev_memo_{eid}_{i}")

                        if st.form_submit_button("✏️ 予定を更新する", use_container_width=True):
                            sb_update("staff_events", {
                                "staff_id":      staff_opts_e[e_staff],
                                "task_type":     e_task,
                                "event_date":    str(e_date),
                                "planned_start": fmt_time(e_start),
                                "planned_end":   fmt_time(e_end),
                                "location":      e_location.strip() or None,
                                "memo":          e_memo.strip() or None,
                            }, {"id": eid})
                            st.markdown('<div class="success-box">予定を更新しました</div>', unsafe_allow_html=True)
                            st.cache_data.clear(); st.rerun()
        else:
            st.markdown('<div class="info-box">この日の予定はありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ: 月別カレンダー（全員の出勤・休み一覧）
# ════════════════════════════════════════════════════════
with tab_calendar:
    import calendar as cal_module

    cal_month = st.session_state["cal_month"]

    # 月ナビゲーション
    mc1, mc2, mc3, mc4 = st.columns([1, 1, 1, 2])
    with mc1:
        if st.button("← 前月", use_container_width=True):
            y, m = cal_month.year, cal_month.month
            st.session_state["cal_month"] = date(y-1, 12, 1) if m == 1 else date(y, m-1, 1)
            st.rerun()
    with mc2:
        if st.button("今月", type="primary", use_container_width=True):
            st.session_state["cal_month"] = date.today().replace(day=1); st.rerun()
    with mc3:
        if st.button("翌月 →", use_container_width=True):
            y, m = cal_month.year, cal_month.month
            st.session_state["cal_month"] = date(y+1, 1, 1) if m == 12 else date(y, m+1, 1)
            st.rerun()

    cal_month = st.session_state["cal_month"]
    st.markdown(f'<div class="section-head">{cal_month.year}年{cal_month.month}月 出勤カレンダー</div>', unsafe_allow_html=True)

    if staff_df.empty:
        st.markdown('<div class="info-box">従業員が登録されていません</div>', unsafe_allow_html=True)
    else:
        # その月の日数
        num_days = cal_module.monthrange(cal_month.year, cal_month.month)[1]
        days = [date(cal_month.year, cal_month.month, d) for d in range(1, num_days+1)]

        active_staff_cal = staff_df[staff_df["is_active"] == True] if "is_active" in staff_df.columns else staff_df

        # 出勤日をセットに
        workday_set = set()
        if not workdays_df.empty:
            for _, wd in workdays_df.iterrows():
                workday_set.add((int(wd["staff_id"]), str(wd["work_date"])[:10]))

        # 予定がある日をセットに
        event_set = {}
        if not events_df.empty:
            for _, ev in events_df.iterrows():
                if ev.get("status") == "cancelled": continue
                key = (int(ev["staff_id"]), str(ev["event_date"])[:10])
                event_set[key] = event_set.get(key, 0) + 1

        # カレンダーテーブルを構築（横=日付、縦=スタッフ）
        html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse;font-size:.72rem;white-space:nowrap;">'
        # ヘッダー行（日付）
        html += '<tr><th style="position:sticky;left:0;background:#1e3a5f;color:white;padding:6px 10px;border:1px solid #ddd;z-index:1;">従業員</th>'
        for d in days:
            wd_label = WEEKDAY_JP[d.weekday()]
            # 土日に色
            bg = "#1e3a5f"
            if d.weekday() == 5: bg = "#2563eb"   # 土
            elif d.weekday() == 6: bg = "#dc2626" # 日
            is_today = (d == date.today())
            border = "3px solid #f59e0b" if is_today else "1px solid #ddd"
            html += f'<th style="background:{bg};color:white;padding:4px 6px;border:{border};min-width:32px;">{d.day}<br><span style="font-size:.65rem;">{wd_label}</span></th>'
        html += '<th style="background:#1e3a5f;color:white;padding:6px 10px;border:1px solid #ddd;">出勤日数</th></tr>'

        # 各スタッフの行
        for _, s in active_staff_cal.iterrows():
            sid = int(s["id"])
            sname = s["name"]
            work_count = 0
            html += f'<tr><td style="position:sticky;left:0;background:#f9fafb;font-weight:600;padding:6px 10px;border:1px solid #ddd;z-index:1;">{sname}</td>'
            for d in days:
                dstr = str(d)
                # 雇用形態を考慮した出勤判定
                is_work, _, _ = get_workday_v2(s, d, workdays_df, holidays_df)
                ev_count = event_set.get((sid, dstr), 0)
                if is_work:
                    work_count += 1
                    # 出勤（予定があれば数を表示）
                    if ev_count > 0:
                        html += f'<td style="background:#dbeafe;text-align:center;padding:4px;border:1px solid #ddd;color:#1e3a5f;font-weight:700;" title="{ev_count}件の予定">●<br><span style="font-size:.6rem;">{ev_count}</span></td>'
                    else:
                        html += '<td style="background:#ecfdf5;text-align:center;padding:4px;border:1px solid #ddd;color:#15803d;">●</td>'
                else:
                    # 休み（予定があれば休日出勤扱いで表示）
                    if ev_count > 0:
                        html += f'<td style="background:#fef3c7;text-align:center;padding:4px;border:1px solid #ddd;color:#d97706;font-weight:700;" title="休日出勤 {ev_count}件">▲</td>'
                    else:
                        html += '<td style="background:#f9fafb;text-align:center;padding:4px;border:1px solid #ddd;color:#d1d5db;">-</td>'
            html += f'<td style="text-align:center;padding:4px;border:1px solid #ddd;font-weight:700;">{work_count}日</td></tr>'
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

        # 凡例
        st.markdown('<div style="margin-top:12px;font-size:.75rem;color:#6b7280;">凡例: '
                    '<span style="background:#ecfdf5;color:#15803d;padding:2px 8px;">● 出勤</span> '
                    '<span style="background:#dbeafe;color:#1e3a5f;padding:2px 8px;">● 出勤+予定あり(数字)</span> '
                    '<span style="background:#fef3c7;color:#d97706;padding:2px 8px;">▲ 休日出勤</span> '
                    '<span style="background:#f9fafb;color:#9ca3af;padding:2px 8px;">- 休み</span></div>',
                    unsafe_allow_html=True)

        # その月の集計
        st.markdown('<div class="section-head">月間サマリー</div>', unsafe_allow_html=True)
        summary_rows = []
        for _, s in active_staff_cal.iterrows():
            sid = int(s["id"])
            wc = sum(1 for d in days if get_workday_v2(s, d, workdays_df, holidays_df)[0])
            ec = sum(event_set.get((sid, str(d)), 0) for d in days)
            summary_rows.append({"従業員": s["name"], "出勤日数": wc, "予定件数": ec})
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════
# タブ3: 従業員管理（勤務時間廃止・出勤日登録方式）
# ════════════════════════════════════════════════════════
with tab_staff:
    task_names = tasks_df["name"].tolist() if not tasks_df.empty else []

    # 従業員追加
    st.markdown('<div class="section-head">従業員を追加</div>', unsafe_allow_html=True)
    with st.form(key="add_staff_form"):
        ac1, ac2 = st.columns(2)
        with ac1:
            new_name  = st.text_input("名前 *")
            new_email = st.text_input("メール（任意）")
            new_phone = st.text_input("電話（任意）")
            new_emp = st.selectbox("雇用形態 *",
                ["アルバイト・業務委託（出勤日を登録）", "契約社員・正社員（休日を登録）"])
        with ac2:
            new_skills = st.multiselect("担当可能な業務", task_names)
            st.caption("正社員のデフォルト勤務時間（変更可）")
            dc1, dc2 = st.columns(2)
            with dc1: new_dstart = st.time_input("開始", value=time_type(10,0), key="new_dstart")
            with dc2: new_dend   = st.time_input("終了", value=time_type(19,0), key="new_dend")
            new_note   = st.text_area("メモ", height=68)
        if st.form_submit_button("従業員を登録する"):
            if not new_name.strip():
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                emp_type = "fulltime" if "正社員" in new_emp else "parttime"
                res = sb_insert("staff_members", {
                    "name":      new_name.strip(),
                    "email":     new_email.strip() or None,
                    "phone":     new_phone.strip() or None,
                    "skills":    json.dumps(new_skills, ensure_ascii=False),
                    "work_schedule": "{}",
                    "employment_type": emp_type,
                    "default_start": fmt_time(new_dstart),
                    "default_end":   fmt_time(new_dend),
                    "note":      new_note.strip() or None,
                    "is_active": True,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear(); st.rerun()

    # 出勤日を登録（アルバイト・業務委託用）
    st.markdown('<div class="section-head">出勤日を登録（アルバイト・業務委託）</div>', unsafe_allow_html=True)
    st.caption("アルバイト・業務委託の方の出勤日と勤務時間を登録します。正社員の個別勤務時間の上書きにも使えます。")
    if staff_df.empty:
        st.markdown('<div class="info-box">先に従業員を登録してください</div>', unsafe_allow_html=True)
    else:
        active_staff = staff_df[staff_df["is_active"] == True] if "is_active" in staff_df.columns else staff_df
        staff_options = {s["name"]: int(s["id"]) for _, s in active_staff.iterrows()}
        with st.form(key="add_workday_form"):
            wc1, wc2, wc3, wc4 = st.columns(4)
            with wc1: wd_staff = st.selectbox("従業員 *", list(staff_options.keys()))
            with wc2: wd_date  = st.date_input("出勤日 *", value=date.today())
            with wc3: wd_start = st.time_input("開始", value=time_type(10,0))
            with wc4: wd_end   = st.time_input("終了", value=time_type(19,0))
            if st.form_submit_button("出勤日を登録する"):
                sid = staff_options[wd_staff]
                existing_wd = pd.DataFrame()
                if not workdays_df.empty:
                    existing_wd = workdays_df[
                        (workdays_df["staff_id"] == sid) &
                        (workdays_df["work_date"].astype(str) == str(wd_date))
                    ]
                if not existing_wd.empty:
                    sb_update("staff_work_days", {
                        "start_time": fmt_time(wd_start),
                        "end_time":   fmt_time(wd_end),
                    }, {"id": int(existing_wd.iloc[0]["id"])})
                    st.markdown(f'<div class="success-box">{wd_staff}さんの{wd_date}の勤務時間を更新しました</div>', unsafe_allow_html=True)
                else:
                    sb_insert("staff_work_days", {
                        "staff_id":   sid,
                        "work_date":  str(wd_date),
                        "start_time": fmt_time(wd_start),
                        "end_time":   fmt_time(wd_end),
                    })
                    st.markdown(f'<div class="success-box">{wd_staff}さんの{wd_date}を出勤日として登録しました</div>', unsafe_allow_html=True)
                st.cache_data.clear(); st.rerun()

    # 休日を登録（契約社員・正社員用）
    st.markdown('<div class="section-head">休日を登録（契約社員・正社員）</div>', unsafe_allow_html=True)
    st.caption("正社員・契約社員の方の休日を登録します。休日以外は自動的に出勤（デフォルト勤務時間）になります。")
    if not staff_df.empty:
        # 正社員のみ選択肢に
        fulltime_staff = active_staff[active_staff["employment_type"] == "fulltime"] if "employment_type" in active_staff.columns else pd.DataFrame()
        if fulltime_staff.empty:
            st.markdown('<div class="info-box">契約社員・正社員が登録されていません</div>', unsafe_allow_html=True)
        else:
            ft_options = {s["name"]: int(s["id"]) for _, s in fulltime_staff.iterrows()}
            with st.form(key="add_holiday_form"):
                hc1, hc2, hc3 = st.columns([2, 2, 1])
                with hc1: hd_staff = st.selectbox("従業員 *", list(ft_options.keys()), key="hd_staff")
                with hc2: hd_date  = st.date_input("休日 *", value=date.today(), key="hd_date")
                with hc3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    hd_submit = st.form_submit_button("休日を登録")
                if hd_submit:
                    sid = ft_options[hd_staff]
                    existing_hd = pd.DataFrame()
                    if not holidays_df.empty:
                        existing_hd = holidays_df[
                            (holidays_df["staff_id"] == sid) &
                            (holidays_df["holiday_date"].astype(str) == str(hd_date))
                        ]
                    if existing_hd.empty:
                        sb_insert("staff_holidays", {"staff_id": sid, "holiday_date": str(hd_date)})
                        st.markdown(f'<div class="success-box">{hd_staff}さんの{hd_date}を休日として登録しました</div>', unsafe_allow_html=True)
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.markdown('<div class="info-box">既に休日として登録されています</div>', unsafe_allow_html=True)

            # 登録済み休日一覧
            if not holidays_df.empty:
                ft_ids = list(ft_options.values())
                future_hd = holidays_df[
                    (holidays_df["staff_id"].isin(ft_ids)) &
                    (holidays_df["holiday_date"].astype(str) >= str(date.today()))
                ].sort_values("holiday_date")
                if not future_hd.empty:
                    st.markdown("**今後の休日:**")
                    for _, hd in future_hd.iterrows():
                        hdid = int(hd["id"])
                        hd_sname = "不明"
                        sm = fulltime_staff[fulltime_staff["id"] == hd["staff_id"]]
                        if not sm.empty: hd_sname = sm.iloc[0]["name"]
                        hc1, hc2 = st.columns([4, 1])
                        with hc1:
                            st.caption(f"{hd_sname} — {hd['holiday_date']}")
                        with hc2:
                            if st.button("削除", key=f"delhd_{hdid}"):
                                sb_delete("staff_holidays", {"id": hdid})
                                st.cache_data.clear(); st.rerun()

    # 従業員一覧
    st.markdown('<div class="section-head">従業員一覧</div>', unsafe_allow_html=True)
    if staff_df.empty:
        st.markdown('<div class="info-box">従業員がいません</div>', unsafe_allow_html=True)
    else:
        for i, (_, s) in enumerate(staff_df.iterrows()):
            sid = int(s["id"])
            skills = parse_json_field(s.get("skills"), [])
            active = s.get("is_active", True)
            # このスタッフの今後の出勤日
            future_wd = pd.DataFrame()
            if not workdays_df.empty:
                future_wd = workdays_df[
                    (workdays_df["staff_id"] == sid) &
                    (workdays_df["work_date"].astype(str) >= str(date.today()))
                ].sort_values("work_date")

            emp_type = s.get("employment_type", "parttime") or "parttime"
            emp_label = "契約社員・正社員" if emp_type == "fulltime" else "アルバイト・業務委託"
            with st.expander(f"{'🟢' if active else '⚫'} {s['name']} | {emp_label} | 担当: {', '.join(skills) if skills else '未設定'}"):
                st.markdown(f"**雇用形態:** {emp_label}")
                st.markdown(f"**担当可能業務:** {', '.join(skills) if skills else '未設定'}")
                if emp_type == "fulltime":
                    st.markdown(f"**デフォルト勤務時間:** {fmt_time(s.get('default_start','10:00'))}〜{fmt_time(s.get('default_end','19:00'))}")
                if s.get("email"): st.markdown(f"**メール:** {s['email']}")
                if s.get("phone"): st.markdown(f"**電話:** {s['phone']}")

                # 今後の出勤日一覧
                if not future_wd.empty:
                    st.markdown("**今後の出勤日:**")
                    for _, wd in future_wd.iterrows():
                        wdid = int(wd["id"])
                        wc1, wc2 = st.columns([4, 1])
                        with wc1:
                            wdate = pd.to_datetime(wd["work_date"]).date()
                            st.caption(f"{wd['work_date']}（{WEEKDAY_JP[wdate.weekday()]}） {fmt_time(wd['start_time'])}〜{fmt_time(wd['end_time'])}")
                        with wc2:
                            if st.button("削除", key=f"del_wd_{wdid}_{i}"):
                                sb_delete("staff_work_days", {"id": wdid})
                                st.cache_data.clear(); st.rerun()
                else:
                    st.caption("今後の出勤日は登録されていません")

                # ── 従業員情報を編集 ────────────────────────────────────────
                st.markdown("---")
                st.markdown("**従業員情報を編集**")
                with st.form(key=f"edit_staff_{sid}_{i}"):
                    esc1, esc2 = st.columns(2)
                    with esc1:
                        e_name  = st.text_input("名前", value=s["name"], key=f"esn_{sid}_{i}")
                        e_email = st.text_input("メール", value=s.get("email","") or "", key=f"ese_{sid}_{i}")
                        e_phone = st.text_input("電話", value=s.get("phone","") or "", key=f"esp_{sid}_{i}")
                        # 雇用形態
                        emp_opts = ["アルバイト・業務委託（出勤日を登録）", "契約社員・正社員（休日を登録）"]
                        cur_emp_idx = 1 if emp_type == "fulltime" else 0
                        e_emp = st.selectbox("雇用形態", emp_opts, index=cur_emp_idx, key=f"esemp_{sid}_{i}")
                    with esc2:
                        e_skills = st.multiselect("担当可能な業務", task_names, default=[sk for sk in skills if sk in task_names], key=f"essk_{sid}_{i}")
                        st.caption("正社員のデフォルト勤務時間")
                        edc1, edc2 = st.columns(2)
                        with edc1:
                            try:
                                ds_parts = fmt_time(s.get("default_start","10:00")).split(":")
                                cur_dstart = time_type(int(ds_parts[0]), int(ds_parts[1]))
                            except Exception:
                                cur_dstart = time_type(10, 0)
                            e_dstart = st.time_input("開始", value=cur_dstart, key=f"esds_{sid}_{i}")
                        with edc2:
                            try:
                                de_parts = fmt_time(s.get("default_end","19:00")).split(":")
                                cur_dend = time_type(int(de_parts[0]), int(de_parts[1]))
                            except Exception:
                                cur_dend = time_type(19, 0)
                            e_dend = st.time_input("終了", value=cur_dend, key=f"esde_{sid}_{i}")
                        e_note = st.text_input("メモ", value=s.get("note","") or "", key=f"esnote_{sid}_{i}")

                    if st.form_submit_button("✏️ 従業員情報を更新する"):
                        new_emp_type = "fulltime" if "正社員" in e_emp else "parttime"
                        sb_update("staff_members", {
                            "name":            e_name.strip(),
                            "email":           e_email.strip() or None,
                            "phone":           e_phone.strip() or None,
                            "skills":          json.dumps(e_skills, ensure_ascii=False),
                            "employment_type": new_emp_type,
                            "default_start":   fmt_time(e_dstart),
                            "default_end":     fmt_time(e_dend),
                            "note":            e_note.strip() or None,
                        }, {"id": sid})
                        st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                        st.cache_data.clear(); st.rerun()

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("無効化" if active else "有効化", key=f"toggle_staff_{sid}_{i}"):
                        sb_update("staff_members", {"is_active": not active}, {"id": sid})
                        st.cache_data.clear(); st.rerun()
                with bc2:
                    if st.button("🗑️ 削除", key=f"del_staff_{sid}_{i}"):
                        sb_delete("staff_members", {"id": sid})
                        st.cache_data.clear(); st.rerun()

# ════════════════════════════════════════════════════════
# タブ4: 予定管理
# ════════════════════════════════════════════════════════
with tab_events:
    if staff_df.empty:
        st.markdown('<div class="info-box">先に従業員を登録してください</div>', unsafe_allow_html=True)
    else:
        active_staff = staff_df[staff_df["is_active"] == True] if "is_active" in staff_df.columns else staff_df
        staff_options = {s["name"]: int(s["id"]) for _, s in active_staff.iterrows()}
        task_names = tasks_df["name"].tolist() if not tasks_df.empty else []

        # 予定モード選択
        event_mode = st.radio("予定タイプ", ["単独予定", "複数人予定（研修・新人教育など）"], horizontal=True)

        if event_mode == "単独予定":
            st.markdown('<div class="section-head">予定を追加</div>', unsafe_allow_html=True)
            with st.form(key="add_event_form"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    ev_staff = st.selectbox("担当者 *", list(staff_options.keys()))
                    ev_task  = st.selectbox("業務種類 *", task_names)
                    ev_date  = st.date_input("日付", value=st.session_state["sched_date"])
                with ec2:
                    ev_start = st.time_input("開始時間", value=time_type(10,0))
                    ev_dur   = st.number_input("所要時間（時間）", min_value=0.5, value=2.0, step=0.5)
                    calc_end = calc_end_time(ev_start, ev_dur)
                    st.markdown(f'<div class="info-box">終了時間（自動計算）: <strong>{calc_end}</strong></div>', unsafe_allow_html=True)
                ec3, ec4 = st.columns(2)
                with ec3: ev_location = st.text_input("📍 場所（任意）", placeholder="例: 渋谷")
                with ec4: ev_memo = st.text_input("メモ（任意）")

                if st.form_submit_button("予定を追加する"):
                    sid = staff_options[ev_staff]
                    staff_row = active_staff[active_staff["id"] == sid].iloc[0]
                    skills = parse_json_field(staff_row.get("skills"), [])

                    # 出勤日チェック（staff_work_days ベース）
                    is_work, w_start, w_end = get_workday(sid, ev_date, workdays_df)

                    status = "confirmed"; reasons = []; is_holiday_work = False
                    if not is_work:
                        status = "need_action"
                        reasons.append(f"{ev_staff}さんは{ev_date}が出勤日として登録されていません")
                        is_holiday_work = True
                    else:
                        start_f = time_to_float(ev_start); end_f = time_to_float(calc_end)
                        ws_f = time_to_float(w_start); we_f = time_to_float(w_end)
                        if ws_f is not None and we_f is not None:
                            if start_f < ws_f or end_f > we_f:
                                status = "adjusting"
                                reasons.append(f"勤務時間（{fmt_time(w_start)}〜{fmt_time(w_end)}）外です")

                    if skills and ev_task not in skills:
                        status = "need_action"
                        reasons.append(f"{ev_staff}さんは「{ev_task}」を担当できません")

                    res = sb_insert("staff_events", {
                        "staff_id":        sid,
                        "task_type":       ev_task,
                        "event_date":      str(ev_date),
                        "planned_start":   fmt_time(ev_start),
                        "planned_end":     calc_end,
                        "location":        ev_location.strip() or None,
                        "memo":            ev_memo.strip() or None,
                        "status":          status,
                        "is_holiday_work": is_holiday_work,
                        "adjust_reason":   " / ".join(reasons) if reasons else None,
                    })
                    if res:
                        if status == "confirmed":
                            st.markdown('<div class="success-box">✅ 予定を追加しました（確定）</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="err-box">⚠️ 予定を追加しましたが調整が必要です<br>理由: {" / ".join(reasons)}</div>', unsafe_allow_html=True)
                            # 代替スタッフ候補
                            st.markdown('<div class="section-head">代替スタッフ候補</div>', unsafe_allow_html=True)
                            candidates = []
                            for _, cs in active_staff.iterrows():
                                if int(cs["id"]) == sid: continue
                                c_work, c_ws, c_we = get_workday(int(cs["id"]), ev_date, workdays_df)
                                c_skills = parse_json_field(cs.get("skills"), [])
                                if not c_work: continue
                                if c_skills and ev_task not in c_skills: continue
                                c_events = events_df[
                                    (events_df["staff_id"] == cs["id"]) &
                                    (events_df["event_date"].astype(str) == str(ev_date))
                                ] if not events_df.empty else pd.DataFrame()
                                busy = False
                                start_f = time_to_float(ev_start); end_f = time_to_float(calc_end)
                                if not c_events.empty:
                                    for _, ce in c_events.iterrows():
                                        cps = time_to_float(ce["planned_start"]); cpe = time_to_float(ce["planned_end"])
                                        if cps is not None and cpe is not None:
                                            if not (end_f <= cps or start_f >= cpe):
                                                busy = True; break
                                if not busy:
                                    candidates.append(f"{cs['name']}（{fmt_time(c_ws)}〜{fmt_time(c_we)} 勤務・{ev_task}対応可）")
                            if candidates:
                                for c in candidates:
                                    st.markdown(f'<div class="success-box">✅ {c}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="info-box">対応可能な代替スタッフが見つかりませんでした</div>', unsafe_allow_html=True)
                        st.cache_data.clear()

        else:
            # ── 複数人予定（研修・新人教育）──────────────────────────────────
            st.markdown('<div class="section-head">複数人予定を追加（研修・新人教育など）</div>', unsafe_allow_html=True)
            st.caption("先生役と生徒役をまとめて選び、全員のタイムラインに同じ予定を一括登録します。")
            with st.form(key="add_multi_event_form"):
                mec1, mec2 = st.columns(2)
                with mec1:
                    m_task = st.selectbox("業務種類 *", task_names, key="m_task")
                    m_date = st.date_input("日付", value=st.session_state["sched_date"], key="m_date")
                    m_teacher = st.selectbox("先生役（任意）", ["なし"] + list(staff_options.keys()), key="m_teacher")
                with mec2:
                    m_start = st.time_input("開始時間", value=time_type(10,0), key="m_start")
                    m_dur   = st.number_input("所要時間（時間）", min_value=0.5, value=2.0, step=0.5, key="m_dur")
                    m_calc_end = calc_end_time(m_start, m_dur)
                    st.markdown(f'<div class="info-box">終了時間: <strong>{m_calc_end}</strong></div>', unsafe_allow_html=True)

                # 生徒役（複数選択）
                m_students = st.multiselect("参加者（生徒役・複数選択可）*", list(staff_options.keys()), key="m_students")
                mec3, mec4 = st.columns(2)
                with mec3: m_location = st.text_input("📍 場所（任意）", key="m_loc")
                with mec4: m_memo = st.text_input("メモ（任意）", key="m_memo")

                if st.form_submit_button("全員に予定を追加する"):
                    # 対象者リストを作成（先生+生徒、重複排除）
                    targets = []
                    if m_teacher != "なし":
                        targets.append((m_teacher, "先生"))
                    for stu in m_students:
                        if stu != m_teacher:  # 先生と重複しない
                            targets.append((stu, "参加者"))

                    if not targets:
                        st.markdown('<div class="err-box">先生役または参加者を1人以上選んでください</div>', unsafe_allow_html=True)
                    else:
                        success_count = 0
                        warn_list = []
                        for staff_name_t, role in targets:
                            tsid = staff_options[staff_name_t]
                            tstaff_row = active_staff[active_staff["id"] == tsid].iloc[0]
                            tskills = parse_json_field(tstaff_row.get("skills"), [])

                            # 出勤日チェック
                            t_is_work, t_ws, t_we = get_workday(tsid, m_date, workdays_df)
                            t_status = "confirmed"; t_reasons = []; t_holiday = False
                            if not t_is_work:
                                t_status = "need_action"
                                t_reasons.append(f"{staff_name_t}さんは出勤日ではありません")
                                t_holiday = True

                            # メモに役割を追記
                            role_memo = f"[{role}] " + (m_memo.strip() if m_memo.strip() else "")

                            res = sb_insert("staff_events", {
                                "staff_id":        tsid,
                                "task_type":       m_task,
                                "event_date":      str(m_date),
                                "planned_start":   fmt_time(m_start),
                                "planned_end":     m_calc_end,
                                "location":        m_location.strip() or None,
                                "memo":            role_memo.strip() or None,
                                "status":          t_status,
                                "is_holiday_work": t_holiday,
                                "is_group":        True,
                                "adjust_reason":   " / ".join(t_reasons) if t_reasons else None,
                            })
                            if res:
                                success_count += 1
                                if t_reasons:
                                    warn_list.append(f"{staff_name_t}: {' / '.join(t_reasons)}")

                        st.markdown(f'<div class="success-box">✅ {success_count}名に「{m_task}」を登録しました</div>', unsafe_allow_html=True)
                        if warn_list:
                            st.markdown('<div class="err-box">⚠️ 以下は調整が必要です:<br>' + "<br>".join(warn_list) + '</div>', unsafe_allow_html=True)
                        st.cache_data.clear()

# ════════════════════════════════════════════════════════
# タブ5: 設定（業務種類の追加・編集・削除）
# ════════════════════════════════════════════════════════
with tab_settings:
    st.markdown('<div class="section-head">業務種類を追加</div>', unsafe_allow_html=True)
    with st.form(key="add_task_form"):
        tc1, tc2, tc3 = st.columns([3, 2, 1])
        with tc1: t_name  = st.text_input("業務種類名 *", placeholder="例: 通訳")
        with tc2: t_color = st.color_picker("表示色", value="#3b82f6")
        with tc3: t_order = st.number_input("表示順", min_value=0, value=10)
        if st.form_submit_button("業務種類を追加"):
            if not t_name.strip():
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("staff_task_types", {"name": t_name.strip(), "color": t_color, "sort_order": t_order})
                if res:
                    st.markdown('<div class="success-box">追加しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear(); st.rerun()

    # 登録済み業務種類（編集・削除）
    st.markdown('<div class="section-head">登録済み業務種類（編集・削除）</div>', unsafe_allow_html=True)
    if tasks_df.empty:
        st.markdown('<div class="info-box">業務種類がありません</div>', unsafe_allow_html=True)
    else:
        for i, (_, t) in enumerate(tasks_df.iterrows()):
            tid = int(t["id"])
            with st.expander(f'{t["name"]}（表示順: {t.get("sort_order",0)}）'):
                with st.form(key=f"edit_task_{tid}_{i}"):
                    etc1, etc2, etc3 = st.columns([3, 2, 1])
                    with etc1:
                        e_name = st.text_input("業務種類名", value=t["name"], key=f"etn_{tid}_{i}")
                    with etc2:
                        e_color = st.color_picker("表示色", value=t.get("color","#3b82f6"), key=f"etc_{tid}_{i}")
                    with etc3:
                        e_order = st.number_input("表示順", min_value=0, value=int(t.get("sort_order",0)), key=f"eto_{tid}_{i}")
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.form_submit_button("✏️ 更新する"):
                            sb_update("staff_task_types", {
                                "name": e_name.strip(), "color": e_color, "sort_order": e_order
                            }, {"id": tid})
                            st.markdown('<div class="success-box">更新しました</div>', unsafe_allow_html=True)
                            st.cache_data.clear(); st.rerun()
                    with bc2:
                        if st.form_submit_button("🗑️ 削除する"):
                            sb_delete("staff_task_types", {"id": tid})
                            st.cache_data.clear(); st.rerun()
