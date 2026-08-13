// Boot, hash routing, keyboard shortcuts, theme.

import { loadAll, subscribe, state, undo } from './state.js';
import { openAddFlow, isOpen as isModalOpen } from './components/addflow.js';
import { openPalette, isPaletteOpen } from './components/palette.js';
import { isDetailOpen, closeDetail } from './components/detail.js';
import { isSoundOn, toggleSound } from './components/fx.js';
import { isMusicOn, toggleMusic } from './components/music.js';
import { enterView } from './components/motion.js';
import { toast } from './components/toast.js';
import { renderDashboard } from './views/dashboard.js';
import { renderPipeline } from './views/pipeline.js';
import { renderMap, refreshMapData, onThemeChange } from './views/map.js';
import { renderInsights } from './views/analytics.js';
import { renderPrep } from './views/prep.js';

const VIEWS = {
  dashboard: renderDashboard,
  pipeline: renderPipeline,
  map: renderMap,
  insights: renderInsights,
  prep: renderPrep,
};

function currentView() {
  const name = (location.hash || '#/dashboard').replace('#/', '');
  return VIEWS[name] ? name : 'dashboard';
}

let lastAnimatedView = null;

function renderCurrent() {
  const name = currentView();
  state.view = name;
  document.querySelectorAll('.view').forEach((sec) => { sec.hidden = sec.id !== `view-${name}`; });
  document.querySelectorAll('.nav a').forEach((a) => {
    a.setAttribute('aria-selected', a.dataset.view === name ? 'true' : 'false');
  });
  const el = document.getElementById(`view-${name}`);
  VIEWS[name](el);
  // Entrance motion only on navigation — data refreshes re-render in place.
  if (name !== lastAnimatedView) {
    lastAnimatedView = name;
    enterView(el, name);
  }
}

// ---- theme ----

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('apptracker-theme', theme);
  onThemeChange(document.getElementById('view-map'));
  if (state.view === 'map') renderCurrent();
}

document.getElementById('theme-btn').onclick = () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
};

const soundBtn = document.getElementById('sound-btn');
function paintSoundBtn() {
  soundBtn.style.opacity = isSoundOn() ? '' : '.4';
  soundBtn.title = isSoundOn() ? 'Sound effects on — click to mute' : 'Sound effects off';
}
soundBtn.onclick = () => { toggleSound(); paintSoundBtn(); };
paintSoundBtn();

const musicBtn = document.getElementById('music-btn');
function paintMusicBtn() {
  musicBtn.style.opacity = isMusicOn() ? '' : '.4';
  musicBtn.title = isMusicOn() ? 'Music on — click to stop' : 'Background music (generated live)';
}
musicBtn.onclick = () => { toggleMusic(); paintMusicBtn(); };
paintMusicBtn();

// ---- global wiring ----

document.getElementById('new-btn').onclick = () => openAddFlow();
document.getElementById('palette-btn').onclick = () => openPalette();

window.addEventListener('hashchange', renderCurrent);

subscribe(() => {
  // Re-render the active view whenever data changes; map refreshes in place.
  if (state.view === 'map') refreshMapData(document.getElementById('view-map'));
  else renderCurrent();
});

document.addEventListener('keydown', (e) => {
  const tag = document.activeElement?.tagName;
  const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

  if (e.key === 'Escape' && !isPaletteOpen()) {
    const modalRoot = document.getElementById('modal-root');
    if (modalRoot.firstChild) { modalRoot.innerHTML = ''; return; }
    if (isDetailOpen()) { closeDetail(); return; }
  }

  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    openPalette();
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !typing) {
    e.preventDefault();
    undo().then((r) => toast(`Undid: ${r.undone}`))
      .catch((err) => { if (err.status === 404) toast('Nothing to undo.'); });
    return;
  }
  if (typing || isModalOpen() || isPaletteOpen() || isDetailOpen()) return;

  if (e.key === 'n' || e.key === 'N') { e.preventDefault(); openAddFlow(); }
  else if (e.key >= '1' && e.key <= '5') {
    location.hash = '#/' + ['map', 'dashboard', 'pipeline', 'insights', 'prep'][Number(e.key) - 1];
  }
});

// ---- boot ----

applyThemeFromStorage();
function applyThemeFromStorage() {
  const saved = localStorage.getItem('apptracker-theme');
  if (saved) document.documentElement.dataset.theme = saved;
}

loadAll()
  .then(renderCurrent)
  .catch(() => {
    document.getElementById('views').innerHTML =
      `<div class="empty" style="padding-top:20vh">Could not load data — check that the server is running, then reload.</div>`;
  });
