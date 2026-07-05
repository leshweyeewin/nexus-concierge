import os
import sys
import asyncio
import yaml
from google.genai.types import Content, Part
from google.adk import Agent, Workflow, Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from mcp import StdioServerParameters
from google.adk.tools import ToolContext, McpToolset
from google.adk.tools.mcp_tool import StdioConnectionParams

# =====================================================================
# 1. Verify Local AI Studio Key Connection and Load Config
# =====================================================================
if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
    raise ValueError("CRITICAL: neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is defined.")

def load_adk_config():
    config_path = "adk_config.yml"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                print("[Config] Configuration loaded successfully from adk_config.yml")
                return cfg
        except Exception as e:
            print(f"[Warning] Could not parse {config_path}: {e}")
    else:
        print(f"[Warning] {config_path} not found. Using system defaults.")
    return None

adk_config = load_adk_config()

def get_agent_config(agent_name: str, default_model: str, default_instruction: str):
    if adk_config and "agents" in adk_config:
        for agent in adk_config["agents"]:
            if agent.get("name") == agent_name:
                return (
                    agent.get("model", default_model),
                    agent.get("system_instruction", default_instruction)
                )
    return default_model, default_instruction

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

events_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "events"],
            env=_mcp_env
        ),
        timeout=45.0,  # default (5s) isn't enough for subprocess startup + live scrape/API calls; extra headroom for slower cloud/free-tier CPU
    )
)

tiktok_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "tiktok"],
            env=_mcp_env
        ),
        timeout=45.0,  # default (5s) isn't enough for subprocess startup + live scrape/API calls; extra headroom for slower cloud/free-tier CPU
    )
)

market_toolset = MaskingMcpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["mcp_servers.py", "--server", "market"],
            env=_mcp_env
        ),
        timeout=45.0,  # default (5s) isn't enough for subprocess startup + live scrape/API calls; extra headroom for slower cloud/free-tier CPU
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
    # NOTE: route_task and finish_delegation can run as sibling parallel function
    # calls within the SAME model turn (ADK executes them as concurrent asyncio
    # tasks, each with its OWN ToolContext instance) — a plain attribute set here
    # (e.g. `tool_context._route_called = ...`) lives only on THIS call's Context
    # object and is invisible to finish_delegation's separate Context. `state` is
    # the one thing actually shared/persisted across sibling calls in the same
    # turn, so the pending-route flag must live there instead.
    tool_context.state["_pending_route"] = sub_agent
    return f"Orchestrator routing workflow step to: '{sub_agent}'"

def finish_delegation(consolidated_text: str, tool_context: ToolContext) -> str:
    """Call this when all requested sub-agent tasks are completed.
    Pass the final consolidated summary/briefing in consolidated_text.
    """
    # Gemini can emit route_task and finish_delegation as parallel calls in the SAME
    # turn, which would otherwise let finish_delegation overwrite route_task's target
    # and skip the specialist's turn entirely — finalizing on a guessed placeholder
    # instead of real data. If a specialist was just routed to but hasn't actually run
    # yet, force the real handoff instead of finalizing.
    pending = tool_context.state.get("_pending_route")
    if pending:
        tool_context.actions.route = pending
        return (f"ERROR: Cannot finish yet — '{pending}' has not actually returned data. "
                f"Forcing handoff to '{pending}' now. Wait for its real response before calling finish_delegation again.")
    tool_context.state["final_response"] = consolidated_text
    tool_context.actions.route = "final"
    return "Finalizing delegation and compiling response."

def _clear_pending_route(callback_context):
    """Runs after a specialist agent's node genuinely finishes its turn.
    Clears the '_pending_route' flag set by route_task so a later, legitimate
    finish_delegation call (after this specialist has actually returned data)
    isn't mistaken for the same race it was guarding against.
    """
    callback_context.state["_pending_route"] = None

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

def match_speaker_to_interests(speaker_interests: list[str], tool_context: ToolContext) -> str:
    """Matches an upcoming speaker's tech stack/interests with the user's software engineering interests/profile."""
    user_ints = tool_context.state.setdefault('user_interests', ["Python", "FastAPI", "Gemini API", "LLM Orchestration"])
    matched = [interest for interest in speaker_interests if any(ui.lower() in interest.lower() or interest.lower() in ui.lower() for ui in user_ints)]
    if matched:
        return f"Tech Match Found! Speaker interests {speaker_interests} align with your profile interests: {matched} (Full profile: {user_ints})"
    return f"No direct match found. Speaker interests: {speaker_interests}. User profile interests: {user_ints}"

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
    if entry_price <= 0:
        return f"ERROR: entry_price must be a positive number, got {entry_price}."

    rules = tool_context.state.setdefault('trading_parameters', {})
    max_loss = rules.get("max_loss_limit", 0.02)

    implied_loss = (entry_price - stop_loss) / entry_price
    if implied_loss > max_loss:
        return f"RISK ALERT: Trade setup for {ticker} crosses personal loss threshold! Implied loss: {implied_loss:.2%}, limit is {max_loss:.2%}. Setup rejected."
    return f"SUCCESS: Setup for {ticker} is within personal risk thresholds. Implied loss: {implied_loss:.2%}, limit is {max_loss:.2%}. Setup approved."

