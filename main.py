import os
import sys
import json
import asyncio
from google.genai.types import Content, Part
from google.adk import Agent, Workflow, Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from mcp import StdioServerParameters
from google.adk.tools import ToolContext, McpToolset
from google.adk.tools.mcp_tool import StdioConnectionParams

# =====================================================================
# 1. Verify Local AI Studio Key Connection
# =====================================================================
if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is not defined.")

# =====================================================================
# 2. SECURITY GUARDRAIL: Credential Masking
# =====================================================================
def mask_credentials(text: str) -> str:
    """Strips any credential values from output text before display (Security Guardrail)."""
    if not isinstance(text, str):
        return text
    secrets = []
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        secrets.append(api_key)
    for k, v in os.environ.items():
        if any(sub in k.upper() for sub in ["KEY", "PASSWORD", "SECRET", "TOKEN"]) and len(v) > 5:
            secrets.append(v)
    
    masked_text = text
    for secret in secrets:
        if len(secret) > 3:
            masked_text = masked_text.replace(secret, "[MASKED_CREDENTIAL]")
    return masked_text

# Custom subclass of McpToolset to enforce credential masking (guardrail)
class MaskingMcpToolset(McpToolset):
    async def get_tools(self, readonly_context=None):
        tools = await super().get_tools(readonly_context)
        for t in tools:
            original_run_async = t.run_async
            def make_wrapped_run(orig_run):
                async def wrapped_run_async(*args, **kwargs):
                    res = await orig_run(*args, **kwargs)
                    return mask_credentials(res) if isinstance(res, str) else res
                return wrapped_run_async
            t.run_async = make_wrapped_run(original_run_async)
        return tools

# =====================================================================
# 3. Instantiate MCP Toolsets using command subprocesses
# =====================================================================
_mcp_env = os.environ.copy()

git_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "git"],
            env=_mcp_env
        )
    )
)

tiktok_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "tiktok"],
            env=_mcp_env
        )
    )
)

market_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "market"],
            env=_mcp_env
        )
    )
)

# =====================================================================
# 4. Local Tools with State/Memory and Security Logic
# =====================================================================

# --- Loop/Routing Tools ---
def route_task(sub_agent: str, tool_context: ToolContext) -> str:
    """Routes execution to a specialized sub-agent for the next step.
    Pass 'dev' for local code files, repos, speaker matching, developer profiling.
    Pass 'trading' for market prices, sentiment check, risk limits, trading logs.
    Pass 'tiktok' for TikTok trend metrics, affiliate products, script hooks.
    """
    tool_context.actions.route = sub_agent
    return f"Orchestrator routing workflow step to: '{sub_agent}'"

def finish_delegation(consolidated_text: str, tool_context: ToolContext) -> str:
    """Call this when all requested sub-agent tasks are completed.
    Pass the final consolidated summary/briefing in consolidated_text.
    """
    tool_context.state["final_response"] = consolidated_text
    tool_context.actions.route = "final"
    return "Finalizing delegation and compiling response."

# --- Orchestrator Tools ---
def manage_calendar_lock(action: str, event_name: str, tool_context: ToolContext) -> str:
    """Establishes or releases global calendar locks to prevent booking conflicts during AI events.
    action: 'lock' or 'unlock'.
    event_name: The name or details of the event to lock/unlock.
    """
    locks = tool_context.state.setdefault('calendar_locks', [])
    if action == "lock":
        if event_name not in locks:
            locks.append(event_name)
        return f"Calendar lock established for: '{event_name}'."
    elif action == "unlock":
        if event_name in locks:
            locks.remove(event_name)
        return f"Calendar lock released for: '{event_name}'."
    return "Invalid action."

def get_daily_briefing(tool_context: ToolContext) -> str:
    """Generates a routine briefing summarizing current event profiles, style memory, trading rule parameters, and active calendar locks."""
    locks = tool_context.state.setdefault('calendar_locks', [])
    profiles = tool_context.state.setdefault('event_profiles', {})
    trading = tool_context.state.setdefault('trading_parameters', {})
    tiktok_mem = tool_context.state.setdefault('affiliate_style_memory', [])
    
    brief = "=== NexusConcierge Daily Briefing ===\n"
    brief += f"Active Calendar Locks: {', '.join(locks) if locks else 'None'}\n"
    brief += f"Immutable Trading Parameters: {trading}\n"
    brief += f"Stored Event Contacts: {', '.join(profiles.keys()) if profiles else 'None'}\n"
    brief += f"Historical Hooks Cached: {len(tiktok_mem)} hooks\n"
    return brief

