'use strict';
/* ============================================================
   Commute Commander — app.js
   Production-grade agentic morning briefing UI
   ============================================================ */

const $ = id => document.getElementById(id);

/* ── DOM refs ── */
const form = $('briefing-form');
const queryInput = $('briefing-query');
const userIdInput = $('user-id');
const submitBtn = $('submit-btn');
const intentConfirm = $('intent-confirm');
const examplePrompts = $('example-prompts');
const resultsArea = $('results-area');
const dashControls = $('dash-controls');

// Hero
const heroTemp = $('hero-temp');
const heroCondition = $('hero-condition');
const tempLinePath = $('temp-line');
const uvBandPath = $('uv-band');
const metricTemp = $('metric-temp');
const metricTempSub = $('metric-temp-sub');
const metricEta = $('metric-eta');
const metricEtaSub = $('metric-eta-sub');
const metricUv = $('metric-uv');
const metricUvSub = $('metric-uv-sub');

// Action cards
const commuteSubtitle = $('commute-subtitle');
const commuteEtaBadge = $('commute-eta-badge');
const breakfastSubtitle = $('breakfast-subtitle');
const breakfastTimeBadge = $('breakfast-time-badge');

// Mini cards
const weatherMiniSub = $('weather-mini-sub');
const weatherMiniFoot = $('weather-mini-foot');
const uvProgress = $('uv-progress');
const uvPct = $('uv-pct');
const newsMiniSub = $('news-mini-sub');
const newsMiniFoot = $('news-mini-foot');
const recipeStepsSub = $('recipe-steps-sub');
const recipeStepsList = $('recipe-steps-list');
const recipeStepsFoot = $('recipe-steps-foot');

// News panel
const newsFeedPanel = $('news-feed-panel');

// Modal — using strict references to avoid event-bubbling bugs
const detailModal = $('detail-modal');
const modalTitle = $('modal-title');
const modalBody = $('modal-body');
const modalClose = $('modal-close');
const modalBox = $('modal-box');
const modalBackdrop = $('modal-backdrop');

// Toast
const toastEl = $('toast');

// Map Modal refs
const mapModal = $('map-modal');
const mapModalClose = $('map-modal-close');
const mapModalBackdrop = $('map-modal-backdrop');
const modalMapEl = $('modal-map');

/* ── State ── */
let state = {
  sessionId: null,
  intent: null,
  sections: {},
  isModalOpen: false,
};

/* ── Utilities ── */
function showToast(msg, type = '') {
  toastEl.textContent = msg;
  toastEl.className = `toast${type ? ' toast-' + type : ''}`;
  toastEl.classList.remove('hidden');
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => toastEl.classList.add('hidden'), 3500);
}

/* ── Modal helpers (Bug Fix: strict event handling) ── */
function openModal(title, html) {
  modalTitle.textContent = title;
  modalBody.innerHTML = html;
  detailModal.classList.remove('hidden');
  state.isModalOpen = true;
  // Move focus to the close button for accessibility
  requestAnimationFrame(() => modalClose.focus());
}

function closeModal() {
  detailModal.classList.add('hidden');
  state.isModalOpen = false;
}

// Close button — stopPropagation prevents bubbling to data-expand delegation
modalClose.addEventListener('click', e => {
  e.stopPropagation();
  closeModal();
});

// Backdrop — only close if the user clicked the backdrop itself, not the modal box
modalBackdrop.addEventListener('click', e => {
  if (e.target === modalBackdrop) closeModal();
});

// Modal internal action buttons (e.g. from Commute details to interactive planner)
modalBody?.addEventListener('click', e => {
  if (e.target.closest('#btn-modal-open-drawer')) {
    closeModal();
    openCommuteDrawer();
  } else if (e.target.closest('#btn-modal-open-map')) {
    closeModal();
    openMapModal();
  }
});

// Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (state.isModalOpen) {
      e.preventDefault();
      closeModal();
    }
    if (mapModal && !mapModal.classList.contains('hidden')) {
      e.preventDefault();
      closeMapModal();
    }
  }
});

/* ── Loading ── */
function setLoading(on) {
  submitBtn.disabled = on;
  submitBtn.title = on ? 'Working…' : 'Create briefing';
  submitBtn.setAttribute('aria-busy', on ? 'true' : 'false');
}

function setSkeleton(el, white = false) {
  if (!el) return;
  el.textContent = ' ';
  el.classList.add(white ? 'skeleton-line-white' : 'skeleton-line');
}
function clearSkeleton(el) {
  if (!el) return;
  el.classList.remove('skeleton-line', 'skeleton-line-white');
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatTime(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
}

/* ── Sparkline ── */
function drawSparkline(hourly) {
  if (!hourly || hourly.length < 2) return;
  const W = 700, H = 120;
  const temps = hourly.map(h => parseFloat(h.temp) || 0);
  const uvs = hourly.map(h => parseFloat(h.uv_index) || 0);
  const tMin = Math.min(...temps) - 2, tMax = Math.max(...temps) + 2;
  const uvMax = Math.max(...uvs, 1);
  const n = hourly.length;
  const px = i => (i / (n - 1)) * W;
  const pyT = t => H - ((t - tMin) / (tMax - tMin)) * (H * .75) - H * .1;
  const pyU = u => H - (u / uvMax) * (H * .55) - H * .05;

  const pts = temps.map((t, i) => ({ x: px(i), y: pyT(t) }));
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const cx1 = pts[i].x + (pts[i + 1].x - pts[i].x) / 3;
    const cx2 = pts[i + 1].x - (pts[i + 1].x - pts[i].x) / 3;
    d += ` C ${cx1} ${pts[i].y}, ${cx2} ${pts[i + 1].y}, ${pts[i + 1].x} ${pts[i + 1].y}`;
  }
  if (tempLinePath) tempLinePath.setAttribute('d', d);

  const up = uvs.map((u, i) => ({ x: px(i), y: pyU(u) }));
  let ud = `M ${up[0].x} ${H} L ${up[0].x} ${up[0].y}`;
  for (let i = 0; i < up.length - 1; i++) {
    const cx1 = up[i].x + (up[i + 1].x - up[i].x) / 3;
    const cx2 = up[i + 1].x - (up[i + 1].x - up[i].x) / 3;
    ud += ` C ${cx1} ${up[i].y}, ${cx2} ${up[i + 1].y}, ${up[i + 1].x} ${up[i + 1].y}`;
  }
  ud += ` L ${up[up.length - 1].x} ${H} Z`;
  if (uvBandPath) uvBandPath.setAttribute('d', ud);
}

/* ── Card renderers ── */
function renderWeather(payload) {
  const d = payload.data; if (!d) return;
  clearSkeleton(heroTemp); clearSkeleton(heroCondition);
  heroTemp.textContent = `${d.temp}°${d.temp_unit || 'C'}`;
  heroCondition.textContent = d.condition || '--';

  clearSkeleton(metricTemp); clearSkeleton(metricTempSub);
  metricTemp.textContent = `${d.temp}°`;
  metricTempSub.textContent = d.condition || 'Current';

  clearSkeleton(metricUv); clearSkeleton(metricUvSub);
  metricUv.textContent = d.uv_index !== undefined ? String(d.uv_index) : '--';
  metricUvSub.textContent = 'UV Index';

  clearSkeleton(weatherMiniSub); clearSkeleton(weatherMiniFoot);
  weatherMiniSub.style.color = '';
  weatherMiniSub.textContent = `${d.condition} · H ${d.high}° / L ${d.low}°`;
  weatherMiniFoot.textContent = d.uv_label || '';

  const uv = parseFloat(d.uv_index) || 0;
  const pct = Math.min(Math.round((uv / 11) * 100), 100);
  uvProgress.style.width = `${pct}%`;
  uvProgress.setAttribute('aria-valuenow', pct);
  uvPct.textContent = `UV ${uv}`;

  if (d.hourly?.length) drawSparkline(d.hourly);
}

function renderCommute(payload) {
  const d = payload.data; if (!d) return;
  clearSkeleton(commuteSubtitle); clearSkeleton(commuteEtaBadge);
  commuteSubtitle.style.color = '';
  const mode = d.recommended_mode || 'drive';
  const modeLabel = d.mode_label || (mode.charAt(0).toUpperCase() + mode.slice(1));
  const eta = d.eta_minutes || '--';
  const dist = d.distance_km ? ` · ${d.distance_km} km` : '';

  // Show origin → destination route if available, otherwise show alert or mode
  let subtitle = '';
  if (d.origin?.label && d.dest?.label) {
    const originShort = d.origin.label.split(',')[0];
    const destShort = d.dest.label.split(',')[0];
    subtitle = `${originShort} → ${destShort}`;
    if (d.alerts?.length) subtitle += ` · ${d.alerts[0]}`;
  } else if (d.alerts?.length) {
    subtitle = d.alerts[0];
  } else {
    subtitle = `${modeLabel} recommended${dist}`;
  }

  commuteSubtitle.textContent = subtitle;
  commuteEtaBadge.textContent = `${eta} min`;

  clearSkeleton(metricEta); clearSkeleton(metricEtaSub);
  metricEta.textContent = `${eta} min`;
  metricEtaSub.textContent = modeLabel;

  // Render Leaflet map with real polyline + markers
  renderCommuteMap(d);
}

