# Commute Commander — UI & Visual Design Specification

> **Specification Version**: 2.2  
> **Visual Direction**: Modern Glassmorphism · Deep Navy Canvas · Lavender & Purple Accents · Vibrant Domain Indicators  
> **Target Form Factors**: Responsive Desktop (1280px+), Tablet (850px), Mobile (560px)

---

## 1. Application Layout & View Hierarchy

The Commute Commander dashboard is structured into a persistent vertical sidebar, a top branding bar, and four primary view containers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sidebar (Vertical Rail) │ Topbar (App Title + Current View Indicator)       │
│ ─────────────────────── ├───────────────────────────────────────────────────┤
│ [💬 Ask]               │ View Container (Active View)                      │
│ [🗺️ Itinerary]         │ ┌───────────────────────┐ ┌─────────────────────┐ │
│ [⏱️ History]           │ │ Primary Content Grid  │ │ Right Sidebar Panel │ │
│ [⚙️ Settings]          │ │ • Query Input Form    │ │ • News Feed         │ │
│                         │ │ • Intent Badges       │ │ • Live Leaflet Map  │ │
│                         │ │ • Weather Hero Card   │ └─────────────────────┘ │
│                         │ │ • Commute Card        │                         │
│                         │ │ • Dynamic Meal Card   │                         │
│                         │ │ • Itinerary Card      │                         │
│                         │ └───────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Views & Navigation

| View ID | Sidebar Trigger | Purpose & Elements |
|---|---|---|
| `#view-ask` | 💬 **Ask** | Natural-language query form, prompt chips, reactive agent cards, and real-time SSE loading states. |
| `#view-itinerary` | 🗺️ **Itinerary** | Dedicated multi-day travel planner with destination search, day sliders, budget presets, and day-by-day itineraries. |
| `#view-history` | ⏱️ **History** | Chronological timeline of saved briefing sessions retrieved from SQLite with quick-load and delete controls. |
| `#view-settings` | ⚙️ **Settings** | Configuration form for default location, transport modes, units (°C/°F, km/mi), and default sections. |

---

## 3. Card Specifications & Interactive Components

### 3.1 Hero Weather Card (`#weather-hero`)
- **Visual**: Large gradient hero card with live conditions, high/low range, and UV index.
- **Sparkline Curve**: SVG temperature trend line with UV band gradient generated from hourly forecast data.
- **Metric Row**: Real-time temperature, commute ETA, and UV peak badge.

### 3.2 Commute Intelligence Card (`#commute-card`)
- **Visual**: Purple-accented card displaying recommended transit mode and duration.
- **Status Indicators**:
  - `🟢 Live · TomTom`: Verified routing via TomTom API.
  - `🟡 Advisory`: Calculated advisory routing.
- **Alerts**: Real-time traffic delay badges and weather-adjusted mode advisories.
- **Actions**: Refresh button and Expand button opening the fullscreen Leaflet map modal.

### 3.3 Dynamic Meal Idea Card (`#breakfast-card`)
- **Dynamic Header & Icon**: Automatically updates based on parsed meal type:
  - 🍳 **Breakfast Idea**
  - 🥗 **Lunch Idea**
  - 🍲 **Dinner Idea**
  - 🥪 **Snack Idea**
  - 🍽️ **Meal Idea**
- **Time Badge**: Displays prep time limit (e.g. `15 min`).
- **Interactive Actions**:
  - `🔄 Swap`: Requests a fresh alternate dish from the MealAgent.
  - `↗ Expand`: Opens the Recipe Modal with step-by-step cooking directions, nutrition highlights, chef tips, primary ingredients, and minimal pantry staples.

### 3.4 Travel Itinerary Card (`#itinerary-card`)
- **Card Head**: Destination name, day count badge, budget tier (`Budget`, `Moderate`, `Luxury`), and estimated daily cost.
- **Quick Actions**:
  - `✉️ Send via Gmail MCP Tool`: Opens the email share modal with pre-populated itinerary summary.
  - `Full Planner ↗`: Navigates to the dedicated Itinerary Planner tab.
- **Day Schedule Cards**: Morning, afternoon, and evening activity blocks with locations and local dining spots (Lunch & Dinner).

### 3.5 Interactive Leaflet Route Map (`#commute-map`)
- **Map Engine**: Leaflet 1.9.4 with OpenStreetMap tiles.
- **Route Polyline**: Purple primary route polyline (weight 4) with origin (purple pin) and destination (pink pin) markers.
- **Alternate Routes**: Dashed grey polylines with hover tooltips showing alternative transit mode and ETA.

---

## 4. Modal Dialogs

### 4.1 Recipe Detail Modal (`#detail-modal`)
- **Badges**: Meal type, prep time, cook time, and total time.
- **Nutrition Highlights**: Protein content, caloric estimate, and dietary tags.
- **Chef's Pro Tip**: Highlighted culinary guidance box.
- **Ingredients Section**: Clear separation between primary user ingredients and minimal pantry staples.
- **Step-by-Step Directions**: Numbered, formatted cooking instructions.

### 4.2 Email Share Modal (`#email-modal`)
- **Inputs**: Recipient email input (auto-populated with `RECIPIENT_EMAIL` from `.env` or settings) and editable subject line.
- **Dispatch**: Triggers `POST /api/share/email` to send via the Gmail FastMCP tool server.

---

## 5. Loading States & Progressive SSE Streaming

1. **Submission**: All card text containers display animated skeleton shimmer placeholders immediately upon query submission.
2. **Progressive Arrival**: As the SSE stream emits section payloads, individual skeleton loaders are replaced with populated card data without waiting for other agents.
3. **Completion**: Terminal `{"event":"done"}` signals the close of the stream and reveals dashboard action buttons (Re-run, Save, Edit Query).

---

## 6. Color Tokens & Design System

| Token Name | Hex Code / Value | Usage |
|---|---|---|
| `--bg-canvas` | `#0f111a` | Deep navy background canvas |
| `--bg-card` | `rgba(25, 28, 44, 0.85)` | Glassmorphism card container background |
| `--border` | `rgba(255, 255, 255, 0.08)` | Subtle translucent border |
| `--purple-primary` | `#7c5cfc` | Primary brand color, active navigation, main route polyline |
| `--purple-light` | `#a78bfa` | Card headings and secondary accents |
| `--pink-accent` | `#f472b6` | Destination pins, temperature curves, highlights |
| `--green-success` | `#34d399` | Live data badge, low UV indicator, success toasts |
| `--amber-warning` | `#fbbf24` | Moderate UV indicator, advisory data badge |
| `--red-error` | `#f87171` | High UV indicator, traffic delays, error messages |

---

## 7. Security & XSS Prevention

All user inputs, query strings, and dynamic API strings rendered into the DOM are sanitized via `escHtml()`:

```javascript
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```
No raw untrusted strings are ever directly concatenated into `innerHTML`.
