# Commute Commander — API Contract Specification

> **Specification Version**: 2.2  
> **Protocol Support**: HTTP/1.1 REST, Server-Sent Events (SSE), FastMCP In-Process Protocol  
> **Data Encoding**: JSON (`application/json`), SSE (`text/event-stream`)

---

## 1. Overview & Base Conventions

All API routes are served relative to `http://localhost:8000`. Responses use standard HTTP status codes.

### Error Envelope Format
When an API error occurs, responses return an error JSON object with an HTTP error code (e.g. 400, 404, 500):
```json
{
  "error": {
    "code": "invalid_request",
    "message": "Detailed description of the validation or operational error."
  }
}
```

---

## 2. Primary Briefing Endpoint

### `POST /api/briefing`
Executes the ReAct Agentic Loop, discovers tools, generates section payloads, performs cross-domain reflection, and returns a synthesized summary.

#### Request Headers:
`Content-Type: application/json`

#### Request Body:
```json
{
  "query": "I'm leaving from Chicago to Downtown. Give me weather, commute, top news, and a 15-minute lunch with chicken and spinach.",
  "user_id": "guest"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | **Yes** | Natural language briefing or itinerary request. |
| `user_id` | `string` | No | Identifier for the user session (defaults to `"guest"`). |

#### Response (200 OK):
```json
{
  "session_id": "guest-20260817234500",
  "intent": {
    "location": "Chicago",
    "destination": "Downtown",
    "sections": ["weather", "commute", "news", "breakfast"],
    "ingredients": ["chicken", "spinach"],
    "meal_type": "lunch",
    "time_constraint": "15 minutes",
    "travel_intent": false,
    "days": 2,
    "budget": "moderate"
  },
  "sections": {
    "weather": {
      "section": "weather",
      "status": "success",
      "data": {
        "city": "Chicago",
        "temp": 24,
        "high": 27,
        "low": 19,
        "condition": "Clear Sky",
        "uv_index": 6.2,
        "uv_label": "High",
        "hourly": [
          {"time": "06:00", "temp": 19, "uv": 0.1},
          {"time": "09:00", "temp": 22, "uv": 2.4},
          {"time": "12:00", "temp": 26, "uv": 6.2},
          {"time": "15:00", "temp": 27, "uv": 4.8},
          {"time": "18:00", "temp": 23, "uv": 0.5}
        ]
      }
    },
    "commute": {
      "section": "commute",
      "status": "success",
      "data": {
        "origin": {"label": "Chicago", "lat": 41.8781, "lon": -87.6298},
        "dest": {"label": "Downtown", "lat": 41.8827, "lon": -87.6233},
        "recommended_mode": "drive",
        "eta_minutes": 14,
        "distance_km": 4.2,
        "source": "TomTom",
        "polyline": [[41.8781, -87.6298], [41.8805, -87.6265], [41.8827, -87.6233]],
        "alternates": [
          {"mode": "transit", "eta_minutes": 18, "distance_km": 4.0},
          {"mode": "bike", "eta_minutes": 16, "distance_km": 3.8},
          {"mode": "walk", "eta_minutes": 45, "distance_km": 3.6}
        ],
        "alerts": []
      }
    },
    "breakfast": {
      "section": "breakfast",
      "status": "success",
      "data": {
        "name": "Spinach & Chicken Mediterranean Skillet",
        "recipe_name": "Spinach & Chicken Mediterranean Skillet",
        "meal_type": "lunch",
        "prep_time_minutes": 7,
        "cook_time_minutes": 8,
        "total_time_minutes": 15,
        "ingredients_used": ["chicken breast", "fresh spinach"],
        "pantry_staples": ["1 tbsp olive oil", "1 clove garlic", "sea salt", "black pepper"],
        "steps": [
          "Dice chicken breast and season with salt, pepper, and garlic.",
          "Heat olive oil in a skillet over medium-high heat and sear chicken for 6 minutes.",
          "Toss in spinach leaves and cook for 2 minutes until wilted.",
          "Serve immediately with a lemon wedge."
        ],
        "nutrition_highlights": "32g Protein · Low Carb · 280 kcal",
        "chef_tip": "Sear the chicken in a hot skillet without overcrowding to lock in moisture.",
        "category": "Quick Lunch",
        "area": "Mediterranean"
      }
    },
    "news": {
      "section": "news",
      "status": "success",
      "data": {
        "headlines": [
          {
            "title": "Global Clean Energy Investments Reach New Milestone in 2026",
            "source": "BBC News",
            "url": "https://bbc.com/news/world-12345",
            "published_at": "2026-08-17T15:00:00Z"
          }
        ]
      }
    }
  },
  "summary": "Good afternoon! In Chicago, it's 24°C and clear with high UV (6.2). Your drive to Downtown will take 14 minutes. For lunch, try Spinach & Chicken Mediterranean Skillet (7-min prep) featuring chicken and spinach. Tip: Sear chicken in a hot skillet to lock in moisture.",
  "briefing": "Good afternoon! In Chicago...",
  "loop_trace": [
    {
      "step": 1,
      "thought": "I need weather data for Chicago. FastMCP server 'weather' exposes ['get_weather'].",
      "action": "weather.get_weather",
      "action_args": {"location": "Chicago"},
      "observation": "Received weather data: 24°C, UV 6.2, condition: Clear Sky.",
      "duration_ms": 320
    },
    {
      "step": 2,
      "thought": "I need commute data between Chicago and Downtown.",
      "action": "commute.get_commute_route",
      "action_args": {"origin": "Chicago", "dest": "Downtown", "mode": "drive"},
      "observation": "Received route: 14 minutes (4.2 km).",
      "duration_ms": 410
    },
    {
      "step": 3,
      "thought": "Generating lunch idea featuring chicken and spinach within 15 minutes.",
      "action": "recipe.get_meal_recipe",
      "action_args": {"ingredients": ["chicken", "spinach"], "time_constraint": "15 min", "meal_type": "lunch"},
      "observation": "Generated recipe: Spinach & Chicken Mediterranean Skillet.",
      "duration_ms": 780
    },
    {
      "step": 4,
      "thought": "Fetching top news headlines.",
      "action": "news.get_headlines",
      "action_args": {},
      "observation": "Received 5 verified headlines.",
      "duration_ms": 250
    },
    {
      "step": 5,
      "thought": "All requested sections gathered. Running cross-section reflection.",
      "action": "reflect",
      "action_args": {},
      "observation": "Reflection confirmed: Commute time and lunch prep are compatible; Lunch choice suits current conditions.",
      "duration_ms": 5
    },
    {
      "step": 6,
      "thought": "Composing natural language synthesis.",
      "action": "synthesize_response",
      "action_args": {},
      "observation": "Generated natural language briefing summary.",
      "duration_ms": 10
    }
  ],
  "reflection": {
    "changes_made": [],
    "confirmations": [
      "Commute time and lunch prep are compatible",
      "Lunch choice suits the weather",
      "All sections reviewed — no adjustments needed"
    ]
  },
  "tools_discovered": {
    "weather": ["get_weather"],
    "commute": ["get_commute_route", "get_commute_advice"],
    "recipe": ["get_meal_recipe", "get_recipe"],
    "news": ["get_headlines"],
    "itinerary": ["get_itinerary"],
    "gmail": ["send_email_briefing", "send_itinerary_email"]
  }
}
```

---

## 3. Server-Sent Events (SSE) Streaming

### `GET /api/briefing/{session_id}/stream`

Establishes a persistent SSE stream (`text/event-stream`). As each agent completes execution in its background thread, a JSON event is immediately emitted.

#### Event Stream Format:
```
data: {"section":"weather","status":"success","data":{"city":"Chicago","temp":24,...}}