function renderBreakfast(payload) {
  const d = payload.data; if (!d) return;
  clearSkeleton(breakfastSubtitle); clearSkeleton(breakfastTimeBadge);
  breakfastSubtitle.style.color = '';

  const mType = (d.meal_type || 'meal').toLowerCase();
  const iconMap = {
    breakfast: '🍳',
    lunch: '🥗',
    dinner: '🍲',
    snack: '🥪',
    meal: '🍽️',
  };
  const icon = iconMap[mType] || '🍽️';

  const mealIconEl = $('meal-card-icon');
  if (mealIconEl) mealIconEl.textContent = icon;

  const mealTitleEl = $('breakfast-title');
  if (mealTitleEl) {
    const titleMap = {
      breakfast: 'Breakfast Idea',
      lunch: 'Lunch Idea',
      dinner: 'Dinner Idea',
      snack: 'Snack Idea',
      meal: 'Meal Idea',
    };
    mealTitleEl.textContent = titleMap[mType] || `${mType.charAt(0).toUpperCase() + mType.slice(1)} Idea`;
  }

  const recipeName = d.name || d.recipe_name || 'Personalized recipe';
  breakfastSubtitle.textContent = recipeName;
  const prep = d.prep_time_minutes || 0;
  breakfastTimeBadge.textContent = `${prep} min`;

  // Recipe Steps mini-card
  if (recipeStepsSub) {
    clearSkeleton(recipeStepsSub);
    recipeStepsSub.style.color = '';
    const steps = d.steps || [];
    const stepCount = steps.length;
    recipeStepsSub.textContent = stepCount
      ? `${recipeName}${d.area ? ' · ' + d.area : ''}`
      : recipeName;

    if (recipeStepsList && stepCount > 0) {
      recipeStepsList.classList.remove('hidden');
      // Show first 3 steps inline
      recipeStepsList.innerHTML = steps.slice(0, 3).map(
        s => `<li>${escHtml(String(s))}</li>`
      ).join('');
    }

    if (recipeStepsFoot) {
      const extraInfo = d.nutrition_highlights ? ` · ${d.nutrition_highlights}` : '';
      recipeStepsFoot.textContent = stepCount
        ? `${stepCount} step${stepCount !== 1 ? 's' : ''} · ${prep} min prep${extraInfo}`
        : `${prep} min prep`;
    }
  }
}

function renderNews(payload) {
  const d = payload.data; if (!d?.headlines) return;
  const headlines = d.headlines.slice(0, 5);
  clearSkeleton(newsMiniSub); clearSkeleton(newsMiniFoot);
  newsMiniSub.style.color = '';
  newsMiniSub.textContent = headlines[0]?.title || 'No headlines';
  newsMiniFoot.textContent = `${headlines.length} loaded`;

  const np = $('news-progress');
  if (np) { np.style.width = '100%'; np.setAttribute('aria-valuenow', 100); }
  $('news-pct').textContent = 'Live';

  newsFeedPanel.innerHTML = '';
  headlines.forEach((item, i) => {
    const row = document.createElement('div');
    row.className = 'news-row';
    row.setAttribute('role', item.url ? 'link' : 'article');
    if (item.url) {
      row.style.cursor = 'pointer';
      row.title = 'Open article';
      row.addEventListener('click', () => window.open(item.url, '_blank', 'noopener,noreferrer'));
    }
    row.innerHTML = `
      <span class="news-num">${i + 1}</span>
      <div class="news-content">
        <b>${escHtml(item.title)}</b>
        <span>${escHtml(item.source)} · ${formatTime(item.timestamp)}</span>
      </div>
      ${item.url ? '<span style="color:var(--muted);font-size:12px;flex-shrink:0;padding-left:4px">↗</span>' : ''}`;
    newsFeedPanel.appendChild(row);
  });
}

function renderCardError(section, message) {
  const map = {
    weather: weatherMiniSub, commute: commuteSubtitle,
    breakfast: breakfastSubtitle, news: newsMiniSub,
  };
  const el = map[section]; if (!el) return;
  clearSkeleton(el);
  el.textContent = message || `Couldn't load ${section}.`;
  el.style.color = '#b92241';
}

function renderIntentChips(intent) {
  if (!intent?.location) return;

  // Location chip
  const locChip = $('chip-location');
  if (locChip) locChip.textContent = `📍 ${intent.location}`;

  // Destination chip — show only if a destination was extracted
  const destChip = $('chip-destination');
  if (destChip) {
    if (intent.destination) {
      destChip.textContent = `→ ${intent.destination}`;
      destChip.classList.remove('hidden');
    } else {
      destChip.classList.add('hidden');
    }
  }

  // Section chips
  ['weather', 'commute', 'news', 'breakfast', 'itinerary'].forEach(sec => {
    const chip = $('chip-' + sec); if (!chip) return;
    const isPresent = intent.sections?.includes(sec) || (sec === 'breakfast' && (intent.sections?.includes('meal') || intent.sections?.includes('recipe')));
    if (isPresent) {
      chip.classList.remove('hidden');
      if (sec === 'breakfast') {
        const mType = intent.meal_type || 'meal';
        chip.textContent = mType.charAt(0).toUpperCase() + mType.slice(1);
      }
    } else {
      chip.classList.add('hidden');
    }
  });

  intentConfirm.classList.remove('hidden');
}

function dispatchSection(section, payload) {
  state.sections[section] = payload;
  if (payload.status === 'error') { renderCardError(section, payload.error?.message); return; }
  switch (section) {
    case 'weather': renderWeather(payload); break;
    case 'commute': renderCommute(payload); break;
    case 'breakfast': renderBreakfast(payload); break;
    case 'news': renderNews(payload); break;
    case 'itinerary': renderItinerary(payload); break;
  }
}

/* ════════════════════════════════════════════════════════════
   LEAFLET MAP
   Manages a single Leaflet map instance in #commute-map.
   renderCommuteMap(data) is called by renderCommute() whenever
   fresh commute data arrives.
   ════════════════════════════════════════════════════════════ */
const mapEl = $('commute-map');
const mapEmptyState = $('map-empty-state');
const mapBadge = $('map-source-badge');

let _leafletMap = null;   // L.Map instance (created once)
let _routeLayer = null;   // L.LayerGroup for route + markers
let _altLayers = [];     // alternate route polylines

/* Tile layer — OpenStreetMap (no API key required) */
const _TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const _TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function _ensureMap(lat, lon) {
  if (mapEmptyState) mapEmptyState.classList.add('hidden');
  if (mapEl) mapEl.classList.remove('hidden');

  if (_leafletMap) {
    _leafletMap.setView([lat, lon], 12);
    setTimeout(() => { if (_leafletMap) _leafletMap.invalidateSize(); }, 150);
    return;
  }

  _leafletMap = L.map('commute-map', {
    zoomControl: true,
    attributionControl: true,
    scrollWheelZoom: false,   // don't hijack page scroll
  });

  L.tileLayer(_TILE_URL, {
    attribution: _TILE_ATTR,
    maxZoom: 19,
  }).addTo(_leafletMap);

  _leafletMap.setView([lat, lon], 12);

  // Force Leaflet to recalculate container size (needed when div was hidden/zero-size)
  setTimeout(() => { if (_leafletMap) _leafletMap.invalidateSize(); }, 200);
}

function _makePinIcon(color) {
  /* Tiny SVG circle marker — avoids the default Leaflet image dependency */
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
    <circle cx="11" cy="11" r="9" fill="${color}" stroke="white" stroke-width="2"/>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -14],
  });
}

let _ORIGIN_ICON = null;
let _DEST_ICON = null;

function resetCommuteMap(statusMsg = 'Run a briefing to see your route here.') {
  if (_routeLayer) {
    _routeLayer.clearLayers();
  }
  if (_leafletMap && _altLayers && _altLayers.length) {
    _altLayers.forEach(l => {
      try { _leafletMap.removeLayer(l); } catch { }
    });
    _altLayers = [];
  }
  if (mapBadge) {
    mapBadge.classList.add('hidden');
    mapBadge.textContent = '';
  }
  if (mapEl) {
    mapEl.classList.add('hidden');
  }
  if (mapEmptyState) {
    mapEmptyState.textContent = statusMsg;
    mapEmptyState.classList.remove('hidden');
  }
}

