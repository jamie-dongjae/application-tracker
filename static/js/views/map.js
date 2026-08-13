// Map view: MapLibre + CARTO tiles, clustered status-colored pins,
// filter sidebar, dossier panel, unmapped tray, geocode backfill.

import { api } from '../api.js';
import { state, STATUSES, STATUS_COLORS, NEXT_STATUS, getApp, patchApplication, undo, esc, fmtDate } from '../state.js';
import { openDetail } from '../components/detail.js';
import { toast } from '../components/toast.js';
import { statusFx } from '../components/fx.js';

const STATUS_HEX = {
  'Wishlist': '#94a2c4', 'Applied': '#e5aa3f', 'Interview': '#5fb2f2',
  'Offer': '#3ecf95', 'Rejected': '#f0647d', 'Withdrawn': '#66759b',
};

// Hyperreal space view: satellite imagery on a globe with atmosphere.
// Esri World Imagery + CARTO label overlay — free with attribution.
const SPACE_STYLE = {
  version: 8,
  projection: { type: 'globe' },
  glyphs: 'https://tiles.basemaps.cartocdn.com/fonts/{fontstack}/{range}.pbf',
  sky: {
    'sky-color': '#02060f',
    'horizon-color': '#1b4468',
    'fog-color': '#0a1c2e',
    'sky-horizon-blend': 0.6,
    'horizon-fog-blend': 0.6,
    'fog-ground-blend': 0.85,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 6, 0.4, 10, 0],
  },
  sources: {
    satellite: {
      type: 'raster',
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© Esri, Maxar, Earthstar Geographics',
    },
    labels: {
      type: 'raster',
      tiles: ['https://basemaps.cartocdn.com/rastertiles/dark_only_labels/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© CARTO © OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#01030a' } },
    { id: 'satellite', type: 'raster', source: 'satellite',
      paint: { 'raster-fade-duration': 250, 'raster-saturation': 0.08, 'raster-contrast': 0.04 } },
    { id: 'labels', type: 'raster', source: 'labels', minzoom: 3.5, paint: { 'raster-opacity': 0.9 } },
  ],
};

let map = null;

function mapped() { return state.apps.filter((a) => a.latitude !== '' && a.longitude !== '' && a.latitude != null); }

function unmapped() {
  return state.apps.filter((a) => (a.latitude === '' || a.latitude == null) && a.geo_status !== 'remote');
}

function passesFilter(a) {
  const f = state.mapFilter;
  if (f.statuses.size && !f.statuses.has(a.status)) return false;
  if (f.query) {
    const q = f.query.toLowerCase();
    if (!`${a.company} ${a.title} ${a.location}`.toLowerCase().includes(q)) return false;
  }
  return true;
}

function toGeoJSON() {
  // Spread identical coordinates in a tiny ring so stacked pins stay clickable.
  const seen = new Map();
  return {
    type: 'FeatureCollection',
    features: mapped().filter(passesFilter).map((a) => {
      const key = `${a.latitude},${a.longitude}`;
      const n = seen.get(key) || 0;
      seen.set(key, n + 1);
      const jitter = n === 0 ? [0, 0]
        : [Math.cos(n * 2.4) * 0.004 * Math.ceil(n / 8), Math.sin(n * 2.4) * 0.003 * Math.ceil(n / 8)];
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [a.longitude + jitter[0], a.latitude + jitter[1]] },
        properties: { id: a.id, status: a.status, company: a.company },
      };
    }),
  };
}

export function renderMap(el) {
  if (!el.dataset.built) {
    el.dataset.built = '1';
    el.innerHTML = `
      <div class="map-wrap"><div id="map"></div></div>
      <div class="map-panel map-stats" id="map-stats"></div>
      <div class="map-panel map-side">
        <input id="map-q" placeholder="Filter companies…" autocomplete="off">
        <div class="filter-chips" id="map-chips"></div>
        <div class="row-list" id="map-list"></div>
        <div id="map-unmapped"></div>
      </div>
      <div class="map-panel map-dossier" id="map-dossier" hidden></div>`;
    el.querySelector('#map-q').addEventListener('input', (e) => {
      state.mapFilter.query = e.target.value;
      refreshMapData(el);
    });
  }
  buildMapOnce(el);
  refreshMapData(el);
  // The container may have been laid out after map construction (hash
  // navigation inserts it in the same frame) — force a resize next frame.
  if (map) requestAnimationFrame(() => map && map.resize());
}

