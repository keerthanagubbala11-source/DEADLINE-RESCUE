import uuid
from datetime import date, datetime, time

import pandas as pd
import streamlit as st

import auth
import engine
import planner
import storage

st.set_page_config(page_title="Deadline Rescue", page_icon="⏰", layout="wide")

TODAY = date.today()
CATEGORIES = ["Academic", "Career", "Personal", "Household", "Health", "Other"]
STATUSES = ["Not Started", "In Progress", "Completed", "Blocked"]
IMPORTANCE = list(engine.IMPORTANCE)

# ---------- authentication gate ----------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.title("⏰ Deadline Rescue")
        st.write("Your AI-assisted planner for deadlines, errands and long-term goals. "
                 "Log in or create an account to continue.")
        tab_in, tab_up = st.tabs(["Log In", "Sign Up"])
        with tab_in:
            with st.form("login_form"):
                u = st.text_input("Username")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Log In", type="primary"):
                    user = auth.login(u, pw)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
        with tab_up:
            with st.form("signup_form"):
                name = st.text_input("Display name")
                u2 = st.text_input("Choose a username")
                pw2 = st.text_input("Password (min 8 characters)", type="password")
                pw3 = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Create account"):
                    if pw2 != pw3:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = auth.register(u2, name, pw2)
                        (st.success if ok else st.error)(msg)
    st.stop()

USER = st.session_state.user["username"]
if "tasks" not in st.session_state:
    st.session_state.tasks = storage.load_tasks(USER)
if "saved_plan" not in st.session_state:
    st.session_state.saved_plan = storage.load_plan(USER)


def persist():
    storage.save_tasks(USER, st.session_state.tasks)


def find(task_id):
    return next(t for t in st.session_state.tasks if t["id"] == task_id)


def mark_done(task_id):
    t = find(task_id)
    t["status"], t["completed_on"] = "Completed", TODAY.isoformat()
    persist()


def set_status(task_id, status):
    find(task_id)["status"] = status
    persist()


def delete(task_id):
    st.session_state.tasks = [t for t in st.session_state.tasks if t["id"] != task_id]
    persist()


def log_time(task_id, hours):
    find(task_id)["spent_hours"] = round(find(task_id).get("spent_hours", 0.0) + hours, 2)
    persist()


# ---------- sidebar ----------
st.sidebar.title("⏰ Deadline Rescue")
st.sidebar.write(f"Signed in as **{st.session_state.user['display_name']}**")
if st.sidebar.button("Log out"):
    for k in ("user", "tasks", "saved_plan", "proposed"):
        st.session_state.pop(k, None)
    st.rerun()
page = st.sidebar.radio("Go to", ["My Day", "All Tasks", "AI Rescue Planner", "Progress & Insights"])
daily_hours = st.sidebar.slider("Max planned hours per day", 1, 12, 6)
st.sidebar.caption("Your data is stored separately from other users.")

rows = engine.analyse(st.session_state.tasks, TODAY, daily_hours)

st.markdown(f"### Hello, {st.session_state.user['display_name']}! Today is {TODAY.strftime('%A, %d %B %Y')}")


def task_row(r, key_prefix):
    with st.container(border=True):
        a, b, c, d, e = st.columns([5, 2, 1, 1, 1])
        a.markdown(f"**{r['title']}**  \n{r['category']} · due {r['deadline']} · {r['importance']}")
        b.markdown(f"`{r['group']}`  \nscore {r['score']} · {r['remaining']}h left")
        if r["status"] != "Completed":
            if c.button("✅", key=f"{key_prefix}-done-{r['id']}", help="Mark complete"):
                mark_done(r["id"])
                st.rerun()
            with d.popover("⏱", help="Log time"):
                h = st.number_input("Hours spent", 0.25, 12.0, 0.5, 0.25, key=f"{key_prefix}-h-{r['id']}")
                if st.button("Add", key=f"{key_prefix}-add-{r['id']}"):
                    log_time(r["id"], h)
                    if r["status"] == "Not Started":
                        set_status(r["id"], "In Progress")
                    st.rerun()
        with e.popover("🗑", help="Delete"):
            st.write("Delete this task permanently?")
            if st.button("Yes, delete", key=f"{key_prefix}-del-{r['id']}"):
                delete(r["id"])
                st.rerun()