# =====================================================================
# 5. Specialized Domain Agents
# =====================================================================
dev_model, dev_instruction = get_agent_config(
    "DevRelopsAgent",
    "gemini-3.1-flash-lite",
    (
        "You are a master technical networker in Singapore. You scan dev events around town. "
        "You use the fetch_dev_event_feeds tool to pull live agendas from Telegram, Meetup, GeeksHacking, STACK, and Google Developer Space. "
        "You also manage the user's schedule using the list_google_calendar_events and create_google_calendar_event tools, "
        "and you search the user's emails for tech event details and invitations using the search_gmail_emails tool. "
        "Match the extracted events with the user's software engineering interests to build a bulletproof networking plan."
    )
)
dev_agent = Agent(
    name="DevRelopsAgent",
    model=dev_model,
    instruction=dev_instruction,
    tools=[events_toolset, manage_event_profiles, match_speaker_to_interests],
    after_agent_callback=_clear_pending_route
)

tiktok_model, tiktok_instruction = get_agent_config(
    "CreativeAffiliateAgent",
    "gemini-3.1-flash-lite",
    (
        "You are the Creative Copywriter Agent. Generate creative hooks and TikTok scripts based on trending "
        "hashtags, keyword performance, and product datasets. Sourced from the TikTok App, Gmail, and the Telegram "
        "groups: 'TTS Beauty Creator Community', 'Tiktok Shop SG New Creators', 'Tiktok Shop SG Affiliate Creator Community', "
        "'SG Tiktok Live Creators Community', and 'Tiktok Shop SG Video Brand Opportunities' via fetch_tiktok_creator_feeds.\n"
        "Always adapt script hooks to the historical affiliate brand voice/style memory in your context."
    )
)
tiktok_agent = Agent(
    name="CreativeAffiliateAgent",
    model=tiktok_model,
    instruction=tiktok_instruction,
    tools=[tiktok_toolset, manage_style_memory],
    after_agent_callback=_clear_pending_route
)

trading_model, trading_instruction = get_agent_config(
    "QuantitativeRiskAgent",
    "gemini-3.1-flash-lite",
    (
        "You are the Quantitative Risk Agent. You use the get_live_price tool to fetch price feeds, "
        "get_options_chain to analyze Options chains, and get_moomoo_tiger_indicators for MooMoo/Tiger sentiment indicators.\n"
        "HARD RULE ON PRICE FRESHNESS: get_live_price may return a JSON payload with \"stale\": true when the live feed "
        "is unavailable and a cached value is being served instead. Never present a stale price as current — always check "
        "for the \"stale\" field and, if present, explicitly tell the user the price is stale and quote the \"as_of\" timestamp.\n"
        "HARD RULE ON RISK CHECKS: Whenever the user proposes or asks about a trade setup with an entry price and stop-loss "
        "(or you have both values), you MUST call the check_risk_setup tool to validate it against the immutable risk "
        "thresholds — never estimate or eyeball the percentage-loss/threshold comparison yourself. Relay the tool's verdict "
        "verbatim, including the word 'rejected' or 'approved' exactly as returned, rather than paraphrasing it into a "
        "generic warning.\n"
        "HARD RULE: You have ZERO financial autonomy and cannot place real trades. Warn the user if a setup violates rules. "
        "Execution remains strictly locked behind Human-in-the-Loop validation."
    )
)
trading_agent = Agent(
    name="QuantitativeRiskAgent",
    model=trading_model,
    instruction=trading_instruction,
    tools=[market_toolset, get_trading_rules, check_risk_setup],
    after_agent_callback=_clear_pending_route
)

