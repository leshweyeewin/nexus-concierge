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
        # Check files in local folder
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
            # Only allow reading inside workspace for security
            abs_path = os.path.abspath(file_path)
            cwd = os.getcwd()
            if not abs_path.startswith(cwd):
                return "Access denied: file path is outside workspace."
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(1000) # first 1000 chars
            return f"File: {file_path}\nContent:\n{content}..."
        except Exception as e:
            return f"Error reading {file_path}: {str(e)}"

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

elif args.server == "market":
    @mcp.tool(name="get_live_price", description="Fetch live price feeds and indicators for active trading pairs.")
    def get_live_price(ticker: str) -> str:
        # Simulated live prices
        prices = {
            "BTC": {"price": 95200.0, "change_24h": "+2.4%", "rsi_14": 62.5, "macd": "Bullish crossovers"},
            "ETH": {"price": 3150.0, "change_24h": "-0.5%", "rsi_14": 49.2, "macd": "Neutral consolidation"},
            "SOL": {"price": 182.5, "change_24h": "+5.1%", "rsi_14": 71.0, "macd": "Oversold warning"}
        }
        data = prices.get(ticker.upper(), {"price": 100.0, "change_24h": "0.0%", "rsi_14": 50.0, "macd": "Unknown"})
        return json.dumps(data)

    @mcp.tool(name="get_vector_trade_logs", description="Retrieve historical setup outcomes from vector database logs.")
    def get_vector_trade_logs() -> str:
        logs = [
            {"date": "2026-06-25", "setup": "RSI Oversold Bounce", "ticker": "BTC", "outcome": "Success (+4.5%)", "notes": "Entered at RSI=28, exited at 55"},
            {"date": "2026-06-28", "setup": "Breakout pullback support", "ticker": "ETH", "outcome": "Stopped out (-1.5%)", "notes": "Fake breakout under key resistance"}
        ]
        return json.dumps(logs)

if __name__ == "__main__":
    mcp.run(transport="stdio")