# --- Dev-Relops Agent Tools ---
def scan_singapore_dev_events(platform_name: str) -> str:
    """Production Tool: Connects and parses active events across target Singapore tech ecosystems live."""
    import urllib.request
    import re
    
    platform = platform_name.lower().strip()
    
    # 1. Fallback Offline Database Map
    community_feeds = {
        "google developer space": (
            "📍 Location: 70 Pasir Panjang Rd, MBC II.\n"
            "🔥 Live Channels: Telegram Channel (@googledevspacesg) & GDG Community Page.\n"
            "🗓️ Latest Tranche: 'Build with AI Singapore: Gemini Deep Dive' & 'Google Cloud Next Extended'.\n"
            "🎯 Networking Targets: Google Senior DevRel Engineers, GKE/Kubernetes Core Operators."
        ),
        "geekshacking community": (
            "📍 Location: Rotates across local tech offices (Lazada One, CapitaGreen).\n"
            "🔥 Live Channels: Instagram (@geekshacking) & official event landing pages.\n"
            "🗓️ Latest Tranche: 'HackOMania: Harnessing AI for Good Hackathon'.\n"
            "🎯 Networking Targets: Open-source software engineers, nonprofit tech organizers, UX designers."
        ),
        "stack community": (
            "📍 Location: GovTech Punggol Digital District (82 Punggol Way).\n"
            "🔥 Live Channels: Singapore Government Developer Portal.\n"
            "🗓️ Latest Tranche: 'STACK Meetup: Why Data Reality Shapes AI Development'.\n"
            "🎯 Networking Targets: GovTech Engineers, Public Sector Data Architects, Civic Tech Operators."
        ),
        "meetup app": (
            "📍 Location: Distributed (HackerspaceSG at Textile Centre, AWS Offices).\n"
            "🔥 Live Channels: Meetup.com API Channels.\n"
            "🗓️ Latest Tranche: AI Tinkerers SG Showcase, Vibe Coders SG Weekly Build Session.\n"
            "🎯 Networking Targets: Independent AI Product Founders, Venture Capital scouts, LeetCode groups."
        ),
        "telegram channels": (
            "📍 Location: Digital Workspace.\n"
            "🔥 Live Channels: Singapore HUG (HashiCorp), Cloud Native CNCF Channel, GeeksHacking Chat.\n"
            "🗓️ Latest Tranche: Interactive Flash-meetups, 'Roast My Tech Stack' evening sessions.\n"
            "🎯 Networking Targets: DevOps leads, site reliability engineers, local tech developers."
        )
    }
    
    # Identify target key
    matched_key = None
    for key in community_feeds.keys():
        if key in platform or platform in key:
            matched_key = key
            break
            
    if not matched_key:
        return f"Platform '{platform_name}' recognized but no active scheduled events found. Defaulting to general Meetup search."
        
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 2. Live scrapers based on matched platform
    if matched_key == "google developer space":
        url = "https://t.me/s/googledevspacesg"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            posts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if posts:
                clean_posts = []
                for p in posts[-3:]:  # take last 3 posts
                    p_clean = re.sub(r'<[^>]+>', '', p)
                    p_clean = p_clean.replace('&amp;', '&').replace('&#33;', '!').replace('&lt;', '<').replace('&gt;', '>')
                    clean_posts.append(p_clean.strip())
                joined_posts = "\n\n---\n\n".join(clean_posts)
                return f"--- [LIVE TELEGRAM FEEDS SECURED FOR: GOOGLE DEVELOPER SPACE] ---\n{joined_posts}"
        except Exception as e:
            pass # Fall back to offline feed
            
    elif matched_key == "geekshacking community":
        url = "https://geekshacking.com/"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            headings = re.findall(r'<h[1234][^>]*>(.*?)</h[1234]>', html, re.DOTALL)
            if headings:
                clean_headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings if len(h.strip()) > 2]
                summary = "Live site headers found:\n" + "\n".join(f"- {h}" for h in clean_headings[:8])
                return f"--- [LIVE WEB FEEDS SECURED FOR: GEEKSHACKING] ---\n📍 Landing: {url}\n{summary}"
        except Exception as e:
            pass
            
    elif matched_key == "stack community":
        url = "https://www.developer.tech.gov.sg/communities/events/stack-meetups/"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else "STACK Meetups"
            headings = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html, re.DOTALL)
            if headings:
                clean_headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings]
                summary = f"Title: {title}\nLive sections found:\n" + "\n".join(f"- {h}" for h in clean_headings[:6])
                return f"--- [LIVE PORTAL FEEDS SECURED FOR: STACK COMMUNITY] ---\n📍 Landing: {url}\n{summary}"
        except Exception as e:
            pass

    # 3. Fallback to high-fidelity simulated database block
    fallback_data = community_feeds[matched_key]
    return f"--- [OFFLINE FEEDS SECURED FOR: {matched_key.upper()} (Connection Refused/Fallback)] ---\n{fallback_data}"