function renderCommuteMap(data) {
  if (!data) {
    resetCommuteMap('No route data available for this query.');
    return;
  }

  if (!_ORIGIN_ICON) _ORIGIN_ICON = _makePinIcon('#7260c3');
  if (!_DEST_ICON) _DEST_ICON = _makePinIcon('#f06a9a');

  const origin = data.origin || {};
  const dest = data.dest || {};
  const polyline = data.polyline || [];
  const source = data.source || 'advisory';

  const hasCoords = (
    typeof origin.lat === 'number' && typeof origin.lon === 'number' &&
    typeof dest.lat === 'number' && typeof dest.lon === 'number'
  );

  if (!hasCoords) {
    const alertMsg = data.alerts?.[0] || 'No coordinates available for this commute.';
    resetCommuteMap(`Advisory Commute: ${alertMsg}`);
    if (mapBadge) {
      mapBadge.textContent = 'Advisory';
      mapBadge.className = 'map-source-badge source-advisory';
      mapBadge.classList.remove('hidden');
    }
    return;
  }

  // Unhide map element & hide placeholder
  if (mapEl) mapEl.classList.remove('hidden');
  if (mapEmptyState) mapEmptyState.classList.add('hidden');

  // Initialise map centred on origin
  _ensureMap(origin.lat, origin.lon);

  // Clear previous route layers
  if (_routeLayer) {
    _routeLayer.clearLayers();
  } else if (_leafletMap) {
    _routeLayer = L.layerGroup().addTo(_leafletMap);
  }
  if (_leafletMap && _altLayers.length) {
    _altLayers.forEach(l => {
      try { _leafletMap.removeLayer(l); } catch { }
    });
    _altLayers = [];
  }

  // ── Main route polyline ────────────────────────────────────
  if (polyline.length >= 2) {
    const routeLine = L.polyline(polyline, {
      color: '#7260c3',
      weight: 4,
      opacity: 0.85,
      lineJoin: 'round',
    }).addTo(_routeLayer);

    // Fit map to the route bounds with padding
    _leafletMap.fitBounds(routeLine.getBounds(), { padding: [20, 20] });
  } else {
    // No polyline — just set view between the two points
    const mid = [
      (origin.lat + dest.lat) / 2,
      (origin.lon + dest.lon) / 2,
    ];
    _leafletMap.setView(mid, 12);
  }

  // ── Alternate route polylines (dimmed) ─────────────────────
  (data.alternates || []).forEach(alt => {
    if (!alt.polyline || alt.polyline.length < 2) return;
    const altLine = L.polyline(alt.polyline, {
      color: '#b4a9dd',
      weight: 2.5,
      opacity: 0.55,
      dashArray: '6 6',
    });
    altLine.bindTooltip(
      `${alt.mode ? alt.mode.charAt(0).toUpperCase() + alt.mode.slice(1) : 'Alt'}: ${alt.eta_minutes || '--'} min`,
      { sticky: true }
    );
    altLine.addTo(_leafletMap);
    _altLayers.push(altLine);
  });

  // ── Origin marker ──────────────────────────────────────────
  L.marker([origin.lat, origin.lon], { icon: _ORIGIN_ICON })
    .bindPopup(`<b>Start</b><br>${origin.label || ''}`)
    .addTo(_routeLayer);

  // ── Destination marker ─────────────────────────────────────
  L.marker([dest.lat, dest.lon], { icon: _DEST_ICON })
    .bindPopup(`<b>Destination</b><br>${dest.label || ''}`)
    .addTo(_routeLayer);

  // ── Source badge ───────────────────────────────────────────
  if (mapBadge) {
    const isTomTom = source === 'tomtom';
    const isORS = source === 'ors';
    mapBadge.textContent = isTomTom ? 'Live · TomTom' : (isORS ? 'Live · ORS' : 'Advisory');
    mapBadge.className = `map-source-badge${!isTomTom && !isORS ? ' source-advisory' : ''}`;
    mapBadge.classList.remove('hidden');
  }

  setTimeout(() => { if (_leafletMap) _leafletMap.invalidateSize(); }, 200);
}

/* ── API ── */
async function postBriefing(query, userId) {
  const res = await fetch('/api/briefing', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, user_id: userId }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Server error');
  return data;
}

async function refreshSection(sessionId, section) {
  const res = await fetch(`/api/briefing/${sessionId}/${section}/refresh`, { method: 'POST' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || 'Refresh failed');
  return data;
}

async function fetchHistory() {
  const res = await fetch('/api/history');
  if (!res.ok) return { sessions: [] };
  return res.json();
}

/* ── SSE streaming briefing ── */
function streamBriefing(sessionId) {
  const es = new EventSource(`/api/briefing/${sessionId}/stream`);
  es.onmessage = e => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.event === 'done') {
        es.close();
        dashControls.classList.remove('hidden');
        setLoading(false);
        if (!state.sections['commute'] || state.sections['commute']?.status === 'error') {
          resetCommuteMap('No commute route in this briefing');
        }
        return;
      }
      if (payload.section) dispatchSection(payload.section, payload);
    } catch { /* ignore malformed events */ }
  };
  es.onerror = () => {
    es.close();
    dashControls.classList.remove('hidden');
    setLoading(false);
    if (!state.sections['commute']) {
      resetCommuteMap('No commute route in this briefing');
    }
  };
}

/* ── Submit ── */
form.addEventListener('submit', async e => {
  e.preventDefault();
  const query = queryInput.value.trim();
  const userId = userIdInput.value.trim() || 'guest';
  if (!query) return;

  // Clear previous session data & reset commute map dynamically
  state.sections = {};
  resetCommuteMap('Calculating commute route…');

  setLoading(true);
  examplePrompts.classList.add('hidden');
  intentConfirm.classList.add('hidden');
  resultsArea.classList.remove('hidden');
  dashControls.classList.add('hidden');
  newsFeedPanel.innerHTML = '<p class="empty-state">Loading headlines…</p>';

  // Reset card colors to avoid stale error colors from a previous failed run
  [commuteSubtitle, weatherMiniSub, newsMiniSub, breakfastSubtitle, recipeStepsSub].forEach(el => {
    if (el) el.style.color = '';
  });

  // Skeletons on cards
  [heroTemp, heroCondition, metricTemp, metricEta, metricUv].forEach(el => setSkeleton(el, true));
  [commuteSubtitle, commuteEtaBadge, breakfastSubtitle, breakfastTimeBadge,
    weatherMiniSub, newsMiniSub, recipeStepsSub].forEach(el => setSkeleton(el));

  $('topbar-heading').textContent = 'Getting your briefing…';

  try {
    const data = await postBriefing(query, userId);
    state.sessionId = data.session_id;
    state.intent = data.intent;

    $('topbar-heading').textContent = 'Here\'s your briefing';
    $('topbar-eyebrow').textContent = data.intent?.location || 'Commute Commander';
    renderIntentChips(data.intent);

    const sections = data.sections || {};
    const requestedSections = data.intent?.sections || [];

    // Render daily briefing sections (weather, commute, breakfast, news)
    ['weather', 'commute', 'breakfast', 'news'].forEach(sec => {
      if (sections[sec]) dispatchSection(sec, sections[sec]);
    });

    if (!sections.commute && !requestedSections.includes('commute')) {
      resetCommuteMap('No commute route in this query');
    }

    // Render itinerary in the Ask view without hijacking the user to the planner page.
    if (sections.itinerary) {
      dispatchSection('itinerary', sections.itinerary);
    }

    // SSE stream picks up any sections not yet in the POST response
    streamBriefing(data.session_id);
  } catch (err) {
    $('topbar-heading').textContent = 'Something went wrong';
    showToast(err.message || 'Could not create briefing.', 'error');
    ['weather', 'commute', 'breakfast', 'news'].forEach(sec => renderCardError(sec, null));
    resetCommuteMap('Briefing error occurred');
    setLoading(false);
  }
});

/* ── Example chips ── */
document.querySelectorAll('.example-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    queryInput.value = btn.dataset.query;
    form.requestSubmit();
  });
});

