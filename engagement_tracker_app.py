import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime, timedelta, time
import plotly.graph_objects as go
import plotly.express as px
import math

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Engagement Tracker | CLC LBU",
    page_icon="📊",
    layout="wide",
)

# ── Branding ─────────────────────────────────────────────────────────────────
TEAL        = "#1A7A7A"
AMBER       = "#C8760A"
ENGAGED_COL = "#1a7a4a"
NOT_COL     = "#a32d2d"
SUPPORT_COLORS = {
    "1:1":          TEAL,
    "Small Group":  AMBER,
    "Independent":  "#4a72b0",
    "Peer":         "#6a4ab0",
}
SUPPORT_TYPES = ["1:1", "Small Group", "Independent", "Peer"]
PROGRAMS      = ["JP", "PY", "SY"]
DAY_NAMES     = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

st.markdown(f"""
<style>
  .block-container {{ padding-top: 1.2rem; }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
  .stTabs [data-baseweb="tab"] {{
    background: #f0f5f5; border-radius: 6px 6px 0 0;
    padding: 6px 16px; font-size: 13px;
  }}
  .stTabs [aria-selected="true"] {{
    background: {TEAL} !important; color: white !important;
  }}
  div[data-testid="metric-container"] > div {{
    background: #f7f7f5; border-radius: 8px; padding: 10px;
    border: 1px solid #e0e0e0;
  }}
  .eng-badge  {{ display:inline-block; padding:2px 10px; border-radius:20px;
    background:#e8f5ee; color:{ENGAGED_COL}; font-weight:600; font-size:12px; }}
  .not-badge  {{ display:inline-block; padding:2px 10px; border-radius:20px;
    background:#fce8e8; color:{NOT_COL};     font-weight:600; font-size:12px; }}
  .hyp-card   {{ background:white; border:1px solid #e0e0e0; border-radius:10px;
    padding:14px 16px; margin-bottom:12px; }}
  .tag {{ display:inline-block; font-size:10px; font-weight:700; letter-spacing:.5px;
    padding:2px 8px; border-radius:20px; margin-right:4px; }}
  .tag-bsem {{ background:#e8f5f5; color:#0f5252; }}
  .tag-pbis {{ background:#fdf3e3; color:#7a4a00; }}
  .tag-t1   {{ background:#e8f5ee; color:{ENGAGED_COL}; }}
  .tag-t2   {{ background:#fff3e0; color:#7a4a00; }}
  .tag-t3   {{ background:#fce8e8; color:{NOT_COL}; }}
</style>
""", unsafe_allow_html=True)

# ── Supabase ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

# ── Data helpers ──────────────────────────────────────────────────────────────
def get_students():
    r = supabase.table("engagement_students").select("*").eq("active", True).order("name").execute()
    return r.data or []

def get_entries_for_date(student_id: str, entry_date: date) -> list:
    r = (supabase.table("engagement_entries")
         .select("*")
         .eq("student_id", student_id)
         .eq("entry_date", str(entry_date))
         .order("entry_time")
         .execute())
    return r.data or []

def get_entries_range(student_id: str, start: date, end: date) -> pd.DataFrame:
    r = (supabase.table("engagement_entries")
         .select("*")
         .eq("student_id", student_id)
         .gte("entry_date", str(start))
         .lte("entry_date", str(end))
         .order("entry_date")
         .order("entry_time")
         .execute())
    data = r.data or []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.date
    return df

def get_all_entries(student_id: str) -> pd.DataFrame:
    r = (supabase.table("engagement_entries")
         .select("*")
         .eq("student_id", student_id)
         .order("entry_date")
         .order("entry_time")
         .execute())
    data = r.data or []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.date
    return df

