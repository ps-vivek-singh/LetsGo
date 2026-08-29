# Commute Commander — Architecture & Execution Workflows

> **Document Summary**: In-depth architectural execution pipelines, ReAct loop state transitions, FastMCP tool discovery diagrams, multi-factor reflection workflows, and SSE streaming mechanisms.

---

## 1. End-to-End System Flowchart

```mermaid
graph TD
    Client[Web Dashboard / CLI / REST Client] -->|1. Submit Query| WebApp[HTTP Server: scripts/webapp.py]
    WebApp -->|2. Dispatch| Orchestrator[OrchestratorAgent]
    Orchestrator -->|3. Initialize ReAct| Loop[AgenticLoop: src/agents/agentic_loop.py]
    
    subgraph "Step 1: Perception"
        Loop --> Parser[QueryParser: src/nlp/query_parser.py]
        Parser --> Intent["Extracted Intent (Location, Sections, Ingredients, Meal Type, Days, Budget)"]
    end

    subgraph "Step 2: Tool Discovery"
        Loop --> Discovery[MCPAgent.connect & RealMCPServer]
        Discovery --> ToolList["Discovered FastMCP Tools (@mcp.tool)"]
    end

    subgraph "Step 3-5: Execution & Observation"
        Loop --> Action[Execute Section Tools]
        Action --> W_MCP["weather_tools.py (@mcp.tool get_weather)"]
        Action --> C_MCP["commute_tools.py (@mcp.tool get_commute_route)"]
        Action --> M_MCP["recipe_tools.py (@mcp.tool get_meal_recipe)"]
        Action --> N_MCP["news_tools.py (@mcp.tool get_headlines)"]
        Action --> I_MCP["itinerary_tools.py (@mcp.tool get_itinerary)"]
    end

    subgraph "Step 6: Reflection & Consistency"
        Loop --> Engine[ReflectionEngine: src/agents/reflection.py]
        Engine --> Rules{"Audit 5 Multi-Factor Consistency Rules"}
        Rules --> ReflResult["Reflection Result (Changes Made + Confirmations)"]
    end

    subgraph "Step 7: Response Synthesis"
        Loop --> Synth[ResponseSynthesizer: src/agents/response_synthesizer.py]
        Synth --> ExecutiveSummary["Natural-Language Summary (Emoji Icons & Tips)"]
    end

    subgraph "State Persistence"
        Orchestrator --> SQLite[(SQLite DB: sessions.db WAL Mode)]
    end

    Loop --> Envelope["Structured Response + SSE Stream"]
    Envelope --> Client
```

---

## 2. ReAct Agentic Loop Sequence

The `AgenticLoop` coordinates tool invocations dynamically through 7 distinct phases:

```mermaid
sequenceDiagram
    autonumber
    participant UI as Client / Web Dashboard
    participant Orch as OrchestratorAgent
    participant Loop as AgenticLoop
    participant Parser as QueryParser
    participant MCP as RealMCPServer / FastMCP
    participant Refl as ReflectionEngine
    participant Synth as ResponseSynthesizer
    participant DB as SQLiteSessionManager

    UI->>Orch: POST /api/briefing {query, user_id}
    Orch->>DB: start_session(user_id) -> session_id
    Orch->>Loop: run(query, session_id)
    
    Note over Loop,Parser: Phase 1: Perceive
    Loop->>Parser: parse(query)
    Parser-->>Loop: Intent {location, destination, sections, ingredients, meal_type, ...}
    
    Note over Loop,MCP: Phase 2: Tool Discovery
    Loop->>MCP: list_tools() across all servers
    MCP-->>Loop: {weather: [get_weather], recipe: [get_meal_recipe], ...}
    
    Note over Loop,MCP: Phase 3-5: Plan, Act & Observe
    loop For each section in intent.sections
        Loop->>Loop: Generate ReAct Thought
        Loop->>MCP: Invoke tool with structured parameters
        MCP-->>Loop: Raw observation payload
        Loop->>Loop: Shape domain card data & record duration_ms
    end
    
    Note over Loop,Refl: Phase 6: Cross-Domain Reflection
    Loop->>Refl: reflect(sections, intent)
    Refl->>Refl: Apply 5 consistency rules (Heat, Cold, UV, Commute vs Prep, Weather vs Meal)
    Refl-->>Loop: ReflectionResult {changes_made, confirmations}
    
    Note over Loop,Synth: Phase 7: Synthesis
    Loop->>Synth: synthesize_response(sections, intent, reflection)
    Synth-->>Loop: Concise, natural language executive briefing
    
    Loop->>DB: save_briefing(session_id, sections) & log_interaction()
    Loop-->>Orch: Complete AgenticResult
    Orch-->>UI: Full JSON Response Envelope
```