orch_model = "gemini-3.1-flash-lite"
orch_instruction = (
    "You are the central engine of NexusConcierge. Parse the core message details.\n"
    "Process:\n"
    "1. Analyze the user's input to determine which specific domains are requested:\n"
    "   - Developer events, calendars, contacts, or networking -> 'dev'\n"
    "   - Market data, stock/option prices, metrics, or trading risk -> 'trading'\n"
    "   - TikTok trend data, affiliate marketing products, copywriting, or video script hooks -> 'tiktok'\n"
    "2. Only route to a specialist if the user's request explicitly or implicitly requires information or actions from that specialist's domain.\n"
    "3. If the user's query does not require any specialist (e.g. greeting, general knowledge, or follow-up question that can be answered from local context), call `finish_delegation` immediately with your response.\n"
    "4. Route sequentially, one specialist at a time. Do not make multiple specialist calls in parallel.\n"
    "5. Once all relevant specialist tasks for the query have completed, synthesize the answers and call `finish_delegation` to output the final response.\n\n"
    "HARD RULE ON TOOL SCOPE: `get_daily_briefing` and `manage_calendar_lock` only read/write your own internal session "
    "state (locks, cached profiles, trading params) — they NEVER touch the user's real Google Calendar, Gmail, TikTok "
    "feeds, or market data. Any request that mentions the calendar, schedule, upcoming events, emails, tickers/prices, "
    "or TikTok trends MUST be routed via `route_task` to the matching specialist ('dev', 'trading', or 'tiktok'), even "
    "if `get_daily_briefing` sounds like it could answer it. Only call `get_daily_briefing`/`manage_calendar_lock` "
    "directly when the user explicitly asks about locks or wants an internal status summary.\n\n"
    "HARD RULE ON ORDERING: NEVER call `finish_delegation` in the same turn as `route_task`, and NEVER call it before "
    "a routed specialist has actually returned real data for every part of the request. If you haven't received the "
    "specialist's actual results yet (only a routing acknowledgement), wait — do not guess, fabricate, or write a "
    "placeholder like 'please stand by' into `consolidated_text`. `consolidated_text` must always be built only from "
    "real data/results actually returned by the specialists.\n\n"
    "HARD RULE ON FINISHING: As soon as a specialist's response already answers what the user asked for (and no other specialists "
    "are needed for other parts of the query), you MUST call `finish_delegation` with that data in the SAME turn you review it — "
    "do not end your turn by asking the user an open-ended follow-up question or offering a menu of next steps instead. "
    "Only ask the user something if their original request was genuinely ambiguous about which specialist or ticker/topic they meant. "
    "Every turn must call `route_task` or `finish_delegation` — never end a turn with neither.\n\n"
    "HARD SECURITY RULES:\n"
    "1. Zero Financial Autonomy: NEVER independently execute any real trade. Warn immediately if trade execution is requested.\n"
    "2. Credential Masking: Never leak API keys, passwords, or secret tokens in responses."
)
if adk_config and "orchestrator" in adk_config:
    orch_model = adk_config["orchestrator"].get("model", orch_model)
    orch_instruction = adk_config["orchestrator"].get("system_instruction", orch_instruction)