def add_student(name: str, program: str, dob=None, notes: str = "") -> bool:
    try:
        supabase.table("engagement_students").insert({
            "name": name, "program": program,
            "dob": str(dob) if dob else None,
            "notes": notes or None,
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding student: {e}")
        return False

def log_entry(student_id: str, entry_date: date, entry_time: time,
              engaged: bool, support_type: str, note: str, logged_by: str) -> bool:
    try:
        supabase.table("engagement_entries").insert({
            "student_id":   student_id,
            "entry_date":   str(entry_date),
            "entry_time":   entry_time.strftime("%H:%M:%S"),
            "engaged":      engaged,
            "support_type": support_type,
            "note":         note or None,
            "logged_by":    logged_by,
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error logging entry: {e}")
        return False

def delete_entry(entry_id: str) -> bool:
    try:
        supabase.table("engagement_entries").delete().eq("id", entry_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting entry: {e}")
        return False

# ── Session state ─────────────────────────────────────────────────────────────
if "staff_name" not in st.session_state:
    st.session_state.staff_name = ""
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0

# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_title, col_staff = st.columns([0.08, 0.62, 0.30])
with col_logo:
    st.markdown(f"<div style='font-size:32px;margin-top:4px;'>📊</div>", unsafe_allow_html=True)
with col_title:
    st.markdown(f"<h2 style='color:{TEAL};margin:0;font-size:22px;'>Engagement Tracker</h2>"
                f"<p style='color:#888;font-size:12px;margin:0;'>CLC Learning & Behaviour Unit</p>",
                unsafe_allow_html=True)
with col_staff:
    staff_input = st.text_input("Your name", value=st.session_state.staff_name,
                                 placeholder="Staff name (logged with entries)",
                                 label_visibility="collapsed")
    if staff_input:
        st.session_state.staff_name = staff_input

st.divider()

# ── Student selector ──────────────────────────────────────────────────────────
students = get_students()
student_names = [s["name"] for s in students]
student_map   = {s["name"]: s for s in students}

col_sel, col_prog, col_add = st.columns([0.45, 0.25, 0.30])
with col_sel:
    selected_name = st.selectbox("Student", ["— select —"] + student_names,
                                  label_visibility="collapsed")
with col_prog:
    if selected_name != "— select —" and selected_name in student_map:
        s = student_map[selected_name]
        st.markdown(f"<div style='padding:8px 0;font-size:13px;color:#888;'>"
                    f"Program: <strong style='color:{TEAL};'>{s['program']}</strong></div>",
                    unsafe_allow_html=True)
with col_add:
    with st.popover("+ Add student", use_container_width=True):
        new_name    = st.text_input("Student name")
        new_program = st.selectbox("Program", PROGRAMS)
        new_dob     = st.date_input("Date of birth (optional)", value=None)
        new_notes   = st.text_area("Notes (optional)", height=60)
        if st.button("Add student", type="primary", use_container_width=True):
            if new_name.strip():
                if add_student(new_name.strip(), new_program, new_dob, new_notes):
                    st.success(f"Added {new_name.strip()}")
                    st.rerun()
            else:
                st.warning("Enter a student name.")

student = student_map.get(selected_name) if selected_name != "— select —" else None

if not student:
    st.info("Select or add a student to begin.")
    st.stop()

student_id = student["id"]

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_log, tab_today, tab_week, tab_hyp, tab_reports = st.tabs(
    ["📝 Log Entry", "📅 Today", "📆 This Week", "🧠 Hypothesis", "📄 Reports"]
)

# ═══════════════════════════════════════════════════════════════════
# TAB 1 — LOG ENTRY
# ═══════════════════════════════════════════════════════════════════
with tab_log:
    if not st.session_state.staff_name:
        st.warning("Enter your name at the top before logging entries.")

    col_form, col_entries = st.columns([0.45, 0.55])

    with col_form:
        st.markdown(f"#### Log an entry for {selected_name}")

        log_date = st.date_input("Date", value=date.today())
        log_time = st.time_input("Time", value=datetime.now().time().replace(second=0, microsecond=0))

        st.markdown("**Engagement status**")
        eng_col1, eng_col2 = st.columns(2)
        with eng_col1:
            engaged_btn = st.button("✅  Engaged", use_container_width=True,
                                     type="primary" if st.session_state.get("_eng") == True else "secondary")
        with eng_col2:
            not_btn = st.button("❌  Not Engaged", use_container_width=True,
                                 type="primary" if st.session_state.get("_eng") == False else "secondary")

        if engaged_btn:
            st.session_state["_eng"] = True
        if not_btn:
            st.session_state["_eng"] = False

        if "_eng" in st.session_state:
            status_label = "✅ Engaged" if st.session_state["_eng"] else "❌ Not Engaged"
            status_col   = ENGAGED_COL if st.session_state["_eng"] else NOT_COL
            st.markdown(f"<div style='font-size:13px;color:{status_col};font-weight:600;"
                        f"padding:4px 0;'>Selected: {status_label}</div>", unsafe_allow_html=True)

        st.markdown("**Support type**")
        support_cols = st.columns(4)
        sup_labels = {"1:1": "👤 1:1", "Small Group": "👥 Small\nGroup",
                      "Independent": "📖 Indep.", "Peer": "🤝 Peer"}
        for i, sup in enumerate(SUPPORT_TYPES):
            with support_cols[i]:
                if st.button(sup_labels[sup], use_container_width=True,
                              type="primary" if st.session_state.get("_sup") == sup else "secondary"):
                    st.session_state["_sup"] = sup

        if "_sup" in st.session_state:
            st.markdown(f"<div style='font-size:13px;color:{TEAL};font-weight:600;"
                        f"padding:4px 0;'>Support: {st.session_state['_sup']}</div>",
                        unsafe_allow_html=True)

        log_note = st.text_area("Note (optional)", height=80,
                                 placeholder="Context, trigger, antecedent, behaviour observed...")

        if st.button("Log Entry", type="primary", use_container_width=True):
            if "_eng" not in st.session_state:
                st.error("Select Engaged or Not Engaged.")
            elif "_sup" not in st.session_state:
                st.error("Select a support type.")
            elif not st.session_state.staff_name:
                st.error("Enter your name at the top.")
            else:
                if log_entry(student_id, log_date, log_time,
                             st.session_state["_eng"],
                             st.session_state["_sup"],
                             log_note,
                             st.session_state.staff_name):
                    st.success("Entry logged!")
                    st.rerun()

    with col_entries:
        st.markdown(f"#### Today's entries — {date.today().strftime('%a %-d %b')}")
        todays = get_entries_for_date(student_id, date.today())
        if not todays:
            st.info("No entries yet today.")
        else:
            for e in reversed(todays):
                row1, row2 = st.columns([0.85, 0.15])
                with row1:
                    badge = ("✅ Engaged" if e["engaged"] else "❌ Not Engaged")
                    badge_css = "eng-badge" if e["engaged"] else "not-badge"
                    note_txt = f" — *{e['note']}*" if e.get("note") else ""
                    st.markdown(
                        f"`{e['entry_time'][:5]}` "
                        f"<span class='{badge_css}'>{badge}</span> "
                        f"· {e['support_type']}"
                        f"{note_txt} "
                        f"<span style='font-size:11px;color:#aaa;'>({e['logged_by']})</span>",
                        unsafe_allow_html=True,
                    )
                with row2:
                    if st.button("✕", key=f"del_{e['id']}", help="Delete"):
                        delete_entry(e["id"])
                        st.rerun()
            st.caption(f"{len(todays)} entries — "
                       f"{sum(1 for e in todays if e['engaged'])} engaged / "
                       f"{sum(1 for e in todays if not e['engaged'])} not engaged")


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — TODAY
# ═══════════════════════════════════════════════════════════════════
with tab_today:
    selected_date = st.date_input("View date", value=date.today(), key="today_date")
    entries = get_entries_for_date(student_id, selected_date)

    if not entries:
        st.info(f"No entries logged for {selected_name} on {selected_date.strftime('%a %-d %b %Y')}.")
    else:
        total   = len(entries)
        eng_n   = sum(1 for e in entries if e["engaged"])
        not_n   = total - eng_n
        pct     = round(eng_n / total * 100)
        pct_col = ENGAGED_COL if pct >= 70 else (AMBER if pct >= 50 else NOT_COL)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total entries",    total)
        m2.metric("Engaged",          eng_n)
        m3.metric("Not engaged",      not_n)
        m4.metric("Engagement rate",  f"{pct}%")

        # Timeline
        st.markdown("##### Engagement timeline")
        times_min = []
        for e in entries:
            h, m, *_ = e["entry_time"].split(":")
            times_min.append(int(h) * 60 + int(m))

        min_t = min(times_min + [480])
        max_t = max(times_min + [900])
        span  = max_t - min_t or 1

        fig_tl = go.Figure()
        for i, e in enumerate(entries):
            t     = times_min[i]
            next_t = times_min[i + 1] if i + 1 < len(times_min) else max_t
            width  = max(0.5, (next_t - t) / span)
            color  = ENGAGED_COL if e["engaged"] else NOT_COL
            label  = "Engaged" if e["engaged"] else "Not engaged"
            fig_tl.add_trace(go.Bar(
                x=[width], y=[0], orientation="h",
                marker_color=color, base=[(t - min_t) / span],
                name=label,
                hovertemplate=f"{e['entry_time'][:5]} — {label} ({e['support_type']})<extra></extra>",
                showlegend=False,
            ))
        fig_tl.update_layout(
            height=80, margin=dict(l=0, r=0, t=0, b=20),
            xaxis=dict(range=[0, 1], tickvals=[0, 0.5, 1],
                       ticktext=[f"{min_t//60}:{min_t%60:02d}",
                                 f"{((min_t+max_t)//2)//60}:{((min_t+max_t)//2)%60:02d}",
                                 f"{max_t//60}:{max_t%60:02d}"],
                       showgrid=False),
            yaxis=dict(visible=False),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            barmode="overlay",
        )
        st.plotly_chart(fig_tl, use_container_width=True, config={"displayModeBar": False})

        # Support breakdown
        st.markdown("##### Support type breakdown")
        sup_c = {s: 0 for s in SUPPORT_TYPES}
        sup_e = {s: 0 for s in SUPPORT_TYPES}
        for e in entries:
            sup_c[e["support_type"]] += 1
            if e["engaged"]:
                sup_e[e["support_type"]] += 1

        fig_sup = go.Figure()
        for sup in SUPPORT_TYPES:
            if sup_c[sup]:
                eng_pct = round(sup_e[sup] / sup_c[sup] * 100)
                fig_sup.add_trace(go.Bar(
                    name=sup, x=[sup], y=[sup_c[sup]],
                    marker_color=SUPPORT_COLORS[sup],
                    text=[f"{sup_c[sup]} entries<br>{eng_pct}% engaged"],
                    textposition="outside",
                ))
        fig_sup.update_layout(
            height=260, showlegend=False,
            margin=dict(l=0, r=0, t=20, b=0),
            yaxis=dict(title="Entries"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sup, use_container_width=True, config={"displayModeBar": False})

        # Entry log
        st.markdown("##### Entry log")
        df_day = pd.DataFrame(entries)[["entry_time","engaged","support_type","note","logged_by"]]
        df_day["entry_time"]    = df_day["entry_time"].str[:5]
        df_day["engaged"]       = df_day["engaged"].map({True:"✅ Engaged", False:"❌ Not engaged"})
        df_day.columns          = ["Time","Status","Support","Note","Logged by"]
        df_day                  = df_day.fillna("—")
        st.dataframe(df_day, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — WEEK
# ═══════════════════════════════════════════════════════════════════
with tab_week:
    wc1, wc2, wc3 = st.columns([0.25, 0.50, 0.25])
    with wc1:
        if st.button("← Prev week"):
            st.session_state.week_offset -= 1
    with wc3:
        if st.button("Next week →"):
            st.session_state.week_offset += 1
    with wc2:
        if st.button("This week", use_container_width=True):
            st.session_state.week_offset = 0

    # Compute Mon–Fri of offset week
    today    = date.today()
    dow      = today.weekday()
    monday   = today - timedelta(days=dow) + timedelta(weeks=st.session_state.week_offset)
    friday   = monday + timedelta(days=4)
    week_lbl = f"Week of {monday.strftime('%-d %b')} – {friday.strftime('%-d %b %Y')}"
    st.markdown(f"<h4 style='color:{TEAL};margin:6px 0;'>{week_lbl}</h4>", unsafe_allow_html=True)

    df_week = get_entries_range(student_id, monday, friday)

    week_data = []
    for i in range(5):
        d    = monday + timedelta(days=i)
        rows = df_week[df_week["entry_date"] == d] if not df_week.empty else pd.DataFrame()
        tot  = len(rows)
        eng  = int(rows["engaged"].sum()) if tot else 0
        pct  = round(eng / tot * 100) if tot else None
        week_data.append({"day": DAY_NAMES[i], "date": d, "total": tot, "engaged": eng,
                          "not_eng": tot - eng, "pct": pct})

    # Week grid chart
    fig_week = go.Figure()
    for wd in week_data:
        if wd["total"]:
            label = wd["day"][:3] + f"\n{wd['date'].strftime('%-d %b')}"
            fig_week.add_trace(go.Bar(
                name="Engaged", x=[label], y=[wd["engaged"]],
                marker_color=ENGAGED_COL, showlegend=True if wd == week_data[0] else False,
            ))
            fig_week.add_trace(go.Bar(
                name="Not engaged", x=[label], y=[wd["not_eng"]],
                marker_color=NOT_COL, showlegend=True if wd == week_data[0] else False,
            ))
    fig_week.update_layout(
        barmode="stack", height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis=dict(title="Entries"),
        legend=dict(orientation="h", y=1.1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_week, use_container_width=True, config={"displayModeBar": False})

    # Week table
    week_rows = []
    for wd in week_data:
        is_today = wd["date"] == date.today()
        pct_disp = f"{wd['pct']}%" if wd["pct"] is not None else "—"
        week_rows.append({
            "Day":          ("📌 " if is_today else "") + wd["day"],
            "Date":         wd["date"].strftime("%-d %b"),
            "Total":        wd["total"] or "—",
            "Engaged":      wd["engaged"] if wd["total"] else "—",
            "Not engaged":  wd["not_eng"] if wd["total"] else "—",
            "Rate":         pct_disp,
        })
    st.dataframe(pd.DataFrame(week_rows), use_container_width=True, hide_index=True)

    # Week summary metrics
    all_tot  = sum(w["total"]   for w in week_data)
    all_eng  = sum(w["engaged"] for w in week_data)
    week_pct = round(all_eng / all_tot * 100) if all_tot else 0

    wm1, wm2, wm3, wm4 = st.columns(4)
    wm1.metric("Days with data", sum(1 for w in week_data if w["total"]))
    wm2.metric("Total entries",  all_tot)
    wm3.metric("Engaged",        all_eng)
    wm4.metric("Weekly rate",    f"{week_pct}%" if all_tot else "—")


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — HYPOTHESIS
# ═══════════════════════════════════════════════════════════════════
with tab_hyp:
    st.markdown(f"<div style='background:{TEAL};color:white;border-radius:10px;"
                f"padding:14px 18px;margin-bottom:16px;'>"
                f"<strong>BSEM & PBIS Pattern Analysis</strong> — {selected_name}</div>",
                unsafe_allow_html=True)

    # Gather last 10 school days
    end_d   = date.today()
    start_d = end_d - timedelta(days=20)  # enough buffer for 10 school days
    df_all  = get_entries_range(student_id, start_d, end_d)

    if df_all.empty:
        st.info("No data found. Log entries in the Log Entry tab first.")
    else:
        total   = len(df_all)
        eng_n   = int(df_all["engaged"].sum())
        eng_rate = eng_n / total

        # Time of day
        def hour_of(t):
            return int(str(t).split(":")[0])

        df_all["hour"] = df_all["entry_time"].apply(hour_of)
        morn = df_all[df_all["hour"] < 12]
        aft  = df_all[df_all["hour"] >= 12]
        morn_rate = float(morn["engaged"].mean()) if len(morn) else None
        aft_rate  = float(aft["engaged"].mean())  if len(aft)  else None

        # Support analysis
        sup_stats = {}
        for sup in SUPPORT_TYPES:
            rows = df_all[df_all["support_type"] == sup]
            if len(rows) >= 2:
                sup_stats[sup] = {
                    "count": len(rows),
                    "rate":  float(rows["engaged"].mean()),
                }

        # Day variability
        day_rates = df_all.groupby("entry_date")["engaged"].mean()
        sd_val    = float(day_rates.std()) if len(day_rates) >= 3 else None

        # Build cards
        cards = []

        # PBIS Tier
        if eng_rate >= 0.8:
            tier, tier_tag, tier_css = "Tier 1", "Tier 1", "tag-t1"
            tier_text = (f"At {round(eng_rate*100)}% engagement, universal Tier 1 supports appear effective. "
                         f"The student is accessing the curriculum with expected success.")
            tier_strats = ["Continue current strategies and monitor weekly",
                           "Celebrate strengths directly with the student",
                           "Consider peer leadership / mentoring opportunities"]
        elif eng_rate >= 0.55:
            tier, tier_tag, tier_css = "Tier 2", "Tier 2", "tag-t2"
            tier_text = (f"Engagement at {round(eng_rate*100)}% suggests Tier 2 targeted support is warranted. "
                         f"The student is partially accessing the curriculum but requires structured additional support.")
            tier_strats = ["Check-In Check-Out (CICO) process",
                           "Small group social-emotional skills program",
                           "Behaviour support planning with defined GAS goals",
                           "Fortnightly data review cycle with team"]
        else:
            tier, tier_tag, tier_css = "Tier 3", "Tier 3", "tag-t3"
            tier_text = (f"Engagement at {round(eng_rate*100)}% indicates significant barriers to learning. "
                         f"Intensive individualised Tier 3 support is required with a formal behaviour support plan.")
            tier_strats = ["Formal Functional Behaviour Assessment (FBA)",
                           "Individualised Behaviour Support Plan (BSP)",
                           "Consult with BSSS / Psychologist / allied health",
                           "Intensive relationship-based re-engagement program",
                           "Multi-agency collaboration and case conference"]

        cards.append({"icon": "📊", "fw": "pbis", "title": f"{tier} Support Indicated",
                      "body": tier_text, "tier_tag": tier_tag, "tier_css": tier_css,
                      "strats": tier_strats})

        # Morning/afternoon pattern
        if morn_rate is not None and aft_rate is not None and abs(aft_rate - morn_rate) > 0.20:
            if aft_rate < morn_rate:
                cards.append({"icon": "🌇", "fw": "bsem",
                    "title": "Afternoon dysregulation pattern",
                    "body": (f"Morning engagement ({round(morn_rate*100)}%) is notably stronger than afternoon "
                             f"({round(aft_rate*100)}%). This may reflect fatigue-related dysregulation, a narrowing "
                             f"window of tolerance as the day progresses, or cumulative unmet sensory/regulation needs."),
                    "strats": ["Introduce afternoon regulation break or co-regulation routine",
                               "Sensory diet review with OT",
                               "Movement-based transition activity mid-afternoon",
                               "Reduce cognitive load in afternoon sessions"]})
            else:
                cards.append({"icon": "🌅", "fw": "bsem",
                    "title": "Morning dysregulation pattern",
                    "body": (f"Morning engagement ({round(morn_rate*100)}%) is notably lower than afternoon "
                             f"({round(aft_rate*100)}%). The student may be arriving dysregulated — "
                             f"possibly from home context, sleep difficulties, or heightened anxiety at school start."),
                    "strats": ["Morning arrival check-in with trusted adult",
                               "Gentle transition routine before academic demands",
                               "Wellbeing conversation at drop-off or arrival",
                               "Consider home-school communication plan"]})

        # 1:1 relational
        if "1:1" in sup_stats and sup_stats["1:1"]["rate"] > 0.70:
            r = round(sup_stats["1:1"]["rate"] * 100)
            cards.append({"icon": "🤝", "fw": "bsem",
                "title": "Relational safety key to engagement",
                "body": (f"The student is significantly more engaged during 1:1 support ({r}%). "
                         f"This aligns with BSEM's emphasis on relational safety — the student accesses "
                         f"learning most effectively when they feel seen, safe, and supported by a trusted adult."),
                "strats": ["Identify and maintain a consistent trusted adult",
                           "Prioritise relationship before task — connect before content",
                           "Use 1:1 as a bridge to gradual independence",
                           "Co-regulation moments before group or independent tasks"]})

        # Peer strength
        if "Peer" in sup_stats and sup_stats["Peer"]["rate"] > 0.65:
            r = round(sup_stats["Peer"]["rate"] * 100)
            cards.append({"icon": "👥", "fw": "bsem",
                "title": "Peer connection supports engagement",
                "body": (f"Peer-supported tasks show {r}% engagement — a strength to leverage. "
                         f"Social connection is a core BSEM wellbeing domain. Peer relationships may be "
                         f"providing belonging, scaffolding, and motivation."),
                "strats": ["Intentionally structure peer partnerships",
                           "Use cooperative learning structures",
                           "Build peer mentoring opportunities",
                           "Monitor peer dynamics for potential social triggers"]})

        # Independent difficulty
        if "Independent" in sup_stats and sup_stats["Independent"]["rate"] < 0.45:
            r = round(sup_stats["Independent"]["rate"] * 100)
            cards.append({"icon": "📖", "fw": "bsem",
                "title": "Difficulty with independent learning tasks",
                "body": (f"Engagement drops to {r}% during independent work. This may reflect limited "
                         f"self-regulation capacity, difficulty initiating tasks (executive function), "
                         f"low self-efficacy, or tasks that exceed the student's current window of tolerance."),
                "strats": ["Break independent tasks into smaller, explicit steps",
                           "Visual task schedule / now-then board",
                           "Check task match — reduce cognitive load if needed",
                           "Gradual release with fading adult support",
                           "Strength-based entry points to build confidence"]})

        # Small group difficulty
        if "Small Group" in sup_stats and sup_stats["Small Group"]["rate"] < 0.45:
            cards.append({"icon": "💬", "fw": "bsem",
                "title": "Group dynamics may be a trigger",
                "body": ("Small group settings are associated with lower engagement. This may indicate "
                         "heightened social anxiety, peer relational issues, sensory sensitivity to group "
                         "noise, or social skill deficits that make group participation feel unsafe."),
                "strats": ["Assess peer dynamics within group settings",
                           "Review group composition and size",
                           "Social skills / emotion coaching support",
                           "Sensory assessment if noise or proximity is a factor",
                           "Zones of Regulation check-ins before group tasks"]})

        # High variability
        if sd_val is not None and sd_val > 0.25:
            cards.append({"icon": "⚡", "fw": "bsem",
                "title": "High day-to-day variability observed",
                "body": (f"Engagement varies significantly across school days (SD: {sd_val:.2f}). "
                         f"This inconsistency is a hallmark of trauma-impacted learning — the student's "
                         f"regulated state is likely influenced by external factors such as home context, "
                         f"sleep, specific triggers, or transitions."),
                "strats": ["Investigate patterns around low-engagement days (staffing, timetable, day of week)",
                           "Home-school wellbeing communication",
                           "Wellbeing rating check-in at start of each day",
                           "Predictable routines to reduce transition anxiety",
                           "Trauma-informed formulation with team"]})

        # Strengths
        if eng_rate > 0.50:
            cards.append({"icon": "⭐", "fw": "bsem",
                "title": "Strengths to build on",
                "body": (f"Despite barriers, the student demonstrates {round(eng_rate*100)}% engagement — "
                         f"showing capacity for learning when conditions are right. This is a significant "
                         f"strength and evidence the student is reaching toward connection and participation."),
                "strats": [f"Explore what made the {round(eng_rate*100)}% engaged moments work",
                           "Identify and name strengths directly with the student",
                           "Use engaged moments as the baseline — not the exception",
                           "Strengths-based conversation: 'I notice when you...'"]})

        # Render cards
        for c in cards:
            fw_col = TEAL if c["fw"] == "bsem" else AMBER
            fw_lbl = "BSEM" if c["fw"] == "bsem" else "PBIS"
            tier_html = (f"<span class='tag {c.get('tier_css','')}'>{c.get('tier_tag','')}</span>"
                         if c.get("tier_tag") else "")
            strats_html = "".join(f"<li style='margin-bottom:3px;font-size:12px;color:#555;'>{s}</li>"
                                  for s in c["strats"])
            st.markdown(f"""<div class="hyp-card">
              <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:8px;">
                <div style="font-size:24px;">{c["icon"]}</div>
                <div>
                  <span class="tag tag-{c['fw']}">{fw_lbl}</span>{tier_html}
                  <div style="font-size:14px;font-weight:600;margin-top:2px;">{c["title"]}</div>
                </div>
              </div>
              <div style="font-size:13px;color:#555;line-height:1.6;margin-bottom:8px;">{c["body"]}</div>
              <div style="border-top:1px solid #eee;padding-top:8px;">
                <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
                            color:{fw_col};margin-bottom:4px;">Suggested strategies</div>
                <ul style="padding-left:16px;">{strats_html}</ul>
              </div>
            </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 5 — REPORTS
# ═══════════════════════════════════════════════════════════════════
with tab_reports:

    def report_css():
        return f"""
        <style>
          *{{box-sizing:border-box;margin:0;padding:0;}}
          body{{font-family:-apple-system,'Segoe UI',sans-serif;font-size:13px;color:#1a1a1a;
                background:#fff;padding:24px 32px;max-width:840px;margin:0 auto;}}
          .rpt-header{{border-bottom:3px solid {TEAL};padding-bottom:14px;margin-bottom:22px;}}
          .org{{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}}
          .rpt-title{{font-size:22px;font-weight:700;color:{TEAL};margin-bottom:2px;}}
          .rpt-sub{{font-size:13px;color:#555;}}
          .rpt-meta{{font-size:11px;color:#aaa;margin-top:6px;}}
          .section{{margin-bottom:22px;}}
          .sec-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;
                      color:{TEAL};border-bottom:1px solid #e0e0e0;padding-bottom:5px;margin-bottom:12px;}}
          .stats-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}}
          .stat-box{{background:#f7f7f5;border:1px solid #e0e0e0;border-radius:8px;padding:10px 12px;text-align:center;}}
          .stat-num{{font-size:26px;font-weight:700;font-family:'Courier New',monospace;}}
          .stat-lbl{{font-size:10px;color:#888;margin-top:2px;text-transform:uppercase;letter-spacing:.3px;}}
          .teal{{color:{TEAL};}} .grn{{color:{ENGAGED_COL};}} .red{{color:{NOT_COL};}} .amb{{color:{AMBER};}}
          table{{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;}}
          th{{background:#f0f5f5;color:{TEAL};font-weight:600;padding:7px 10px;
              text-align:left;border:1px solid #d4e8e8;}}
          td{{padding:6px 10px;border:1px solid #e8e8e8;vertical-align:top;}}
          tr:nth-child(even) td{{background:#fafafa;}}
          .badge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;}}
          .badge.eng{{background:#e8f5ee;color:{ENGAGED_COL};}}
          .badge.not{{background:#fce8e8;color:{NOT_COL};}}
          .hyp-card{{border:1px solid #e0e0e0;border-radius:8px;padding:12px 14px;margin-bottom:10px;}}
          .tag{{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.5px;
                padding:2px 6px;border-radius:20px;margin-right:4px;}}
          .tag-bsem{{background:#e8f5f5;color:#0f5252;}}
          .tag-pbis{{background:#fdf3e3;color:#7a4a00;}}
          .tag-t1{{background:#e8f5ee;color:{ENGAGED_COL};}}
          .tag-t2{{background:#fff3e0;color:#7a4a00;}}
          .tag-t3{{background:#fce8e8;color:{NOT_COL};}}
          .bar-wrap{{height:26px;background:#f0f0f0;border-radius:6px;overflow:hidden;
                     display:flex;margin-bottom:4px;}}
          .bar-seg{{height:100%;}}
          .sup-row{{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:12px;}}
          .sup-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
          .sup-bar-out{{flex:1;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;}}
          .sup-bar-in{{height:100%;border-radius:4px;}}
          .footer{{margin-top:28px;padding-top:12px;border-top:1px solid #e0e0e0;
                   font-size:10px;color:#aaa;display:flex;justify-content:space-between;}}
          .print-btn{{display:block;margin:0 0 16px;padding:9px 18px;background:{TEAL};
                      color:white;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;}}
          @media print{{.print-btn{{display:none;}}@page{{margin:1.5cm;}}}}
        </style>"""

    def footer_html(student_name):
        now = datetime.now().strftime("%-d %b %Y, %H:%M")
        return (f"<div class='footer'>"
                f"<span>CLC Learning &amp; Behaviour Unit — Cowandilla Learning Centre</span>"
                f"<span>Generated {now} | Student: {student_name}</span></div>")

    def sup_breakdown_html(entries_list):
        sup_c = {s: 0 for s in SUPPORT_TYPES}
        sup_e = {s: 0 for s in SUPPORT_TYPES}
        for e in entries_list:
            sup_c[e["support_type"]] += 1
            if e["engaged"]:
                sup_e[e["support_type"]] += 1
        max_c = max(sup_c.values()) or 1
        rows = ""
        for sup in SUPPORT_TYPES:
            c   = sup_c[sup]
            pct_bar = round(c / max_c * 100)
            pct_eng = round(sup_e[sup] / c * 100) if c else 0
            col = SUPPORT_COLORS[sup]
            rows += (f"<div class='sup-row'>"
                     f"<span class='sup-dot' style='background:{col}'></span>"
                     f"<span style='min-width:95px;'>{sup}</span>"
                     f"<div class='sup-bar-out'><div class='sup-bar-in' "
                     f"style='width:{pct_bar}%;background:{col}'></div></div>"
                     f"<span style='min-width:120px;color:#888;font-size:11px;'>"
                     f"{c} entries{f' ({pct_eng}% engaged)' if c else ''}</span></div>")
        return rows

    st.markdown("Download formatted summary reports for case conferences, team meetings, and placement reviews.")
    st.info("Reports download as HTML files. Open in any browser → File → Print → Save as PDF.", icon="ℹ️")
    st.divider()

    # ── DAILY REPORT ─────────────────────────────────────────────────────
    with st.expander("📅  Daily Engagement Summary", expanded=True):
        st.markdown("Snapshot of a single day — rate, timeline, support breakdown, full entry log, and reflection prompts.")
        rpt_date = st.date_input("Select date", value=date.today(), key="rpt_date")
        if st.button("Generate daily report", type="primary"):
            entries = get_entries_for_date(student_id, rpt_date)
            total   = len(entries)
            eng_n   = sum(1 for e in entries if e["engaged"])
            not_n   = total - eng_n
            pct     = round(eng_n / total * 100) if total else 0
            pc      = "grn" if pct >= 70 else ("amb" if pct >= 50 else "red")
            date_lbl = rpt_date.strftime("%A, %-d %B %Y")

            # Timeline bar
            if total:
                times_min = []
                for e in entries:
                    h, m, *_ = e["entry_time"].split(":")
                    times_min.append(int(h) * 60 + int(m))
                min_t = min(times_min + [480]); max_t = max(times_min + [900])
                span  = max_t - min_t or 1
                segs  = ""
                for i, e in enumerate(entries):
                    t      = times_min[i]
                    next_t = times_min[i + 1] if i + 1 < len(times_min) else max_t
                    w      = max(1, round((next_t - t) / span * 100))
                    col    = ENGAGED_COL if e["engaged"] else NOT_COL
                    etime  = e["entry_time"][:5]
                    segs  += f"<div class='bar-seg' style='width:{w}%;background:{col};' title='{etime}'></div>"
                tl_html = f"<div class='bar-wrap'>{segs}</div>"
                min_lbl = f"{min_t//60}:{min_t%60:02d}"
                max_lbl = f"{max_t//60}:{max_t%60:02d}"
            else:
                tl_html = "<p style='color:#888;font-size:12px;'>No entries.</p>"
                min_lbl = max_lbl = ""

            rows_html = ""
            for e in entries:
                b = "eng" if e["engaged"] else "not"
                bl = "Engaged" if e["engaged"] else "Not engaged"
                note = e.get("note") or "—"
                rows_html += (f"<tr><td>{e['entry_time'][:5]}</td>"
                              f"<td><span class='badge {b}'>{bl}</span></td>"
                              f"<td>{e['support_type']}</td>"
                              f"<td>{note}</td>"
                              f"<td>{e['logged_by']}</td></tr>")

            html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
            <title>Daily Engagement — {selected_name}</title>{report_css()}</head><body>
            <button class="print-btn" onclick="window.print()">🖨 Print / Save as PDF</button>
            <div class="rpt-header">
              <div class="org">Cowandilla Learning Centre — Learning &amp; Behaviour Unit</div>
              <div class="rpt-title">Daily Engagement Summary</div>
              <div class="rpt-sub">{selected_name} &mdash; {date_lbl}</div>
              <div class="rpt-meta">Program: {student["program"]} &nbsp;|&nbsp; Document type: Engagement Record</div>
            </div>
            <div class="section">
              <div class="sec-title">Engagement overview</div>
              <div class="stats-row">
                <div class="stat-box"><div class="stat-num teal">{total}</div><div class="stat-lbl">Total entries</div></div>
                <div class="stat-box"><div class="stat-num grn">{eng_n}</div><div class="stat-lbl">Engaged</div></div>
                <div class="stat-box"><div class="stat-num red">{not_n}</div><div class="stat-lbl">Not engaged</div></div>
                <div class="stat-box"><div class="stat-num {pc}">{pct}%</div><div class="stat-lbl">Engagement rate</div></div>
              </div>
            </div>
            <div class="section">
              <div class="sec-title">Engagement timeline</div>
              {tl_html}
              <div style="display:flex;gap:16px;margin-top:6px;font-size:11px;color:#888;">
                <span>Start: {min_lbl}</span><span>End: {max_lbl}</span>
                <span style="display:flex;align-items:center;gap:3px;">
                  <span style="width:10px;height:10px;background:{ENGAGED_COL};display:inline-block;border-radius:2px;"></span>Engaged
                </span>
                <span style="display:flex;align-items:center;gap:3px;">
                  <span style="width:10px;height:10px;background:{NOT_COL};display:inline-block;border-radius:2px;"></span>Not engaged
                </span>
              </div>
            </div>
            <div class="section">
              <div class="sec-title">Support type breakdown</div>
              {sup_breakdown_html(entries) if total else "<p style='color:#888;font-size:12px;'>No entries.</p>"}
            </div>
            <div class="section">
              <div class="sec-title">Full entry log</div>
              {"<table><thead><tr><th>Time</th><th>Status</th><th>Support</th><th>Note</th><th>Logged by</th></tr></thead><tbody>" + rows_html + "</tbody></table>" if total else "<p style='color:#888;font-size:12px;'>No entries recorded for this date.</p>"}
            </div>
            <div class="section">
              <div class="sec-title">Reflection prompts</div>
              <table><tbody>
                <tr><td style="width:36%;font-weight:600;">What supported engagement today?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">What were barriers to engagement?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">Patterns or triggers observed?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">Adjustments for tomorrow?</td><td>&nbsp;</td></tr>
              </tbody></table>
            </div>
            {footer_html(selected_name)}</body></html>"""

            fname = f"Daily_Engagement_{selected_name.replace(' ','_')}_{rpt_date}.html"
            st.download_button("⬇ Download daily report", data=html.encode(),
                               file_name=fname, mime="text/html", use_container_width=True)

    # ── WEEKLY REPORT ─────────────────────────────────────────────────────
    with st.expander("📆  Weekly Engagement Summary"):
        st.markdown("Day-by-day breakdown across a school week — trends, statistics, and support analysis.")
        week_options = {
            "This week":    0, "Last week": -1, "2 weeks ago": -2,
            "3 weeks ago": -3, "4 weeks ago": -4,
        }
        week_sel = st.selectbox("Select week", list(week_options.keys()), key="rpt_week")
        if st.button("Generate weekly report", type="primary"):
            offset   = week_options[week_sel]
            today_d  = date.today()
            mon      = today_d - timedelta(days=today_d.weekday()) + timedelta(weeks=offset)
            fri      = mon + timedelta(days=4)
            df_w     = get_entries_range(student_id, mon, fri)
            week_lbl = f"{mon.strftime('%-d %b')} – {fri.strftime('%-d %b %Y')}"

            day_rows_html = ""
            all_tot = 0; all_eng = 0
            all_entries_list = []
            for i in range(5):
                d      = mon + timedelta(days=i)
                rows   = df_w[df_w["entry_date"] == d] if not df_w.empty else pd.DataFrame()
                tot    = len(rows)
                eng    = int(rows["engaged"].sum()) if tot else 0
                all_tot += tot; all_eng += eng
                pct_d  = round(eng / tot * 100) if tot else None
                pc_d   = "grn" if (pct_d or 0) >= 70 else ("amb" if (pct_d or 0) >= 50 else "red")
                is_t   = d == date.today()
                day_rows_html += (
                    f"<tr style='{'background:#f0f8f0;' if is_t else ''}'>"
                    f"<td><strong>{DAY_NAMES[i]}</strong></td>"
                    f"<td>{d.strftime('%-d %b')}</td>"
                    f"<td style='text-align:center;'>{tot or '—'}</td>"
                    f"<td style='text-align:center;'>{eng if tot else '—'}</td>"
                    f"<td style='text-align:center;'>{tot-eng if tot else '—'}</td>"
                    f"<td style='text-align:center;font-weight:600;color:{ENGAGED_COL if (pct_d or 0)>=70 else (AMBER if (pct_d or 0)>=50 else NOT_COL)};'>"
                    f"{'—' if pct_d is None else str(pct_d)+'%'}</td></tr>")
                if tot:
                    all_entries_list.extend(rows.to_dict("records"))

            week_pct = round(all_eng / all_tot * 100) if all_tot else 0
            wp_col   = "grn" if week_pct >= 70 else ("amb" if week_pct >= 50 else "red")

            html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
            <title>Weekly Engagement — {selected_name}</title>{report_css()}</head><body>
            <button class="print-btn" onclick="window.print()">🖨 Print / Save as PDF</button>
            <div class="rpt-header">
              <div class="org">Cowandilla Learning Centre — Learning &amp; Behaviour Unit</div>
              <div class="rpt-title">Weekly Engagement Summary</div>
              <div class="rpt-sub">{selected_name} &mdash; Week of {week_lbl}</div>
              <div class="rpt-meta">Program: {student["program"]} &nbsp;|&nbsp; Document type: Engagement Record</div>
            </div>
            <div class="section">
              <div class="sec-title">Week overview</div>
              <div class="stats-row">
                <div class="stat-box"><div class="stat-num teal">{all_tot}</div><div class="stat-lbl">Total entries</div></div>
                <div class="stat-box"><div class="stat-num grn">{all_eng}</div><div class="stat-lbl">Engaged</div></div>
                <div class="stat-box"><div class="stat-num red">{all_tot-all_eng}</div><div class="stat-lbl">Not engaged</div></div>
                <div class="stat-box"><div class="stat-num {wp_col}">{week_pct}%</div><div class="stat-lbl">Weekly rate</div></div>
              </div>
            </div>
            <div class="section">
              <div class="sec-title">Day-by-day breakdown</div>
              <table><thead><tr><th>Day</th><th>Date</th><th style="text-align:center;">Entries</th>
              <th style="text-align:center;">Engaged</th><th style="text-align:center;">Not engaged</th>
              <th style="text-align:center;">Rate</th></tr></thead><tbody>{day_rows_html}</tbody></table>
            </div>
            <div class="section">
              <div class="sec-title">Support type breakdown (whole week)</div>
              {sup_breakdown_html(all_entries_list) if all_entries_list else "<p style='color:#888;font-size:12px;'>No entries this week.</p>"}
            </div>
            <div class="section">
              <div class="sec-title">Team reflection</div>
              <table><tbody>
                <tr><td style="width:36%;font-weight:600;">What patterns emerged this week?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">Which strategies were most effective?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">What adjustments are needed next week?</td><td>&nbsp;</td></tr>
                <tr><td style="font-weight:600;">Actions for team meeting?</td><td>&nbsp;</td></tr>
              </tbody></table>
            </div>
            {footer_html(selected_name)}</body></html>"""

            fname = f"Weekly_Engagement_{selected_name.replace(' ','_')}_{mon}.html"
            st.download_button("⬇ Download weekly report", data=html.encode(),
                               file_name=fname, mime="text/html", use_container_width=True)

    # ── PLACEMENT REPORT ──────────────────────────────────────────────────
    with st.expander("📋  Placement Engagement Summary"):
        st.markdown("Full longitudinal summary across all recorded data — for placement reviews, case conferences, and IEP development.")
        if st.button("Generate placement report", type="primary"):
            df_all    = get_all_entries(student_id)
            total_all = len(df_all)

            if df_all.empty:
                st.warning("No data recorded yet for this student.")
            else:
                eng_all  = int(df_all["engaged"].sum())
                not_all  = total_all - eng_all
                pct_all  = round(eng_all / total_all * 100)
                pc_all   = "grn" if pct_all >= 70 else ("amb" if pct_all >= 50 else "red")

                # Days with data
                days_with_data = df_all["entry_date"].nunique()
                date_range     = f"{df_all['entry_date'].min().strftime('%-d %b %Y')} – {df_all['entry_date'].max().strftime('%-d %b %Y')}"

                # Daily trajectory table
                day_summary = (df_all.groupby("entry_date")["engaged"]
                               .agg(["sum","count"])
                               .rename(columns={"sum":"eng","count":"tot"}))
                day_summary["pct"] = (day_summary["eng"] / day_summary["tot"] * 100).round().astype(int)
                traj_rows = ""
                for d, row in day_summary.iterrows():
                    d_lbl    = d.strftime('%a %-d %b %Y') if hasattr(d, 'strftime') else str(d)
                    pct_val  = row['pct']
                    pct_col2 = ENGAGED_COL if pct_val >= 70 else (AMBER if pct_val >= 50 else NOT_COL)
                    traj_rows += (f"<tr><td>{d_lbl}</td>"
                                  f"<td style='text-align:center;'>{row['tot']}</td>"
                                  f"<td style='text-align:center;'>{row['eng']}</td>"
                                  f"<td style='text-align:center;'>{row['tot']-row['eng']}</td>"
                                  f"<td style='text-align:center;font-weight:600;color:{pct_col2};'>{pct_val}%</td></tr>")

                # Engagement rate trend (simple text trend)
                rates = day_summary["pct"].tolist()
                if len(rates) >= 3:
                    first_half = sum(rates[:len(rates)//2]) / (len(rates)//2)
                    second_half = sum(rates[len(rates)//2:]) / (len(rates) - len(rates)//2)
                    if second_half - first_half > 8:
                        trend_txt = f"Improving — engagement rate has trended upward across the placement period (early avg: {round(first_half)}%, recent avg: {round(second_half)}%)."
                        trend_col = ENGAGED_COL
                    elif first_half - second_half > 8:
                        trend_txt = f"Declining — engagement rate has trended downward (early avg: {round(first_half)}%, recent avg: {round(second_half)}%). Review supports urgently."
                        trend_col = NOT_COL
                    else:
                        trend_txt = f"Stable — engagement rate has remained relatively consistent (early avg: {round(first_half)}%, recent avg: {round(second_half)}%)."
                        trend_col = AMBER
                else:
                    trend_txt = "Insufficient data for trend analysis (minimum 3 days required)."
                    trend_col = "#888"

                # PBIS tier
                if pct_all >= 80:
                    tier_lbl, tier_css2 = "Tier 1 — Universal supports effective", "tag-t1"
                elif pct_all >= 55:
                    tier_lbl, tier_css2 = "Tier 2 — Targeted support required", "tag-t2"
                else:
                    tier_lbl, tier_css2 = "Tier 3 — Intensive individualised support required", "tag-t3"

                all_entries_list2 = df_all.to_dict("records")

                html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
                <title>Placement Engagement — {selected_name}</title>{report_css()}</head><body>
                <button class="print-btn" onclick="window.print()">🖨 Print / Save as PDF</button>
                <div class="rpt-header">
                  <div class="org">Cowandilla Learning Centre — Learning &amp; Behaviour Unit</div>
                  <div class="rpt-title">Placement Engagement Summary</div>
                  <div class="rpt-sub">{selected_name} &mdash; {date_range}</div>
                  <div class="rpt-meta">Program: {student["program"]} &nbsp;|&nbsp;
                  {days_with_data} school days &nbsp;|&nbsp; Document type: Placement Review</div>
                </div>
                <div class="section">
                  <div class="sec-title">Overall engagement summary</div>
                  <div class="stats-row">
                    <div class="stat-box"><div class="stat-num teal">{total_all}</div><div class="stat-lbl">Total entries</div></div>
                    <div class="stat-box"><div class="stat-num grn">{eng_all}</div><div class="stat-lbl">Engaged</div></div>
                    <div class="stat-box"><div class="stat-num red">{not_all}</div><div class="stat-lbl">Not engaged</div></div>
                    <div class="stat-box"><div class="stat-num {pc_all}">{pct_all}%</div><div class="stat-lbl">Engagement rate</div></div>
                  </div>
                  <p style="font-size:12px;padding:10px 12px;background:#f7f7f5;border-radius:6px;
                            border-left:3px solid {trend_col};margin-top:4px;">
                    <strong>Trend:</strong> {trend_txt}
                  </p>
                  <p style="font-size:12px;margin-top:8px;">
                    <span class="tag {tier_css2}">{tier_lbl}</span>
                  </p>
                </div>
                <div class="section">
                  <div class="sec-title">Support type effectiveness</div>
                  {sup_breakdown_html(all_entries_list2)}
                </div>
                <div class="section">
                  <div class="sec-title">Day-by-day engagement log</div>
                  <table><thead><tr><th>Date</th><th style="text-align:center;">Entries</th>
                  <th style="text-align:center;">Engaged</th><th style="text-align:center;">Not engaged</th>
                  <th style="text-align:center;">Rate</th></tr></thead><tbody>{traj_rows}</tbody></table>
                </div>
                <div class="section">
                  <div class="sec-title">BSEM & PBIS hypothesis summary</div>
                  <p style="font-size:12px;color:#555;margin-bottom:10px;">
                    Patterns identified from logged engagement data. Use these as hypotheses to guide team
                    discussion — not as definitive conclusions.
                  </p>
                  <table><tbody>
                    <tr><td style="width:36%;font-weight:600;">Strongest engagement context</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Most significant barrier identified</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Function of disengagement (hypothesis)</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Key relational factors</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">BSEM domains of concern</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Recommended next steps</td><td>&nbsp;</td></tr>
                  </tbody></table>
                </div>
                <div class="section">
                  <div class="sec-title">Placement recommendation</div>
                  <table><tbody>
                    <tr><td style="width:36%;font-weight:600;">Continued LBU placement</td>
                        <td>&#9744; Recommended &nbsp;&nbsp; &#9744; Not recommended &nbsp;&nbsp; &#9744; Review in __ weeks</td></tr>
                    <tr><td style="font-weight:600;">Transition readiness</td>
                        <td>&#9744; Ready for mainstream &nbsp;&nbsp; &#9744; Partial transition &nbsp;&nbsp; &#9744; Not ready</td></tr>
                    <tr><td style="font-weight:600;">Recommendations</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Review date</td><td>&nbsp;</td></tr>
                    <tr><td style="font-weight:600;">Completed by</td><td>&nbsp;</td></tr>
                  </tbody></table>
                </div>
                {footer_html(selected_name)}</body></html>"""

                fname = f"Placement_Engagement_{selected_name.replace(' ','_')}.html"
                st.download_button("⬇ Download placement report", data=html.encode(),
                                   file_name=fname, mime="text/html", use_container_width=True)