/* ── Refresh delegation ── */
document.addEventListener('click', async e => {
  // Don't process if modal is open to avoid accidental clicks
  if (state.isModalOpen) return;
  const btn = e.target.closest('[data-refresh]');
  if (!btn || !state.sessionId) return;
  const section = btn.dataset.refresh;
  btn.disabled = true; btn.style.opacity = '.5';
  try {
    const payload = await refreshSection(state.sessionId, section);
    dispatchSection(section, payload);
    showToast(`${section} refreshed ✓`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false; btn.style.opacity = '';
  }
});

/* ── Expand delegation ── */
document.addEventListener('click', e => {
  // Skip if modal is already open
  if (state.isModalOpen) return;
  const btn = e.target.closest('[data-expand]');
  if (!btn) return;
  const section = btn.dataset.expand;
  const payload = state.sections[section];
  if (!payload) { showToast(`Run a briefing first.`); return; }
  const title = section.charAt(0).toUpperCase() + section.slice(1) + ' Details';
  openModal(title, buildDetailHtml(section, payload));
});

/* ── Modal builders ── */
function buildDetailHtml(section, payload) {
  if (payload.status === 'error') return `<div class="card-error"><span>⚠</span><span>${escHtml(payload.error?.message || 'Error')}</span></div>`;
  const d = payload.data;
  switch (section) {
    case 'weather': return buildWeatherDetail(d);
    case 'commute': return buildCommuteDetail(d);
    case 'breakfast': return buildBreakfastDetail(d);
    case 'news': return buildNewsDetail(d);
    default: return '<p>No detail.</p>';
  }
}

function buildWeatherDetail(d) {
  const rows = (d.hourly || []).map(h =>
    `<div class="alt-item"><b>${escHtml(h.time)}</b><span>${escHtml(h.temp)}° · UV ${escHtml(String(h.uv_index))}</span></div>`
  ).join('');
  return `<h3>Current</h3>
    <p>${escHtml(d.condition)} · ${escHtml(String(d.temp))}°${escHtml(d.temp_unit || 'C')}</p>
    <p>High <strong>${escHtml(String(d.high))}°</strong> / Low <strong>${escHtml(String(d.low))}°</strong></p>
    <h3>UV</h3><p>UV ${escHtml(String(d.uv_index))} — ${escHtml(d.uv_label || '')}</p>
    <h3>Hourly</h3><div class="alt-list">${rows || '<p>No data.</p>'}</div>`;
}

function buildCommuteDetail(d) {
  const mode = d.recommended_mode || 'drive';
  const label = d.mode_label || (mode.charAt(0).toUpperCase() + mode.slice(1));
  const dist = d.distance_km ? `${d.distance_km} km` : '';
  const src = d.source === 'tomtom' ? '🟢 Live data via TomTom' : '🟡 Advisory estimate';
  const alerts = (d.alerts || []).map(a =>
    `<div class="alert-banner" style="margin-bottom:8px"><span>⚠</span><span>${escHtml(a)}</span></div>`).join('');
  const alts = (d.alternates || []).map(a =>
    `<div class="alt-item">
       <b>${escHtml(a.mode.charAt(0).toUpperCase() + a.mode.slice(1))}</b>
       <span>${escHtml(String(a.eta_minutes))} min${a.distance_km ? ' · ' + a.distance_km + ' km' : ''}</span>
     </div>`).join('');
  const origin = d.origin?.label ? `<p style="margin:4px 0"><strong>Origin:</strong> ${escHtml(d.origin.label)}</p>` : '';
  const destTxt = d.dest?.label ? `<p style="margin:4px 0"><strong>Destination:</strong> ${escHtml(d.dest.label)}</p>` : '';

  return `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
      <h3 style="margin:0">Recommended Route</h3>
      <span class="chip chip-sm chip-commute" style="text-transform:uppercase;font-size:10px;font-weight:700">${escHtml(label)}</span>
    </div>
    ${origin}${destTxt}
    <p style="margin:8px 0">Estimated Travel Time: <strong>${escHtml(String(d.eta_minutes))} min</strong>${dist ? ' · Distance: <strong>' + escHtml(dist) + '</strong>' : ''}</p>
    <p style="font-size:11px;color:var(--text-muted);margin-bottom:12px">${src}</p>
    ${alerts}
    <h3 style="margin-top:14px">Alternative Transit Modes</h3>
    <div class="alt-list">${alts || '<p>No alternates available.</p>'}</div>
    <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-sm" id="btn-modal-open-drawer" type="button" style="display:inline-flex;align-items:center;gap:6px;background:var(--purple-primary,#7260c3);color:white;border:none;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer">
        🗺️ Interactive Route Planner
      </button>
      <button class="btn btn-sm btn-outline" id="btn-modal-open-map" type="button" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer">
        🔍 Centered Map View
      </button>
    </div>`;
}

function buildBreakfastDetail(d) {
  const mType = (d.meal_type || 'meal').toUpperCase();
  const steps = (d.steps || []).map(s => `<li>${escHtml(String(s))}</li>`).join('');
  const alts = (d.alternates || []).map(a => `<div class="alt-item"><b>${escHtml(a.recipe_name)}</b><span>${escHtml(String(a.prep_time_minutes))} min</span></div>`).join('');
  const ings = (d.ingredients_used || d.ingredients || []).map(i => escHtml(String(i))).join(', ');
  const pantry = (d.pantry_staples || []).map(p => escHtml(String(p))).join(', ');
  const nutrition = d.nutrition_highlights ? `<p style="color:var(--accent-pink,#f06a9a);font-weight:600">✨ ${escHtml(d.nutrition_highlights)}</p>` : '';
  const chefTip = d.chef_tip ? `<div style="background:rgba(240,106,154,0.1);border-left:3px solid #f06a9a;padding:8px 12px;border-radius:4px;margin:10px 0;font-size:12px"><strong>Chef's Pro Tip:</strong> ${escHtml(d.chef_tip)}</div>` : '';
  const cookTime = d.cook_time_minutes ? ` | Cook: <strong>${escHtml(String(d.cook_time_minutes))} min</strong>` : '';

  return `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
      <h3 style="margin:0">${escHtml(d.name || d.recipe_name || 'Recipe')}</h3>
      <span class="chip chip-sm chip-breakfast" style="text-transform:uppercase;font-size:10px;font-weight:700">${escHtml(mType)}</span>
    </div>
    ${nutrition}
    <p>Prep: <strong>${escHtml(String(d.prep_time_minutes || 10))} min</strong>${cookTime}</p>
    <p><strong>Primary Ingredients:</strong> ${ings || '—'}</p>
    ${pantry ? `<p><strong>Pantry Staples:</strong> ${pantry}</p>` : ''}
    ${chefTip}
    <h3 style="margin-top:14px">Step-by-Step Directions</h3><ol style="padding-left:20px;line-height:1.6">${steps || '<li>No steps available.</li>'}</ol>
    ${alts ? `<h3 style="margin-top:14px">Quick Alternatives</h3><div class="alt-list">${alts}</div>` : ''}`;
}

function buildNewsDetail(d) {
  const rows = (d.headlines || []).map(h => {
    const titleHtml = h.url
      ? `<a href="${escHtml(h.url)}" target="_blank" rel="noopener noreferrer"
            style="color:var(--ink);text-decoration:none;font-weight:600">${escHtml(h.title)}</a>`
      : `<b>${escHtml(h.title)}</b>`;
    const extLink = h.url
      ? `<a href="${escHtml(h.url)}" target="_blank" rel="noopener noreferrer"
            aria-label="Open article" style="color:var(--muted);font-size:13px;flex-shrink:0">↗</a>`
      : '';
    return `<div class="alt-item" style="align-items:flex-start;gap:10px">
      <div style="flex:1;min-width:0">
        ${titleHtml}<br>
        <span style="font-size:9.5px;color:var(--muted)">${escHtml(h.source)} · ${formatTime(h.timestamp)}</span>
      </div>${extLink}
    </div>`;
  }).join('');
  return `<h3>Top Headlines</h3><div class="alt-list">${rows || '<p>No headlines.</p>'}</div>`;
}

/* ── Breakfast swap ── */
const swapBtn = $('breakfast-swap-btn');
if (swapBtn) swapBtn.addEventListener('click', async () => {
  if (!state.sessionId) return;
  swapBtn.disabled = true;
  try {
    const payload = await refreshSection(state.sessionId, 'breakfast');
    dispatchSection('breakfast', payload);
    showToast('New recipe loaded ✓', 'success');
  } catch (err) { showToast(err.message, 'error'); }
  finally { swapBtn.disabled = false; }
});

/* ── Period chips ── */
document.querySelectorAll('.period-chips .chip').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.period-chips .chip').forEach(b => b.classList.remove('chip-active'));
    btn.classList.add('chip-active');
  });
});

/* ── Dashboard controls ── */
const rerunBtn = $('rerun-btn');
const saveBtn = $('save-btn');
const editBtn = $('edit-btn');

rerunBtn?.addEventListener('click', async () => {
  if (!state.sessionId) { if (queryInput.value.trim()) form.requestSubmit(); return; }
  rerunBtn.disabled = true;
  try {
    const res = await fetch(`/api/briefing/${state.sessionId}/rerun`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error?.message || 'Re-run failed');
    const sections = data.sections || {};
    ['weather', 'commute', 'breakfast', 'news'].forEach(sec => {
      if (sections[sec]) dispatchSection(sec, sections[sec]);
    });
    showToast('Briefing refreshed ✓', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    rerunBtn.disabled = false;
  }
});
editBtn?.addEventListener('click', () => { queryInput.focus(); queryInput.select(); });
saveBtn?.addEventListener('click', async () => {
  if (!state.sessionId) return;
  saveBtn.disabled = true;
  try {
    const res = await fetch(`/api/briefing/${state.sessionId}/save`, { method: 'POST' });
    const d = await res.json();
    showToast(d.saved ? 'Briefing saved! ✓' : (d.error?.message || 'Not saved — retry?'), d.saved ? 'success' : 'error');
  } catch { showToast('Save failed — retry?', 'error'); }
  finally { saveBtn.disabled = false; }
});

/* ── Sidebar view switching ── */
const VIEWS = ['ask', 'itinerary', 'history', 'settings'];

function switchView(name) {
  VIEWS.forEach(v => {
    $('view-' + v)?.classList.toggle('hidden', v !== name);
    $('view-' + v)?.classList.toggle('active-view', v === name);
  });
  document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === name);
  });

  const headings = {
    ask: ['Commute Commander', 'Good morning — what\'s your plan?'],
    itinerary: ['Commute Commander', 'Travel Itinerary Planner'],
    history: ['Commute Commander', 'Briefing History'],
    settings: ['Commute Commander', 'Settings'],
  };
  const [eyebrow, heading] = headings[name] || headings.ask;
  $('topbar-eyebrow').textContent = eyebrow;
  $('topbar-heading').textContent = heading;

  if (name === 'history') loadHistory();
  if (name === 'settings') loadSettings();
  if (name === 'ask' && state.sections['itinerary']) {
    renderItinerary(state.sections['itinerary']);
  }
}

