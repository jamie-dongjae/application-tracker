// Command palette (⌘K): navigation, actions, jump-to-application.

import { state, undo, esc } from '../state.js';
import { openAddFlow } from './addflow.js';
import { openDetail } from './detail.js';
import { toast } from './toast.js';

const root = document.getElementById('palette-root');
let items = [];
let active = 0;

function commands() {
  const nav = [
    { kind: 'go', label: 'Dashboard', run: () => (location.hash = '#/dashboard'), hint: '1' },
    { kind: 'go', label: 'Pipeline', run: () => (location.hash = '#/pipeline'), hint: '2' },
    { kind: 'go', label: 'Map', run: () => (location.hash = '#/map'), hint: '3' },
    { kind: 'go', label: 'Insights', run: () => (location.hash = '#/insights'), hint: '4' },
    { kind: 'go', label: 'Prep', run: () => (location.hash = '#/prep'), hint: '5' },
  ];
  const actions = [
    { kind: 'do', label: 'New application', run: () => openAddFlow(), hint: 'N' },
    { kind: 'do', label: 'Undo last change', run: async () => { const r = await undo(); toast(`Undid: ${r.undone}`); }, hint: '⌘Z' },
    { kind: 'do', label: 'Toggle theme', run: () => document.getElementById('theme-btn').click() },
    { kind: 'do', label: 'Geocode unmapped locations', run: () => { location.hash = '#/map'; document.dispatchEvent(new CustomEvent('apptracker:backfill')); } },
  ];
  const apps = state.apps.map((a) => ({
    kind: 'app',
    label: `${a.company} — ${a.title}`,
    run: () => openDetail(a.id),
  }));
  return [...actions, ...nav, ...apps];
}

export function openPalette() {
  if (root.firstChild) { closePalette(); return; }
  root.innerHTML = `
    <div class="palette-veil">
      <div class="palette">
        <input id="palette-input" placeholder="Type a command or company…" autocomplete="off" spellcheck="false">
        <div class="palette-list" id="palette-list"></div>
      </div>
    </div>`;
  root.querySelector('.palette-veil').addEventListener('mousedown', (e) => {
    if (e.target === e.currentTarget) closePalette();
  });
  const input = root.querySelector('#palette-input');
  input.focus();
  input.addEventListener('input', () => render(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { active = Math.min(active + 1, items.length - 1); paint(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { active = Math.max(active - 1, 0); paint(); e.preventDefault(); }
    else if (e.key === 'Enter') { items[active]?.run(); closePalette(); }
    else if (e.key === 'Escape') closePalette();
  });
  render('');
}

export function closePalette() { root.innerHTML = ''; }

export function isPaletteOpen() { return !!root.firstChild; }

function render(query) {
  const q = query.trim().toLowerCase();
  const all = commands();
  items = (q ? all.filter((c) => c.label.toLowerCase().includes(q)) : all).slice(0, 12);
  active = 0;
  paint();
}

function paint() {
  const list = root.querySelector('#palette-list');
  if (!list) return;
  list.innerHTML = items.map((c, i) => `
    <div class="palette-item ${i === active ? 'active' : ''}" data-i="${i}">
      <span class="palette-kind">${c.kind === 'app' ? 'OPEN' : c.kind === 'go' ? 'GO' : 'RUN'}</span>
      <span>${esc(c.label)}</span>
      ${c.hint ? `<span class="hint">${esc(c.hint)}</span>` : ''}
    </div>`).join('') || `<div class="empty">No matches</div>`;
  list.querySelectorAll('.palette-item').forEach((el) => {
    el.onclick = () => { items[Number(el.dataset.i)]?.run(); closePalette(); };
  });
}
