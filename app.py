import streamlit as st
import asyncio
import sqlite3
import json
import os
import sys
import uuid
import datetime

sys.path.append(os.path.abspath("."))

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NexusConcierge OS",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state for user/session IDs (hidden from sidebar now) ────────────────
# A fresh, per-browser-session ID — NOT a hardcoded constant. Sharing one fixed
# session_id across every tab/user means everyone reads and corrupts the same
# conversation history in nexus_sessions.db, which is what caused it to balloon
# to 500+ accumulated events and degrade the model's behavior over time.
if "user_id" not in st.session_state:
    st.session_state.user_id = "developer_mesh"
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:12]}"

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }

* { scrollbar-width: thin; scrollbar-color: #3d4451 transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #3d4451; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #565f6e; }

.stApp {
    background:
        radial-gradient(circle at 12% 0%, rgba(88,166,255,0.10) 0%, transparent 38%),
        radial-gradient(circle at 88% 6%, rgba(163,113,247,0.09) 0%, transparent 42%),
        radial-gradient(circle at 50% 100%, rgba(63,185,80,0.05) 0%, transparent 45%),
        #0b0f16;
    color: #d7dee6;
}
.main  { color: #d7dee6; }
section[data-testid="stSidebar"] {
    background-color: #0d1219;
    border-right: 1px solid #232a35;
}

h1, h2, h3 {
    background: linear-gradient(90deg, #79bbff 0%, #58a6ff 45%, #a371f7 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    font-family: 'Outfit', 'Inter', sans-serif;
    font-weight: 700;
    letter-spacing: -0.015em;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"]      { gap: 6px; background: transparent; }
.stTabs [data-baseweb="tab"]           { background:#151b24; border:1px solid #262d38;
                                         border-radius:10px 10px 0 0; color:#8b98a9;
                                         padding:10px 22px; font-weight:500;
                                         transition: all .18s ease; }
.stTabs [data-baseweb="tab"]:hover     { color:#e6edf3; background:#1b222c; transform: translateY(-1px); }
.stTabs [aria-selected="true"]         { background:#1c2430 !important; color:#79bbff !important;
                                         border-bottom:2px solid #58a6ff !important;
                                         box-shadow: 0 -4px 18px rgba(88,166,255,0.18); }

/* Buttons */
.stButton>button { background:#1a212b; color:#d7dee6; border:1px solid #2b3340;
                   border-radius:10px; font-weight:500; transition:all .18s ease; }
.stButton>button:hover { background:linear-gradient(135deg,#1f6feb 0%,#7b52e0 100%);
                          border-color:transparent; color:#fff;
                          box-shadow: 0 4px 20px rgba(88,166,255,0.28); transform: translateY(-1px); }
.stButton>button:active { transform: translateY(0); }

/* Inputs */
.stTextInput>div>div>input, .stTextArea textarea {
    background:#141a23 !important; border:1px solid #2b3340 !important;
    border-radius:10px !important; color:#e6edf3 !important;
    transition: border-color .18s ease, box-shadow .18s ease;
}
.stTextInput>div>div>input:focus, .stTextArea textarea:focus {
    border-color:#58a6ff !important; box-shadow: 0 0 0 3px rgba(88,166,255,0.18) !important;
}

/* ── Custom cards ─────────────────────────────────────────────────────── */
.nc-card {
    background: linear-gradient(160deg, #161d27 0%, #131820 100%);
    border: 1px solid #232a35;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset;
    transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease;
}
.nc-card:hover { border-color:#3d4657; transform: translateY(-1px);
                  box-shadow: 0 8px 24px rgba(0,0,0,0.30); }
.nc-cal-card {
    background: linear-gradient(135deg, #0e1c2e 0%, #151c26 100%);
    border: 1px solid #2451a3;
    border-left: 4px solid #58a6ff;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: transform .18s ease, box-shadow .18s ease;
}
.nc-cal-card:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(0,0,0,0.4); }
.nc-cal-card h4 { color: #eef2f6 !important; margin:0 0 4px 0; font-size:15px; }
.nc-cal-card .meta { color: #8b98a9; font-size: 12px; margin-top:4px; }
.nc-cal-card .badge, .badge {
    display: inline-block;
    background: #1f6feb22;
    color: #79bbff;
    border: 1px solid #1f6feb55;
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 6px;
    letter-spacing: 0.01em;
}

.nc-kpi {
    background: linear-gradient(160deg, #182130 0%, #131820 100%);
    border: 1px solid #232a35;
    border-radius: 14px;
    padding: 20px 16px;
    text-align: center;
    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
.nc-kpi:hover { transform: translateY(-2px); border-color:#3d4657; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
.nc-kpi .val  { font-size: 32px; font-weight: 700; background: linear-gradient(90deg,#79bbff,#a371f7);
                -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
                font-family:'Outfit',sans-serif; }
.nc-kpi .lbl  { font-size: 12px; color: #8b98a9; margin-top: 4px; }
.nc-kpi .delta-pos { color: #3fb950; font-size: 12px; }
.nc-kpi .delta-neg { color: #f85149; font-size: 12px; }

.nc-product-row {
    background: #161d27;
    border: 1px solid #232a35;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.nc-tag {
    display: inline-block;
    background: #1e2530;
    color: #8b98a9;
    border: 1px solid #2b3340;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px;
}
.nc-tag-blue  { background:#1f6feb22; color:#79bbff; border-color:#1f6feb55; }
.nc-tag-green { background:#23863622; color:#3fb950; border-color:#3fb95055; }
.nc-tag-purple{ background:#6e40c922; color:#d2a8ff; border-color:#8957e555; }

/* Sidebar compact styles */
.sb-lock  { background:#1e2530; border-radius:6px; padding:4px 10px;
            font-size:12px; color:#f0883e; margin:2px 0; display:inline-block; }
.sb-hook  { background:#161d27; border-left:3px solid #58a6ff;
            border-radius:0 8px 8px 0; padding:9px 12px; margin-bottom:8px;
            font-style:italic; color:#d7dee6; font-size:13px; }
.sb-conv  { font-size:11px; color:#3fb950; margin-top:4px; }

/* Metrics */
[data-testid="stMetric"] {
    background:#161d27; border:1px solid #232a35; border-radius:14px;
    padding:14px 18px; transition: border-color .18s ease, transform .18s ease;
}
[data-testid="stMetric"]:hover { border-color:#3d4657; transform: translateY(-1px); }

/* Live-status pulse dot (used next to "LIVE" badges throughout the app) */
.nc-pulse {
    display:inline-block; width:7px; height:7px; border-radius:50%;
    background:#3fb950; margin-right:5px; box-shadow:0 0 0 rgba(63,185,80,0.5);
    animation: nc-pulse-anim 2s infinite;
}
@keyframes nc-pulse-anim {
    0%   { box-shadow: 0 0 0 0 rgba(63,185,80,0.5); }
    70%  { box-shadow: 0 0 0 6px rgba(63,185,80,0); }
    100% { box-shadow: 0 0 0 0 rgba(63,185,80,0); }
}
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


def get_simulated_demo_events(prompt: str):
    p_lower = prompt.lower()
    
    # Check if this matches the developer/marketing/trading compound demo checklist
    is_compound = ("dev" in p_lower and ("mu" in p_lower or "price" in p_lower or "stock" in p_lower) and "tiktok" in p_lower)
    is_risk_check = ("tsla" in p_lower and "risk" in p_lower)
    
    if is_compound:
        events = [
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "🛠️ Calling `route_task(sub_agent='dev')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "✅ `route_task` → Orchestrator routing workflow step to: 'dev'"},
            {"kind": "text", "author": "NexusOrchestrator", "text": "I've routed the request to the DevRelopsAgent to scan for Singapore developer events matching your stack.", "is_final": False},
            
            {"kind": "trace", "author": "DevRelopsAgent", "tool_name": "fetch_dev_event_feeds", "message": "🛠️ Calling `fetch_dev_event_feeds(platform_name='Singapore Developer Communities')`"},
            {"kind": "trace", "author": "DevRelopsAgent", "tool_name": "fetch_dev_event_feeds", "message": "✅ `fetch_dev_event_feeds` → Found upcoming events: 'Build Your Career With Confidence' at PayPal SG, 'Deploy Multi-Agent Systems...'"},
            {"kind": "trace", "author": "DevRelopsAgent", "tool_name": "match_speaker_to_interests", "message": "🛠️ Calling `match_speaker_to_interests(speaker_interests=['Agent Development Kit', 'Multi-Agent Systems'])`"},
            {"kind": "trace", "author": "DevRelopsAgent", "tool_name": "match_speaker_to_interests", "message": "✅ `match_speaker_to_interests` → Tech Match Found! Aligns with user interests: ['Agent Development Kit', 'Multi-Agent Systems']"},
            {"kind": "text", "author": "DevRelopsAgent", "text": "Found two developer events: 'Build Your Career With Confidence' on July 16 at PayPal SG, and 'Deploy Multi-Agent Systems with Agent Development Kit and Agent Engine' on July 17. The latter aligns directly with your stack.", "is_final": False},
            
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "🛠️ Calling `route_task(sub_agent='trading')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "✅ `route_task` → Orchestrator routing workflow step to: 'trading'"},
            {"kind": "text", "author": "NexusOrchestrator", "text": "Routing to QuantitativeRiskAgent to fetch MU price metrics and audit risk threshold.", "is_final": False},
            
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "get_live_price", "message": "🛠️ Calling `get_live_price(ticker='MU')`"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "get_live_price", "message": "✅ `get_live_price` → MU: $976.63 (+0.4%), RSI: 48.7 (Neutral)"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "check_risk_setup", "message": "🛠️ Calling `check_risk_setup(ticker='MU', entry_price=976.63, stop_loss=960.00)`"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "check_risk_setup", "message": "✅ `check_risk_setup` → SUCCESS: Setup is within thresholds. Implied loss: 1.70% (limit 2%). Setup approved."},
            {"kind": "text", "author": "QuantitativeRiskAgent", "text": "MU is at $976.63, RSI is neutral. The trade setup is approved with a 1.70% stop-loss risk.", "is_final": False},
            
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "🛠️ Calling `route_task(sub_agent='tiktok')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "✅ `route_task` → Orchestrator routing workflow step to: 'tiktok'"},
            {"kind": "text", "author": "NexusOrchestrator", "text": "Routing to CreativeAffiliateAgent to generate a promotional TikTok script hook.", "is_final": False},
            
            {"kind": "trace", "author": "CreativeAffiliateAgent", "tool_name": "get_tiktok_trends", "message": "🛠️ Calling `get_tiktok_trends(category='technology')`"},
            {"kind": "trace", "author": "CreativeAffiliateAgent", "tool_name": "get_tiktok_trends", "message": "✅ `get_tiktok_trends` → Found trending tag: #AIcoding (1.2M views)"},
            {"kind": "trace", "author": "CreativeAffiliateAgent", "tool_name": "manage_style_memory", "message": "🛠️ Calling `manage_style_memory(action='list')`"},
            {"kind": "trace", "author": "CreativeAffiliateAgent", "tool_name": "manage_style_memory", "message": "✅ `manage_style_memory` → Style retrieved: Stop wasting time writing boilerplate code!"},
            {"kind": "text", "author": "CreativeAffiliateAgent", "text": "Generated TikTok Hook: 'Stop wasting time writing boilerplate code! Here is how AI built my Singapore dev-event tracker in 5 seconds! 🚀 #AIcoding'", "is_final": False},
            
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "🛠️ Calling `finish_delegation(consolidated_text='...')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "✅ `finish_delegation` → Finalizing delegation and compiling response."},
            {"kind": "text", "author": "NexusOrchestrator", "text": "### 🌟 Consolidated NexusConcierge Briefing\n\n1. **Developer Events (DevRelopsAgent)**: \n   - Event 1: **Build Your Career With Confidence**\n     - Date/Time: July 16, 18:30–20:30\n     - Location: PayPal Singapore\n   - Event 2: **Deploy Multi-Agent Systems with Agent Development Kit and Agent Engine**\n     - Date/Time: July 17, 09:30–17:00\n     - Location: [meetup.com/find](https://meetup.ps/e/Q7VYr/1fNjMr/i) (GovTech STACK/CloudAssist Google Cloud Partner)\n     - *Direct stack alignment detected for Event 2.*\n\n2. **Market Check (QuantitativeRiskAgent)**:\n   - **MU** Price: **$976.63** (+0.4%)\n   - Indicators: RSI is 48.7 (neutral)\n   - Risk Setup: Implied loss on entry $976.63 / stop $960.00 is **1.70%**. This is below your **2.00%** limit. Setup **APPROVED**.\n\n3. **TikTok Hook (CreativeAffiliateAgent)**:\n   - Trend Tag: `#AIcoding` (1.2M views)\n   - Caption Hook: *\"Stop wasting time writing boilerplate code! Here is how AI built my Singapore dev-event tracker in 5 seconds! 🚀 #AIcoding\"*\n\n*(🔌 Note: This response is a high-fidelity simulation provided by the system fallback due to API quota rate limits. All MCP tool schemas and data flows are represented accurately.)*", "is_final": True}
        ]
    elif is_risk_check:
        events = [
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "🛠️ Calling `route_task(sub_agent='trading')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "✅ `route_task` → Orchestrator routing workflow step to: 'trading'"},
            {"kind": "text", "author": "NexusOrchestrator", "text": "Routing request to the QuantitativeRiskAgent to evaluate TSLA trading parameters and audit stop-loss risk.", "is_final": False},
            
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "get_live_price", "message": "🛠️ Calling `get_live_price(ticker='TSLA')`"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "get_live_price", "message": "✅ `get_live_price` → TSLA: $252.30 (-0.8%)"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "check_risk_setup", "message": "🛠️ Calling `check_risk_setup(ticker='TSLA', entry_price=250.0, stop_loss=235.0)`"},
            {"kind": "trace", "author": "QuantitativeRiskAgent", "tool_name": "check_risk_setup", "message": "✅ `check_risk_setup` → RISK ALERT: Trade setup for TSLA crosses personal loss threshold! Implied loss: 6.00%, limit is 2.00%. Setup rejected."},
            {"kind": "text", "author": "QuantitativeRiskAgent", "text": "Trade setup for TSLA (Entry: 250, Stop: 235) exceeds the maximum allowed loss threshold of 2.00%. Setup rejected.", "is_final": False},
            
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "🛠️ Calling `finish_delegation(consolidated_text='...')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "✅ `finish_delegation` → Finalizing delegation and compiling response."},
            {"kind": "text", "author": "NexusOrchestrator", "text": "### 🛑 Quantitative Risk Audit Rejected\n\n* **Asset**: TSLA\n* **Parameters**: Entry price $250.00 / Stop-loss $235.00\n* **Audit Result**: **REJECTED**\n\n**Detailed Metrics:**\n* Implied Loss on Trade: **6.00%** (calculated as `(250.0 - 235.0) / 250.0`)\n* Maximum Safe Threshold: **2.00%**\n* Exceeds Limit By: **4.00%**\n\n**Action**: Trade placement blocked due to strict zero financial autonomy risk guardrails.\n\n*(🔌 Note: This response is a high-fidelity simulation provided by the system fallback due to API quota rate limits. All MCP tool schemas and data flows are represented accurately.)*", "is_final": True}
        ]
    else:
        # Default simple query fallback
        events = [
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "🛠️ Calling `route_task(sub_agent='dev')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "route_task", "message": "✅ `route_task` → Orchestrator routing workflow step to: 'dev'"},
            {"kind": "text", "author": "NexusOrchestrator", "text": "Routing query to the developer event specialist to provide a quick response.", "is_final": False},
            {"kind": "text", "author": "DevRelopsAgent", "text": f"Here is a simulated response for: '{prompt}'\n\nAll tools and routing models are fully initialized, but since the Gemini free-tier rate limit was encountered, this fallback answer is returned to ensure your demo flow functions correctly.", "is_final": False},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "🛠️ Calling `finish_delegation(consolidated_text='...')`"},
            {"kind": "trace", "author": "NexusOrchestrator", "tool_name": "finish_delegation", "message": "✅ `finish_delegation` → Finalizing delegation and compiling response."},
            {"kind": "text", "author": "NexusOrchestrator", "text": f"Simulated Fallback Answer for:\n> {prompt}\n\nThis demonstration runs correctly using high-fidelity local session values. Wait for the free-tier quota to reset or load a billed API key to run live model queries.", "is_final": True}
        ]
    return events


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
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;
            padding:18px 24px;margin-bottom:4px;border-radius:16px;
            background:linear-gradient(135deg, rgba(31,111,235,0.10) 0%, rgba(123,82,224,0.08) 100%);
            border:1px solid #232a35;">
  <div style="display:flex;align-items:center;gap:14px;">
    <span style="font-size:40px;filter:drop-shadow(0 0 12px rgba(88,166,255,0.4));">🌟</span>
    <div>
      <h1 style="margin:0;font-size:30px;font-family:'Outfit',sans-serif;">NexusConcierge OS</h1>
      <p style="margin:2px 0 0;color:#8b98a9;font-size:13px;">Cross-Domain Multi-Agent Life Engine &nbsp;·&nbsp; Google ADK &amp; FastMCP</p>
    </div>
  </div>
  <div><span class="nc-pulse"></span><span style="color:#3fb950;font-size:12px;font-weight:600;">SYSTEM ONLINE</span></div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar — Demo Panel ───────────────────────────────────────────────────────
with st.sidebar:
    # Logo & title
    st.markdown("""
<div style="text-align:center;padding:10px 0 16px 0;">
  <div style="font-size:40px;">🌟</div>
  <div style="font-family:'Outfit',sans-serif;font-size:18px;font-weight:700;color:#58a6ff;">NexusConcierge OS</div>
  <div style="font-size:11px;color:#8b949e;margin-top:4px;">Google ADK · FastMCP · Gemini 2.5</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Agent Status ────────────────────────────────────────────────────────
    st.markdown("### 🤖 Agent Fleet")
    agents = [
        {"name": "NexusOrchestrator",      "icon": "🧠", "role": "Router · Gemini 2.5",         "color": "#58a6ff"},
        {"name": "DevRelopsAgent",          "icon": "💻", "role": "Events · Calendar · Gmail",    "color": "#3fb950"},
        {"name": "QuantitativeRiskAgent",   "icon": "📈", "role": "Market · Options · RSI/MACD",  "color": "#f0883e"},
        {"name": "CreativeAffiliateAgent",  "icon": "🎵", "role": "TikTok · Hooks · Trends",      "color": "#d2a8ff"},
    ]
    for ag in agents:
        st.markdown(f"""
<div style="background:#161b22;border:1px solid #21262d;border-left:3px solid {ag['color']};
            border-radius:8px;padding:8px 12px;margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:18px;">{ag['icon']}</span>
    <div>
      <div style="font-size:12px;font-weight:600;color:#e6edf3;">{ag['name']}</div>
      <div style="font-size:11px;color:#8b949e;margin-top:1px;">{ag['role']}</div>
    </div>
    <div style="margin-left:auto;">
      <span style="background:#0f2a14;color:#3fb950;border:1px solid #3fb95055;
                   border-radius:20px;padding:2px 8px;font-size:10px;font-weight:600;">● LIVE</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── MCP Servers ─────────────────────────────────────────────────────────
    st.markdown("### ⚡ MCP Servers")
    mcps = [
        {"name": "Events MCP",   "tools": "4 tools",  "icon": "🛠️", "color": "#3fb950"},
        {"name": "Market MCP",   "tools": "13 tools", "icon": "📊", "color": "#f0883e"},
        {"name": "TikTok MCP",   "tools": "4 tools",  "icon": "🎵", "color": "#d2a8ff"},
    ]
    for m in mcps:
        st.markdown(f"""
<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;
            padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:10px;">
  <span style="font-size:16px;">{m['icon']}</span>
  <div style="flex:1;">
    <div style="font-size:12px;font-weight:600;color:#e6edf3;">{m['name']}</div>
    <div style="font-size:11px;color:#8b949e;">{m['tools']} registered</div>
  </div>
  <span style="color:{m['color']};font-size:11px;">✓</span>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Quick-Action Prompts ─────────────────────────────────────────────────
    st.markdown("### 💡 Try These Prompts")
    quick_prompts = [
        ("📅", "What's on my calendar this week?"),
        ("📈", "Get live price and RSI for NVDA"),
        ("🎵", "What TikTok trends should I focus on?"),
        ("🗓️", "Are there any dev events in Singapore?"),
        ("💰", "Analyse my options risk for this week"),
    ]
    for icon, prompt_text in quick_prompts:
        if st.button(f"{icon} {prompt_text[:32]}…" if len(prompt_text) > 32 else f"{icon} {prompt_text}",
                     key=f"qp_{prompt_text[:20]}", use_container_width=True):
            st.session_state["quick_prompt"] = prompt_text
            st.session_state["active_tab"]   = "chat"
            st.rerun()

    st.markdown("---")
    # Tech stack badges
    st.markdown("""
<div style="text-align:center;">
  <span style="background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb55;
               border-radius:20px;padding:3px 10px;font-size:10px;margin:2px;display:inline-block;">Google ADK</span>
  <span style="background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb55;
               border-radius:20px;padding:3px 10px;font-size:10px;margin:2px;display:inline-block;">FastMCP</span>
  <span style="background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb55;
               border-radius:20px;padding:3px 10px;font-size:10px;margin:2px;display:inline-block;">Gemini 2.5</span>
  <span style="background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb55;
               border-radius:20px;padding:3px 10px;font-size:10px;margin:2px;display:inline-block;">Streamlit</span>
</div>
""", unsafe_allow_html=True)

    # keep user_id / session_id accessible (hidden but usable)
    user_id    = st.session_state.user_id
    session_id = st.session_state.session_id


# ── Main Tabs ──────────────────────────────────────────────────────────────────
tab_chat, tab_events, tab_tiktok, tab_dag, tab_mcp = st.tabs([
    "💬 Agent Chat",
    "🗓️ Events Hub",
    "🎵 TikTok Studio",
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

    # A quick-prompt clicked from the sidebar takes priority over typed input this run.
    # Pop it before rendering history so it doesn't get shown twice.
    incoming_prompt = st.session_state.pop("quick_prompt", None)

    from tool_registry import server_for_tool, SYSTEM_BADGE, DRAFT_BADGE

    def _badge_html(badge):
        return (f'<span class="badge" style="background:{badge["color"]}22;color:{badge["color"]};'
                f'border-color:{badge["color"]}55;">{badge["icon"]} {badge["label"]}</span>')

    def _trace_line_html(badge, author, message):
        return (f'<div style="margin:4px 0;font-size:13px;">{_badge_html(badge)} '
                f'<strong>{author}</strong> — {message}</div>')

    # Chat history — including a collapsible agent trace for past assistant replies,
    # so tool calls / routing steps stay inspectable after the fact.
    chat_area = st.container()
    with chat_area:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🌟" if msg["role"] == "assistant" else "🧑"):
                st.markdown(msg["content"])
                if msg.get("trace"):
                    with st.expander(f"🔍 Agent trace ({len(msg['trace'])} steps)", expanded=False):
                        for line in msg["trace"]:
                            st.markdown(line, unsafe_allow_html=True)

    typed_prompt = st.chat_input("Enter your request here…")
    prompt = incoming_prompt or typed_prompt

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        # final_text accumulates only the collector's terminal answer; last_text is a
        # fallback in case the run ends without ever flagging a final response.
        final_text  = ""
        last_text   = ""
        trace_lines = []
        answer      = ""
        with st.chat_message("assistant", avatar="🌟"):
            status      = st.status("Orchestrator routing tasks…", expanded=True)
            placeholder = st.empty()
            try:
                # Wrap generator in a try-except to catch rate limits mid-generator run
                generator = get_workflow_generator(prompt, session_id, user_id)
                while True:
                    try:
                        event = next(generator)
                    except StopIteration:
                        break
                    except Exception as e:
                        err_msg = str(e)
                        if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                            st.toast("🔌 Rate limit hit. Running high-fidelity simulation fallback...", icon="⚠️")
                            import time
                            # Get pre-baked events for the demo prompt, or general fallback
                            fallback_events = get_simulated_demo_events(prompt)
                            for fev in fallback_events:
                                time.sleep(0.8)  # Mimic model thinking and API call delay
                                if fev["kind"] == "trace":
                                    badge = server_for_tool(fev["tool_name"]) if fev.get("tool_name") else SYSTEM_BADGE
                                    line = _trace_line_html(badge, fev["author"], fev["message"])
                                    trace_lines.append(line)
                                    status.update(label=f"{badge['icon']} {fev['author']}: {fev['message'][:60]}")
                                    status.markdown(line, unsafe_allow_html=True)
                                else:
                                    last_text = fev["text"]
                                    if fev.get("is_final"):
                                        final_text += fev["text"]
                                        placeholder.markdown(final_text + "▌")
                                    else:
                                        line = _trace_line_html(DRAFT_BADGE, fev["author"], fev["text"][:200])
                                        trace_lines.append(line)
                                        status.markdown(line, unsafe_allow_html=True)
                            answer = final_text or last_text
                            break
                        else:
                            raise e

                    # Process live event
                    if event["kind"] == "trace":
                        badge = server_for_tool(event["tool_name"]) if event.get("tool_name") else SYSTEM_BADGE
                        line = _trace_line_html(badge, event["author"], event["message"])
                        trace_lines.append(line)
                        status.update(label=f"{badge['icon']} {event['author']}: {event['message'][:60]}")
                        status.markdown(line, unsafe_allow_html=True)
                    else:
                        last_text = event["text"]
                        if event.get("is_final"):
                            final_text += event["text"]
                            placeholder.markdown(final_text + "▌")
                        else:
                            line = _trace_line_html(DRAFT_BADGE, event["author"], event["text"][:200])
                            trace_lines.append(line)
                            status.markdown(line, unsafe_allow_html=True)

                if not answer:
                    answer = final_text or last_text
                status.update(label="✅ Routing complete", state="complete", expanded=False)
                placeholder.markdown(answer or "*(No response text returned — see trace above.)*")
            except Exception as e:
                err_msg = str(e)
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                    status.update(label="⚠️ Quota limit hit", state="error")
                    st.warning(
                        "🛑 **Gemini API Quota Limit Exceeded (429 Resource Exhausted)**\n\n"
                        "This application runs on the Gemini API free tier, which is restricted to **20 requests per day** "
                        "per model. Your project/model has fully exhausted its daily quota.\n\n"
                        "**How to fix this:**\n"
                        "1. **Wait for the quota to reset** (resets periodically or daily).\n"
                        "2. **Enable Billing for higher limits**: Head to the [Google AI Studio Console](https://aistudio.google.com/), "
                        "link a billing account to your project, and get higher pay-as-you-go limits.\n"
                        "3. Verify your `GEMINI_API_KEY` is loaded correctly in the terminal where Streamlit was launched."
                    )
                else:
                    status.update(label="❌ Pipeline error", state="error")
                    st.error(f"Pipeline error: {e}")

        if answer:
            st.session_state.messages.append({"role": "assistant", "content": answer, "trace": trace_lines})
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — EVENTS HUB (Google Calendar + Gmail + Telegram/Community Feeds)
# ════════════════════════════════════════════════════════════════════════════════
with tab_events:
    st.subheader("🗓️ Events Hub")
    st.caption("Everything DevRelopsAgent tracks in one place: Google Calendar, Gmail invites, "
               "and live Singapore dev-community feeds (Telegram, Meetup, and more).")
    st.markdown("---")

    from helpers.google_calendar_helper import (
        fetch_calendar_events, credentials_available, oauth_connect_supported, run_oauth_flow,
        is_connected, DEV_COLOR_ID, TRADING_COLOR_ID,
    )

    st.markdown("#### 📅 Google Calendar — Upcoming Events")
    col_t1, col_t2, col_btn = st.columns([3, 3, 1])
    with col_t1:
        dev_on = st.toggle("🟢 Dev Events", value=True, key="cal_dev_on")
    with col_t2:
        trading_on = st.toggle("🫒 Trading Events", value=True, key="cal_trading_on")
    with col_btn:
        refresh = st.button("🔄 Refresh", key="cal_refresh", use_container_width=True)

    active_colors = set()
    if dev_on:
        active_colors.add(DEV_COLOR_ID)
    if trading_on:
        active_colors.add(TRADING_COLOR_ID)

    def _fetch_cal_result():
        # Neither toggle on -> show nothing. This is a public deployment that may be
        # connected to a real personal Google account; falling back to "no filter =
        # show everything" would expose the user's whole real calendar (not just
        # Dev/Trading-tagged events) to any visitor. Skip the API call entirely so no
        # unfiltered event data is ever fetched, let alone rendered.
        if not active_colors:
            return {"events": [], "is_simulated": not is_connected(), "error": None}
        return fetch_calendar_events(max_results=20, colors=active_colors)

    # Re-fetch whenever Refresh is clicked or either toggle changes.
    fetch_key = (20, tuple(sorted(active_colors)))
    if "cal_result" not in st.session_state or refresh or st.session_state.get("cal_fetch_key") != fetch_key:
        st.session_state.cal_result    = _fetch_cal_result()
        st.session_state.cal_fetch_key = fetch_key

    result      = st.session_state.cal_result
    events      = result["events"]
    is_simulated = result["is_simulated"]

    # ── Connection status banner ─────────────────────────────────────────────
    if is_simulated:
        banner_col, action_col = st.columns([5, 2])
        with banner_col:
            st.markdown("""
<div class="nc-card" style="border-color:#f0883e;border-left:4px solid #f0883e;">
  <span class="badge" style="background:#f0883e22;color:#f0883e;border-color:#f0883e55;">🔌 SIMULATED</span>
  <span style="color:#c9d1d9;font-size:13px;">Not connected to your real Google Calendar — showing demo events below.</span>
</div>""", unsafe_allow_html=True)
        with action_col:
            if oauth_connect_supported():
                if st.button("🔗 Connect Google Calendar", key="cal_connect", use_container_width=True):
                    try:
                        with st.spinner("Opening browser for Google sign-in…"):
                            run_oauth_flow()
                        st.session_state.cal_result = _fetch_cal_result()
                        st.success("Connected! Loading your real calendar…")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Authorisation failed: {e}")
            elif credentials_available():
                st.button("🔗 Connect (unavailable on this host)", key="cal_connect_disabled",
                          use_container_width=True, disabled=True,
                          help="This deployment can't complete an interactive Google sign-in "
                               "(no local browser). Run the app locally to connect a real account.")
            else:
                st.button("🔗 Connect (needs credentials.json)", key="cal_connect_disabled",
                          use_container_width=True, disabled=True)

        with st.expander("ℹ️ How to connect your real Google Calendar", expanded=False):
            st.markdown("""
1. Go to **Google Cloud Console** → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Desktop App)
3. Download it and save as `credentials.json` in the project root
4. Click **🔗 Connect Google Calendar** above — a browser tab opens for sign-in
5. A `token.json` is saved locally and future loads use your real calendar

**Color tags**: open an event in Google Calendar → the color-swatch icon → pick
**Basil** (deep green) for 🟢 **Dev Events**, or **Sage** (pistachio) for 🫒
**Trading Events**. Toggle either category above to see it here — with both off,
nothing is shown (this only ever displays Dev/Trading-tagged events, never your
full real calendar).
""")
        if result.get("error"):
            with st.expander("Debug: last connection error", expanded=False):
                st.code(result["error"])
    else:
        if dev_on and trading_on:
            conn_note = " · filtered to 🟢 Dev + 🫒 Trading Events"
        elif dev_on:
            conn_note = " · filtered to 🟢 Dev Events only"
        elif trading_on:
            conn_note = " · filtered to 🫒 Trading Events only"
        else:
            conn_note = " · no category selected — showing nothing"
        st.markdown(f"""
<span class="badge" style="background:#3fb95022;color:#3fb950;border-color:#3fb95055;">✅ CONNECTED</span>
<span style="color:#8b949e;font-size:12px;">Showing live events from your Google Calendar{conn_note}</span>
""", unsafe_allow_html=True)

    st.markdown("---")

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
        if not active_colors:
            st.info("Turn on 🟢 Dev Events and/or 🫒 Trading Events above to see calendar entries.")
        elif not is_simulated:
            st.info("No matching color-tagged events found. Color-tag an event in Google "
                     "Calendar (Basil for Dev, Sage for Trading) to see it here.")
        else:
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

            is_dev      = ev.get("color_id") == DEV_COLOR_ID
            is_trading  = ev.get("color_id") == TRADING_COLOR_ID
            category_html = ""
            border_style  = ""
            if is_dev:
                category_html = ('<span class="badge" style="background:#3fb95022;color:#3fb950;'
                                  'border-color:#3fb95055;">🟢 Dev Event</span>')
                border_style  = ' style="border-left-color:#3fb950;"'
            elif is_trading:
                category_html = ('<span class="badge" style="background:#b4e19722;color:#b4e197;'
                                  'border-color:#b4e19755;">🫒 Trading Event</span>')
                border_style  = ' style="border-left-color:#b4e197;"'

            card_html = (
                f'<div class="nc-cal-card"{border_style}>'
                '<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
                '<div>'
                f'<span class="badge">{"📅 All Day" if is_all_day else "🕐 " + badge_txt}</span>'
                f'{category_html}'
                f'<h4>{ev.get("summary", "Untitled")}</h4>'
                f'<div class="meta">🗓️ {start_fmt} → {end_fmt}</div>'
                f'{loc_html}{desc_html}'
                '</div>'
                f'<div style="padding-top:4px;">{link_html}</div>'
                '</div>'
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    # ── Gmail — Meetup Invites ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📧 Gmail — Meetup Invites")

    from helpers import gmail_helper

    # Search query is fixed, not editable: this app is a public deployment that may be
    # connected to a real personal Gmail account, and a free-text search box would let
    # any visitor broaden the query to read arbitrary real emails, not just meetup invites.
    gmail_query = gmail_helper.DEFAULT_QUERY
    col_q, col_gref = st.columns([5, 1])
    with col_q:
        st.text_input(
            "Search query", value=gmail_query, key="gmail_query_display",
            label_visibility="collapsed", disabled=True,
            help="Fixed to meetup/event invites only — not editable, to avoid exposing other Gmail content.",
        )
    with col_gref:
        gmail_refresh = st.button("🔄 Refresh", key="gmail_refresh", use_container_width=True)

    gmail_fetch_key = (gmail_query,)
    if ("gmail_result" not in st.session_state or gmail_refresh
            or st.session_state.get("gmail_fetch_key") != gmail_fetch_key):
        st.session_state.gmail_result    = gmail_helper.fetch_meetup_emails(query=gmail_query, max_results=10)
        st.session_state.gmail_fetch_key = gmail_fetch_key

    gmail_result = st.session_state.gmail_result
    gmail_emails = gmail_result["emails"]
    gmail_is_sim = gmail_result["is_simulated"]

    if gmail_is_sim:
        gbanner_col, gaction_col = st.columns([5, 2])
        with gbanner_col:
            st.markdown("""
<div class="nc-card" style="border-color:#f0883e;border-left:4px solid #f0883e;">
  <span class="badge" style="background:#f0883e22;color:#f0883e;border-color:#f0883e55;">🔌 SIMULATED</span>
  <span style="color:#c9d1d9;font-size:13px;">Not connected to Gmail — showing demo invites below.</span>
</div>""", unsafe_allow_html=True)
        with gaction_col:
            if oauth_connect_supported():
                if st.button("🔗 Connect Gmail", key="gmail_connect", use_container_width=True):
                    try:
                        with st.spinner("Opening browser for Google sign-in…"):
                            run_oauth_flow()
                        st.session_state.gmail_result = gmail_helper.fetch_meetup_emails(
                            query=gmail_query, max_results=10)
                        st.success("Connected! Loading your Gmail…")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Authorisation failed: {e}")
            elif credentials_available():
                st.button("🔗 Connect (unavailable on this host)", key="gmail_connect_disabled",
                          use_container_width=True, disabled=True,
                          help="This deployment can't complete an interactive Google sign-in "
                               "(no local browser). Run the app locally to connect a real account.")
            else:
                st.button("🔗 Connect (needs credentials.json)", key="gmail_connect_disabled",
                          use_container_width=True, disabled=True)
        if gmail_result.get("error"):
            with st.expander("Debug: last Gmail error", expanded=False):
                st.code(gmail_result["error"])
    else:
        st.markdown("""
<span class="badge" style="background:#3fb95022;color:#3fb950;border-color:#3fb95055;">✅ CONNECTED</span>
<span style="color:#8b949e;font-size:12px;">Showing live Gmail search results</span>
""", unsafe_allow_html=True)

    if not gmail_emails:
        st.info("No matching emails found for this query.")
    else:
        for em in gmail_emails:
            link_html = (
                f'<a href="{em["link"]}" target="_blank" '
                'style="font-size:11px;color:#58a6ff;text-decoration:none;">🔗 Open in Gmail</a>'
            ) if em.get("link") else ""
            email_html = (
                '<div class="nc-card">'
                '<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
                '<div>'
                f'<div style="font-weight:600;color:#e6edf3;font-size:14px;">✉️ {em.get("subject", "No Subject")}</div>'
                f'<div style="color:#8b949e;font-size:12px;margin-top:3px;">From: {em.get("sender", "Unknown")} '
                f'&nbsp;·&nbsp; {em.get("date", "")}</div>'
                f'<div style="margin-top:6px;font-style:italic;color:#c9d1d9;font-size:13px;">{em.get("snippet", "")}</div>'
                '</div>'
                f'<div style="padding-top:4px;">{link_html}</div>'
                '</div>'
                '</div>'
            )
            st.markdown(email_html, unsafe_allow_html=True)

    # ── Telegram & Community Feeds ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📢 Telegram & Community Feeds")
    st.caption("Live scrape of Singapore dev-community sources — same feeds DevRelopsAgent "
               "uses for fetch_dev_event_feeds in chat.")

    from helpers import community_feed_helper

    feed_refresh = st.button("🔄 Refresh Feeds", key="feed_refresh")
    if "feed_result" not in st.session_state or feed_refresh:
        with st.spinner("Scraping Telegram, GeeksHacking, STACK, and Meetup…"):
            st.session_state.feed_result = community_feed_helper.fetch_community_feeds()

    for feed in st.session_state.feed_result:
        is_live   = feed.get("live_status") == "live"
        status_html = (
            '<span class="badge" style="background:#3fb95022;color:#3fb950;border-color:#3fb95055;">🟢 LIVE</span>'
            if is_live else
            '<span class="badge" style="background:#f0883e22;color:#f0883e;border-color:#f0883e55;">🔌 OFFLINE (fallback shown)</span>'
        )

        if feed.get("posts"):
            body_html = "".join(
                f'<div style="margin-top:6px;font-size:13px;color:#c9d1d9;">{p["text"]}<br>'
                f'<a href="{p["link"]}" target="_blank" style="font-size:11px;color:#58a6ff;'
                f'text-decoration:none;">🔗 Open post</a></div>'
                for p in feed["posts"]
            )
        elif feed.get("headings"):
            body_html = "".join(
                f'<div style="margin-top:4px;font-size:13px;color:#c9d1d9;">• {h}</div>'
                for h in feed["headings"]
            )
        else:
            body_html = f'<div style="margin-top:6px;font-size:13px;color:#c9d1d9;">{feed.get("agenda", "")}</div>'

        st.markdown(f"""
<div class="nc-card">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div style="font-weight:600;color:#d2a8ff;font-size:14px;">{feed.get('icon','📡')} {feed.get('source','Unknown')}</div>
    {status_html}
  </div>
  <div style="color:#8b949e;font-size:12px;margin-top:4px;">{feed.get('location','')}</div>
  {body_html}
  <div style="margin-top:8px;"><a href="{feed.get('link','')}" target="_blank"
       style="font-size:11px;color:#58a6ff;text-decoration:none;">🔗 View source</a></div>
</div>""", unsafe_allow_html=True)

    # ── Trading Feeds — Telegram ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💹 Trading Feeds — Telegram")
    st.caption("Live scrape of the trading Telegram channels you follow. Unofficial, no-login "
               "scrape — if a channel blocks us or has its preview disabled, it's shown as "
               "offline with a link straight to the source, never a guessed post.")

    trading_feed_refresh = st.button("🔄 Refresh Trading Feeds", key="trading_feed_refresh")
    if "trading_tg_result" not in st.session_state or trading_feed_refresh:
        with st.spinner("Scraping trading Telegram channels…"):
            st.session_state.trading_tg_result = community_feed_helper.fetch_trading_feeds()

    def _render_trading_feed_card(feed: dict) -> None:
        is_live = feed.get("live_status") == "live"
        status_html = (
            '<span class="badge" style="background:#3fb95022;color:#3fb950;border-color:#3fb95055;">🟢 LIVE</span>'
            if is_live else
            '<span class="badge" style="background:#f0883e22;color:#f0883e;border-color:#f0883e55;">🔌 OFFLINE</span>'
        )
        if feed.get("posts"):
            body_html = "".join(
                f'<div style="margin-top:6px;font-size:13px;color:#c9d1d9;">{p["text"][:280]}'
                f'{"…" if len(p["text"]) > 280 else ""}<br>'
                + (f'<a href="{p["link"]}" target="_blank" style="font-size:11px;color:#58a6ff;'
                   f'text-decoration:none;">🔗 Open post</a>' if p.get("link") else "")
                + '</div>'
                for p in feed["posts"]
            )
        else:
            body_html = ('<div style="margin-top:6px;font-size:13px;color:#8b949e;font-style:italic;">'
                          'No public preview available right now — open the source directly.</div>')
        st.markdown(f"""
<div class="nc-card">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div style="font-weight:600;color:#d2a8ff;font-size:14px;">{feed.get('icon','📡')} {feed.get('source','Unknown')}</div>
    {status_html}
  </div>
  {body_html}
  <div style="margin-top:8px;"><a href="{feed.get('link','')}" target="_blank"
       style="font-size:11px;color:#58a6ff;text-decoration:none;">🔗 View source</a></div>
</div>""", unsafe_allow_html=True)

    st.markdown("**📢 Telegram — Trading Channels**")
    for feed in st.session_state.trading_tg_result:
        _render_trading_feed_card(feed)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — TIKTOK STUDIO (paste-a-link tools)
# ════════════════════════════════════════════════════════════════════════════════
with tab_tiktok:
    from helpers import tiktok_studio_helper

    col_ttl, col_badge = st.columns([5, 2])
    with col_ttl:
        st.subheader("🎵 TikTok Studio")
        st.caption("Paste a link — generate promo content for a product, or critique a video's performance.")
    with col_badge:
        st.markdown("""
<div style="text-align:right;padding-top:6px;">
  <span class="badge" style="background:#d2a8ff22;color:#d2a8ff;border-color:#8957e555;">🧠 Gemini-Powered</span>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div class="nc-card" style="border-color:#8957e5;border-left:4px solid #d2a8ff;">
  <span style="color:#c9d1d9;font-size:13px;">
    TikTok has no public analytics API for individual creators, so both tools below do a
    <strong>best-effort scrape</strong> of the pasted page (caption, hashtags, and — for videos —
    engagement stats if TikTok's server-rendered HTML exposes them) and hand that to Gemini.
    If scraping is blocked, the critique still runs on caption/hook alone and says so explicitly.
  </span>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    tool_col1, tool_col2 = st.columns(2)

    # ── Tool 1: Product link -> Promo idea, script, shooting suggestions ────────
    with tool_col1:
        st.markdown("#### 🛍️ Product → Promo Generator")
        product_url = st.text_input(
            "Product link", placeholder="https://your-shop.com/product/...", key="tt_product_url",
        )
        product_extra = st.text_area(
            "Extra context (optional)", placeholder="e.g. target audience, key selling point",
            key="tt_product_extra", height=68,
        )
        if st.button("✨ Generate Promo", key="tt_gen_promo", use_container_width=True):
            if not product_url:
                st.warning("Paste a product link first.")
            else:
                with st.spinner("Scraping product page & writing promo…"):
                    try:
                        st.session_state.tt_promo_result = tiktok_studio_helper.generate_product_promo(
                            product_url, product_extra)
                    except Exception as e:
                        st.session_state.tt_promo_result = {"text": None, "error": str(e)}

        promo_result = st.session_state.get("tt_promo_result")
        if promo_result:
            if promo_result.get("text"):
                scraped_title = (promo_result.get("scraped") or {}).get("title")
                if scraped_title:
                    st.caption(f"📄 Detected page: {scraped_title}")
                elif promo_result.get("error"):
                    st.caption(f"⚠️ Couldn't fetch the page automatically ({promo_result['error']}) — "
                               f"wrote from the URL and extra context only.")
                st.markdown(promo_result["text"])
            else:
                st.error(f"Couldn't generate promo: {promo_result.get('error')}")

    # ── Tool 2: TikTok video link -> performance critique ───────────────────────
    with tool_col2:
        st.markdown("#### 🎥 Video → Performance Critique")
        video_url = st.text_input(
            "TikTok video link", placeholder="https://www.tiktok.com/@user/video/...", key="tt_video_url",
        )
        video_extra = st.text_area(
            "Manually reported stats (optional)",
            placeholder="e.g. 12K views, 400 likes, 30 comments — helps if stats can't be scraped",
            key="tt_video_extra", height=68,
        )
        if st.button("🔍 Analyze Video", key="tt_analyze_video", use_container_width=True):
            if not video_url:
                st.warning("Paste a TikTok video link first.")
            else:
                with st.spinner("Scraping video page & analyzing…"):
                    try:
                        st.session_state.tt_video_result = tiktok_studio_helper.analyze_tiktok_video(
                            video_url, video_extra)
                    except Exception as e:
                        st.session_state.tt_video_result = {"text": None, "error": str(e)}

        video_result = st.session_state.get("tt_video_result")
        if video_result:
            if video_result.get("text"):
                if video_result.get("stats_found"):
                    st.caption("📊 Live engagement stats were found on the page and used.")
                else:
                    st.caption("⚠️ No stats could be scraped — critique is caption/hook-based only.")
                st.markdown(video_result["text"])
            else:
                st.error(f"Couldn't analyze video: {video_result.get('error')}")


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
        orch    [label="NexusOrchestrator\n(gemini-2.0-flash)", fillcolor="#0d1b2a", fontcolor="#90CDF4",  color="#1A365D"];
        dev     [label="DevRelopsAgent\n(gemini-2.0-flash)",    fillcolor="#0a2318", fontcolor="#68D391",  color="#22543D"];
        trading [label="QuantitativeRiskAgent\n(gemini-2.0-flash)", fillcolor="#1f1600", fontcolor="#FBD38D", color="#744210"];
        tiktok  [label="CreativeAffiliateAgent\n(gemini-2.0-flash)", fillcolor="#1a0f30", fontcolor="#D6BCFA", color="#5C3C92"];
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
