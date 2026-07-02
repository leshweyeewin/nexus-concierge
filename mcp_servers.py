import os
import sys
import json
import argparse
from mcp.server.fastmcp import FastMCP

# Parse arguments
parser = argparse.ArgumentParser(description="NexusConcierge Specialized MCP Server")
parser.add_argument("--server", type=str, required=True, choices=["git", "tiktok", "market"], help="Specify which sub-server to start")
args, unknown = parser.parse_known_args()

server_name = f"{args.server}-server"
mcp = FastMCP(server_name)

if args.server == "git":
    @mcp.tool(name="get_active_repo_context", description="Fetch the frameworks and structure of local development projects.")
    def get_active_repo_context(repo_name: str) -> str:
        try:
            files = os.listdir(".")
            file_list = ", ".join(files)
            return f"Repo: {repo_name} | Files in workspace: {file_list} | Main Architecture Stack: Python, FastAPI, Gemini API, google-adk."
        except Exception as e:
            return f"Repo: {repo_name} | Main Architecture Stack: Python, FastAPI, Gemini API, google-adk. Error listing files: {str(e)}"

    @mcp.tool(name="check_active_branch_code", description="Reads content of a specific code file in the active repository.")
    def check_active_branch_code(file_path: str) -> str:
        try:
            if not os.path.exists(file_path):
                return f"File {file_path} not found."
            abs_path = os.path.abspath(file_path)
            cwd = os.getcwd()
            if not abs_path.startswith(cwd):
                return "Access denied: file path is outside workspace."
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(1000) # first 1000 chars
            return f"File: {file_path}\nContent:\n{content}..."
        except Exception as e:
            return f"Error reading {file_path}: {str(e)}"

    @mcp.tool(name="fetch_dev_event_feeds", description="Scans developer channels (Telegram channels: Stack Community, Geeks Social, Google Developer Space, GeeksHacking, Meetup app, Gmail) for event agendas, invites, and speaker profiles.")
    def fetch_dev_event_feeds() -> str:
        feeds = [
            {
                "source": "Telegram: Stack Community",
                "invite_found": True,
                "agenda": "AI Meetup Singapore 2026 - Speaker: Dr. Melissa Tan on 'Agentic RAG with Google ADK'",
                "tech_stack": ["Google ADK", "Python", "FastAPI"],
                "speaker": "Melissa Tan"
            },
            {
                "source": "Meetup: Google Developer Space Singapore",
                "invite_found": True,
                "agenda": "Google Developer Space SG: Hands-on GenAI. Agenda: Building Local MCP servers using FastMCP.",
                "tech_stack": ["FastMCP", "TypeScript", "Python"],
                "speaker": "Kenneth Ng"
            },
            {
                "source": "Gmail Inbox",
                "invite_found": False,
                "agenda": "Agenda update: Panel discussion on cross-domain multi-agent platforms.",
                "tech_stack": ["LLM Orchestration"],
                "speaker": "Unknown"
            }
        ]
        return json.dumps(feeds)

elif args.server == "tiktok":
    @mcp.tool(name="get_tiktok_trends", description="Tracks trending hashtags, hooks, and performance metrics on TikTok.")
    def get_tiktok_trends() -> str:
        trends = {
            "trending_hashtags": ["#AIPrep", "#DevLife", "#NextConcierge", "#ProductivityHack"],
            "top_hooks": [
                "This one tool saved my SaaS project $1000 a month.",
                "Stop wasting time writing boilerplate code! Here is how AI did it in 5 seconds."
            ],
            "average_engagement_rate": "8.5%"
        }
        return json.dumps(trends)

    @mcp.tool(name="get_affiliate_products", description="Returns active TikTok affiliate products and performance data.")
    def get_affiliate_products() -> str:
        products = [
            {"product_name": "Smart Desk Organiser", "commission_rate": "15%", "conversion_rate": "4.2%", "rating": 4.8},
            {"product_name": "AI Productivity Notebook", "commission_rate": "20%", "conversion_rate": "5.6%", "rating": 4.9},
            {"product_name": "USB-C Portable Monitor", "commission_rate": "10%", "conversion_rate": "3.1%", "rating": 4.7}
        ]
        return json.dumps(products)

    @mcp.tool(name="get_keyword_metrics", description="Returns search volume and competition level for TikTok keywords.")
    def get_keyword_metrics(keyword: str) -> str:
        metrics = {
            "keyword": keyword,
            "monthly_search_volume": 45000,
            "competition_level": "medium-high",
            "recommended_hook_type": "problem-solving"
        }
        return json.dumps(metrics)

    @mcp.tool(name="fetch_tiktok_creator_feeds", description="Gathers video script ideas, trend reports, and product options from TikTok App, Gmail, and specialized creator Telegram channels (TTS Beauty Creator Community, Tiktok Shop SG New Creators, SG Tiktok Live Creators Community, etc.)")
    def fetch_tiktok_creator_feeds() -> str:
        feeds = {
            "Tiktok App": {
                "trending_hook": "They don't want you to know this simple coding trick...",
                "suggested_product": "AI Productivity Notebook"
            },
            "Telegram: Tiktok Shop SG Affaliate Creator Community": {
                "active_brief": "High commission challenge: promote USB-C Portable Monitors to remote developers.",
                "commission_bonus": "+5% extra for top creators"
            },
            "Telegram: SG Tiktok Live Creators Community": {
                "trend": "Live coding streams are experiencing a 35% surge in viewer retention."
            }
        }
        return json.dumps(feeds)