document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.dataset.view === 'signout') { showToast('Signed out.'); return; }
    switchView(btn.dataset.view);
  });
});

async function deleteHistoryItem(sessionId, itemEl) {
  if (!confirm('Are you sure you want to delete this briefing from history?')) return;
  try {
    const res = await fetch(`/api/history/${sessionId}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to delete');

    itemEl.style.opacity = '0';
    itemEl.style.transform = 'scale(0.9)';
    setTimeout(() => {
      itemEl.remove();
      const list = $('history-list');
      if (!list.querySelector('.history-item')) {
        list.innerHTML = '<p class="empty-state">Your morning briefings will show up here once you run your first query.</p>';
      }
    }, 200);
    showToast('Briefing deleted from history ✓', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function clearAllHistory() {
  if (!confirm('Are you sure you want to clear ALL briefing history? This cannot be undone.')) return;
  try {
    const res = await fetch('/api/history', { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to clear history');

    const list = $('history-list');
    list.innerHTML = '<p class="empty-state">Your morning briefings will show up here once you run your first query.</p>';
    showToast('Briefing history cleared ✓', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadHistory() {
  const list = $('history-list');
  list.innerHTML = '<p class="empty-state">Loading…</p>';
  try {
    const data = await fetchHistory();
    const sessions = data.sessions || [];
    if (!sessions.length) {
      list.innerHTML = '<p class="empty-state">Your morning briefings will show up here once you run your first query.</p>';
      return;
    }
    list.innerHTML = '';
    sessions.forEach(s => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.setAttribute('role', 'button'); item.setAttribute('tabindex', '0');
      item.innerHTML = `
        <div class="history-info">
          <b>${escHtml(s.query || s.session_id)}</b>
          <span>${escHtml(s.session_id)} · ${s.created_at ? formatTime(s.created_at) : ''}</span>
        </div>
        <button class="history-delete-btn" aria-label="Delete history item" data-id="${s.session_id}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      `;

      item.addEventListener('click', e => {
        if (e.target.closest('.history-delete-btn')) return;
        queryInput.value = s.query || '';
        switchView('ask');
        form.requestSubmit();
      });

      item.querySelector('.history-delete-btn').addEventListener('click', e => {
        e.stopPropagation();
        deleteHistoryItem(s.session_id, item);
      });

      list.appendChild(item);
    });
  } catch (err) {
    list.innerHTML = '<p class="empty-state">Could not load history.</p>';
  }
}

/* ── Settings ── */
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const s = await res.json();
    const locEl = $('setting-location');
    const unitsEl = $('setting-units');
    if (locEl) locEl.value = s.default_location || '';
    if (unitsEl) unitsEl.value = s.units || 'metric';
    document.querySelectorAll('#settings-form input[type=checkbox]').forEach(cb => {
      cb.checked = (s.default_sections || []).includes(cb.value);
    });
  } catch { /* silently ignore */ }
}

$('settings-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const sections = [...document.querySelectorAll('#settings-form input[type=checkbox]:checked')]
    .map(cb => cb.value);
  const body = {
    default_location: $('setting-location')?.value.trim() || '',
    units: $('setting-units')?.value || 'metric',
    default_sections: sections,
  };
  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    showToast(res.ok ? 'Preferences saved! ✓' : 'Save failed — retry?', res.ok ? 'success' : 'error');
  } catch { showToast('Save failed — retry?', 'error'); }
});

// Pre-fill settings when the view opens
document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
  if (btn.dataset.view === 'settings') btn.addEventListener('click', loadSettings, { once: false });
});

/* ──────────────────────────────────────────────────────────────
   COMMUTE NOW DRAWER (OLA/UBER STYLE)
────────────────────────────────────────────────────────────── */
const commuteDrawer = $('commute-drawer');
const drawerPanel = $('drawer-panel');
const drawerClose = $('drawer-close');
const drawerBackdrop = $('drawer-backdrop');
const drawerForm = $('drawer-form');
const drawerFrom = $('drawer-from');
const drawerTo = $('drawer-to');
const drawerSubmit = $('drawer-submit');
const drawerResults = $('drawer-results');
const drawerEta = $('drawer-eta');
const drawerDistance = $('drawer-distance');
const drawerSource = $('drawer-source');
const drawerAlerts = $('drawer-alerts');

let _drawerMap = null;
let _drawerRouteLayer = null;
let _drawerAltLayers = [];
let _activeCommuteMode = 'drive';

function openCommuteDrawer(prefillData) {
  const commPayload = prefillData || state.sections['commute'];
  const commData = commPayload?.data;

  if (commData) {
    if (commData.origin?.label) {
      drawerFrom.value = commData.origin.label;
    } else if (state.intent?.location && state.intent.location !== 'current location') {
      drawerFrom.value = state.intent.location;
    }
    if (commData.dest?.label) {
      drawerTo.value = commData.dest.label;
    } else if (state.intent?.destination) {
      drawerTo.value = state.intent.destination;
    }

    if (commData.recommended_mode) {
      _activeCommuteMode = commData.recommended_mode;
      document.querySelectorAll('#drawer-modes .drawer-mode-btn').forEach(btn => {
        const isActive = btn.dataset.mode === _activeCommuteMode;
        btn.classList.toggle('mode-active', isActive);
        btn.setAttribute('aria-checked', String(isActive));
      });
    }

    // Render text metrics if available
    if (commData.eta_minutes !== undefined) {
      drawerEta.textContent = `${commData.eta_minutes} min`;
      drawerDistance.textContent = `${commData.distance_km || '--'} km`;
      drawerSource.textContent = commData.source === 'tomtom' ? 'Live TomTom' : (commData.source || 'advisory');

      // Render alerts
      drawerAlerts.innerHTML = '';
      (commData.alerts || []).forEach(a => {
        const banner = document.createElement('div');
        banner.className = 'alert-banner';
        banner.innerHTML = `<span>⚠</span><span>${escHtml(a)}</span>`;
        drawerAlerts.appendChild(banner);
      });

      drawerResults.classList.remove('hidden');
    }
  } else if (state.intent) {
    if (state.intent.location && state.intent.location !== 'current location') {
      drawerFrom.value = state.intent.location;
    }
    if (state.intent.destination) {
      drawerTo.value = state.intent.destination;
    }
  }

  commuteDrawer.classList.remove('hidden');

  // Initialize map with a small delay so container size is ready
  setTimeout(() => {
    if (!_drawerMap) {
      _drawerMap = L.map('drawer-map', {
        zoomControl: true,
        attributionControl: true,
        scrollWheelZoom: false,
      });
      L.tileLayer(_TILE_URL, {
        attribution: _TILE_ATTR,
        maxZoom: 19,
      }).addTo(_drawerMap);
      _drawerMap.setView([20.5937, 78.9629], 5);
    }
    _drawerMap.invalidateSize();

    if (commData && (commData.polyline?.length >= 2 || (commData.origin?.lat && commData.dest?.lat))) {
      renderDrawerMapRoute(commData);
    }
  }, 200);
}

function renderDrawerMapRoute(data) {
  if (!_drawerMap) return;
  _drawerMap.invalidateSize();

  const origin = data.origin || {};
  const dest = data.dest || {};
  const polyline = data.polyline || [];

  // Clear previous layer
  if (_drawerRouteLayer) {
    _drawerRouteLayer.clearLayers();
  } else {
    _drawerRouteLayer = L.layerGroup().addTo(_drawerMap);
  }
  _drawerAltLayers.forEach(l => _drawerMap.removeLayer(l));
  _drawerAltLayers = [];

  // Draw main route polyline
  if (polyline.length >= 2) {
    const routeLine = L.polyline(polyline, {
      color: '#7260c3',
      weight: 5,
      opacity: 0.85,
      lineJoin: 'round',
    }).addTo(_drawerRouteLayer);

    _drawerMap.fitBounds(routeLine.getBounds(), { padding: [35, 35] });
  } else if (origin.lat && origin.lon) {
    _drawerMap.setView([origin.lat, origin.lon], 12);
  }

  // Draw pins
  const originIcon = _ORIGIN_ICON || _makePinIcon('#7260c3');
  const destIcon = _DEST_ICON || _makePinIcon('#f06a9a');

  if (origin.lat && origin.lon) {
    L.marker([origin.lat, origin.lon], { icon: originIcon })
      .bindPopup(`<b>Start</b><br>${origin.label || ''}`)
      .addTo(_drawerRouteLayer);
  }
  if (dest.lat && dest.lon) {
    L.marker([dest.lat, dest.lon], { icon: destIcon })
      .bindPopup(`<b>Destination</b><br>${dest.label || ''}`)
      .addTo(_drawerRouteLayer);
  }
}

function closeCommuteDrawer() {
  commuteDrawer.classList.add('hidden');
}

// Click commute card to open
$('commute-card')?.addEventListener('click', e => {
  if (e.target.closest('.card-actions')) return;
  openCommuteDrawer();
});

drawerClose?.addEventListener('click', closeCommuteDrawer);
drawerBackdrop?.addEventListener('click', closeCommuteDrawer);