---

## 3. Dynamic Meals Workflow (Breakfast, Lunch, Dinner, Snack)

```mermaid
graph TD
    Query["User Query: 'Quick lunch with chicken and spinach under 15 min'"] --> Parse["QueryParser: meal_type='lunch', ingredients=['chicken', 'spinach'], time='15 min'"]
    Parse --> Dispatch["MealAgent / Orchestrator"]
    Dispatch --> ToolCall["FastMCP Tool: get_meal_recipe()"]
    
    subgraph "Creative LLM Generation Pipeline"
        ToolCall --> LLM["LLMClient (NVIDIA NIM / Groq / OpenAI)"]
        LLM --> Prompt["Prompt: Feature chicken & spinach prominently. Add minimal pantry essentials only. Provide chef_tip & nutrition_highlights."]
        LLM --> Temp["Temperature ~0.75 (Ensures variety on identical ingredients)"]
        Temp --> Output["JSON Recipe: Name, Steps, Times, Staples, Highlights, Tip"]
    end
    
    subgraph "Fallback Resilience"
        ToolCall -.->|If Offline / No Key| Fallback["Generative Chef Engine (10+ Cuisines & Pantry Isolator)"]
    end

    Output --> SectionShape["Shape 'breakfast' / 'meal' Section Data"]
    Fallback --> SectionShape
    SectionShape --> ReflectionPass["ReflectionEngine: Check Meal Prep Time vs Commute ETA & Weather Temp"]
    ReflectionPass --> CardRender["Render Dynamic UI Card (🥗 Icon, Badges, Modal)"]
```

---

## 4. Multi-Day Travel Itinerary & FastMCP Email Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Traveler as Traveler
    participant UI as Web Dashboard
    participant API as scripts/webapp.py
    participant Agent as ItineraryAgent
    participant Tool as itinerary_tools.py (FastMCP)
    participant Gmail as email_tools.py (FastMCP)
    participant SMTP as Google SMTP (smtp.gmail.com:587)

    Traveler->>UI: Enter destination: "Tokyo", Days: 3, Budget: "Moderate"
    UI->>API: POST /api/itinerary
    API->>Agent: run_structured("Tokyo", days=3, budget="moderate")
    Agent->>Tool: get_itinerary("Tokyo", 3, "moderate", interests)
    Tool-->>Agent: Day-by-day morning, afternoon, evening schedule + dining
    Agent-->>API: Structured Itinerary JSON
    API-->>UI: Render Itinerary Card & Day Tabs
    
    Traveler->>UI: Click "✉️ Send via Gmail MCP Tool"
    UI->>UI: Pre-populate RECIPIENT_EMAIL from settings / .env
    Traveler->>UI: Confirm & Click "Send Email"
    UI->>API: POST /api/share/email {to_email, subject, body_html}
    API->>Gmail: send_itinerary_email(to_email, location, summary)
    Gmail->>SMTP: Connect TLS 587 -> Authenticate GMAIL_APP_PASSWORD -> Send MIME HTML
    SMTP-->>Gmail: 250 OK Message Accepted
    Gmail-->>API: {status: "sent", delivered: true, message_id: "..."}
    API-->>UI: {success: true}
    UI->>Traveler: Toast: "Email sent via Gmail FastMCP Tool! ✉️"