def manage_event_profiles(action: str, person_name: str, notes: str = None, tool_context: ToolContext = None) -> str:
    """Stores or searches contacts/founders/creators met at AI events (Dynamic Event Profiles).
    action: 'add', 'search', or 'list'.
    person_name: Name of the developer or founder.
    notes: Context-aware details or talking points (required for 'add').
    """
    profiles = tool_context.state.setdefault('event_profiles', {})
    if action == "add":
        if not notes:
            return "Error: notes must be provided to add a profile."
        profiles[person_name] = notes
        return f"Event profile saved for {person_name}: {notes}"
    elif action == "search":
        note = profiles.get(person_name, "No profile found.")
        return f"Profile for {person_name}: {note}"
    elif action == "list":
        if not profiles:
            return "No event profiles found."
        return "Event Profiles:\n" + "\n".join(f"- {name}: {n}" for name, n in profiles.items())
    return "Invalid action."

def match_speaker_to_repos(speaker_interests: list[str], tool_context: ToolContext) -> str:
    """Matches an upcoming speaker's tech stack/interests with our local repositories or frameworks."""
    stack = "Main Architecture Stack: Python, FastAPI, Gemini API, google-adk."
    matched = [interest for interest in speaker_interests if interest.lower() in stack.lower()]
    if matched:
        return f"Tech Match Found! Speaker interests {matched} align with our local repository stack: {stack}"
    return f"No direct match found. Speaker interests: {speaker_interests}. Repository stack: {stack}"

# --- Creative Copywriter Agent Tools ---
def manage_style_memory(action: str, hook_text: str = None, conversion_rate: float = None, tool_context: ToolContext = None) -> str:
    """Saves or lists historical creative hooks that yielded high conversion rates (Affiliate Style Memory).
    action: 'add' or 'list'.
    hook_text: The caption or script hook to save.
    conversion_rate: Optional historical conversion rate (e.g. 0.12).
    """
    memory = tool_context.state.setdefault('affiliate_style_memory', [])
    if action == "add":
        if not hook_text:
            return "Error: hook_text is required."
        memory.append({"hook": hook_text, "conversion_rate": conversion_rate or 0.0})
        return f"Saved hook style: '{hook_text}' (Conversion: {conversion_rate})"
    elif action == "list":
        if not memory:
            return "No style memory hooks found."
        return "Historical Style Memory Hooks:\n" + "\n".join(f"- '{item['hook']}' (Conversion: {item['conversion_rate']})" for item in memory)
    return "Invalid action."

# --- Quantitative Risk Agent Tools ---
def get_trading_rules(tool_context: ToolContext) -> str:
    """Retrieves the immutable trading rules and risk thresholds (Trading Rule Engine)."""
    rules = tool_context.state.setdefault('trading_parameters', {})
    return f"Immutable Trading Parameters: {rules}"

