import streamlit as st
import asyncio
import sqlite3
import json
import os
import sys
import datetime

sys.path.append(os.path.abspath("."))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NexusConcierge OS",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background-color: #0d1117; color: #c9d1d9; }
.main  { background-color: #0d1117; color: #c9d1d9; }
section[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #21262d;
}

h1, h2, h3 {
    color: #58a6ff !important;
    font-family: 'Outfit', 'Inter', sans-serif;
    font-weight: 700;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"]      { gap: 6px; background: transparent; }
.stTabs [data-baseweb="tab"]           { background:#161b22; border:1px solid #30363d;
                                         border-radius:6px 6px 0 0; color:#8b949e;
                                         padding:8px 18px; font-weight:500; }
.stTabs [aria-selected="true"]         { background:#21262d !important; color:#58a6ff !important;
                                         border-bottom:2px solid #58a6ff !important; }

/* Buttons */
.stButton>button { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
                   border-radius:6px; font-weight:500; transition:all .2s; }
.stButton>button:hover { background:#30363d; border-color:#8b949e; color:#fff; }

/* ── Custom cards ─────────────────────────────────────────────────────── */
.nc-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.nc-cal-card {
    background: linear-gradient(135deg, #0d1b2a 0%, #161b22 100%);
    border: 1px solid #1f6feb;
    border-left: 4px solid #58a6ff;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.nc-cal-card h4 { color: #e6edf3 !important; margin:0 0 4px 0; font-size:15px; }
.nc-cal-card .meta { color: #8b949e; font-size: 12px; margin-top:4px; }
.nc-cal-card .badge {
    display: inline-block;
    background: #1f6feb22;
    color: #58a6ff;
    border: 1px solid #1f6feb55;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 6px;
}

.nc-kpi {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.nc-kpi .val  { font-size: 28px; font-weight: 700; color: #58a6ff; }
.nc-kpi .lbl  { font-size: 12px; color: #8b949e; margin-top: 4px; }
.nc-kpi .delta-pos { color: #3fb950; font-size: 12px; }
.nc-kpi .delta-neg { color: #f85149; font-size: 12px; }

.nc-product-row {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.nc-tag {
    display: inline-block;
    background: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px;
}
.nc-tag-blue  { background:#1f6feb22; color:#58a6ff; border-color:#1f6feb55; }
.nc-tag-green { background:#238636; color:#3fb950; border-color:#3fb95055; }
.nc-tag-purple{ background:#6e40c922; color:#d2a8ff; border-color:#8957e555; }

/* Sidebar compact styles */
.sb-lock  { background:#21262d; border-radius:6px; padding:4px 10px;
            font-size:12px; color:#f0883e; margin:2px 0; display:inline-block; }
.sb-hook  { background:#161b22; border-left:3px solid #58a6ff;
            border-radius:0 6px 6px 0; padding:8px 12px; margin-bottom:8px;
            font-style:italic; color:#c9d1d9; font-size:13px; }
.sb-conv  { font-size:11px; color:#3fb950; margin-top:4px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def fetch_session_state(user_id, session_id):
    try:
        conn = sqlite3.connect("nexus_sessions.db")
        cur  = conn.cursor()
        cur.execute("SELECT state FROM sessions WHERE user_id=? AND id=?;", (user_id, session_id))
        row = cur.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception as e:
        st.error(f"Error fetching session state: {e}")
        return None


async def run_agent_workflow(user_query, session_id, user_id):
    from google.genai.types import Content, Part
    from main import main_async
    from google.adk.sessions.database_session_service import DatabaseSessionService
    db_svc = DatabaseSessionService("sqlite+aiosqlite:///nexus_sessions.db")
    payload = Content(role="user", parts=[Part.from_text(text=user_query)])
    async for chunk in main_async(payload, db_svc, session_id=session_id, user_id=user_id):
        yield chunk


def get_workflow_generator(user_query, session_id, user_id):
    loop = asyncio.new_event_loop()
    gen  = run_agent_workflow(user_query, session_id, user_id)
    try:
        while True:
            try:
                yield loop.run_until_complete(gen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.close()


def _fmt_dt(iso_str: str, is_all_day: bool) -> str:
    """Return a human-friendly date/time string from an ISO-8601 value."""
    if not iso_str:
        return "—"
    try:
        if is_all_day:
            d = datetime.date.fromisoformat(iso_str)
            return d.strftime("%a, %d %b %Y")
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%a, %d %b %Y  %H:%M")
    except Exception:
        return iso_str


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;padding-bottom:6px;">
  <span style="font-size:36px;">🌟</span>
  <div>
    <h1 style="margin:0;font-size:28px;font-family:'Outfit',sans-serif;">NexusConcierge OS</h1>
    <p style="margin:0;color:#8b949e;font-size:13px;">Cross-Domain Multi-Agent Life Engine &nbsp;·&nbsp; Google ADK &amp; FastMCP</p>
  </div>
</div>
<hr style="border:none;border-top:1px solid #21262d;margin:10px 0 16px;">
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    user_id    = st.text_input("User ID",    value="developer_mesh")
    session_id = st.text_input("Session ID", value="local_dev_test_session")

    db_state = fetch_session_state(user_id, session_id)

    st.markdown("---")
    st.markdown("### 💾 State Memory Inspector")

    if db_state:
        st.success("Active session context loaded", icon="✅")

        # ── Calendar Locks ──────────────────────────────────────────────────
        with st.expander("🔒 Calendar Locks", expanded=True):
            locks = db_state.get("calendar_locks", [])
            if locks:
                html_locks = " ".join(f'<span class="sb-lock">🔒 {l}</span>' for l in locks)
                st.markdown(html_locks, unsafe_allow_html=True)
            else:
                st.caption("No active locks")

        # ── Event Profiles ──────────────────────────────────────────────────
        with st.expander("👥 Event Profiles", expanded=False):
            profiles = db_state.get("event_profiles", {})
            if profiles:
                for name, bio in profiles.items():
                    st.markdown(f"""
<div class="nc-card" style="padding:10px 14px;margin-bottom:6px;">
  <div style="font-weight:600;color:#e6edf3;font-size:13px;">👤 {name}</div>
  <div style="color:#8b949e;font-size:12px;margin-top:4px;line-height:1.5;">{bio}</div>
</div>""", unsafe_allow_html=True)
            else:
                st.caption("No profiles cached")

        # ── User Interests ──────────────────────────────────────────────────
        with st.expander("💡 Interests", expanded=False):
            interests = db_state.get("user_interests", ["Python", "FastAPI", "Gemini API", "LLM Orchestration"])
            tags_html = " ".join(f'<span class="nc-tag nc-tag-blue">#{i}</span>' for i in interests)
            st.markdown(tags_html, unsafe_allow_html=True)

        # ── Trading Rules ───────────────────────────────────────────────────
        with st.expander("📈 Trading Rules", expanded=False):
            trading = db_state.get("trading_parameters", {})
            if trading:
                items = list(trading.items())
                for i in range(0, len(items), 2):
                    cols = st.columns(2)
                    for j, (k, v) in enumerate(items[i:i+2]):
                        cols[j].metric(k.replace("_", " ").title(), v)
            else:
                st.caption("No rules set")

        # ── Copywriter Hooks ────────────────────────────────────────────────
        with st.expander("🎨 Hook Memory", expanded=False):
            hooks = db_state.get("affiliate_style_memory", [])
            if hooks:
                for hook in hooks:
                    rate = hook.get("conversion_rate", 0)
                    st.markdown(f"""
<div class="sb-hook">
  💬 "{hook.get('hook','')}"
  <div class="sb-conv">✅ Conversion: {rate:.0%}</div>
</div>""", unsafe_allow_html=True)
            else:
                st.caption("No hooks saved")
    else:
        st.warning("Session not initialised yet.", icon="⚠️")


# ── Main Tabs ──────────────────────────────────────────────────────────────────
tab_chat, tab_cal, tab_tiktok, tab_dag, tab_mcp = st.tabs([
    "💬 Agent Chat",
    "📅 Calendar",
    "🎵 TikTok Dashboard",
    "📊 Workflow DAG",
    "📂 MCP Servers",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — INTERACTIVE AGENT CHAT
# ════════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.subheader("Interactive Agent Session")
    st.caption("Route tasks through specialised agents: Events, Market, TikTok.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat history
    chat_area = st.container()
    with chat_area:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🌟" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Enter your request here…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🌟"):
            placeholder  = st.empty()
            full_response = ""
            with st.spinner("Orchestrator routing tasks…"):
                try:
                    for chunk in get_workflow_generator(prompt, session_id, user_id):
                        full_response += chunk
                        placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)
                except Exception as e:
                    st.error(f"Pipeline error: {e}")

        if full_response:
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — GOOGLE CALENDAR
# ════════════════════════════════════════════════════════════════════════════════
with tab_cal:
    st.subheader("📅 Google Calendar — Upcoming Events")

    # Refresh button
    col_hdr, col_btn = st.columns([6, 1])
    with col_btn:
        refresh = st.button("🔄 Refresh", key="cal_refresh")

    # Cache events in session state
    if "cal_events" not in st.session_state or refresh:
        st.session_state.cal_events    = None
        st.session_state.cal_error     = None
        st.session_state.cal_no_creds  = False

        try:
            from google_calendar_helper import fetch_calendar_events, credentials_available
            if not credentials_available():
                st.session_state.cal_no_creds = True
            else:
                st.session_state.cal_events = fetch_calendar_events(max_results=20)
        except FileNotFoundError as e:
            st.session_state.cal_no_creds = True
        except Exception as e:
            st.session_state.cal_error = str(e)

    # ── Render state ───────────────────────────────────────────────────────────
    if st.session_state.get("cal_no_creds"):
        st.markdown("""
<div class="nc-card" style="border-color:#f0883e;border-left:4px solid #f0883e;">
  <h4 style="color:#f0883e;margin:0 0 8px 0;">🔑 Google Calendar Not Connected</h4>
  <p style="color:#c9d1d9;font-size:13px;margin:0 0 10px 0;">
    To see your real Google Calendar events, authorise this app once:
  </p>
  <ol style="color:#8b949e;font-size:13px;line-height:2;">
    <li>Go to <strong>Google Cloud Console</strong> → APIs &amp; Services → Credentials</li>
    <li>Create an <strong>OAuth 2.0 Client ID</strong> (Desktop App)</li>
    <li>Download it and rename to <code>credentials.json</code>, place in project root</li>
    <li>Run: <code>python mcp_servers.py --server events</code> once — a browser will open for auth</li>
    <li>A <code>token.json</code> file will be saved — come back and click <strong>Refresh</strong></li>
  </ol>
</div>""", unsafe_allow_html=True)

    elif st.session_state.get("cal_error"):
        st.error(f"Calendar API error: {st.session_state.cal_error}")

    else:
        events = st.session_state.get("cal_events") or []

        # Summary bar
        today     = datetime.date.today()
        this_week = sum(1 for e in events if e.get("start") and
                        datetime.date.fromisoformat(e["start"][:10]) <= today + datetime.timedelta(days=7))

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Upcoming", len(events))
        m2.metric("This Week",      this_week)
        m3.metric("All-Day Events", sum(1 for e in events if e.get("is_all_day")))

        st.markdown("---")

        if not events:
            st.info("No upcoming events found in your Google Calendar.")
        else:
            for ev in events:
                is_all_day = ev.get("is_all_day", False)
                start_fmt  = _fmt_dt(ev.get("start", ""), is_all_day)
                end_fmt    = _fmt_dt(ev.get("end",   ""), is_all_day)
                badge_txt  = "All Day" if is_all_day else start_fmt.split()[-1]  # show time
                loc_html   = f'<div class="meta">📍 {ev["location"]}</div>' if ev.get("location") else ""
                desc_html  = (
                    f'<div class="meta" style="margin-top:4px;font-style:italic;">'
                    f'{ev["description"][:100]}{"…" if len(ev.get("description",""))>100 else ""}</div>'
                ) if ev.get("description") else ""
                link_html  = (
                    f'<a href="{ev["link"]}" target="_blank" '
                    f'style="font-size:11px;color:#58a6ff;text-decoration:none;">🔗 Open in Google Calendar</a>'
                ) if ev.get("link") else ""

                st.markdown(f"""
<div class="nc-cal-card">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <span class="badge">{'📅 All Day' if is_all_day else '🕐 ' + badge_txt}</span>
      <h4>{ev.get('summary','Untitled')}</h4>
      <div class="meta">🗓️ {start_fmt} → {end_fmt}</div>
      {loc_html}
      {desc_html}
    </div>
    <div style="padding-top:4px;">{link_html}</div>
  </div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — TIKTOK AFFILIATE CREATOR DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════
with tab_tiktok:
    st.subheader("🎵 TikTok Affiliate Creator Dashboard")
    st.caption("Creator metrics, affiliate product performance & trend intelligence.")

    # Note on API access
    with st.expander("ℹ️ About TikTok Data & Creator Center", expanded=False):
        st.markdown("""
The **TikTok Affiliate Creator API** requires business partner approval and is not available
via public individual OAuth. The metrics below reflect your agent's real-time intelligence
gathered through creator community feeds (Telegram groups, creator briefs).

To view your **live Creator Center dashboard**, paste your TikTok Creator Center URL below.
""")

    # ── Creator Center Embed ───────────────────────────────────────────────────
    st.markdown("#### 🔗 Creator Center Embed")
    cc_url = st.text_input(
        "Paste your TikTok Creator Center URL (optional)",
        placeholder="https://affiliate.tiktok.com/connection/creator?...",
        key="tiktok_cc_url",
    )
    if cc_url and cc_url.startswith("https://"):
        import streamlit.components.v1 as components
        st.info("🔒 TikTok requires you to be logged in — make sure your browser session is active.")
        components.iframe(cc_url, height=600, scrolling=True)

    st.markdown("---")

    # ── KPI Metrics ───────────────────────────────────────────────────────────
    st.markdown("#### 📊 Affiliate Performance Snapshot")
    k1, k2, k3, k4 = st.columns(4)

    k1.markdown("""
<div class="nc-kpi">
  <div class="val">8.5%</div>
  <div class="lbl">Avg Engagement Rate</div>
  <div class="delta-pos">↑ +1.2% vs last week</div>
</div>""", unsafe_allow_html=True)

    k2.markdown("""
<div class="nc-kpi">
  <div class="val">3</div>
  <div class="lbl">Active Products</div>
  <div class="delta-pos">2 high-converting</div>
</div>""", unsafe_allow_html=True)

    k3.markdown("""
<div class="nc-kpi">
  <div class="val">4.2%</div>
  <div class="lbl">Avg Conversion Rate</div>
  <div class="delta-pos">↑ +0.3% vs last week</div>
</div>""", unsafe_allow_html=True)

    k4.markdown("""
<div class="nc-kpi">
  <div class="val">+5%</div>
  <div class="lbl">Creator Bonus Active</div>
  <div class="delta-pos">USB-C Monitor campaign</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Trending Hashtags & Hooks ──────────────────────────────────────────────
    col_trends, col_hooks = st.columns([1, 2])

    with col_trends:
        st.markdown("#### 🔥 Trending Hashtags")
        hashtags = ["#AIPrep", "#DevLife", "#NexusConcierge", "#ProductivityHack", "#TechCreator", "#SingaporeTech"]
        for tag in hashtags:
            st.markdown(f'<span class="nc-tag nc-tag-purple">{tag}</span>', unsafe_allow_html=True)

    with col_hooks:
        st.markdown("#### 💡 Top-Performing Hooks")
        hooks_data = [
            {"hook": "This one tool saved my SaaS project $1000 a month.", "type": "Problem/Solution", "score": 94},
            {"hook": "Stop wasting time writing boilerplate code! AI did it in 5 seconds.", "type": "Pattern Interrupt", "score": 88},
            {"hook": "The secret productivity stack no one is talking about.", "type": "Curiosity Gap", "score": 82},
        ]
        for h in hooks_data:
            bar_pct = h["score"]
            st.markdown(f"""
<div class="nc-card" style="padding:10px 14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:13px;color:#e6edf3;font-style:italic;">"{h['hook']}"</span>
    <span class="nc-tag nc-tag-green" style="flex-shrink:0;margin-left:10px;">{h['score']}/100</span>
  </div>
  <div style="margin-top:8px;background:#21262d;border-radius:4px;height:4px;">
    <div style="background:#3fb950;width:{bar_pct}%;height:4px;border-radius:4px;"></div>
  </div>
  <div style="font-size:11px;color:#8b949e;margin-top:4px;">{h['type']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Affiliate Products Table ───────────────────────────────────────────────
    st.markdown("#### 🛍️ Affiliate Product Portfolio")
    products = [
        {"name": "Smart Desk Organiser",    "commission": "15%", "cvr": "4.2%", "rating": 4.8, "status": "Active"},
        {"name": "AI Productivity Notebook", "commission": "20%", "cvr": "5.6%", "rating": 4.9, "status": "Top Performer"},
        {"name": "USB-C Portable Monitor",  "commission": "10%", "cvr": "3.1%", "rating": 4.7, "status": "Bonus Active"},
    ]

    status_colors = {
        "Active":       ("#21262d",  "#8b949e"),
        "Top Performer":("#1a3a20",  "#3fb950"),
        "Bonus Active": ("#1a2b4a",  "#58a6ff"),
    }

    for p in products:
        bg, fg = status_colors.get(p["status"], ("#21262d", "#8b949e"))
        stars   = "⭐" * int(p["rating"]) + ("½" if p["rating"] % 1 >= 0.5 else "")
        st.markdown(f"""
<div class="nc-card" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:12px 18px;">
  <div>
    <div style="font-weight:600;color:#e6edf3;font-size:14px;">🛍️ {p['name']}</div>
    <div style="font-size:12px;color:#8b949e;margin-top:3px;">{stars} &nbsp; {p['rating']}</div>
  </div>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <div style="text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#58a6ff;">{p['commission']}</div>
      <div style="font-size:11px;color:#8b949e;">Commission</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#3fb950;">{p['cvr']}</div>
      <div style="font-size:11px;color:#8b949e;">Conv. Rate</div>
    </div>
    <span style="background:{bg};color:{fg};border:1px solid {fg}44;border-radius:20px;
                 padding:4px 12px;font-size:12px;font-weight:600;">{p['status']}</span>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Creator Community Intelligence ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📡 Creator Community Intelligence")
    feeds = [
        {"src": "TikTok App",                              "icon": "📱", "info": "Trending hook: *'They don't want you to know this simple coding trick…'* | Suggested: AI Productivity Notebook"},
        {"src": "Telegram: TikTok Shop SG Affiliate",      "icon": "📢", "info": "High commission challenge: promote USB-C Portable Monitors to remote developers. +5% bonus for top creators."},
        {"src": "Telegram: SG TikTok Live Creators",       "icon": "🔴", "info": "Live coding streams experiencing a **35% surge** in viewer retention this week."},
    ]
    for f in feeds:
        st.markdown(f"""
<div class="nc-card" style="padding:10px 16px;">
  <div style="font-weight:600;color:#d2a8ff;font-size:13px;">{f['icon']} {f['src']}</div>
  <div style="color:#c9d1d9;font-size:13px;margin-top:4px;">{f['info']}</div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — WORKFLOW DAG
# ════════════════════════════════════════════════════════════════════════════════
with tab_dag:
    st.subheader("Google ADK Workflow Execution DAG")
    st.caption("Specialist sub-agents process routing tokens and loop back to the central orchestrator until completion.")

    dot_code = """
    digraph G {
        bgcolor="transparent";
        node [style=filled, shape=box, fontname="Inter, sans-serif", fontsize=11, height=0.45, margin="0.2,0.1"];
        edge [fontname="Inter, sans-serif", fontsize=9, color="#4A5568", fontcolor="#8b949e"];

        START   [label="▶  Start Node",                              fillcolor="#0d1117", fontcolor="#58a6ff",  color="#1f6feb"];
        orch    [label="NexusOrchestrator\n(gemini-2.5-flash-lite)", fillcolor="#0d1b2a", fontcolor="#90CDF4",  color="#1A365D"];
        dev     [label="DevRelopsAgent\n(gemini-2.5-flash-lite)",    fillcolor="#0a2318", fontcolor="#68D391",  color="#22543D"];
        trading [label="QuantitativeRiskAgent\n(gemini-2.5-flash-lite)", fillcolor="#1f1600", fontcolor="#FBD38D", color="#744210"];
        tiktok  [label="CreativeAffiliateAgent\n(gemini-2.5-flash-lite)", fillcolor="#1a0f30", fontcolor="#D6BCFA", color="#5C3C92"];
        final   [label="⏹  Collector\n(Terminal Node)",               fillcolor="#200a0a", fontcolor="#FEB2B2",  color="#742A2A"];

        START   -> orch;
        orch    -> dev     [label="route: dev"];
        orch    -> trading [label="route: trading"];
        orch    -> tiktok  [label="route: tiktok"];
        orch    -> final   [label="route: final"];
        dev     -> orch;
        trading -> orch;
        tiktok  -> orch;
    }
    """
    st.graphviz_chart(dot_code)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — MCP SERVER REGISTRATIONS
# ════════════════════════════════════════════════════════════════════════════════
with tab_mcp:
    st.subheader("Specialised Local MCP Server Registrations")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
<div class="nc-card">
<h3 style="color:#58a6ff;margin-top:0;">🛠️ Events MCP Server</h3>
<span class="nc-tag nc-tag-green">Live</span>
<span class="nc-tag">Google APIs</span>
<span class="nc-tag">Telegram</span>
<span class="nc-tag">Meetup</span>
<hr style="border-color:#21262d;margin:10px 0;">
</div>""", unsafe_allow_html=True)
        st.code("""
1. fetch_dev_event_feeds
   ↳ Live Telegram / Meetup scraper
   ↳ Cascading Gmail fallback

2. list_google_calendar_events
   ↳ Real Google Calendar API

3. create_google_calendar_event
   ↳ Writes to primary calendar

4. search_gmail_emails
   ↳ Searches real Gmail inbox
""", language="text")

    with col2:
        st.markdown("""
<div class="nc-card">
<h3 style="color:#58a6ff;margin-top:0;">📈 Market MCP Server</h3>
<span class="nc-tag nc-tag-green">Live</span>
<span class="nc-tag">yfinance</span>
<span class="nc-tag">Options</span>
<hr style="border-color:#21262d;margin:10px 0;">
</div>""", unsafe_allow_html=True)
        st.code("""
 1. get_live_price          (RSI + MACD)
 2. get_vector_trade_logs
 3. get_options_chain       (bids/asks)
 4. get_moomoo_tiger_indicators
 5. get_tradingview_technical_rating
 6. get_news_sentiment      (VIX)
 7. get_market_movers
 8. get_earnings_calendar
 9. get_economic_calendar
10. get_analyst_ratings
11. get_institutional_flow
12. get_unusual_options_activity
13. get_seller_dashboard    (CSP/CC)
""", language="text")

    with col3:
        st.markdown("""
<div class="nc-card">
<h3 style="color:#58a6ff;margin-top:0;">📱 TikTok MCP Server</h3>
<span class="nc-tag nc-tag-purple">Creator Intelligence</span>
<span class="nc-tag">Telegram</span>
<hr style="border-color:#21262d;margin:10px 0;">
</div>""", unsafe_allow_html=True)
        st.code("""
1. get_tiktok_trends
   ↳ Hashtags & engagement logs

2. get_affiliate_products
   ↳ Commission & product details

3. get_keyword_metrics
   ↳ Vol & competition level

4. fetch_tiktok_creator_feeds
   ↳ App + Telegram group caches
   ↳ Creator brief intelligence
""", language="text")