elif args.server == "market":
    @mcp.tool(name="get_live_price", description="Fetch live price feeds and technical indicators for active US stock tickers.")
    def get_live_price(ticker: str) -> str:
        prices = {
            "TSLA": {"price": 185.20, "change_24h": "+1.8%", "rsi_14": 58.4, "macd": "Neutral-bullish"},
            "NVDA": {"price": 125.40, "change_24h": "+4.2%", "rsi_14": 67.8, "macd": "Strong bullish crossovers"},
            "AAPL": {"price": 215.10, "change_24h": "-0.3%", "rsi_14": 46.5, "macd": "Neutral consolidation"}
        }
        data = prices.get(ticker.upper(), {"price": 150.0, "change_24h": "0.0%", "rsi_14": 50.0, "macd": "Unknown"})
        return json.dumps(data)

    @mcp.tool(name="get_vector_trade_logs", description="Retrieve historical setup outcomes from US Stocks Options vector database logs.")
    def get_vector_trade_logs() -> str:
        logs = [
            {"date": "2026-06-25", "setup": "TSLA Option Bull Put Spread", "ticker": "TSLA", "outcome": "Success (+8.5% premium captured)", "notes": "Entered on support bounce at $180"},
            {"date": "2026-06-28", "setup": "NVDA Call Option Buy", "ticker": "NVDA", "outcome": "Stopped out (-2.1%)", "notes": "Implied volatility crush post-earnings"}
        ]
        return json.dumps(logs)

    @mcp.tool(name="get_options_chain", description="Fetch current US stock options contract strikes, expiries, premiums, and implied volatility (IV) mapping to MooMoo and Tiger Brokers Options trading platforms.")
    def get_options_chain(ticker: str) -> str:
        ticker = ticker.upper()
        # Simulated Options chain
        chain = {
            "TSLA": [
                {"contract": "TSLA-20260710-185-C", "type": "Call", "strike": 185, "expiry": "2026-07-10", "premium": 4.50, "iv": "42.5%", "bid": 4.40, "ask": 4.60},
                {"contract": "TSLA-20260710-180-P", "type": "Put", "strike": 180, "expiry": "2026-07-10", "premium": 3.10, "iv": "45.2%", "bid": 3.00, "ask": 3.20}
            ],
            "NVDA": [
                {"contract": "NVDA-20260710-130-C", "type": "Call", "strike": 130, "expiry": "2026-07-10", "premium": 3.20, "iv": "52.4%", "bid": 3.10, "ask": 3.30},
                {"contract": "NVDA-20260710-120-P", "type": "Put", "strike": 120, "expiry": "2026-07-10", "premium": 2.80, "iv": "55.8%", "bid": 2.70, "ask": 2.90}
            ]
        }
        data = chain.get(ticker, [{"contract": f"{ticker}-NOMINAL-C", "type": "Call", "strike": 100, "expiry": "2026-07-10", "premium": 1.50, "iv": "30%", "bid": 1.40, "ask": 1.60}])
        return json.dumps(data)

    @mcp.tool(name="get_moomoo_tiger_indicators", description="Pulls live technical indicators, options volume analysis, and broker AI sentiment indices for active tickers across Tiger Brokers and MooMoo platforms.")
    def get_moomoo_tiger_indicators(ticker: str) -> str:
        ticker = ticker.upper()
        indicators = {
            "moomoo_options_sentiment": "Bullish call-to-put ratio (1.85)",
            "tiger_brokers_ai_signal": "Strong Buy - Options Implied Move: +/- 4.2%",
            "implied_volatility_percentile": "68%",
            "institutional_options_flow_24h": "+$22M net call purchasing"
        }
        return json.dumps(indicators)

if __name__ == "__main__":
    mcp.run(transport="stdio")