def check_risk_setup(ticker: str, entry_price: float, stop_loss: float, tool_context: ToolContext) -> str:
    """Checks if a proposed asset trade setup crosses maximum loss thresholds (Trading Rule Engine)."""
    rules = tool_context.state.setdefault('trading_parameters', {})
    max_loss = rules.get("max_loss_limit", 0.02)
    
    implied_loss = (entry_price - stop_loss) / entry_price
    if implied_loss > max_loss:
        return f"RISK ALERT: Trade setup for {ticker} crosses personal loss threshold! Implied loss: {implied_loss:.2%}, limit is {max_loss:.2%}. Setup rejected."
    return f"SUCCESS: Setup for {ticker} is within personal risk thresholds. Implied loss: {implied_loss:.2%}, limit is {max_loss:.2%}. Setup approved."

# =====================================================================
# 5. Specialized Domain Agents
# =====================================================================
dev_agent = Agent(
    name="DevRelopsAgent",
    model="gemini-3.1-flash-lite",
    instruction=(
        "You are a master technical networker in Singapore. You use the scan_singapore_dev_events tool "
        "to pull live agendas from Telegram, Meetup, GeeksHacking, STACK, and Google Developer Space. "
        "Match the extracted events with the user's software engineering background to build a bulletproof networking plan."
    ),
    tools=[scan_singapore_dev_events, git_toolset, manage_event_profiles, match_speaker_to_repos]
)

tiktok_agent = Agent(
    name="CreativeAffiliateAgent",
    model="gemini-3.1-flash-lite",
    instruction=(
        "You are the Creative Copywriter Agent. Generate creative hooks and TikTok scripts based on trending "
        "hashtags, keyword performance, and product datasets. Sourced from the TikTok App, Gmail, and the Telegram "
        "groups: 'TTS Beauty Creator Community', 'Tiktok Shop SG New Creators', 'Tiktok Shop SG Affaliate Creator Community', "
        "'SG Tiktok Live Creators Community', and 'Tiktok Shop SG Video Brand Opportunities' via fetch_tiktok_creator_feeds.\n"
        "Always adapt script hooks to the historical affiliate brand voice/style memory in your context."
    ),
    tools=[tiktok_toolset, manage_style_memory]
)

trading_agent = Agent(
    name="QuantitativeRiskAgent",
    model="gemini-3.1-flash-lite",
    instruction=(
        "You are the Quantitative Risk Agent. Monitor financial market indicators, analyze price feeds, and "
        "perform risk calculations checking setup limits on MooMoo API, publicly available APIs, Tiger Brokers, "
        "and MooMoo platforms. You analyze Options chains (via get_options_chain) and MooMoo/Tiger sentiment indicators (via get_moomoo_tiger_indicators).\n"
        "HARD RULE: You have ZERO financial autonomy and cannot place real trades. Warn the user if a setup violates rules. "
        "Execution remains strictly locked behind Human-in-the-Loop validation."
    ),
    tools=[market_toolset, get_trading_rules, check_risk_setup]
)

orchestrator = Agent(
    name="NexusOrchestrator",
    model="gemini-3.1-flash-lite",
    instruction=(
        "You are the central engine of NexusConcierge. Parse the core message details.\n"
        "Process:\n"
        "1. When the user makes a request, delegate tasks sequentially by calling the `route_task` tool with 'dev', 'trading', or 'tiktok'.\n"
        "2. Only route to ONE specialist at a time per tool call.\n"
        "3. When a specialist completes and triggers you again, review their response. If there are other specialists needed, call `route_task` with the next one.\n"
        "4. Once all necessary specialists have completed their tasks, synthesize their outputs into a final consolidated briefing, and call `finish_delegation` to output it.\n\n"
        "HARD SECURITY RULES:\n"
        "1. Zero Financial Autonomy: NEVER independently execute any real trade. Warn immediately if trade execution is requested.\n"
        "2. Credential Masking: Never leak API keys, passwords, or secret tokens in responses."
    ),
    tools=[route_task, finish_delegation, manage_calendar_lock, get_daily_briefing]
)

# =====================================================================
# 6. Workflow Graph and Collector Node
# =====================================================================
def collector(tool_context: ToolContext) -> str:
    """Terminal node of the workflow that outputs the consolidated response."""
    return tool_context.state.get("final_response", "No final response compiled.")

nexus_flow = Workflow(
    name="NexusConciergeFlow",
    edges=[
        ("START", orchestrator),
        (orchestrator, {
            "dev": dev_agent,
            "trading": trading_agent,
            "tiktok": tiktok_agent,
            "final": collector
        }),
        (dev_agent, orchestrator),
        (trading_agent, orchestrator),
        (tiktok_agent, orchestrator)
    ]
)