function buildMapOnce(el) {
  if (map) return;
  if (typeof maplibregl === 'undefined') {
    el.querySelector('#map').innerHTML = '<div class="empty" style="padding-top:40vh">Map library failed to load (offline?).</div>';
    return;
  }
  const cinematic = !matchMedia('(prefers-reduced-motion: reduce)').matches;
  map = new maplibregl.Map({
    container: el.querySelector('#map'),
    style: SPACE_STYLE,
    // Start out in space; the load handler flies down to the pins.
    center: [40, 24],
    zoom: cinematic ? 0.8 : 2.4,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');


  map.on('load', () => {
    map.addSource('apps', { type: 'geojson', data: toGeoJSON(), cluster: true, clusterRadius: 42 });
    map.addLayer({
      id: 'clusters', type: 'circle', source: 'apps', filter: ['has', 'point_count'],
      paint: {
        'circle-color': 'rgba(77,214,255,.16)',
        'circle-stroke-color': '#4dd6ff',
        'circle-stroke-width': 1.2,
        'circle-radius': ['step', ['get', 'point_count'], 14, 10, 19, 30, 25],
      },
    });
    map.addLayer({
      id: 'cluster-count', type: 'symbol', source: 'apps', filter: ['has', 'point_count'],
      layout: { 'text-field': '{point_count_abbreviated}', 'text-size': 11, 'text-font': ['Open Sans Semibold'] },
      paint: { 'text-color': '#eaf2ff' },
    });
    map.addLayer({
      id: 'pins', type: 'circle', source: 'apps', filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['match', ['get', 'status'],
          ...Object.entries(STATUS_HEX).flat(), '#94a2c4'],
        'circle-radius': 5.5,
        'circle-stroke-color': 'rgba(255,255,255,.9)',
        'circle-stroke-width': 1.4,
      },
    });

    map.on('click', 'pins', (e) => {
      const id = e.features[0].properties.id;
      showDossier(document.getElementById('view-map'), Number(id));
    });
    map.on('click', 'clusters', async (e) => {
      const feature = e.features[0];
      const zoom = await map.getSource('apps').getClusterExpansionZoom(feature.properties.cluster_id);
      map.easeTo({ center: feature.geometry.coordinates, zoom });
    });
    map.on('mouseenter', 'pins', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'pins', () => { map.getCanvas().style.cursor = ''; });
    map.resize();
    // Cinematic approach: hold the full globe for a beat, then descend to the pins.
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) frameAll(0);
    else setTimeout(() => frameAll(3200), 600);
  });
}

export function refreshMapData(el) {
  if (map && map.getSource('apps')) map.getSource('apps').setData(toGeoJSON());
  paintStats(el);
  paintChips(el);
  paintList(el);
  paintUnmapped(el);
  // Keep an open dossier in sync with fresh data (e.g. after undo).
  const dossier = el.querySelector('#map-dossier');
  if (dossier && !dossier.hidden && dossierId != null) showDossier(el, dossierId);
}

let dossierId = null;

function paintStats(el) {
  const total = state.apps.length;
  const activeN = state.apps.filter((a) => ['Applied', 'Interview'].includes(a.status)).length;
  const offers = state.apps.filter((a) => a.status === 'Offer').length;
  const rejected = state.apps.filter((a) => a.status === 'Rejected').length;
  el.querySelector('#map-stats').innerHTML =
    `<span><b>${total}</b> TRACKED</span><span><b>${activeN}</b> ACTIVE</span>` +
    `<span><b>${offers}</b> OFFERS</span><span><b>${rejected}</b> REJECTED</span>` +
    `<span class="link" id="map-frame">FRAME ALL</span>`;
  el.querySelector('#map-frame').onclick = () => frameAll();
}

function paintChips(el) {
  const box = el.querySelector('#map-chips');
  box.innerHTML = STATUSES.map((s) => `
    <span class="chip ${state.mapFilter.statuses.has(s) ? 'on' : ''}" data-s="${esc(s)}">${esc(s)}</span>`).join('');
  box.querySelectorAll('.chip').forEach((chip) => {
    chip.onclick = () => {
      const s = chip.dataset.s;
      state.mapFilter.statuses.has(s) ? state.mapFilter.statuses.delete(s) : state.mapFilter.statuses.add(s);
      refreshMapData(el);
    };
  });
}

function paintList(el) {
  const rows = state.apps.filter(passesFilter);
  el.querySelector('#map-list').innerHTML = rows.map((a) => `
    <div class="row-item" data-id="${a.id}">
      <span class="dot" style="background:${STATUS_COLORS[a.status] || 'var(--s-wishlist)'}"></span>
      <div class="row-main">
        <div class="row-title">${esc(a.company)}</div>
        <div class="row-sub">${esc(a.title)}${a.location ? ' · ' + esc(a.location) : ''}</div>
      </div>
    </div>`).join('') || '<div class="empty">No matches.</div>';
  el.querySelectorAll('#map-list .row-item').forEach((row) => {
    row.onclick = () => {
      const app = getApp(Number(row.dataset.id));
      if (app && app.latitude !== '' && map) {
        map.flyTo({ center: [app.longitude, app.latitude], zoom: Math.max(map.getZoom(), 8) });
      }
      showDossier(el, Number(row.dataset.id));
    };
  });
}

function paintUnmapped(el) {
  const rows = unmapped();
  const noLoc = rows.filter((a) => !(a.location || '').trim());
  const failed = rows.filter((a) => (a.location || '').trim() && a.geo_status !== 'remote');
  const remote = state.apps.filter((a) => a.geo_status === 'remote').length;
  el.querySelector('#map-unmapped').innerHTML = `
    <hr class="sep">
    <div class="faint" style="font-size:11.5px;display:flex;gap:8px;align-items:center">
      <span>Unmapped <b class="num">${rows.length}</b>${remote ? ` · remote ${remote}` : ''}</span>
      <span class="spacer"></span>
      ${failed.length ? `<span class="link" id="map-backfill">geocode ${failed.length}</span>` : ''}
    </div>
    ${noLoc.length ? `<div class="faint" style="font-size:11px;margin-top:6px">${noLoc.length} without a location — click any card and add one.</div>` : ''}`;
  const btn = el.querySelector('#map-backfill');
  if (btn) btn.onclick = runBackfill;
}

