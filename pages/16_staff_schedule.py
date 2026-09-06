"""
pages/16_staff_schedule.py — スタッフ・スケジュール管理システム

タブ構成:
  ダッシュボード / 日別タイムライン / 従業員管理 / 予定管理 / 設定
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
WEEKDAYS    = ["mon","tue","wed","thu","fri","sat","sun"]
WEEKDAY_JP  = {"mon":"月","tue":"火","wed":"水","thu":"木","fri":"金","sat":"土","sun":"日"}
STATUS_MAP  = {
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
    try:
        return json.loads(val)
    except Exception:
        return default

def time_to_float(t):
    """time または 'HH:MM' を float時間に変換"""
    if t is None: return None
    if isinstance(t, str):
        try:
            h, m = map(int, t[:5].split(":"))
            return h + m / 60
        except Exception:
            return None
    try:
        return t.hour + t.minute / 60
    except Exception:
        return None

def fmt_time(t):
    if t is None: return ""
    if isinstance(t, str): return t[:5]
    try: return t.strftime("%H:%M")
    except Exception: return str(t)[:5]

def calc_end_time(start_t, hours_dur):
    """開始時刻 + 所要時間 → 終了時刻"""
    start_f = time_to_float(start_t)
    if start_f is None: return None
    end_f   = start_f + hours_dur
    h = int(end_f) % 24
    m = int(round((end_f - int(end_f)) * 60))
    if m == 60: h += 1; m = 0
    return f"{h:02d}:{m:02d}"

def get_weekday_key(d):
    return WEEKDAYS[d.weekday()]

@st.cache_data(ttl=60)
def load_all():
    tasks  = to_df(sb_select("staff_task_types", order="sort_order"))
    staff  = to_df(sb_select("staff_members",    order="name"))
    events = to_df(sb_select("staff_events",     order="event_date"))
    return tasks, staff, events

def get_task_color(task_name, tasks_df):
    if not tasks_df.empty:
        m = tasks_df[tasks_df["name"] == task_name]
        if not m.empty:
            return m.iloc[0].get("color", "#3b82f6")
    return "#3b82f6"

def is_working_day(staff_row, target_date):
    """その日が勤務日か（休日でないか）を判定。戻り: (勤務日か, 開始, 終了)"""
    ws = parse_json_field(staff_row.get("work_schedule"), {})
    wd = get_weekday_key(target_date)
    day_schedule = ws.get(wd)
    if day_schedule is None or day_schedule == {}:
        return False, None, None
    return True, day_schedule.get("start"), day_schedule.get("end")

# ════════════════════════════════════════════════════════
tasks_df, staff_df, events_df = load_all()

st.markdown('<div class="page-title">スタッフ・スケジュール管理</div>', unsafe_allow_html=True)

tab_dash, tab_timeline, tab_staff, tab_events, tab_settings = st.tabs([
    "ダッシュボード", "日別タイムライン", "従業員管理", "予定管理", "設定"
])

# 選択中の日付（session_stateで管理）
if "sched_date" not in st.session_state:
    st.session_state["sched_date"] = date.today()

# ════════════════════════════════════════════════════════
# タブ1: ダッシュボード
# ════════════════════════════════════════════════════════
with tab_dash:
    today = date.today()
    st.markdown(f'<div class="section-head">本日 {today}（{WEEKDAY_JP[get_weekday_key(today)]}）の状況</div>', unsafe_allow_html=True)

    # 本日の予定
    today_events = pd.DataFrame()
    if not events_df.empty:
        today_events = events_df[events_df["event_date"].astype(str) == str(today)].copy()
        today_events = today_events[today_events["status"] != "cancelled"]

    # 本日出勤スタッフ数
    working_staff = 0
    if not staff_df.empty:
        for _, s in staff_df.iterrows():
            if not s.get("is_active", True): continue
            is_work, _, _ = is_working_day(s, today)
            # 休日出勤もカウント
            has_holiday_work = False
            if not today_events.empty:
                se = today_events[today_events["staff_id"] == s["id"]]
                has_holiday_work = bool(se["is_holiday_work"].any()) if "is_holiday_work" in se.columns else False
            if is_work or has_holiday_work:
                working_staff += 1

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

    # ── 要対応一覧 ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-head">⚠️ 要対応一覧</div>', unsafe_allow_html=True)
    if not events_df.empty:
        # 今日以降の要対応・調整中・代替要
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
                    f'<div class="err-box">'
                    f'<strong>{staff_name}</strong> | {ev["event_date"]} '
                    f'{fmt_time(ev["planned_start"])}〜{fmt_time(ev["planned_end"])} | '
                    f'{ev["task_type"]} | <span style="color:{status_color};">{status_label}</span>'
                    f'{"<br>理由: " + reason if reason else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )
    else:
        st.markdown('<div class="info-box">予定データがありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ2: 日別タイムライン
# ════════════════════════════════════════════════════════
with tab_timeline:
    # 日付ナビゲーション
    nc1, nc2, nc3, nc4 = st.columns([1, 1, 1, 3])
    with nc1:
        if st.button("← 前日"):
            st.session_state["sched_date"] -= timedelta(days=1); st.rerun()
    with nc2:
        if st.button("今日", type="primary"):
            st.session_state["sched_date"] = date.today(); st.rerun()
    with nc3:
        if st.button("翌日 →"):
            st.session_state["sched_date"] += timedelta(days=1); st.rerun()
    with nc4:
        picked = st.date_input("日付選択", value=st.session_state["sched_date"], key="date_picker", label_visibility="collapsed")
        if picked != st.session_state["sched_date"]:
            st.session_state["sched_date"] = picked; st.rerun()

    view_date = st.session_state["sched_date"]
    wd_jp     = WEEKDAY_JP[get_weekday_key(view_date)]
    st.markdown(f'<div class="section-head">{view_date}（{wd_jp}）のタイムライン</div>', unsafe_allow_html=True)

    if staff_df.empty:
        st.markdown('<div class="info-box">従業員が登録されていません。「従業員管理」タブで追加してください。</div>', unsafe_allow_html=True)
    else:
        # その日の予定
        day_events = pd.DataFrame()
        if not events_df.empty:
            day_events = events_df[events_df["event_date"].astype(str) == str(view_date)].copy()

        # 時間軸ヘッダー
        header_html = '<div style="display:flex;border-bottom:2px solid #1e3a5f;padding-bottom:4px;margin-bottom:4px;">'
        header_html += '<div style="width:80px;flex-shrink:0;font-weight:700;font-size:.8rem;">従業員</div>'
        for h in HOURS:
            header_html += f'<div style="flex:1;text-align:center;font-size:.7rem;color:#6b7280;">{h}:00</div>'
        header_html += '</div>'
        st.markdown(header_html, unsafe_allow_html=True)

        # 各スタッフの行
        for _, s in staff_df.iterrows():
            if not s.get("is_active", True): continue
            sid   = int(s["id"])
            sname = s["name"]
            is_work, w_start, w_end = is_working_day(s, view_date)

            # このスタッフの予定
            s_events = day_events[day_events["staff_id"] == sid] if not day_events.empty else pd.DataFrame()
            s_events = s_events[s_events["status"] != "cancelled"] if not s_events.empty else s_events
            has_holiday_work = bool(s_events["is_holiday_work"].any()) if (not s_events.empty and "is_holiday_work" in s_events.columns) else False

            # 行を構築
            row_html = '<div style="display:flex;align-items:center;border-bottom:1px solid #e5e7eb;min-height:44px;position:relative;">'
            row_html += f'<div style="width:80px;flex-shrink:0;font-weight:600;font-size:.85rem;">{sname}</div>'

            # タイムライン領域
            row_html += '<div style="flex:1;display:flex;position:relative;height:36px;">'

            if not is_work and not has_holiday_work:
                # 休日
                row_html += '<div style="flex:1;background:#f3f4f6;color:#9ca3af;text-align:center;line-height:36px;font-size:.8rem;border-radius:4px;">休日</div>'
            else:
                # 勤務時間の背景
                total_hours = len(HOURS)
                w_start_f = time_to_float(w_start) if w_start else HOURS[0]
                w_end_f   = time_to_float(w_end) if w_end else HOURS[-1]+1

                # 各時間スロットを描画
                for h in HOURS:
                    slot_events = []
                    if not s_events.empty:
                        for _, ev in s_events.iterrows():
                            ps = time_to_float(ev["planned_start"])
                            pe = time_to_float(ev["planned_end"])
                            if ps is not None and pe is not None and ps <= h < pe:
                                slot_events.append(ev)

                    if slot_events:
                        ev = slot_events[0]
                        color = get_task_color(ev["task_type"], tasks_df)
                        row_html += f'<div style="flex:1;background:{color};color:white;text-align:center;line-height:36px;font-size:.65rem;overflow:hidden;white-space:nowrap;" title="{ev["task_type"]}">{ev["task_type"][:4]}</div>'
                    elif is_work and w_start_f <= h < w_end_f:
                        # 勤務中の空き時間
                        row_html += '<div style="flex:1;background:#ecfdf5;border:1px dashed #a7f3d0;" title="空き"></div>'
                    else:
                        # 勤務時間外
                        row_html += '<div style="flex:1;background:#fafafa;"></div>'

            row_html += '</div></div>'
            st.markdown(row_html, unsafe_allow_html=True)

        # 凡例
        st.markdown('<div style="margin-top:12px;font-size:.75rem;color:#6b7280;">凡例: '
                    '<span style="background:#ecfdf5;border:1px dashed #a7f3d0;padding:2px 8px;">空き</span> '
                    '<span style="background:#f3f4f6;padding:2px 8px;">休日</span> '
                    '各色=業務種類</div>', unsafe_allow_html=True)

        # ── その日の予定リスト（詳細・実績記録）──────────────────────────────
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

                with st.expander(
                    f'{staff_name} | {ev["task_type"]} | '
                    f'{fmt_time(ev["planned_start"])}〜{fmt_time(ev["planned_end"])} | {status_label}'
                ):
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

                    # 開始・終了ボタン
                    bc1, bc2, bc3, bc4 = st.columns(4)
                    with bc1:
                        if st.button("▶ 開始", key=f"start_{eid}_{i}"):
                            now = datetime.now().isoformat()
                            sb_update("staff_events", {"actual_start": now}, {"id": eid})
                            st.cache_data.clear(); st.rerun()
                    with bc2:
                        if st.button("■ 終了", key=f"end_{eid}_{i}"):
                            now = datetime.now().isoformat()
                            sb_update("staff_events", {"actual_end": now}, {"id": eid})
                            st.cache_data.clear(); st.rerun()
                    with bc3:
                        # ステータス変更
                        new_status = st.selectbox("状態変更", list(STATUS_MAP.keys()),
                            index=list(STATUS_MAP.keys()).index(ev.get("status","confirmed")),
                            format_func=lambda x: STATUS_MAP[x][0], key=f"st_{eid}_{i}")
                        if new_status != ev.get("status","confirmed"):
                            if st.button("更新", key=f"stupd_{eid}_{i}"):
                                sb_update("staff_events", {"status": new_status}, {"id": eid})
                                st.cache_data.clear(); st.rerun()
                    with bc4:
                        if st.button("🗑️ 削除", key=f"del_{eid}_{i}"):
                            sb_delete("staff_events", {"id": eid})
                            st.cache_data.clear(); st.rerun()
        else:
            st.markdown('<div class="info-box">この日の予定はありません</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# タブ3: 従業員管理
# ════════════════════════════════════════════════════════
with tab_staff:
    st.markdown('<div class="section-head">従業員を追加</div>', unsafe_allow_html=True)

    task_names = tasks_df["name"].tolist() if not tasks_df.empty else []

    with st.form(key="add_staff_form"):
        ac1, ac2 = st.columns(2)
        with ac1:
            new_name  = st.text_input("名前 *")
            new_email = st.text_input("メール（任意）")
            new_phone = st.text_input("電話（任意）")
        with ac2:
            new_skills = st.multiselect("担当可能な業務", task_names)
            new_note   = st.text_area("メモ", height=80)

        st.markdown("**通常勤務時間（曜日ごと）**")
        st.caption("休日にする曜日は「休日」にチェック。勤務日は開始・終了時刻を設定")
        work_schedule = {}
        for wd in WEEKDAYS:
            wc1, wc2, wc3 = st.columns([1, 2, 2])
            with wc1:
                is_holiday = st.checkbox(f"{WEEKDAY_JP[wd]}曜 休日", key=f"hol_{wd}")
            if not is_holiday:
                with wc2:
                    ws = st.time_input(f"{WEEKDAY_JP[wd]}開始", value=time_type(9,0), key=f"ws_{wd}", label_visibility="collapsed")
                with wc3:
                    we = st.time_input(f"{WEEKDAY_JP[wd]}終了", value=time_type(18,0), key=f"we_{wd}", label_visibility="collapsed")
                work_schedule[wd] = {"start": fmt_time(ws), "end": fmt_time(we)}
            else:
                work_schedule[wd] = None

        if st.form_submit_button("従業員を登録する"):
            if not new_name.strip():
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("staff_members", {
                    "name":          new_name.strip(),
                    "email":         new_email.strip() or None,
                    "phone":         new_phone.strip() or None,
                    "skills":        json.dumps(new_skills, ensure_ascii=False),
                    "work_schedule": json.dumps(work_schedule, ensure_ascii=False),
                    "note":          new_note.strip() or None,
                    "is_active":     True,
                })
                if res:
                    st.markdown('<div class="success-box">登録しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear(); st.rerun()

    # 従業員一覧
    st.markdown('<div class="section-head">従業員一覧</div>', unsafe_allow_html=True)
    if staff_df.empty:
        st.markdown('<div class="info-box">従業員がいません</div>', unsafe_allow_html=True)
    else:
        for i, (_, s) in enumerate(staff_df.iterrows()):
            sid = int(s["id"])
            skills = parse_json_field(s.get("skills"), [])
            ws     = parse_json_field(s.get("work_schedule"), {})
            active = s.get("is_active", True)

            work_days = [WEEKDAY_JP[wd] for wd in WEEKDAYS if ws.get(wd)]
            holidays  = [WEEKDAY_JP[wd] for wd in WEEKDAYS if not ws.get(wd)]

            with st.expander(f"{'🟢' if active else '⚫'} {s['name']} | 担当: {', '.join(skills) if skills else '未設定'}"):
                st.markdown(f"**担当可能業務:** {', '.join(skills) if skills else '未設定'}")
                st.markdown(f"**勤務曜日:** {', '.join(work_days) if work_days else 'なし'}")
                st.markdown(f"**休日:** {', '.join(holidays) if holidays else 'なし'}")
                if s.get("email"): st.markdown(f"**メール:** {s['email']}")
                if s.get("phone"): st.markdown(f"**電話:** {s['phone']}")

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
    st.markdown('<div class="section-head">予定を追加</div>', unsafe_allow_html=True)

    if staff_df.empty:
        st.markdown('<div class="info-box">先に従業員を登録してください</div>', unsafe_allow_html=True)
    else:
        active_staff = staff_df[staff_df["is_active"] == True] if "is_active" in staff_df.columns else staff_df
        staff_options = {s["name"]: int(s["id"]) for _, s in active_staff.iterrows()}
        task_names = tasks_df["name"].tolist() if not tasks_df.empty else []

        with st.form(key="add_event_form"):
            ec1, ec2 = st.columns(2)
            with ec1:
                ev_staff = st.selectbox("担当者 *", list(staff_options.keys()))
                ev_task  = st.selectbox("業務種類 *", task_names)
                ev_date  = st.date_input("日付", value=st.session_state["sched_date"])
            with ec2:
                ev_start = st.time_input("開始時間", value=time_type(10,0))
                ev_dur   = st.number_input("所要時間（時間）", min_value=0.5, value=2.0, step=0.5)
                # 終了時間の自動計算プレビュー
                calc_end = calc_end_time(ev_start, ev_dur)
                st.markdown(f'<div class="info-box">終了時間（自動計算）: <strong>{calc_end}</strong></div>', unsafe_allow_html=True)

            ec3, ec4 = st.columns(2)
            with ec3:
                ev_location = st.text_input("📍 場所（任意）", placeholder="例: 渋谷")
            with ec4:
                ev_memo = st.text_input("メモ（任意）")

            if st.form_submit_button("予定を追加する"):
                sid = staff_options[ev_staff]
                staff_row = active_staff[active_staff["id"] == sid].iloc[0]

                # 勤務日チェック
                is_work, w_start, w_end = is_working_day(staff_row, ev_date)
                skills = parse_json_field(staff_row.get("skills"), [])

                # ステータスと調整理由を自動判定
                status = "confirmed"
                reasons = []
                is_holiday_work = False

                if not is_work:
                    status = "need_action"
                    reasons.append(f"{ev_staff}さんは{WEEKDAY_JP[get_weekday_key(ev_date)]}曜が休日です")
                    is_holiday_work = True
                else:
                    # 勤務時間内かチェック
                    start_f = time_to_float(ev_start)
                    end_f   = time_to_float(calc_end)
                    ws_f    = time_to_float(w_start)
                    we_f    = time_to_float(w_end)
                    if ws_f is not None and we_f is not None:
                        if start_f < ws_f or end_f > we_f:
                            status = "adjusting"
                            reasons.append(f"勤務時間（{w_start}〜{w_end}）外です")

                # 担当可能業務チェック
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
                        st.markdown(
                            f'<div class="err-box">⚠️ 予定を追加しましたが調整が必要です<br>'
                            f'理由: {" / ".join(reasons)}</div>',
                            unsafe_allow_html=True
                        )
                        # 代替スタッフ候補を表示
                        st.markdown('<div class="section-head">代替スタッフ候補</div>', unsafe_allow_html=True)
                        candidates = []
                        for _, cs in active_staff.iterrows():
                            if int(cs["id"]) == sid: continue
                            c_work, c_ws, c_we = is_working_day(cs, ev_date)
                            c_skills = parse_json_field(cs.get("skills"), [])
                            if not c_work: continue
                            if c_skills and ev_task not in c_skills: continue
                            # その時間に予定がないか
                            c_events = events_df[
                                (events_df["staff_id"] == cs["id"]) &
                                (events_df["event_date"].astype(str) == str(ev_date))
                            ] if not events_df.empty else pd.DataFrame()
                            busy = False
                            start_f = time_to_float(ev_start)
                            end_f   = time_to_float(calc_end)
                            if not c_events.empty:
                                for _, ce in c_events.iterrows():
                                    cps = time_to_float(ce["planned_start"])
                                    cpe = time_to_float(ce["planned_end"])
                                    if cps is not None and cpe is not None:
                                        if not (end_f <= cps or start_f >= cpe):
                                            busy = True; break
                            if not busy:
                                candidates.append(f"{cs['name']}（{c_ws}〜{c_we} 勤務・{ev_task}対応可）")
                        if candidates:
                            for c in candidates:
                                st.markdown(f'<div class="success-box">✅ {c}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="info-box">対応可能な代替スタッフが見つかりませんでした</div>', unsafe_allow_html=True)
                    st.cache_data.clear()

# ════════════════════════════════════════════════════════
# タブ5: 設定（業務種類）
# ════════════════════════════════════════════════════════
with tab_settings:
    st.markdown('<div class="section-head">業務種類の管理</div>', unsafe_allow_html=True)

    with st.form(key="add_task_form"):
        tc1, tc2, tc3 = st.columns([3, 2, 1])
        with tc1: t_name  = st.text_input("業務種類名 *", placeholder="例: 通訳")
        with tc2: t_color = st.color_picker("表示色", value="#3b82f6")
        with tc3: t_order = st.number_input("表示順", min_value=0, value=10)
        if st.form_submit_button("業務種類を追加"):
            if not t_name.strip():
                st.markdown('<div class="err-box">名前は必須です</div>', unsafe_allow_html=True)
            else:
                res = sb_insert("staff_task_types", {
                    "name": t_name.strip(), "color": t_color, "sort_order": t_order
                })
                if res:
                    st.markdown('<div class="success-box">追加しました</div>', unsafe_allow_html=True)
                    st.cache_data.clear(); st.rerun()

    st.markdown('<div class="section-head">登録済み業務種類</div>', unsafe_allow_html=True)
    if not tasks_df.empty:
        for i, (_, t) in enumerate(tasks_df.iterrows()):
            tid = int(t["id"])
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f'<span style="display:inline-block;width:16px;height:16px;background:{t.get("color","#3b82f6")};border-radius:3px;vertical-align:middle;margin-right:8px;"></span>**{t["name"]}**', unsafe_allow_html=True)
            with c2:
                st.caption(f"順序: {t.get('sort_order',0)}")
            with c3:
                if st.button("削除", key=f"del_task_{tid}_{i}"):
                    sb_delete("staff_task_types", {"id": tid})
                    st.cache_data.clear(); st.rerun()