// Handle mode selection buttons
document.querySelectorAll('#drawer-modes .drawer-mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#drawer-modes .drawer-mode-btn').forEach(b => {
      b.classList.remove('mode-active');
      b.setAttribute('aria-checked', 'false');
    });
    btn.classList.add('mode-active');
    btn.setAttribute('aria-checked', 'true');
    _activeCommuteMode = btn.dataset.mode;

    // Auto-refresh route calculation if locations are already filled
    if (drawerFrom.value.trim() && drawerTo.value.trim()) {
      calculateDrawerRoute();
    }
  });
});

async function calculateDrawerRoute() {
  const fromVal = drawerFrom.value.trim();
  const toVal = drawerTo.value.trim();
  if (!fromVal || !toVal) return;

  drawerSubmit.disabled = true;
  drawerSubmit.textContent = 'Calculating route…';

  try {
    const res = await fetch('/api/commute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from: fromVal,
        to: toVal,
        mode: _activeCommuteMode
      })
    });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.error || 'Failed to fetch commute path.');

    if (payload.status === 'error') {
      throw new Error(payload.error?.message || 'Error occurred during route calculation.');
    }

    const data = payload.data || payload;

    // Render text metrics
    drawerEta.textContent = `${data.eta_minutes || '--'} min`;
    drawerDistance.textContent = `${data.distance_km || '--'} km`;
    drawerSource.textContent = data.source || 'advisory';

    // Render alerts
    drawerAlerts.innerHTML = '';
    (data.alerts || []).forEach(a => {
      const banner = document.createElement('div');
      banner.className = 'alert-banner';
      banner.innerHTML = `<span>⚠</span><span>${escHtml(a)}</span>`;
      drawerAlerts.appendChild(banner);
    });

    // Show results section
    drawerResults.classList.remove('hidden');

    // Draw Leaflet Route Map
    setTimeout(() => {
      renderDrawerMapRoute(data);
    }, 200);

    // Sync to main page commute map & cards
    state.sections['commute'] = { status: 'success', data };
    renderCommute({ status: 'success', data });

    showToast('Commute route updated! ✓', 'success');

  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    drawerSubmit.disabled = false;
    drawerSubmit.textContent = 'Get Live Route';
  }
}

drawerForm?.addEventListener('submit', e => {
  e.preventDefault();
  calculateDrawerRoute();
});

/* ──────────────────────────────────────────────────────────────
   CENTERED POPUP MAP MODAL
   ────────────────────────────────────────────────────────────── */
let _modalMap = null;
let _modalRouteLayer = null;
let _modalAltLayers = [];

function openMapModal() {
  const payload = state.sections['commute'];
  if (!payload || payload.status !== 'success' || !payload.data) {
    showToast('Run a commute briefing first.');
    return;
  }

  const data = payload.data;
  const origin = data.origin || {};
  const dest = data.dest || {};
  const polyline = data.polyline || [];

  const hasCoords = (
    typeof origin.lat === 'number' && typeof origin.lon === 'number' &&
    typeof dest.lat === 'number' && typeof dest.lon === 'number'
  );

  if (!hasCoords) return;

  mapModal?.classList.remove('hidden');

  setTimeout(() => {
    if (!_modalMap) {
      _modalMap = L.map('modal-map', {
        zoomControl: true,
        attributionControl: true,
        scrollWheelZoom: true,
      });
      L.tileLayer(_TILE_URL, {
        attribution: _TILE_ATTR,
        maxZoom: 19,
      }).addTo(_modalMap);
    }
    _modalMap.invalidateSize();

    // Clear previous layer
    if (_modalRouteLayer) {
      _modalRouteLayer.clearLayers();
    } else {
      _modalRouteLayer = L.layerGroup().addTo(_modalMap);
    }
    _modalAltLayers.forEach(l => _modalMap.removeLayer(l));
    _modalAltLayers = [];

    // Draw main route polyline
    if (polyline.length >= 2) {
      const routeLine = L.polyline(polyline, {
        color: '#7260c3',
        weight: 5,
        opacity: 0.85,
        lineJoin: 'round',
      }).addTo(_modalRouteLayer);

      _modalMap.fitBounds(routeLine.getBounds(), { padding: [40, 40] });
    } else {
      _modalMap.setView([origin.lat, origin.lon], 12);
    }

    // Draw alternates
    (data.alternates || []).forEach(alt => {
      if (!alt.polyline || alt.polyline.length < 2) return;
      const altLine = L.polyline(alt.polyline, {
        color: '#b4a9dd',
        weight: 3,
        opacity: 0.65,
        dashArray: '6 6',
      });
      altLine.bindTooltip(
        `${alt.mode.charAt(0).toUpperCase() + alt.mode.slice(1)}: ${alt.eta_minutes} min`,
        { sticky: true }
      );
      altLine.addTo(_modalMap);
      _modalAltLayers.push(altLine);
    });

    // Draw pins
    const originIcon = _ORIGIN_ICON || _makePinIcon('#7260c3');
    const destIcon = _DEST_ICON || _makePinIcon('#f06a9a');

    L.marker([origin.lat, origin.lon], { icon: originIcon })
      .bindPopup(`<b>Start</b><br>${origin.label || ''}`)
      .addTo(_modalRouteLayer);

    L.marker([dest.lat, dest.lon], { icon: destIcon })
      .bindPopup(`<b>Destination</b><br>${dest.label || ''}`)
      .addTo(_modalRouteLayer);

  }, 200);
}

function closeMapModal() {
  mapModal?.classList.add('hidden');
}

// Click live commute map to open centered modal (uses capture phase to bypass Leaflet's stopPropagation)
mapEl?.addEventListener('click', e => {
  if (e.target.closest('.leaflet-control')) return;
  const payload = state.sections['commute'];
  if (payload && payload.status === 'success' && payload.data) {
    openMapModal();
  }
}, true);

mapModalClose?.addEventListener('click', closeMapModal);
mapModalBackdrop?.addEventListener('click', closeMapModal);

// Wire up Clear History Button
$('clear-history-btn')?.addEventListener('click', clearAllHistory);


/* ════════════════════════════════════════════════════════════
   TRAVEL ITINERARY RENDERER & EMAIL SHARING
   ════════════════════════════════════════════════════════════ */