async function runBackfill() {
  await api.post('/api/geocode/backfill');
  toast('Geocoding started — pins appear as locations resolve.');
  const poll = setInterval(async () => {
    const status = await api.get('/api/geocode/backfill/status');
    if (!status.running) {
      clearInterval(poll);
      const { refreshApps } = await import('../state.js');
      await refreshApps();
      toast(`Geocoding done: ${status.ok}/${status.total} resolved${status.failed.length ? `, ${status.failed.length} not found` : ''}.`);
    }
  }, 2500);
}

document.addEventListener('apptracker:backfill', runBackfill);

function showDossier(el, id) {
  const app = getApp(id);
  const box = el.querySelector('#map-dossier');
  if (!app) { box.hidden = true; dossierId = null; return; }
  box.hidden = false;
  dossierId = id;
  box.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px">
      <span class="dot" style="background:${STATUS_COLORS[app.status]}"></span>
      <b style="flex:1">${esc(app.company)}</b>
      <button class="close-x" id="dossier-x">✕</button>
    </div>
    <div class="muted" style="margin:4px 0 10px">${esc(app.title)}</div>
    <div class="row-list" style="font-size:12.5px">
      <div class="row-item" style="cursor:default"><span class="faint">Status</span><span class="spacer"></span>
        <select id="dossier-status" style="width:auto;padding:3px 8px;font-size:12.5px">
          ${STATUSES.map((s) => `<option ${s === app.status ? 'selected' : ''}>${esc(s)}</option>`).join('')}
        </select>
      </div>
      <div class="row-item" style="cursor:default"><span class="faint">Applied</span><span class="spacer"></span><span class="num">${esc(fmtDate(app.date_applied))}</span></div>
      ${app.location ? `<div class="row-item" style="cursor:default"><span class="faint">Location</span><span class="spacer"></span>${esc(app.location)}</div>` : ''}
      ${app.work_type ? `<div class="row-item" style="cursor:default"><span class="faint">Work type</span><span class="spacer"></span>${esc(app.work_type)}</div>` : ''}
      ${app.sponsorship ? `<div class="row-item" style="cursor:default"><span class="faint">Sponsorship</span><span class="spacer"></span>${esc(app.sponsorship)}</div>` : ''}
      ${app.source ? `<div class="row-item" style="cursor:default"><span class="faint">Source</span><span class="spacer"></span>${esc(app.source)}</div>` : ''}
    </div>
    <div class="dossier-actions">
      ${NEXT_STATUS[app.status] ? `<button class="ghost-btn grow" id="dossier-adv">▸ ${esc(NEXT_STATUS[app.status])}</button>` : ''}
      ${['Rejected', 'Withdrawn'].includes(app.status)
        ? `<button class="ghost-btn grow" id="dossier-revive">↩ Revive</button>`
        : `<button class="danger-btn" id="dossier-rej" title="Mark rejected">✕ Reject</button>`}
    </div>
    <div class="dossier-actions">
      ${app.url ? `<a class="ghost-btn" href="${esc(app.url)}" target="_blank" rel="noopener">Posting ↗</a>` : ''}
      <span class="spacer"></span>
      <button class="accent-btn" id="dossier-open">Details</button>
    </div>`;
  box.querySelector('#dossier-x').onclick = () => { box.hidden = true; dossierId = null; };
  box.querySelector('#dossier-open').onclick = () => openDetail(id);
  const move = async (to) => {
    const from = app.status;
    if (from === to) return;
    statusFx(box, to);
    try {
      await patchApplication(id, { status: to }, { optimistic: true });
      toast(`${app.company}: ${from} → ${to}`, { action: 'Undo', onAction: async () => { await undo(); } });
      showDossier(el, id);
    } catch (err) {
      if (err.status !== 409) toast('Change failed. ' + err.message, { error: true });
    }
  };
  box.querySelector('#dossier-status').onchange = (e) => move(e.target.value);
  const adv = box.querySelector('#dossier-adv');
  if (adv) adv.onclick = () => move(NEXT_STATUS[app.status]);
  const rej = box.querySelector('#dossier-rej');
  if (rej) rej.onclick = () => move('Rejected');
  const revive = box.querySelector('#dossier-revive');
  if (revive) revive.onclick = () => move('Applied');
}

function frameAll(duration = 900) {
  if (!map) return;
  const features = toGeoJSON().features;
  if (!features.length) return;
  const lons = features.map((f) => f.geometry.coordinates[0]);
  const lats = features.map((f) => f.geometry.coordinates[1]);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: 90, maxZoom: 10, duration, essential: false });
}

export function onThemeChange() {
  // The space view is theme-independent — nothing to rebuild.
}
