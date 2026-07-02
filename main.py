import os
import sys
import json
import asyncio
from google import genai
# Import Content and Part types from the official genai types namespace
from google.genai.types import Content, Part
from google.adk import Agent, Workflow, Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from mcp import StdioServerParameters
from google.adk.tools import ToolContext
from google.adk.tools.mcp_tool import StdioConnectionParams

# 1. Verify Local AI Studio Key Connection
if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("CRITICAL: GEMINI_API_KEY environment variable is not defined.")

# Helper to mask secret credentials (guardrail)
def mask_credentials(text: str) -> str:
    if not isinstance(text, str):
        return text
    secrets = []
    # Mask Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        secrets.append(api_key)
    # Mask other env vars that look like secrets/keys
    for k, v in os.environ.items():
        if any(sub in k.upper() for sub in ["KEY", "PASSWORD", "SECRET", "TOKEN"]) and len(v) > 5:
            secrets.append(v)
    
    masked_text = text
    for secret in secrets:
        if len(secret) > 3:
            masked_text = masked_text.replace(secret, "[MASKED_CREDENTIAL]")
    return masked_text

# Custom subclass of McpToolset to enforce credential masking (guardrail)
from google.adk.tools import McpToolset
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

# 2. Local Tools with State/Memory and Security Logic

# Orchestrator Tools
def route_tasks(sub_agents: list[str], tool_context: ToolContext) -> str:
    """Delegates tasks to specialized sub-agents based on user requests.
    Pass 'dev' for local code files, repos, speaker matching, developer profiling.
    Pass 'trading' for market prices, sentiment check, risk limits, trading logs.
    Pass 'tiktok' for TikTok trend metrics, affiliate products, script hooks.
    Can pass multiple in a list if the query spans multiple domains.
    """
    tool_context.route = sub_agents
    return f"Orchestrator delegated tasks to: {sub_agents}"

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

# Dev-Relops Agent Tools
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
    # Hardcoded context stack
    stack = "Main Architecture Stack: Python, FastAPI, Gemini API, google-adk."
    matched = [interest for interest in speaker_interests if interest.lower() in stack.lower()]
    if matched:
        return f"Tech Match Found! Speaker interests {matched} align with our local repository stack: {stack}"
    return f"No direct match found. Speaker interests: {speaker_interests}. Repository stack: {stack}"

# Creative Copywriter Agent Tools
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

# Quantitative Risk Agent Tools
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

# 3. Instantiate MCP Toolsets using command subprocesses
git_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "git"],
            env=os.environ.copy()
        )
    )
)

tiktok_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "tiktok"],
            env=os.environ.copy()
        )
    )
)

market_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "market"],
            env=os.environ.copy()
        )
    )
)

# 4. Instantiate Specialized Domain Agents
dev_agent = Agent(
    name="DevRelopsAgent",
    model="gemini-1.5-pro",
    instruction=(
        "You are the Dev-Relops Agent of NexusConcierge. Parse AI event agendas and match speaker "
        "interests to active GitHub repos and frameworks. Ground your responses in local codebase data "
        "by query local directories or code blocks via the git-server tools. Remeaver to check dynamic "
        "event profiles to locate developers or creators you have met before."
    ),
    tools=[git_toolset, manage_event_profiles, match_speaker_to_repos]
)

tiktok_agent = Agent(
    name="CreativeAffiliateAgent",
    model="gemini-1.5-flash",
    instruction=(
        "You are the Creative Copywriter Agent. Generate creative hooks and TikTok scripts based on trending "
        "hashtags, keyword performance, and product datasets. Always adapt script hooks to the historical "
        "affiliate brand voice/style memory in your context."
    ),
    tools=[tiktok_toolset, manage_style_memory]
)

trading_agent = Agent(
    name="QuantitativeRiskAgent",
    model="gemini-1.5-pro",
    instruction=(
        "You are the Quantitative Risk Agent. Monitor financial market indicators, analyze price feeds, and "
        "perform risk calculations checking setup limits. HARD RULE: You have ZERO financial autonomy and "
        "cannot place real trades. Warn the user if a setup violates rules. Execution remains strictly "
        "locked behind Human-in-the-Loop validation."
    ),
    tools=[market_toolset, get_trading_rules, check_risk_setup]
)

orchestrator = Agent(
    name="NexusOrchestrator",
    model="gemini-1.5-flash",
    instruction=(
        "You are the central engine of NexusConcierge. Parse the core message details. "
        "Explicitly delegate tasks to DevRelopsAgent (route 'dev'), QuantitativeRiskAgent (route 'trading'), "
        "or CreativeAffiliateAgent (route 'tiktok') using the route_tasks tool depending on what the user asks. "
        "You can route to multiple sub-agents if needed. "
        "You also handle routine daily briefings, and manage calendar locks. "
        "HARD SECURITY RULE: Zero financial autonomy - never place trades independently, warn if execution is requested."
    ),
    tools=[route_tasks, manage_calendar_lock, get_daily_briefing]
)

# 5. Define Graph Relationships via Structured Workflow Edges
nexus_flow = Workflow(
    name="NexusConciergeFlow",
    edges=[
        ("START", orchestrator),
        (orchestrator, {
            "dev": dev_agent,
            "trading": trading_agent,
            "tiktok": tiktok_agent
        })
    ]
)

# Initialize Session default state asynchronously
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
                "preferred_indicator_triggers": ["RSI_14 < 30 (oversold)", "RSI_14 > 70 (overbought)"]
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

# 6. Execute System Runtime
if __name__ == "__main__":
    print("🚀 NexusConcierge System Pipeline Compiled Successfully.")
    
    # Check if a custom command line argument is passed, otherwise use default test input
    user_query = (
        "I'm speaking at an AI event. Scan my local project repository 'nexus-concierge' "
        "and check if trading conditions for BTC look stable right now."
    )
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        
    print(f"\nUser Input: {user_query}\n")
    
    user_payload = Content(
        role="user",
        parts=[Part.from_text(text=user_query)]
    )
    
    db_session_service = DatabaseSessionService("sqlite+aiosqlite:///nexus_sessions.db")
    asyncio.run(init_session(db_session_service))
    
    runtime_runner = Runner(
        app_name="NexusConciergeApp",
        agent=nexus_flow,
        session_service=db_session_service,
        auto_create_session=True
    )
    
    print("NexusConcierge Output: ", end="", flush=True)
    
    response_stream = runtime_runner.run(
        new_message=user_payload,
        session_id="local_dev_test_session",
        user_id="developer_mesh"
    )
    
    for chunk in response_stream:
        text = ""
        if hasattr(chunk, "text") and chunk.text:
            text = chunk.text
        elif hasattr(chunk, "content") and chunk.content:
            text = chunk.content
        elif isinstance(chunk, str):
            text = chunk
            
        if text:
            # Enforce credential masking on output stream
            print(mask_credentials(text), end="", flush=True)
            
    print("\n\n🏁 Execution Complete.")