function renderItinerary(payload) {
  const card = $('itinerary-card');
  const container = $('itinerary-content');
  if (!card || !container) return;

  state.sections['itinerary'] = payload;

  if (payload.status === 'error') {
    card.classList.remove('hidden');
    container.innerHTML = `<div style="color: #f87171; padding: 12px;">Failed to generate itinerary: ${escHtml(payload.error?.message || 'Unknown error')}</div>`;
    return;
  }

  const d = payload.data || {};
  const days = d.days || [];
  const location = d.location || state.intent?.location || 'Destination';
  const daysCount = d.days_count || days.length || 3;
  const budget = (d.budget || state.intent?.budget || 'moderate').toUpperCase();
  const estimatedCost = d.estimated_cost || '';

  // Update card header title & subtitle in Ask view
  const titleEl = $('itinerary-title');
  if (titleEl) titleEl.textContent = `${location} Travel Itinerary`;
  const subEl = $('itinerary-subtitle');
  if (subEl) subEl.textContent = `${daysCount} Days • ${budget} Budget • FastMCP & NVIDIA NIM`;

  card.classList.remove('hidden');

  // Synchronize form inputs in Itinerary Planner view
  const destInput = $('itinerary-destination-input');
  if (destInput && location && location !== 'Destination') destInput.value = location;
  const daysSelect = $('itinerary-days-select');
  if (daysSelect && daysCount) {
    daysSelect.value = daysCount;
    document.querySelectorAll('#duration-pills .pill-btn').forEach(btn => {
      btn.classList.toggle('pill-active', btn.dataset.val == daysCount);
    });
  }
  const budgetSelect = $('itinerary-budget-select');
  if (budgetSelect && d.budget) {
    budgetSelect.value = d.budget.toLowerCase();
    document.querySelectorAll('#budget-pills .pill-btn').forEach(btn => {
      btn.classList.toggle('pill-active', btn.dataset.val.toLowerCase() === d.budget.toLowerCase());
    });
  }

  let html = `
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; background: var(--bg-2); border: 1px solid var(--border); padding: 10px 16px; border-radius: 8px; flex-wrap: wrap; gap: 8px;">
      <div style="display: flex; align-items: center; gap: 14px;">
        <div>
          <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Destination</span>
          <strong style="color: var(--text-1); font-size: 14px;">${escHtml(location)}</strong>
        </div>
        <div style="width: 1px; height: 20px; background: var(--border);"></div>
        <div>
          <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Pacing</span>
          <strong style="color: #a8a0cc; font-size: 14px;">${daysCount} Days</strong>
        </div>
        <div style="width: 1px; height: 20px; background: var(--border);"></div>
        <div>
          <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Budget</span>
          <strong style="color: #34d399; font-size: 14px;">${budget}</strong>
        </div>
      </div>
      <div style="background: rgba(124,92,252,0.15); color: var(--purple-light); border: 1px solid rgba(124,92,252,0.3); font-weight: 700; padding: 4px 12px; border-radius: 20px; font-size: 12.5px;">
        💰 ${escHtml(estimatedCost || '$100 - $180 / day')}
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 12px;">
  `;

  days.forEach(day => {
    html += `
      <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; transition: all 0.2s ease;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 8px;">
          <div style="font-weight: 700; color: var(--purple-light); font-size: 14px; display: flex; align-items: center; gap: 8px;">
            <span style="background: var(--purple); color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 800;">DAY ${day.day_number}</span>
            <span>${escHtml(day.theme)}</span>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 12.5px;">
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 10px 12px; border-radius: 6px;">
            <b style="color: #fbbf24; display: flex; align-items: center; gap: 6px;">🌅 Morning</b>
            <div style="color: var(--text-1); margin-top: 4px; line-height: 1.4;">${escHtml(day.morning?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 3px;">📍 ${escHtml(day.morning?.location || '')}</small>
          </div>
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 10px 12px; border-radius: 6px;">
            <b style="color: #60a5fa; display: flex; align-items: center; gap: 6px;">☀️ Afternoon</b>
            <div style="color: var(--text-1); margin-top: 4px; line-height: 1.4;">${escHtml(day.afternoon?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 3px;">📍 ${escHtml(day.afternoon?.location || '')}</small>
          </div>
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 10px 12px; border-radius: 6px;">
            <b style="color: #c084fc; display: flex; align-items: center; gap: 6px;">🌙 Evening</b>
            <div style="color: var(--text-1); margin-top: 4px; line-height: 1.4;">${escHtml(day.evening?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 3px;">📍 ${escHtml(day.evening?.location || '')}</small>
          </div>
        </div>
        <div style="margin-top: 10px; font-size: 12px; color: var(--text-2); background: rgba(0,0,0,0.18); padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border);">
          🍽️ <b>Dining:</b> &nbsp; Lunch: <span style="color: var(--text-1);">${escHtml(day.dining?.lunch || 'Local café')}</span> &nbsp;|&nbsp; Dinner: <span style="color: var(--text-1);">${escHtml(day.dining?.dinner || 'Neighborhood bistro')}</span>
        </div>
      </div>
    `;
  });

  if (d.travel_tips && d.travel_tips.length) {
    html += `
      <div style="background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.25); border-left: 4px solid #34d399; padding: 12px 16px; border-radius: 6px; font-size: 12.5px; margin-top: 6px;">
        <strong style="color: #34d399; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">💡 Local Travel Tips:</strong>
        <ul style="margin: 0; padding-left: 18px; color: var(--text-2); line-height: 1.5;">
          ${d.travel_tips.map(t => `<li>${escHtml(t)}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  html += `</div>`;
  container.innerHTML = html;
}

// Email Modal Controllers
const emailModal = $('email-modal');
const emailForm = $('email-share-form');
const btnShareEmail = $('btn-share-email');
const emailClose = $('email-modal-close');
const emailCancel = $('email-modal-cancel');
const emailBackdrop = $('email-modal-backdrop');

function openEmailModal() {
  emailModal?.classList.remove('hidden');
  $('email-recipient-input')?.focus();
}

function closeEmailModal() {
  emailModal?.classList.add('hidden');
}

btnShareEmail?.addEventListener('click', openEmailModal);
emailClose?.addEventListener('click', closeEmailModal);
emailCancel?.addEventListener('click', closeEmailModal);
emailBackdrop?.addEventListener('click', closeEmailModal);

emailForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const recipient = $('email-recipient-input')?.value?.trim();
  const subject = $('email-subject-input')?.value?.trim();
  const submitBtn = $('email-submit-btn');

  if (!recipient) return;

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
  }

  try {
    const itineraryData = state.sections['itinerary']?.data || {};
    const loc = itineraryData.location || state.intent?.location || 'Traveler';
    const res = await fetch('/api/share/email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_email: recipient,
        subject: subject || `Travel Itinerary for ${loc}`,
        session_id: state.sessionId,
        body_html: $('itinerary-content')?.innerHTML || `<p>Travel Itinerary for ${loc}</p>`,
        body_text: `Travel Itinerary for ${loc}`,
      }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast('Email sent via Gmail FastMCP Tool!', 'success');
      closeEmailModal();
    } else {
      showToast(`Email error: ${data.error || 'Failed to send'}`, 'error');
    }
  } catch (err) {
    showToast(`Failed to send email: ${err.message}`, 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send Email';
    }
  }
});


/* ── Shared Itinerary View Renderer & Controls ── */
function copyItineraryText() {
  const itData = state.sections['itinerary'];
  if (!itData || !itData.data) {
    showToast('No itinerary data to copy', 'error');
    return;
  }
  const d = itData.data;
  let text = `✈️ ITINERARY FOR ${(d.location || 'Destination').toUpperCase()} (${d.days_count || (d.days || []).length} DAYS)\n`;
  text += `Budget: ${(d.budget || 'moderate').toUpperCase()} (${d.estimated_cost || ''})\n\n`;
  (d.days || []).forEach(day => {
    text += `📅 DAY ${day.day_number}: ${day.theme}\n`;
    text += `  🌅 Morning: ${day.morning?.activity || ''} (${day.morning?.location || ''})\n`;
    text += `  ☀️ Afternoon: ${day.afternoon?.activity || ''} (${day.afternoon?.location || ''})\n`;
    text += `  🌙 Evening: ${day.evening?.activity || ''} (${day.evening?.location || ''})\n`;
    text += `  🍽️ Dining: Lunch: ${day.dining?.lunch || ''} | Dinner: ${day.dining?.dinner || ''}\n\n`;
  });
  if (d.travel_tips?.length) {
    text += `💡 Local Travel Tips:\n` + d.travel_tips.map(t => `- ${t}`).join('\n');
  }
  navigator.clipboard.writeText(text).then(() => {
    showToast('Itinerary copied to clipboard! 📋', 'success');
  }).catch(() => {
    showToast('Could not copy to clipboard', 'error');
  });
}