```

---

## 5. Fault Tolerance & Multi-Layer Fallback Architecture

| Failure Scenario | Immediate Fallback Mechanism | Impact on User Experience |
|---|---|---|
| **No LLM API Key or LLM Service Downtime** | FastMCP recipe & itinerary tools activate the deterministic Generative Chef Engine and Curated City Itinerary Engine. | Zero downtime; structured recipe and day-by-day itineraries are generated instantly. |
| **TomTom API Rate-Limit or Key Missing** | OpenRouteService API is queried; if unavailable, the Advisory Commute Engine calculates distance-based synthetic ETAs. | Route recommendations, ETAs, and alternate comparisons remain 100% available. |
| **NewsAPI Endpoint Failure** | Multi-feed RSS parser executes fallback chain across BBC, NDTV, and NYT feeds. | Live headlines with publisher attribution and clickable URLs are delivered seamlessly. |
| **Gmail Credentials Missing in `.env`** | Gmail FastMCP tool returns simulated delivery status with detailed confirmation. | System does not crash; UI informs user that credentials need to be set in `.env`. |
| **Individual Agent Timeout** | 45-second per-agent timeout isolates failure to that section's card error envelope. | Other cards render normally; overall briefing succeeds. |

---

## 6. Observability & Telemetry Tracing Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User as User Request
    participant WebApp as scripts/webapp.py
    participant Loop as AgenticLoop
    participant Telemetry as TelemetryEngine (telemetry.py)
    participant Console as Color Console Output
    participant Files as data/telemetry/ (app.log & traces.jsonl)
    participant Metrics as Rolling Metrics Store

    User->>WebApp: POST /api/briefing (query)
    WebApp->>Telemetry: trace_span("http_request", {query})
    WebApp->>Console: [INFO] [HTTP] --> POST /api/briefing (query)
    
    WebApp->>Loop: run(query)
    Loop->>Telemetry: trace_span("agentic_loop", {session_id})
    
    Loop->>Telemetry: trace_span("perceive_intent")
    Loop->>Console: [INFO] [AGENT] [tid:xxx] PERCEIVE: parsing query
    
    loop Per Tool Execution
        Loop->>Telemetry: trace_span("tool_<server>.<tool_name>")
        Loop->>Console: [INFO] [TOOL] [tid:xxx] Invoke <server>.<tool> -> OK (latency_ms)
        Telemetry->>Metrics: record_tool_call(server, tool, latency_ms, status)
    end

    Loop->>Telemetry: trace_span("reflection_audit")
    Loop->>Console: [INFO] [REFLECTION] [tid:xxx] Reflection confirmed all answers
    
    Loop->>Telemetry: trace_span("synthesize_summary")
    Loop->>Console: [INFO] [LLM] nim/meta/llama-3.1-8b-instruct (latency_ms, tokens)
    Telemetry->>Metrics: record_llm_call(model, latency_ms, tokens)

    Loop-->>WebApp: AgenticResult
    WebApp->>Console: [INFO] [HTTP] <-- 200 OK (duration_ms, status=OK)
    Telemetry->>Files: Append structured trace record to traces.jsonl & app.log
```

---

## 7. 7-Layer Evaluation & Benchmarking Execution Pipeline

```mermaid
graph TD
    Runner[CLI Runner: python -m evals.runner --category all / Pytest] --> L1 & L2 & L3 & L4 & L5 & L6 & L7

    subgraph "Layer 1: NLP Intent & Routing"
        L1[eval_intent.py] --> D1[(routing_golden.json - 20 cases)]
        D1 --> E1["Evaluates exact intent matches, F1 scores, & slot precision"]
    end

    subgraph "Layer 2: ReAct Trajectory"
        L2[eval_trajectory.py] --> D2[(trajectory_golden.json - 6 cases)]
        D2 --> E2["Validates tool call sequence, arguments, & step efficiency"]
    end

    subgraph "Layer 3: Reflection Consistency"
        L3[eval_reflection.py] --> D3[(reflection_matrix.json - 7 cases)]
        D3 --> E3["Audits 5 cross-domain consistency & safety rules"]
    end

    subgraph "Layer 4: LLM Judge"
        L4[eval_llm_judge.py] --> D4[(synthesis_golden.json - 3 cases)]
        D4 --> E4["LLM-as-a-judge scores factual faithfulness & completeness"]
    end

    subgraph "Layer 5: Adversarial & OOD"
        L5[eval_adversarial.py] --> D5[(adversarial_edge_cases.json - 12 cases)]
        D5 --> E5["Tests colloquial slang, multi-constraints, & triple conflicts"]
    end

    subgraph "Layer 6: Negative Constraints"
        L6[eval_negative.py] --> D6[(negative_golden.json - 10 cases)]
        D6 --> E6["Validates explicit exclusions, past meal negations, & out-of-scope guards"]
    end

    subgraph "Layer 7: Multi-Tool Orchestration"
        L7[eval_multitool.py] --> D7[(multitool_orchestration_golden.json - 5 cases)]
        D7 --> E7["Tests complex 3-tool and 4-tool multi-agent pipelines"]
    end

    E1 & E2 & E3 & E4 & E5 & E6 & E7 --> Scorecard["Scorecard Summary & JSON Report (evals/results/report_*.json)"]
```

