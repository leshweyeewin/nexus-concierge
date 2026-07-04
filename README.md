# NexusConcierge — Cross-Domain Multi-Agent Life Engine

NexusConcierge is a conditional **Workflow DAG Graph** built on the Google Agent Development Kit (`google-adk`). It coordinates three daily workflows into one session state: 
- Singapore developer networking events
- TikTok affiliate marketing hook generation, and
- Options-trading risk enforcement.

---

## 🏗️ System Architecture

Rather than a single monolithic agent with too many tool options, NexusConcierge uses a structured Orchestrator-Specialist pattern. The orchestrator delegates sequentially and loops back until all tasks are completed.

```
       User Request / Streamlit Input
                     │
                     ▼
             NexusOrchestrator (gemini-3.1-flash-lite)
              ▲      ▲      ▲
              │      │      │
      ┌───────┴┐     │     ┌┴───────┐
      │  dev   │     │     │ tiktok │
      ▼        ▼     │     ▼        ▼
 DevRelops Agent     │  CreativeAffiliate Agent
 (Events MCP)        │  (TikTok MCP)
                     │
               ┌─────┴─────┐
               │  trading  │
               ▼           ▼
             QuantitativeRisk Agent
             (Market MCP)
                     │
                     ▼
            Collector Node (Terminal)
                     │
                     ▼
             Response Stream
```

---

## 🛠️ Features

* **Multi-Agent Orchestration**: Powered by conditional DAG graphs. Each specialist agent is isolated to its own MCP server (FastMCP over stdio).
* **Multi-Source Event Scraping**: Scrapes Singapore Developer Space Telegram previews (extracting real message links), Meetup Singapore, and cascades automatically to check local Gmail emails (`gmail_inbox.json`) if Meetup is offline.
* **Real Stock & Option Metrics (`yfinance`)**: Retrieves live prices, RSI indicators, options strike grids, and calculates a Put/Call volume ratio index as a sentiment proxy.
* **Security & Risk Guardrails**:
  - *Credential Masking*: Automatically strips keys/tokens from tool outputs, replacing them with `[MASKED_CREDENTIAL]`.
  - *Risk Enforcement*: Zero financial autonomy controls; blocks setups exceeding a 2% max-loss threshold.
* **Streamlit Dashboard**: Dark-themed portal featuring real-time stream rendering, live SQLite State Memory Inspector sidebar, Graphviz routing chart, and MCP status board.

---

## 🚀 Quick Start

### 1. Set Environment Keys
Ensure your API keys are defined in your environment:
```powershell
$env:GEMINI_API_KEY="your_api_key"
$env:GOOGLE_API_KEY="your_api_key" # Optional fallback
```

### 2. Install Dependencies
Initialize your virtual environment and install the required modules:
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install google-genai google-adk yfinance streamlit mcp fastmcp aiosqlite graphviz
```

### 3. Run the CLI Pipeline
Verify the E2E multi-agent engine:
```powershell
python main.py
```

### 4. Run the Streamlit Dashboard
Launch the observability portal in your browser:
```powershell
streamlit run app.py
```

---

## 📂 Project Structure

* `main.py`: Central engine compiling the ADK routing graph, database sessions, and executing CLI streaming.
* `app.py`: Streamlit web dashboard, Graphviz visualizer, and SQLite context inspector.
* `mcp_servers.py`: Multi-server hosting the Events, Market, and TikTok MCP tool sets.
* `adk_config.yml`: Single source of truth configuration rules for agent instructions and model definitions.
* `nexus_sessions.db`: SQLite database storing active session states.