# ---------- My Day ----------
if page == "My Day":
    if not rows:
        st.info("No tasks yet. Add one in 'All Tasks' or load a few samples.")
        if st.button("Add sample tasks"):
            st.session_state.tasks = storage.sample_tasks(TODAY)
            persist()
            st.rerun()
    else:
        active = [r for r in rows if r["status"] != "Completed"]
        done_today = [r for r in rows if r.get("completed_on") == TODAY.isoformat()]
        overdue = [r for r in rows if r["group"] == "Overdue"]
        soon = [r for r in active if 0 <= r["days_left"] <= 2]
        planned_h = sum(engine.daily_share_minutes(r, TODAY) for r in active) / 60
        c = st.columns(5)
        c[0].metric("Active tasks", len(active))
        c[1].metric("Done today", len(done_today))
        c[2].metric("Overdue", len(overdue))
        c[3].metric("Due in 48h", len(soon))
        c[4].metric("Suggested hours today", f"{planned_h:.1f}h", f"cap {daily_hours}h", delta_color="off")
        if planned_h > daily_hours:
            st.warning("Your suggested workload is above your daily cap. Open the AI Rescue Planner to see what can wait.")

        left, right = st.columns([3, 2])
        with left:
            st.subheader("Do first")
            first = [r for r in active if r["group"] in ("Overdue", "At Risk", "Do First")][:5]
            if not first:
                st.success("Nothing urgent. Nice position to be in.")
            for r in first:
                task_row(r, "day")
                st.caption(r["why"])
        with right:
            st.subheader("Workload by category (hours left)")
            if active:
                df = pd.DataFrame(active).groupby("category")["remaining"].sum()
                st.bar_chart(df)
            st.subheader("Upcoming deadlines")
            for r in sorted(active, key=lambda x: x["deadline"])[:5]:
                st.write(f"{r['deadline']} · {r['title']} ({r['group']})")
        if st.session_state.saved_plan and st.session_state.saved_plan["date"] == TODAY.isoformat():
            st.subheader("Today's saved plan")
            st.dataframe(pd.DataFrame(st.session_state.saved_plan["blocks"])[["start", "end", "task", "minutes"]],
                         hide_index=True)

# ---------- All Tasks ----------
elif page == "All Tasks":
    with st.expander("➕ Add a task", expanded=not rows):
        with st.form("add_task", clear_on_submit=True):
            title = st.text_input("Title")
            c1, c2, c3 = st.columns(3)
            category = c1.selectbox("Category", CATEGORIES)
            importance = c2.selectbox("Importance", IMPORTANCE, index=1)
            deadline = c3.date_input("Deadline", TODAY)
            c4, c5 = st.columns(2)
            est = c4.number_input("Estimated hours", 0.25, 100.0, 1.0, 0.25)
            pinned = c5.checkbox("Pin (always prioritise)")
            desc = st.text_area("Description (optional)")
            if st.form_submit_button("Add task"):
                if not title.strip():
                    st.error("Please enter a title.")
                else:
                    st.session_state.tasks.append({
                        "id": uuid.uuid4().hex[:8], "title": title.strip(), "description": desc,
                        "category": category, "deadline": deadline.isoformat(), "est_hours": est,
                        "spent_hours": 0.0, "importance": importance, "status": "Not Started",
                        "pinned": pinned, "created": TODAY.isoformat(), "completed_on": None,
                    })
                    persist()
                    st.rerun()

    f1, f2, f3 = st.columns(3)
    q = f1.text_input("Search")
    group_f = f2.multiselect("Group", engine.GROUP_ORDER)
    cat_f = f3.multiselect("Category", CATEGORIES)
    shown = [r for r in rows
             if (not q or q.lower() in r["title"].lower())
             and (not group_f or r["group"] in group_f)
             and (not cat_f or r["category"] in cat_f)]
    st.caption(f"{len(shown)} task(s), highest priority first")
    for r in shown:
        task_row(r, "all")
    if not shown:
        st.info("No tasks match.")