data: {"section":"commute","status":"success","data":{"origin":{...},"eta_minutes":14,...}}

data: {"section":"breakfast","status":"success","data":{"name":"Spinach Chicken Skillet","meal_type":"lunch",...}}

data: {"section":"news","status":"success","data":{"headlines":[...]}}

data: {"event":"done"}
```

---

## 4. Travel Itinerary & Email Dispatch Endpoints

### `POST /api/itinerary`
Generates a multi-day structured travel itinerary.

#### Request:
```json
{
  "location": "Tokyo",
  "days": 3,
  "budget": "moderate",
  "interests": ["Sightseeing", "Food", "Culture"]
}
```

#### Response (200 OK):
```json
{
  "status": "success",
  "data": {
    "location": "Tokyo",
    "days_count": 3,
    "budget": "moderate",
    "estimated_cost": "$100 - $160 / day",
    "days": [
      {
        "day_number": 1,
        "theme": "Tradition Meets Futurism",
        "morning": {"activity": "Visit Senso-ji Temple", "location": "Asakusa", "time": "08:30 - 11:00 AM"},
        "afternoon": {"activity": "Explore Electronics & Anime District", "location": "Akihabara", "time": "01:00 - 04:00 PM"},
        "evening": {"activity": "Observation Deck Night View", "location": "Shibuya Sky", "time": "06:30 - 08:30 PM"},
        "dining": {"lunch": "Fresh Tempura at Daikokuya", "dinner": "Tonkotsu Ramen in Shibuya"}
      }
    ],
    "travel_tips": ["Get a Suica or Pasmo IC card for easy train transfers across Tokyo."]
  }
}
```

---

### `POST /api/share/email`
Dispatches an itinerary or briefing email via the FastMCP Gmail tool.

#### Request:
```json
{
  "to_email": "traveler@example.com",
  "subject": "Your Travel Itinerary for Tokyo",
  "session_id": "guest-20260817234500",
  "body_html": "<div style='font-family: Arial;'><h2>Travel Itinerary for Tokyo</h2><p>Here is your schedule...</p></div>",
  "body_text": "Travel Itinerary for Tokyo\nHere is your schedule..."
}
```

#### Response (200 OK):
```json
{
  "success": true,
  "result": {
    "status": "sent",
    "delivered": true,
    "to": "traveler@example.com",
    "subject": "Your Travel Itinerary for Tokyo",
    "message_id": "<172390823900.21708.12345@smtp.gmail.com>"
  }
}
```

---

## 5. History & Session Management Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/history` | Returns a list of the 20 most recent saved briefing sessions. |
| `GET` | `/api/history/{session_id}` | Retrieves full stored session payload including intent, trace, and section data. |
| `DELETE` | `/api/history/{session_id}` | Permanently deletes a single session from SQLite database. |
| `DELETE` | `/api/history` | Clears all stored sessions from SQLite database. |
| `POST` | `/api/briefing/{session_id}/save` | Marks a session as pinned/saved (`saved = 1`). |
| `POST` | `/api/briefing/{session_id}/rerun` | Re-executes all agents using the stored session intent. |
| `POST` | `/api/briefing/{session_id}/{section}/refresh` | Re-executes only the specified agent section (e.g. `breakfast`, `weather`). |
| `PATCH` | `/api/briefing/{session_id}/intent` | Updates and persists intent fields (e.g., updating location or ingredients). |

