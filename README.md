# Commute Commander

> **Enterprise-Grade Multi-Agent AI System for Daily Routine Optimization, Multi-Modal Commute Intelligence, Dynamic Meal Planning & Personalized Travel Itineraries**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/Architecture-ReAct%20Multi--Agent%20%2B%20FastMCP-purple.svg)](docs/ARCHITECTURE_WORKFLOW.md)
[![Tests](https://img.shields.io/badge/Tests-69%20Passed%20%28100%25%29-brightgreen.svg)](tests/)
[![Evals](https://img.shields.io/badge/Evals-7%20Layers%20Passed-blueviolet.svg)](evals/)
[![Protocol](https://img.shields.io/badge/MCP-FastMCP%20Standard-orange.svg)](src/mcp_tools/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 1. Executive Summary

**Commute Commander** is a modular, autonomous multi-agent application that orchestrates specialist AI agents to provide comprehensive, context-aware daily briefings and personalized travel itineraries. Combining a zero-dependency **NLP Query Parser**, an explicit **ReAct (Reason + Act) Control Loop**, standard **Model Context Protocol (FastMCP)** tool servers, a multi-factor **Cross-Domain Reflection Engine**, and a conversational **Response Synthesizer**, the application generates actionable, highly tailored daily intelligence.

The application functions across three distinct operating environments:
1. **Interactive Command-Line Interface (CLI)**: High-speed terminal interaction for automated scripts and headless environments.
2. **Lightweight Web Application**: A responsive, zero-framework browser dashboard featuring real-time Server-Sent Events (SSE) streaming and interactive Leaflet map polyline routing.
3. **Standalone FastMCP Tool Servers**: Standalone MCP servers that can interface directly with external MCP clients (e.g., Claude Desktop, Cursor, IDEs) over stdio or SSE.

---

## 2. Core Architectural Pillars

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 COMMUTE COMMANDER                                │
├─────────────────────────┬───────────────────────────────┬────────────────────────┤
│   1. NLP INTENT ENGINE  │     2. MULTI-AGENT SYSTEM     │   3. FASTMCP TOOL MESH │
│  • Regex + Pattern Match│  • ReAct Agentic Loop (7-Step)│  • FastMCP Tool Servers│
│  • Zero-ML Instant Start│  • Multi-Factor Reflection    │  • LLM Engine (NVIDIA) │
│  • Multi-Entity Extract │  • NL Response Synthesizer    │  • Gmail SMTP Dispatch │
├─────────────────────────┼───────────────────────────────┼────────────────────────┤
│   4. REAL-TIME STREAM   │     5. PERSISTENCE & STATE    │   6. DUAL INTERFACES   │
│  • Server-Sent Events   │  • SQLite DB (WAL Mode)       │  • Responsive Web Dash │
│  • Thread-Parallel Exec │  • Transactional History      │  • Interactive CLI Tool│
│  • Progressive Rendering│  • Settings Storage Engine    │  • Leaflet Route Maps  │
└─────────────────────────┴───────────────────────────────┴────────────────────────┘
```

---

## 3. Specialist Domain Agents

Commute Commander distributes tasks across five specialist autonomous agents, each maintaining an independent domain contract:

| Agent | Module | Description | Primary Data Sources / Tools |
|---|---|---|---|
| **WeatherAgent** | `src/agents/weather_agent.py` | Fetches real-time temperature, condition labels, UV index peaks, high/low summaries, and 12-hour hourly trends. | Open-Meteo API, OpenWeatherMap, `weather_tools.py` |
| **CommuteAgent** | `src/agents/commute_agent.py` | Resolves geocoded coordinates for origins and destinations, calculates multi-modal ETAs (Drive, Transit, Bike, Walk), identifies traffic delays, and generates Leaflet map polylines. | TomTom Search & Routing APIs, OpenRouteService, `commute_tools.py` |
| **MealAgent** | `src/agents/breakfast_agent.py` | Dynamically generates non-repeating, chef-crafted recipes for **Breakfast, Lunch, Dinner, and Snacks**. Strictly features user ingredients, minimizes extra pantry staples, provides cook/prep times, nutrition highlights, and step-by-step directions. | NVIDIA NIM LLM, FastMCP `recipe_tools.py`, Generative Chef Engine |
| **NewsAgent** | `src/agents/news_agent.py` | Aggregates verified top headlines with publisher attribution, publication timestamps, and direct clickable article URLs. | NewsAPI, Multi-Feed RSS (BBC, NDTV, NYT), `news_tools.py` |
| **ItineraryAgent** | `src/agents/itinerary_agent.py` | Creates multi-day travel plans with morning, afternoon, evening activities, locations, dining recommendations, and budget options. | NVIDIA NIM LLM, FastMCP `itinerary_tools.py`, Curated Destination Engine |

---

## 4. MCP Tools & Server Architecture

All tool integrations adhere strictly to the **Model Context Protocol (FastMCP)** standard:

```
src/mcp_tools/
├── weather_tools.py    → FastMCP("weather-server")  :: @mcp.tool get_weather
├── commute_tools.py    → FastMCP("commute-server")  :: @mcp.tool get_commute_route, get_commute_advice
├── recipe_tools.py     → FastMCP("recipe-server")   :: @mcp.tool get_meal_recipe, get_recipe
├── news_tools.py       → FastMCP("news-server")     :: @mcp.tool get_headlines
├── itinerary_tools.py  → FastMCP("itinerary-server"):: @mcp.tool get_itinerary
├── email_tools.py      → FastMCP("gmail-server")    :: @mcp.tool send_email_briefing, send_itinerary_email
└── real_mcp_server.py  → In-process FastMCP protocol wrapper for dynamic listing & execution
```

### In-Process vs. Standalone Execution
- **In-Process Agent Dispatch**: `RealMCPServer` wraps FastMCP instances directly in Python memory, enabling zero-network-overhead tool discovery (`list_tools()`), health validation (`health_check()`), and argument invocation (`call_tool()`).
- **Standalone Server Deployment**: Any tool file can be run directly (e.g., `python src/mcp_tools/email_tools.py`) to launch an independent MCP server for external client integration over standard I/O or SSE.

---

## 5. ReAct Agentic Loop & Reflection Engine

Every briefing query submitted to the system is executed through a 7-stage **ReAct Control Loop**:

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Browser
    participant Orchestrator as OrchestratorAgent
    participant Loop as AgenticLoop
    participant MCP as FastMCP Tool Servers
    participant Reflection as ReflectionEngine
    participant Synthesizer as ResponseSynthesizer
    participant DB as SQLite DB (WAL)

    User->>Orchestrator: Submit Query ("Quick lunch with chicken under 15 min")
    Orchestrator->>Loop: run(query, session_id)
    Loop->>Loop: 1. PERCEIVE (QueryParser extracts entities & meal_type)
    Loop->>MCP: 2. DISCOVER (List tools on all FastMCP servers)
    Loop->>Loop: 3. PLAN (Route requested sections into execution queue)
    
    loop ACT -> OBSERVE (per section)
        Loop->>MCP: 4. ACT (Invoke tool with structured parameters)
        MCP-->>Loop: 5. OBSERVE (Capture output & shape card data)
    end

    Loop->>Reflection: 6. REFLECT (Cross-check multi-domain rules)
    Reflection-->>Loop: ReflectionResult (changes_made, confirmations)
    Loop->>Synthesizer: 7. SYNTHESIZE (Compose natural-language briefing)
    Synthesizer-->>Loop: Friendly Executive Summary
    Loop->>DB: Persist intent, trace & section results
    Loop-->>Orchestrator: AgenticResult
    Orchestrator-->>User: Structured JSON + SSE Stream
```

### Multi-Factor Reflection Rules
1. **Heat vs. Commute Mode**: `temp ≥ 35°C` with `bike`/`walk` commute → Auto-switches recommendation to `drive` and injects heat advisory.
2. **Freezing Weather Alert**: `temp ≤ 2°C` with `walk`/`bike` → Injects winter road/walkway safety warnings.
3. **High UV Protection**: `uv_index ≥ 8` with outdoor commute → Injects sun protection recommendation.
4. **Commute Duration vs. Meal Prep**: `commute_eta ≥ 45 min` and `meal_prep ≥ 15 min` → Advises a 10-minute quick meal to preserve morning schedule.
5. **Weather & Meal Pairing**:
   - `temp ≥ 30°C` and hot meal requested → Recommends chilled, light, hydrating meal.
   - `temp ≤ 5°C` and cold salad requested → Recommends warm comfort dish (skillet, soup, warm bowl).

---

## 6. Repository Layout

```
L2-Project/
├── src/
│   ├── agents/                  # Autonomous specialist agents
│   │   ├── agentic_loop.py      # ReAct state machine & trace executor
│   │   ├── breakfast_agent.py   # MealAgent (Breakfast, Lunch, Dinner, Snack)
│   │   ├── commute_agent.py     # CommuteAgent (Multi-modal routing & alerts)
│   │   ├── itinerary_agent.py   # ItineraryAgent (Multi-day travel planner)
│   │   ├── news_agent.py        # NewsAgent (Headlines & RSS parser)
│   │   ├── weather_agent.py     # WeatherAgent (Hourly & UV forecast)
│   │   ├── orchestrator.py      # Agent coordinator & session dispatcher
│   │   ├── mcp_agent.py         # MCP protocol client
│   │   ├── reflection.py        # Cross-domain consistency engine
│   │   ├── response_synthesizer.py # Natural language summary composer
│   │   ├── router.py            # Intent routing table
│   │   └── tool_discovery_agent.py # Discovers active tool servers
│   ├── mcp_tools/               # FastMCP tool server modules
│   │   ├── commute_tools.py     # TomTom / OpenRouteService routing tools
│   │   ├── email_tools.py       # Gmail FastMCP server (SMTP dispatch)
│   │   ├── itinerary_tools.py   # Multi-day travel itinerary generation
│   │   ├── news_tools.py        # NewsAPI & multi-feed RSS tools
│   │   ├── recipe_tools.py      # LLM dynamic recipe generation tools
│   │   ├── weather_tools.py     # Open-Meteo & OpenWeatherMap tools
│   │   └── real_mcp_server.py   # FastMCP in-process wrapper
│   ├── nlp/
│   │   └── query_parser.py      # Regex & token pattern entity extractor
│   └── services/
│       ├── config.py            # Dynamic environment & secret manager
│       ├── db.py                # SQLite database interface (WAL mode)
│       ├── llm_client.py        # Multi-provider LLM API interface (NVIDIA NIM / Groq / OpenAI)
│       ├── session_manager.py   # Session & interaction persistence
│       ├── settings_manager.py  # User settings & preferences manager
│       └── telemetry.py         # Dual-mode logger, trace spans & rolling metrics
├── evals/                       # 7-Layer Comprehensive Evaluation Suite
│   ├── datasets/                # Golden benchmark datasets (JSON)
│   │   ├── routing_golden.json  # Layer 1: NLP intent & slot benchmarks (20 cases)
│   │   ├── trajectory_golden.json # Layer 2: ReAct tool selection trajectories (6 cases)
│   │   ├── reflection_matrix.json # Layer 3: Consistency rule matrices (7 cases)
│   │   ├── synthesis_golden.json  # Layer 4: Quality & faithfulness test set (3 cases)
│   │   ├── adversarial_edge_cases.json # Layer 5: Colloquial & OOD cases (12 cases)
│   │   ├── negative_golden.json # Layer 6: Exclusions & temporal negations (10 cases)
│   │   └── multitool_orchestration_golden.json # Layer 7: Complex 3/4-tool combos (5 cases)
│   ├── evaluators/              # Automated evaluators for all 7 layers
│   │   ├── eval_intent.py       # Layer 1: Intent & slot extraction evaluator
│   │   ├── eval_trajectory.py   # Layer 2: ReAct tool sequence & efficiency evaluator
│   │   ├── eval_reflection.py   # Layer 3: Consistency rule auditor
│   │   ├── eval_llm_judge.py    # Layer 4: LLM-as-a-judge quality evaluator
│   │   ├── eval_adversarial.py  # Layer 5: Adversarial & OOD evaluator
│   │   ├── eval_negative.py     # Layer 6: Negative constraints & exclusion evaluator
│   │   └── eval_multitool.py    # Layer 7: Complex multi-tool pipeline evaluator
│   ├── runner.py                # Unified CLI evaluation runner & scorecard generator
│   └── results/                 # Timestamped evaluation reports (JSON)
├── frontend/                    # Static Web Application
│   ├── index.html               # Semantic HTML5 dashboard layout
│   ├── styles.css               # Token-based glassmorphism styling
│   └── app.js                   # Reactive UI controllers & SSE streaming
├── scripts/                     # Executable Entrypoints
│   ├── webapp.py                # Native Python HTTP server (Port 8000)
│   ├── main.py                  # Terminal interactive CLI application
│   └── run_demo.py              # Automated CLI demonstration runner
├── tests/                       # 69 Automated Unit, Integration & Eval Regression Tests
│   ├── test_agentic_loop.py     # ReAct loop, discovery, and trace tests
│   ├── test_email_tools.py      # FastMCP email dispatch tests
│   ├── test_evals_regression.py # Automated CI regression suite for all 7 eval layers
│   ├── test_itinerary.py        # Itinerary generation & routing tests
│   ├── test_llm_client.py       # LLM client & provider tests
│   ├── test_meal_agent.py       # Dynamic meals, pantry, and meal_type tests
│   ├── test_phase6_7.py         # SQLite & SettingsManager tests
│   ├── test_query_parser.py     # NLP entity & intent extraction tests
│   ├── test_reflection.py       # Multi-factor reflection rule tests
│   └── test_session_logging.py  # SQLite session logging tests
├── data/                        # Persistent SQLite database & telemetry logs
│   ├── sessions.db              # Thread-safe SQLite WAL database
│   └── telemetry/               # app.log & structured traces.jsonl
├── config/
│   └── settings.json            # Application configuration & defaults
├── docs/                        # Comprehensive Architecture & API Documentation
│   ├── PROJECT_DOCUMENTATION.md # Comprehensive engineering & phase document
│   ├── ARCHITECTURE_WORKFLOW.md # Pipeline workflows & sequence diagrams
│   ├── ARCHITECTURE_QA.md       # Architecture & engineering Q&A
│   ├── api-contract.md          # REST API & SSE contract specification
│   └── ui-spec.md               # Visual design & UI component specification
├── .env.example                 # Environment configuration template
├── conftest.py                  # Pytest configuration & import paths
└── requirements.txt             # Python package dependencies
```

---

## 7. Installation & Setup

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.14+
- `pip` package manager

### 2. Clone and Install Dependencies
```bash
git clone <repository-url>
cd L2-Project
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to create your local `.env` file:
```bash
cp .env.example .env
```

Edit `.env` to configure your API keys and services:

```env
# ── LLM Engine (NVIDIA NIM / Groq / OpenRouter / OpenAI) ──────────
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=meta/llama-3.1-8b-instruct

# ── External APIs (Optional - Free fallbacks active by default) ───
OPENWEATHER_API_KEY=your_openweather_key
NEWSAPI_API_KEY=your_newsapi_key
TOMTOM_API_KEY=your_tomtom_key
OPENROUTESERVICE_API_KEY=your_openrouteservice_key

# ── Gmail FastMCP Server (For sending/receiving emails) ────────────
GMAIL_USER=your_sender_email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
RECIPIENT_EMAIL=default_recipient@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

> **Note**: Free, zero-configuration public fallbacks (Open-Meteo, RSS feeds, deterministic chef engine, advisory routing) are automatically active if API keys are omitted.

---

## 8. Usage & Execution

### Running the Web Dashboard
```bash
python scripts/webapp.py
```
Open [http://localhost:8000](http://localhost:8000) in your web browser.

### Running the CLI Interface
```bash
python scripts/main.py
```

### Running the Automated Demo
```bash
python scripts/run_demo.py
```

### Running the Automated Test & Eval Suite
```bash
# Run complete test suite (Unit + Integration + 7-Layer Evals Regression)
pytest -v

# Run only the 7-Layer Evals CI Regression Suite
pytest tests/test_evals_regression.py -v
```
Executes all **69 automated tests** with 100% pass rate.

### Running the 7-Layer Evaluation Runner CLI
```bash
# Run all 7 benchmark layers and generate a scorecard
python -m evals.runner

# Run specific evaluation layers
python -m evals.runner --category negative
python -m evals.runner --category multitool
python -m evals.runner --category adversarial
python -m evals.runner --category intent
python -m evals.runner --category trajectory
python -m evals.runner --category reflection
python -m evals.runner --category judge
```

---

## 9. Observability & Telemetry

The application embeds zero-overhead, production-grade observability via `src/services/telemetry.py`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY & TELEMETRY ENGINE                      │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│    DUAL-MODE LOGGING    │    WATERFALL SPANS      │   REAL-TIME METRICS API │
│  • ANSI Console Colors  │  • ReAct Step Profiling │  • GET /api/observability│
│  • data/telemetry/app.log│  • Tool Latency Timing  │    /metrics             │
│  • traces.jsonl Records │  • Token Usage & Costs  │  • GET /traces          │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

- **Dual-Mode Logger**: Real-time ANSI colored terminal output for developers (`[AGENT]`, `[TOOL]`, `[LLM]`, `[REFLECTION]`) and persistent structured files (`data/telemetry/app.log`, `data/telemetry/traces.jsonl`).
- **OpenTelemetry-Compatible Spans**: `trace_span()` context manager tracks durations, argument payloads, status codes, and errors across every perception, tool invocation, and LLM call.
- **REST Telemetry APIs**:
  - `GET /api/observability/metrics` — Latency percentiles (P50, P95), tool counts per server, token consumption, error rates.
  - `GET /api/observability/traces` — Chronological execution traces.
  - `GET /api/observability/traces/<trace_id>` — Deep waterfall span timeline.

---

## 10. 7-Layer Comprehensive Evaluation Suite

Commute Commander incorporates an evaluation suite (`evals/`) testing agent intelligence across 7 layers:

```
────────────────────────────────────────────────────────────────────────
 EVALUATION CATEGORY          | TESTS  | SCORE / METRIC     | STATUS    
────────────────────────────────────────────────────────────────────────
 1. Intent & Routing          | 20     | Acc: 100.0% (F1:1.00) | [ PASSED ]
 2. Agent Trajectory          | 6      | Tool: 100.0% (Eff:100%) | [ PASSED ]
 3. Reflection Rules          | 7      | Pass: 100.0% (7/7) | [ PASSED ]
 4. Output Quality Judge      | 3      | Faithful: 4.3/5.0  | [ PASSED ]
 5. Adversarial & OOD         | 12     | Acc: 100.0% (NLP:100%) | [ PASSED ]
 6. Negative Constraints      | 10     | Pass: 100.0% (10/10) | [ PASSED ]
 7. Multi-Tool Orch           | 5      | Pass: 100.0% (5/5) | [ PASSED ]
────────────────────────────────────────────────────────────────────────
 Result: ALL EVALS PASSED (Completed in 103.75s)
```

1. **Intent & Routing** (`eval_intent.py`): 20 golden cases testing single & multi-intent routing and slot extraction accuracy.
2. **Agent Trajectory** (`eval_trajectory.py`): Validates ReAct tool selection order and step efficiency bounds ($\le 7$ steps).
3. **Reflection Matrix** (`eval_reflection.py`): Tests 5 cross-domain safety and consistency rules.
4. **LLM Faithfulness Judge** (`eval_llm_judge.py`): Automated LLM-as-a-judge scoring factual faithfulness and completeness.
5. **Adversarial & OOD Cases** (`eval_adversarial.py`): Slang transit, weather metaphors, multi-constraint recipe dumps, and triple-conflict edge cases.
6. **Negative Constraints** (`eval_negative.py`): Explicit exclusions (*"skip news"*, *"no commute"*), past temporal negations (*"already ate breakfast"*), and out-of-scope queries (*"write python code"*, *"translate"*).
7. **Complex Multi-Tool Orchestration** (`eval_multitool.py`): 3-tool and 4-tool multi-agent pipelines with order validation and execution efficiency.

---

## 11. Example Natural-Language Queries

| Goal | Sample Query |
|---|---|
| **Multi-Domain Morning Briefing** | *"I'm leaving from Chicago to Downtown. Give me today's weather, top news, commute advice, and a 10-minute breakfast with eggs."* |
| **Negative Constraints (Excluded Tools)** | *"Give me weather and news for Miami, but do not give me any commute or breakfast recipes."* |
| **Past Temporal Negation** | *"I already ate breakfast. Just check traffic from Evanston to Chicago Loop and top headlines."* |
| **4-Tool Multi-Agent Briefing** | *"Chicago morning briefing: weather in Chicago, traffic from Evanston to Loop, top news headlines, and 10-minute breakfast with eggs."* |
| **Lunch Planning with Ingredients** | *"Quick healthy lunch with chicken and spinach under 15 minutes."* |
| **Dinner Planning with Custom Ingredients** | *"Dinner idea with paneer, tomatoes and garlic in 20 min."* |
| **Multi-Day Travel Itinerary** | *"Plan a 3-day travel itinerary for Tokyo focusing on sightseeing, local food, and cultural heritage."* |
| **Travel Plan & Email Dispatch** | *"Give me a 3-day itinerary for Srinagar and email the summary to traveler@example.com."* |

---

## 12. License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for full details.