function filterItineraryDay(dayNum) {
  document.querySelectorAll('.day-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.day == dayNum);
  });
  document.querySelectorAll('.itinerary-day-card').forEach(card => {
    if (dayNum === 'all' || card.dataset.day == dayNum) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
}

function renderItineraryInView(itData, intent) {
  const resultBox = $('view-itinerary-result');
  if (!resultBox) return;

  resultBox.classList.remove('hidden');
  state.sections['itinerary'] = itData;

  if (itData.status === 'error') {
    resultBox.innerHTML = `
      <article class="card hero-card" style="border: 1px solid rgba(239,68,68,0.3); padding: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
          <div style="color: #f87171; font-size: 14px; font-weight: 600;">⚠️ Failed to generate itinerary: ${escHtml(itData.error?.message || itData.error || 'Unknown error')}</div>
          <button class="btn btn-sm" onclick="generateItinerary()" style="background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 600;">
            Retry
          </button>
        </div>
      </article>
    `;
    return;
  }

  const d = itData.data || {};
  const location = d.location || intent?.location || 'Destination';
  const daysCount = d.days_count || (d.days || []).length || 3;
  const budget = d.budget || intent?.budget || 'moderate';
  const estimatedCost = d.estimated_cost || '';
  const daysList = d.days || [];

  let dayTabsHtml = `<div class="day-filter-bar">`;
  dayTabsHtml += `<button type="button" class="day-tab active" data-day="all" onclick="filterItineraryDay('all')">✨ All Days (${daysCount})</button>`;
  daysList.forEach(day => {
    dayTabsHtml += `<button type="button" class="day-tab" data-day="${day.day_number}" onclick="filterItineraryDay(${day.day_number})">Day ${day.day_number}</button>`;
  });
  dayTabsHtml += `</div>`;

  resultBox.innerHTML = `
    <article class="card hero-card" style="border: 1px solid rgba(124,92,252,0.35); padding: 0; overflow: hidden; margin-top: 10px;">
      
      <!-- Top Header & Actions -->
      <div style="padding: 20px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; background: rgba(124,92,252,0.07);">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 26px;">✈️</span>
          <div>
            <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #fff;">${escHtml(location)} Travel Itinerary</h2>
            <small style="color: var(--text-2); font-size: 12px;">${daysCount} Days &bull; ${budget.toUpperCase()} Budget &bull; Curated by FastMCP &amp; NVIDIA NIM</small>
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <button type="button" class="btn-action-ghost" onclick="copyItineraryText()" title="Copy formatted itinerary to clipboard">
            <span>📋</span>
            <span>Copy</span>
          </button>
          <button class="btn btn-sm" onclick="openEmailModal()" type="button" style="display: inline-flex; align-items: center; gap: 6px; background: var(--grad-purple); color: white; border: none; padding: 7px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; box-shadow: var(--shadow-purple);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            Send via Gmail MCP
          </button>
        </div>
      </div>

      <div style="padding: 20px 24px;">
        
        <!-- Summary Stats Banner -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; background: var(--bg-2); border: 1px solid var(--border); padding: 12px 18px; border-radius: var(--r-sm); flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div>
              <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Destination</span>
              <strong style="color: var(--text-1); font-size: 14px;">${escHtml(location)}</strong>
            </div>
            <div style="width: 1px; height: 24px; background: var(--border);"></div>
            <div>
              <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Pacing</span>
              <strong style="color: #a8a0cc; font-size: 14px;">${daysCount} Days Planned</strong>
            </div>
            <div style="width: 1px; height: 24px; background: var(--border);"></div>
            <div>
              <span style="font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-3); display: block;">Budget Tier</span>
              <strong style="color: #34d399; font-size: 14px;">${budget.toUpperCase()}</strong>
            </div>
          </div>
          <div style="background: rgba(124,92,252,0.18); color: var(--purple-light); border: 1px solid rgba(124,92,252,0.35); font-weight: 700; padding: 6px 14px; border-radius: 20px; font-size: 13px;">
            💰 ${escHtml(estimatedCost || '$100 - $180 / day')}
          </div>
        </div>

        <!-- Day Filter Tabs -->
        ${dayTabsHtml}

        <!-- Day List -->
        <div id="view-itinerary-card-body" style="display: flex; flex-direction: column; gap: 14px;"></div>
      </div>
    </article>
  `;

  const bodyEl = $('view-itinerary-card-body');
  if (!bodyEl) return;

  let html = '';
  daysList.forEach(day => {
    html += `
      <div class="itinerary-day-card" data-day="${day.day_number}" style="background: var(--bg-2); border: 1px solid var(--border); border-radius: 12px; padding: 18px; transition: all 0.2s ease;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 10px;">
          <div style="font-weight: 700; color: var(--purple-light); font-size: 15px; display: flex; align-items: center; gap: 8px;">
            <span style="background: var(--purple); color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 800;">DAY ${day.day_number}</span>
            <span>${escHtml(day.theme)}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; font-size: 13px;">
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 12px 14px; border-radius: 8px;">
            <b style="color: #fbbf24; display: flex; align-items: center; gap: 6px;">🌅 Morning</b>
            <div style="color: var(--text-1); margin-top: 6px; line-height: 1.4;">${escHtml(day.morning?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 4px;">📍 ${escHtml(day.morning?.location || '')}</small>
          </div>
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 12px 14px; border-radius: 8px;">
            <b style="color: #60a5fa; display: flex; align-items: center; gap: 6px;">☀️ Afternoon</b>
            <div style="color: var(--text-1); margin-top: 6px; line-height: 1.4;">${escHtml(day.afternoon?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 4px;">📍 ${escHtml(day.afternoon?.location || '')}</small>
          </div>
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 12px 14px; border-radius: 8px;">
            <b style="color: #c084fc; display: flex; align-items: center; gap: 6px;">🌙 Evening</b>
            <div style="color: var(--text-1); margin-top: 6px; line-height: 1.4;">${escHtml(day.evening?.activity || '')}</div>
            <small style="color: var(--text-3); display: block; margin-top: 4px;">📍 ${escHtml(day.evening?.location || '')}</small>
          </div>
        </div>

        <div style="margin-top: 14px; font-size: 12.5px; color: var(--text-2); background: rgba(0,0,0,0.2); padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border);">
          🍽️ <b>Dining:</b> &nbsp; Lunch: <span style="color: var(--text-1);">${escHtml(day.dining?.lunch || 'Local specialty café')}</span> &nbsp;|&nbsp; Dinner: <span style="color: var(--text-1);">${escHtml(day.dining?.dinner || 'Authentic regional restaurant')}</span>
        </div>
      </div>
    `;
  });

  if (d.travel_tips && d.travel_tips.length) {
    html += `
      <div style="background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.25); border-left: 4px solid #34d399; padding: 14px 18px; border-radius: 8px; font-size: 13px; margin-top: 8px;">
        <strong style="color: #34d399; display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-size: 14px;">💡 Local Travel Tips &amp; Insights:</strong>
        <ul style="margin: 0; padding-left: 20px; color: var(--text-2); line-height: 1.6;">
          ${d.travel_tips.map(t => `<li>${escHtml(t)}</li>`).join('')}
        </ul>
      </div>
    `;
  }
  bodyEl.innerHTML = html;
}

/* ── Itinerary Planner View Controller ── */
async function generateItinerary() {
  const destInput = $('itinerary-destination-input');
  const dest = destInput?.value?.trim();
  const days = $('itinerary-days-select')?.value || '3';
  const budget = $('itinerary-budget-select')?.value || 'moderate';
  const genBtn = $('btn-generate-itinerary');
  const resultBox = $('view-itinerary-result');

  if (!dest) {
    if (destInput) {
      destInput.style.borderColor = '#ef4444';
      destInput.focus();
      setTimeout(() => { if (destInput) destInput.style.borderColor = ''; }, 2500);
    }
    showToast('Please enter a destination city or country.', 'error');
    return;
  }

  // Visual button loading state
  if (genBtn) {
    genBtn.disabled = true;
    genBtn.innerHTML = '<span class="spinner-sm"></span> <span>Generating Itinerary…</span>';
  }

  // Show immediate animated loading skeleton card in resultBox
  if (resultBox) {
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = `
      <article class="card hero-card" style="border: 1px solid rgba(124,92,252,0.35); padding: 24px; margin-top: 10px;">
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
          <div class="spinner-sm" style="width: 24px; height: 24px; border-width: 3px; border-top-color: #7c5cfc;"></div>
          <div>
            <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #fff;">Crafting custom itinerary for ${escHtml(dest)}…</h3>
            <small style="color: var(--text-2);">${days} Days · ${budget.toUpperCase()} Budget · Consulting FastMCP &amp; NVIDIA NIM LLM</small>
          </div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div class="skeleton-line skeleton-shimmer" style="height: 48px; border-radius: 8px;"></div>
          <div class="skeleton-line skeleton-shimmer" style="height: 110px; border-radius: 8px;"></div>
          <div class="skeleton-line skeleton-shimmer" style="height: 110px; border-radius: 8px;"></div>
        </div>
      </article>
    `;
  }

  try {
    let itData = null;
    let intent = { location: dest, budget, days: parseInt(days) };

    // Try dedicated /api/itinerary direct endpoint first
    try {
      const res = await fetch('/api/itinerary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: dest, days: parseInt(days), budget }),
      });
      if (res.ok) {
        const directPayload = await res.json();
        if (directPayload && directPayload.status !== 'error') {
          itData = directPayload.section === 'itinerary' ? directPayload : { section: 'itinerary', status: 'success', data: directPayload.data || directPayload };
        }
      }
    } catch { }

    // Fallback to /api/briefing if direct endpoint didn't fulfill
    if (!itData || itData.status === 'error') {
      const q = `plan a trip to ${dest} for ${days} days in a ${budget} budget.`;
      const res = await fetch('/api/briefing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.error || 'Failed to generate itinerary');
      itData = payload.sections?.itinerary || { status: 'error', error: { message: 'No itinerary section generated' } };
      if (payload.intent) intent = payload.intent;
    }

    // 1. Render in Itinerary Planner view
    renderItineraryInView(itData, intent);

    // 2. Synchronize to the Travel Itinerary card in Ask view
    renderItinerary(itData);

    // 3. Update global intent and chips
    if (state.intent) {
      state.intent.location = dest;
      state.intent.days = parseInt(days);
      state.intent.budget = budget;
      if (!state.intent.sections) state.intent.sections = [];
      if (!state.intent.sections.includes('itinerary')) state.intent.sections.push('itinerary');
      renderIntentChips(state.intent);
    }

    showToast(`${dest} itinerary updated across all views! ✓`, 'success');

  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = `
        <article class="card hero-card" style="border: 1px solid rgba(239,68,68,0.3); padding: 24px; margin-top: 10px;">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div style="color: #f87171; font-size: 14px; font-weight: 600;">⚠️ Failed to generate itinerary: ${escHtml(err.message)}</div>
            <button class="btn btn-sm" onclick="generateItinerary()" style="background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 600;">
              Retry
            </button>
          </div>
        </article>
      `;
    }
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    if (genBtn) {
      genBtn.disabled = false;
      genBtn.innerHTML = '<span class="btn-icon">✦</span> <span class="btn-text">Generate Itinerary</span>';
    }
  }
}

/* ── Wire Itinerary Events ── */
$('itinerary-planner-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  generateItinerary();
});

$('btn-generate-itinerary')?.addEventListener('click', e => {
  if (e.target.closest('form')) return;
  generateItinerary();
});

// Destination Preset Chips
document.querySelectorAll('.dest-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = $('itinerary-destination-input');
    if (input && btn.dataset.dest) {
      input.value = btn.dataset.dest;
      input.focus();
      showToast(`Selected ${btn.dataset.dest}`, 'info');
    }
  });
});

// Duration Pills
document.querySelectorAll('#duration-pills .pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#duration-pills .pill-btn').forEach(b => b.classList.remove('pill-active'));
    btn.classList.add('pill-active');
    const input = $('itinerary-days-select');
    if (input) input.value = btn.dataset.val;
  });
});

// Budget Pills
document.querySelectorAll('#budget-pills .pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#budget-pills .pill-btn').forEach(b => b.classList.remove('pill-active'));
    btn.classList.add('pill-active');
    const input = $('itinerary-budget-select');
    if (input) input.value = btn.dataset.val;
  });
});
