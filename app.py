import streamlit as st
import asyncio
import sqlite3
import json
import os
import sys

# Ensure local directories are in Python path
sys.path.append(os.path.abspath("."))

# Page configuration for premium layout
st.set_page_config(
    page_title="NexusConcierge OS",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode / Premium Aesthetics styling
st.markdown("""
<style>
    .main {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .stApp {
        background-color: #0d1117;
    }
    h1, h2, h3 {
        color: #58a6ff !important;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 600;
    }
    .stButton>button {
        background-color: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
        transition: all 0.2s ease-in-out;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #30363d;
        border-color: #8b949e;
        color: #ffffff;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px 6px 0px 0px;
        color: #8b949e;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #21262d !important;
        color: #58a6ff !important;
        border-bottom: 2px solid #58a6ff !important;
    }
</style>
""", unsafe_allow_html=True)

# Fetch current SQLite State Memory
def fetch_session_state(user_id, session_id):
    try:
        conn = sqlite3.connect("nexus_sessions.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state FROM sessions WHERE user_id = ? AND id = ?;",
            (user_id, session_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        st.error(f"Error fetching session state: {e}")
    return None

# Async generator for executing the multi-agent workflow
async def run_agent_workflow(user_query: str, session_id: str, user_id: str):
    from google.genai.types import Content, Part
    from main import main_async
    from google.adk.sessions.database_session_service import DatabaseSessionService
    
    db_session_service = DatabaseSessionService("sqlite+aiosqlite:///nexus_sessions.db")
    user_payload = Content(
        role="user",
        parts=[Part.from_text(text=user_query)]
    )
    
    async for chunk in main_async(user_payload, db_session_service, session_id=session_id, user_id=user_id):
        yield chunk

# Convert async generator to sync generator for Streamlit consumption
def get_workflow_generator(user_query, session_id, user_id):
    loop = asyncio.new_event_loop()
    async_gen = run_agent_workflow(user_query, session_id, user_id)
    try:
        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
    finally:
        loop.close()

# Streamlit Header
st.title("🌟 NexusConcierge OS")
st.caption("Cross-Domain Multi-Agent Life Engine powered by Google ADK & FastMCP")

# Sidebar - Configuration and Database Inspector
st.sidebar.title("🛠️ Configuration")
user_id = st.sidebar.text_input("User ID", value="developer_mesh")
session_id = st.sidebar.text_input("Session ID", value="local_dev_test_session")

# Live database state extraction
db_state = fetch_session_state(user_id, session_id)

st.sidebar.markdown("---")
st.sidebar.title("💾 State Memory Inspector")
if db_state:
    st.sidebar.info(f"Loaded active state database context.")
    
    with st.sidebar.expander("📅 Calendar Locks", expanded=True):
        locks = db_state.get("calendar_locks", [])
        if locks:
            for lock in locks:
                st.write(f"- `{lock}`")
        else:
            st.write("*No active locks*")
            
    with st.sidebar.expander("👤 Event Profiles", expanded=False):
        profiles = db_state.get("event_profiles", {})
        if profiles:
            for p, notes in profiles.items():
                st.write(f"**{p}**:")
                st.write(f"{notes}")
                st.write("---")
        else:
            st.write("*No profiles cached*")
            
    with st.sidebar.expander("💡 User Profile Interests", expanded=False):
        interests = db_state.get("user_interests", ["Python", "FastAPI", "Gemini API", "LLM Orchestration"])
        for interest in interests:
            st.write(f"- {interest}")
            
    with st.sidebar.expander("📈 Immutable Trading Rules", expanded=False):
        trading = db_state.get("trading_parameters", {})
        if trading:
            for k, v in trading.items():
                st.write(f"**{k.replace('_', ' ').title()}**:")
                st.write(f"`{v}`")
        else:
            st.write("*No rules set*")
            
    with st.sidebar.expander("🎨 Copywriter Hook Memory", expanded=False):
        hooks = db_state.get("affiliate_style_memory", [])
        if hooks:
            for hook in hooks:
                st.write(f"💬 *\"{hook['hook']}\"*")
                st.write(f"Conversion: `{hook['conversion_rate']:.0%}`")
                st.write("---")
        else:
            st.write("*No hooks saved*")
else:
    st.sidebar.warning("State database empty or session not initialized yet.")

# Main Panel Layout using Tabs
tab_chat, tab_graph, tab_mcp = st.tabs([
    "💬 Interactive Agent Chat", 
    "📊 Workflow Routing DAG", 
    "📂 MCP Server Registrations"
])

# Interactive Chat Interface
with tab_chat:
    st.subheader("Interactive Agent Session")
    st.write("Submit a request to route tasks through specialized agents (Events, Market, TikTok).")
    
    # Initialize message list in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    # Render chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
    # User Input
    if prompt := st.chat_input("Enter your request here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        # Run agent execution stream
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            
            with st.spinner("Orchestrator routing tasks..."):
                try:
                    for chunk in get_workflow_generator(prompt, session_id, user_id):
                        full_response += chunk
                        placeholder.write(full_response + "▌")
                    placeholder.write(full_response)
                except Exception as e:
                    st.error(f"Error running pipeline: {e}")
                    
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                # Force database state refresh
                st.rerun()

# Workflow routing Graphviz visualization
with tab_graph:
    st.subheader("Google ADK workflow execution DAG")
    st.write("Specialist sub-agents process routing tokens and loop back to the central orchestrator until completion.")
    
    dot_code = """
    digraph G {
        background="transparent";
        node [style=filled, shape=box, fontname="Inter, sans-serif", fontsize=11, border=none, height=0.4];
        edge [fontname="Inter, sans-serif", fontsize=9, color="#4A5568", fontcolor="#8b949e"];
        
        START [label="Start Node", color="#21262d", fontcolor="#58a6ff"];
        orch [label="NexusOrchestrator\\n(gemini-3.1-flash-lite)", color="#1A365D", fontcolor="#90CDF4"];
        dev [label="DevRelopsAgent\\n(gemini-3.1-flash-lite)", color="#22543D", fontcolor="#68D391"];
        trading [label="QuantitativeRiskAgent\\n(gemini-3.1-flash-lite)", color="#744210", fontcolor="#FBD38D"];
        tiktok [label="CreativeAffiliateAgent\\n(gemini-3.1-flash-lite)", color="#5C3C92", fontcolor="#D6BCFA"];
        final [label="Collector Function\\n(Terminal Node)", color="#742A2A", fontcolor="#FEB2B2"];
        
        START -> orch;
        orch -> dev [label="route: dev"];
        orch -> trading [label="route: trading"];
        orch -> tiktok [label="route: tiktok"];
        orch -> final [label="route: final"];
        
        dev -> orch;
        trading -> orch;
        tiktok -> orch;
    }
    """
    st.graphviz_chart(dot_code)

# MCP Server registrations detail dashboard
with tab_mcp:
    st.subheader("Specialized Local MCP Server Registrations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🛠️ Events MCP Server")
        st.markdown("**Tools:**")
        st.code("""
1. fetch_dev_event_feeds
   - Live Telegram/Web Scraper
   - Gathers event agendas live
   - Captures links from posts
        """, language="markdown")
        st.markdown("**Status:** `Live Web & Telegram Scraping`")
        
    with col2:
        st.markdown("### 📈 Market MCP Server")
        st.markdown("**Tools:**")
        st.code("""
1. get_live_price
   - Live price (yfinance API)
   - Dynamic RSI & MACD

2. get_vector_trade_logs
   - Read vector DB simulation

3. get_options_chain
   - Nearest expiry strikes
   - Real bids/asks (yfinance)

4. get_moomoo_tiger_indicators
   - Put/Call volume ratio proxy
        """, language="markdown")
        st.markdown("**Status:** `Live API Integration (yfinance)`")
        
    with col3:
        st.markdown("### 📱 TikTok MCP Server")
        st.markdown("**Tools:**")
        st.code("""
1. get_tiktok_trends
   - Trends & engagement logs

2. get_affiliate_products
   - Commission and details

3. get_keyword_metrics
   - Vol and competition level

4. fetch_tiktok_creator_feeds
   - App and group feed caches
        """, language="markdown")
        st.markdown("**Status:** `Simulated Sandbox (No Business Gating)`")