---

## 6. User Settings & Preferences Endpoints

### `GET /api/settings`
Returns persisted application settings from `settings.json`.

#### Response (200 OK):
```json
{
  "default_location": "Chicago, IL",
  "units": "metric",
  "default_sections": ["weather", "commute", "news", "breakfast"],
  "news_categories": ["general"]
}
```

### `PUT /api/settings`
Updates and validates application preferences.

#### Request:
```json
{
  "default_location": "London, UK",
  "units": "metric",
  "default_sections": ["weather", "commute", "breakfast"]
}
```

#### Response (200 OK):
```json
{
  "default_location": "London, UK",
  "units": "metric",
  "default_sections": ["weather", "commute", "breakfast"],
  "news_categories": ["general"]
}
```

---

## 7. Observability & Telemetry Endpoints

### `GET /api/observability/metrics`
Returns rolling application performance telemetry, tool invocation counts, error rates, latency percentiles (P50/P95), and token consumption.

#### Response (200 OK):
```json
{
  "total_requests": 42,
  "total_tool_calls": 128,
  "tool_calls_by_server": {
    "weather": 38,
    "commute": 35,
    "recipe": 32,
    "news": 23
  },
  "avg_tool_latency_ms": 284.5,
  "p50_tool_latency_ms": 195.0,
  "p95_tool_latency_ms": 820.0,
  "llm_requests": 64,
  "total_tokens_consumed": 48210,
  "avg_llm_latency_ms": 1420.0,
  "error_count": 0,
  "uptime_seconds": 1845.2
}
```

### `GET /api/observability/traces`
Returns a list of the 50 most recent ReAct agent execution traces recorded by `src/services/telemetry.py`.

#### Query Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | `integer` | No | Number of traces to return (default `50`, max `100`). |

#### Response (200 OK):
```json
{
  "traces": [
    {
      "trace_id": "trace-8f92a10c",
      "session_id": "guest-20260819124500",
      "query": "Chicago weather, traffic to Loop, and 10 min breakfast",
      "status": "success",
      "duration_ms": 4820.5,
      "step_count": 7,
      "tool_count": 3,
      "timestamp": "2026-08-19T12:45:04.821Z"
    }
  ]
}
```

### `GET /api/observability/traces/{trace_id}`
Retrieves full span-level waterfall breakdown, event timeline, and execution metadata for a specific execution trace.

#### Response (200 OK):
```json
{
  "trace_id": "trace-8f92a10c",
  "session_id": "guest-20260819124500",
  "query": "Chicago weather, traffic to Loop, and 10 min breakfast",
  "status": "success",
  "total_duration_ms": 4820.5,
  "spans": [
    {
      "name": "perceive_intent",
      "duration_ms": 12.4,
      "status": "OK",
      "attributes": {"sections": ["weather", "commute", "breakfast"]}
    },
    {
      "name": "tool_weather.get_weather",
      "duration_ms": 1640.2,
      "status": "OK",
      "attributes": {"city": "Chicago"}
    },
    {
      "name": "tool_commute.get_commute_route",
      "duration_ms": 1820.1,
      "status": "OK",
      "attributes": {"origin": "Chicago", "destination": "Loop"}
    },
    {
      "name": "reflection_audit",
      "duration_ms": 2.1,
      "status": "OK",
      "attributes": {"overrides": 0}
    },
    {
      "name": "synthesize_summary",
      "duration_ms": 1340.0,
      "status": "OK",
      "attributes": {"tokens": 620}
    }
  ]
}
```

