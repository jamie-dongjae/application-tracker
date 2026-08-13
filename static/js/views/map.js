// Map view: MapLibre + CARTO tiles, clustered status-colored pins,
// filter sidebar, dossier panel, unmapped tray, geocode backfill.

import { api } from '../api.js';
import { state, STATUSES, STATUS_COLORS, NEXT_STATUS, getApp, patchApplication, undo, esc, fmtDate } from '../state.js';
import { openDetail } from '../components/detail.js';
import { toast } from '../components/toast.js';
import { statusFx } from '../components/fx.js';

const STATUS_HEX = {
  'Wishlist': '#8d9ab9', 'Applied': '#d9a441', 'Interview': '#5aa7e8',
  'Offer': '#46c98d', 'Rejected': '#e05c6e', 'Withdrawn': '#5c6a89',
};

const STYLE = {
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
};

let map = null;
let mapTheme = null;

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
  const theme = document.documentElement.dataset.theme || 'dark';
  if (map && mapTheme === theme) return;
  if (map) { map.remove(); map = null; }
  if (typeof maplibregl === 'undefined') {
    el.querySelector('#map').innerHTML = '<div class="empty" style="padding-top:40vh">Map library failed to load (offline?).</div>';
    return;
  }
  mapTheme = theme;
  map = new maplibregl.Map({
    container: el.querySelector('#map'),
    style: STYLE[theme],
    center: [8, 50],
    zoom: 3.4,
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
      paint: { 'text-color': theme === 'dark' ? '#dce5f5' : '#182136' },
    });
    map.addLayer({
      id: 'pins', type: 'circle', source: 'apps', filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['match', ['get', 'status'],
          ...Object.entries(STATUS_HEX).flat(), '#8d9ab9'],
        'circle-radius': ['case', ['==', ['get', 'id'], ['literal', -1]], 8, 5.5],
        'circle-stroke-color': 'rgba(0,0,0,.5)',
        'circle-stroke-width': 1,
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
    frameAll();
  });
}

export function refreshMapData(el) {
  if (map && map.getSource('apps')) map.getSource('apps').setData(toGeoJSON());
  paintStats(el);
  paintChips(el);
  paintList(el);
  paintUnmapped(el);
}

function paintStats(el) {
  const total = state.apps.length;
  const activeN = state.apps.filter((a) => ['Applied', 'Interview'].includes(a.status)).length;
  const offers = state.apps.filter((a) => a.status === 'Offer').length;
  const rejected = state.apps.filter((a) => a.status === 'Rejected').length;
  el.querySelector('#map-stats').innerHTML =
    `<span><b>${total}</b> TRACKED</span><span><b>${activeN}</b> ACTIVE</span>` +
    `<span><b>${offers}</b> OFFERS</span><span><b>${rejected}</b> REJECTED</span>` +
    `<span class="link" id="map-frame">FRAME ALL</span>`;
  el.querySelector('#map-frame').onclick = frameAll;
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
  if (!app) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px">
      <span class="dot" style="background:${STATUS_COLORS[app.status]}"></span>
      <b style="flex:1">${esc(app.company)}</b>
      <button class="close-x" id="dossier-x">✕</button>
    </div>
    <div class="muted" style="margin:4px 0 10px">${esc(app.title)}</div>
    <div class="row-list" style="font-size:12.5px">
      <div class="row-item" style="cursor:default"><span class="faint">Status</span><span class="spacer"></span>${esc(app.status)}</div>
      <div class="row-item" style="cursor:default"><span class="faint">Applied</span><span class="spacer"></span><span class="num">${esc(fmtDate(app.date_applied))}</span></div>
      ${app.location ? `<div class="row-item" style="cursor:default"><span class="faint">Location</span><span class="spacer"></span>${esc(app.location)}</div>` : ''}
      ${app.work_type ? `<div class="row-item" style="cursor:default"><span class="faint">Work type</span><span class="spacer"></span>${esc(app.work_type)}</div>` : ''}
      ${app.sponsorship ? `<div class="row-item" style="cursor:default"><span class="faint">Sponsorship</span><span class="spacer"></span>${esc(app.sponsorship)}</div>` : ''}
      ${app.source ? `<div class="row-item" style="cursor:default"><span class="faint">Source</span><span class="spacer"></span>${esc(app.source)}</div>` : ''}
    </div>
    <div style="display:flex;gap:8px;margin-top:12px">
      ${NEXT_STATUS[app.status] ? `<button class="ghost-btn" id="dossier-adv">▸ ${esc(NEXT_STATUS[app.status])}</button>` : ''}
      ${!['Rejected', 'Withdrawn'].includes(app.status) ? `<button class="danger-btn" id="dossier-rej" style="padding:6px 10px">✕</button>` : ''}
      <span class="spacer"></span>
      ${app.url ? `<a class="ghost-btn" href="${esc(app.url)}" target="_blank" rel="noopener">Posting ↗</a>` : ''}
      <button class="accent-btn" id="dossier-open">Details</button>
    </div>`;
  box.querySelector('#dossier-x').onclick = () => { box.hidden = true; };
  box.querySelector('#dossier-open').onclick = () => openDetail(id);
  const move = async (to) => {
    statusFx(box, to);
    try {
      await patchApplication(id, { status: to }, { optimistic: true });
      toast(`${app.company}: ${app.status} → ${to}`, { action: 'Undo', onAction: async () => { await undo(); } });
      showDossier(el, id);
    } catch (err) {
      if (err.status !== 409) toast('Change failed. ' + err.message, { error: true });
    }
  };
  const adv = box.querySelector('#dossier-adv');
  if (adv) adv.onclick = () => move(NEXT_STATUS[app.status]);
  const rej = box.querySelector('#dossier-rej');
  if (rej) rej.onclick = () => move('Rejected');
}

function frameAll() {
  if (!map) return;
  const features = toGeoJSON().features;
  if (!features.length) return;
  const lons = features.map((f) => f.geometry.coordinates[0]);
  const lats = features.map((f) => f.geometry.coordinates[1]);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: 90, maxZoom: 10, duration: 700 });
}

export function onThemeChange(el) {
  if (state.view === 'map') { mapTheme = null; buildMapOnce(el); }
  else mapTheme = null;
}