# ---------- AI Rescue Planner ----------
elif page == "AI Rescue Planner":
    st.header("AI Rescue Planner")
    c1, c2, c3, c4 = st.columns(4)
    hours = c1.number_input("Available hours today", 0.5, 16.0, 4.0, 0.5)
    start_t = c2.time_input("Start time", time(9, 0))
    block = c3.selectbox("Work block (min)", [30, 45, 60, 90], index=1)
    brk = c4.selectbox("Break (min)", [0, 5, 10, 15], index=2)
    ai_on = planner.ai_available()
    use_ai = st.checkbox("Use Gemini for ordering and reasons", value=ai_on, disabled=not ai_on)
    if not ai_on:
        st.caption("No GEMINI_API_KEY found, so plans are rule-based. See README to add one.")

    if st.button("Generate my plan", type="primary"):
        with st.spinner("Planning..."):
            st.session_state.proposed = planner.make_plan(
                rows, TODAY, hours, datetime.combine(TODAY, start_t), block, brk, use_ai)

    p = st.session_state.get("proposed")
    if p:
        st.subheader(p["source"])
        if p["notice"]:
            st.info(p["notice"])
        st.write(p["summary"])
        if p["overload"]:
            st.error(p["warnings"][0])
        for w in p["warnings"][1 if p["overload"] else 0:]:
            st.warning(w)
        if p["blocks"]:
            st.dataframe(pd.DataFrame(p["blocks"])[["start", "end", "task", "minutes", "group", "reason"]],
                         hide_index=True)
        else:
            st.write("No work blocks to schedule.")
        if p["unscheduled"]:
            st.markdown("**Did not fit today:**")
            for u in p["unscheduled"]:
                st.write(f"- {u['task']} ({u['minutes_short']} min short, {u['group']})")
        for tip in p["tips"]:
            st.write(f"💡 {tip}")
        if st.button("Approve and save this plan"):
            st.session_state.saved_plan = p
            storage.save_plan(USER, p)
            st.success("Plan saved. It will show on My Day.")

# ---------- Progress & Insights ----------
else:
    st.header("Progress & Insights")
    done = [r for r in rows if r["status"] == "Completed"]
    week_ago = (TODAY - pd.Timedelta(days=6)).isoformat()
    this_week = [r for r in done if r.get("completed_on") and r["completed_on"] >= week_ago]
    on_time = [r for r in done if r.get("completed_on") and r["completed_on"] <= r["deadline"]]
    c = st.columns(4)
    c[0].metric("Completed this week", len(this_week))
    c[1].metric("Completion rate", f"{len(done) / len(rows) * 100:.0f}%" if rows else "–")
    c[2].metric("On-time rate", f"{len(on_time) / len(done) * 100:.0f}%" if done else "–")
    tracked = [r for r in done if r["spent_hours"] > 0]
    c[3].metric("Planned vs actual", f"{sum(r['est_hours'] for r in tracked):.1f}h / {sum(r['spent_hours'] for r in tracked):.1f}h" if tracked else "–")
    if rows:
        st.subheader("Tasks by category")
        st.bar_chart(pd.DataFrame(rows).groupby("category").size())
        st.subheader("Tasks by group")
        st.bar_chart(pd.DataFrame(rows).groupby("group").size())
        trend = pd.Series([r["completed_on"] for r in done if r.get("completed_on")]).value_counts().sort_index()
        if not trend.empty:
            st.subheader("Completions per day")
            st.bar_chart(trend)
    else:
        st.info("Add and complete some tasks to see insights.")
    st.caption("These numbers come only from your tracked data. Small steps count: a few finished tasks a week is real progress.")