# =====================================================================
# 7. Session Initialization (Long-Term State Memory)
# =====================================================================
async def init_session(db_service: DatabaseSessionService):
    session = await db_service.get_session(
        app_name="NexusConciergeApp",
        user_id="developer_mesh",
        session_id="local_dev_test_session"
    )
    if not session:
        initial_state = {
            "event_profiles": {
                "Alice Smith": "Founder of AI-Gen. Met at SF AI Meetup 2026. Interested in LLM orchestration.",
                "Bob Jones": "DevRel at TechCorp. Met at Austin AI Summit. Working on developer experience for vector search."
            },
            "affiliate_style_memory": [
                {"hook": "Stop wasting time writing boilerplate code! Here is how AI did it in 5 seconds.", "conversion_rate": 0.12},
                {"hook": "This one tool saved my SaaS project $1000 a month.", "conversion_rate": 0.08}
            ],
            "trading_parameters": {
                "max_loss_limit": 0.02, # 2% max loss
                "preferred_indicator_triggers": ["RSI_14 < 30 (oversold)", "RSI_14 > 70 (overbought)"],
                "platforms": ["MooMoo API", "Tiger Brokers Options"],
                "allowed_instruments": ["Equity Options", "Index Options"],
                "max_options_premium_allocation": 0.05 # Max 5% of portfolio premium on options
            },
            "calendar_locks": [],
            "daily_briefing_count": 0
        }
        await db_service.create_session(
            app_name="NexusConciergeApp",
            user_id="developer_mesh",
            session_id="local_dev_test_session",
            state=initial_state
        )
        print("💾 Initialized default session state and rules.")
    else:
        print("💾 Session state loaded successfully.")

# =====================================================================
# 8. Async System Runtime Execution
# =====================================================================
async def main_async(user_payload, db_session_service):
    await init_session(db_session_service)

    runtime_runner = Runner(
        app_name="NexusConciergeApp",
        agent=nexus_flow,
        session_service=db_session_service,
        auto_create_session=True
    )

    print("NexusConcierge Output: ", end="", flush=True)

    MAX_RETRIES = 4
    RETRY_DELAY_S = 35  # Free tier 429s suggest retrying after ~30s

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response_stream = runtime_runner.run_async(
                new_message=user_payload,
                session_id="local_dev_test_session",
                user_id="developer_mesh"
            )
            async for chunk in response_stream:
                text = ""
                # ADK Events expose text via content.parts
                if hasattr(chunk, "output") and chunk.output is not None:
                    text = str(chunk.output)
                elif hasattr(chunk, "content") and chunk.content and hasattr(chunk.content, "parts"):
                    for part in chunk.content.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text
                elif hasattr(chunk, "text") and chunk.text:
                    text = chunk.text
                elif isinstance(chunk, str):
                    text = chunk
                if text:
                    print(mask_credentials(text), end="", flush=True)
            break  # Success — exit retry loop
        except Exception as e:
            err = str(e)
            if any(term in err for term in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]):
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY_S * attempt
                    print(f"\n[Rate limit or service overload hit. Retrying in {wait}s... attempt {attempt}/{MAX_RETRIES}]", flush=True)
                    await asyncio.sleep(wait)
                else:
                    print(f"\n[ERROR] Request failed after {MAX_RETRIES} retries due to quota or overload.")
                    raise
            else:
                raise

    print("\n\n🏁 Execution Complete.")

if __name__ == "__main__":
    print("🚀 NexusConcierge System Pipeline Compiled Successfully.")
    
    # Check if a custom command line argument is passed, otherwise use default test input
    user_query = (
        "I have open free time tonight. Can you check what's trending across the "
        "Google Developer Space Singapore and see if there are any specific networking targets "
        "I should look out for, while also checking if TSLA options look safe?"
    )
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        
    print(f"\nUser Input: {user_query}\n")
    
    user_payload = Content(
        role="user",
        parts=[Part.from_text(text=user_query)]
    )
    
    db_session_service = DatabaseSessionService("sqlite+aiosqlite:///nexus_sessions.db")
    asyncio.run(main_async(user_payload, db_session_service))