orchestrator = Agent(
    name="NexusOrchestrator",
    model=orch_model,
    instruction=orch_instruction,
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
async def init_session(db_service: DatabaseSessionService, user_id="developer_mesh", session_id="local_dev_test_session"):
    # Using default 'developer_mesh' and 'local_dev_test_session' to ensure session-state persistence in SQLite
    session = await db_service.get_session(
        app_name="NexusConciergeApp",
        user_id=user_id,
        session_id=session_id
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
            "user_interests": ["Python", "FastAPI", "Gemini API", "LLM Orchestration"],
            "daily_briefing_count": 0
        }
        await db_service.create_session(
            app_name="NexusConciergeApp",
            user_id=user_id,
            session_id=session_id,
            state=initial_state
        )
        print("[Database] Initialized default session state and rules.")
    else:
        print("[Database] Session state loaded successfully.")

# =====================================================================
# 8. Async System Runtime Execution
# =====================================================================
async def main_async(user_payload, db_session_service, session_id="local_dev_test_session", user_id="developer_mesh"):
    """
    Yields structured events instead of raw text, so callers can tell the difference
    between the routing/tool-call trace and the actual final answer:
      {"kind": "trace", "author": str, "message": str}
      {"kind": "text",  "author": str, "text": str, "is_final": bool}

    Without this split, every specialist's intermediate response AND the orchestrator's
    final synthesis (which restates the same facts, plus each agent's own boilerplate
    disclaimers) all got flattened into one blob — looking like duplicated output with
    no way to see which agent/tool actually ran.
    """
    await init_session(db_session_service, user_id=user_id, session_id=session_id)

    # Each user turn takes ~4 sequential Gemini calls (orchestrator route -> specialist
    # tool-call -> specialist synthesis -> orchestrator finish), so free-tier per-minute
    # quota is easy to hit. Kept short/shallow on purpose: a long retry cascade (the
    # previous 4 attempts * up to 35s*attempt backoff could run ~3.5 minutes) just makes
    # a quota problem look like a hang. One quick retry surfaces the real quota error fast.
    MAX_RETRIES = 2
    RETRY_DELAY_S = 20  # Free tier 429s are typically per-minute; ~20s covers a partial window

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Built fresh each attempt: a failed attempt can still have partially
            # written events to the session before erroring, so a reused Runner's
            # cached view of session state goes stale and the next append fails with
            # "session has been modified in storage since it was loaded." Recreating
            # the Runner forces a clean reload of the current session state.
            runtime_runner = Runner(
                app_name="NexusConciergeApp",
                agent=nexus_flow,
                session_service=db_session_service,
                auto_create_session=True
            )
            response_stream = runtime_runner.run_async(
                new_message=user_payload,
                session_id=session_id,
                user_id=user_id
            )
            async for chunk in response_stream:
                author = getattr(chunk, "author", None) or getattr(chunk, "node_name", None) or "System"

                try:
                    for fc in chunk.get_function_calls():
                        args_str = mask_credentials(
                            ", ".join(f"{k}={v!r}" for k, v in (fc.args or {}).items())
                        )
                        yield {"kind": "trace", "author": author, "tool_name": fc.name,
                               "message": f"🛠️ Calling `{fc.name}({args_str})`"}
                    for fr in chunk.get_function_responses():
                        resp_str = mask_credentials(str(fr.response))
                        if len(resp_str) > 220:
                            resp_str = resp_str[:220] + "…"
                        yield {"kind": "trace", "author": author, "tool_name": fr.name,
                               "message": f"✅ `{fr.name}` → {resp_str}"}
                except Exception:
                    pass  # Not every chunk type supports function-call introspection.

                text = ""
                is_final = False
                # ADK Events expose text via content.parts. NOTE: is_final only ever True for
                # the collector node's `output` (the finish_delegation consolidated_text) — the
                # orchestrator/specialists' own is_final_response()==True turns are still just
                # one agent's turn ending, NOT the workflow's actual final answer. Treating those
                # as final too was why replies looked duplicated (orchestrator's closing remark +
                # the collector's output both got shown as "the" answer).
                if hasattr(chunk, "output") and chunk.output is not None:
                    text = str(chunk.output)
                    is_final = True  # the collector node's output is always the terminal answer
                elif hasattr(chunk, "content") and chunk.content and getattr(chunk.content, "parts", None) is not None:
                    for part in chunk.content.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text
                elif hasattr(chunk, "text") and chunk.text:
                    text = chunk.text
                elif isinstance(chunk, str):
                    text = chunk

                if text:
                    yield {"kind": "text", "author": author, "text": mask_credentials(text), "is_final": is_final}
            break  # Success — exit retry loop
        except Exception as e:
            err = str(e)
            if any(term in err for term in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]):
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY_S * attempt
                    yield {"kind": "trace", "author": "System",
                           "message": f"Rate limit or service overload hit. Retrying in {wait}s... attempt {attempt}/{MAX_RETRIES}"}
                    await asyncio.sleep(wait)
                else:
                    yield {"kind": "trace", "author": "System",
                           "message": (f"[ERROR] Gemini API quota/rate limit exceeded after {MAX_RETRIES} attempts. "
                                       f"This is a free-tier request-per-minute cap, not a bug in this request — "
                                       f"wait about a minute and try again, or enable Cloud Billing on the API "
                                       f"key's project for higher limits.")}
                    raise
            else:
                raise

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    print("[System] NexusConcierge System Pipeline Compiled Successfully.")
    
    db_session_service = DatabaseSessionService("sqlite+aiosqlite:///nexus_sessions.db")
    
    async def run_single_query(query: str):
        print(f"\nUser Input: {query}\n")
        user_payload = Content(
            role="user",
            parts=[Part.from_text(text=query)]
        )
        print("NexusConcierge Output:\n")
        final_text = ""
        try:
            async for event in main_async(user_payload, db_session_service):
                if event["kind"] == "trace":
                    print(f"  [{event['author']}] {event['message']}", flush=True)
                elif event["kind"] == "text":
                    if event.get("is_final"):
                        final_text += event["text"]
                    print(f"  [{event['author']}] {event['text']}", flush=True)
            print(f"\n--- Final Answer ---\n{final_text or '(no final response text — see trace above)'}")
        except Exception as e:
            print(f"\n❌ Pipeline execution error: {e}")
        print("\n[System] Execution Complete.")

    if len(sys.argv) > 1:
        # Run command line arguments once
        user_query = " ".join(sys.argv[1:])
        asyncio.run(run_single_query(user_query))
    else:
        # Interactive mode
        print("\n==========================================")
        print("💡 NexusConcierge Interactive Console Mode")
        print("==========================================")
        print("Ask any question (e.g. check dev events, check stock prices, write a hook).")
        print("Type 'exit' or 'quit' to end session.\n")
        
        while True:
            try:
                user_input = input("Ask NexusConcierge > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break
                asyncio.run(run_single_query(user_input))
                print("-" * 50 + "\n")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")

