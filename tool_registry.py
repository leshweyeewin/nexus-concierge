"""
tool_registry.py
Static tool-name -> MCP server mapping, so the Agent Chat trace can show which
server each call actually belongs to, matching the MCP Servers tab's icons/colors
instead of a generic wrench icon for every tool.
"""

EVENTS_MCP = {"key": "events", "label": "Events MCP", "icon": "🛠️", "color": "#3fb950"}
MARKET_MCP = {"key": "market", "label": "Market MCP", "icon": "📊", "color": "#f0883e"}
TIKTOK_MCP = {"key": "tiktok", "label": "TikTok MCP", "icon": "🎵", "color": "#d2a8ff"}
CORE_LOCAL = {"key": "core", "label": "Core Orchestration", "icon": "🧠", "color": "#58a6ff"}
SYSTEM_BADGE = {"key": "system", "label": "System", "icon": "⚙️", "color": "#8b949e"}
DRAFT_BADGE = {"key": "draft", "label": "Draft", "icon": "💬", "color": "#8b949e"}

TOOL_TO_SERVER = {
    # Events MCP (mcp_servers.py --server events)
    "list_google_calendar_events": EVENTS_MCP,
    "create_google_calendar_event": EVENTS_MCP,
    "search_gmail_emails": EVENTS_MCP,
    "fetch_dev_event_feeds": EVENTS_MCP,
    # Market MCP (mcp_servers.py --server market)
    "get_live_price": MARKET_MCP,
    "get_vector_trade_logs": MARKET_MCP,
    "get_options_chain": MARKET_MCP,
    "get_moomoo_tiger_indicators": MARKET_MCP,
    "get_tradingview_technical_rating": MARKET_MCP,
    "get_news_sentiment": MARKET_MCP,
    "get_market_movers": MARKET_MCP,
    "get_earnings_calendar": MARKET_MCP,
    "get_economic_calendar": MARKET_MCP,
    "get_analyst_ratings": MARKET_MCP,
    "get_institutional_flow": MARKET_MCP,
    "get_unusual_options_activity": MARKET_MCP,
    "get_seller_dashboard": MARKET_MCP,
    # TikTok MCP (mcp_servers.py --server tiktok)
    "get_tiktok_trends": TIKTOK_MCP,
    "get_affiliate_products": TIKTOK_MCP,
    "get_keyword_metrics": TIKTOK_MCP,
    "fetch_tiktok_creator_feeds": TIKTOK_MCP,
    # Local tools defined directly in main.py — NOT MCP calls, run in-process
    "route_task": CORE_LOCAL,
    "finish_delegation": CORE_LOCAL,
    "manage_calendar_lock": CORE_LOCAL,
    "get_daily_briefing": CORE_LOCAL,
    "manage_style_memory": CORE_LOCAL,
    "get_trading_rules": CORE_LOCAL,
    "check_risk_setup": CORE_LOCAL,
}


def server_for_tool(tool_name: str) -> dict:
    """Return the MCP-server metadata dict for a tool name, defaulting to CORE_LOCAL."""
    return TOOL_TO_SERVER.get(tool_name, CORE_LOCAL)
