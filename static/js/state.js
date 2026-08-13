// Central store: server data + UI state, with a tiny pub/sub.

import { api } from './api.js';

export const STATUSES = ['Wishlist', 'Applied', 'Interview', 'Offer', 'Rejected', 'Withdrawn'];
export const BOARD_STATUSES = STATUSES.slice(0, 4);
export const CLOSED_STATUSES = ['Rejected', 'Withdrawn'];
export const ACTIVE_STATUSES = ['Applied', 'Interview', 'Offer'];
export const WORK_TYPES = ['', 'Onsite', 'Hybrid', 'Remote'];

export const STATUS_COLORS = {
  'Wishlist': 'var(--s-wishlist)',
  'Applied': 'var(--s-applied)',
  'Interview': 'var(--s-screen)',
  'Offer': 'var(--s-offer)',
  'Rejected': 'var(--s-rejected)',
  'Withdrawn': 'var(--s-withdrawn)',
};

// Next stage on the "advance" quick action (Offer is the end of the line).
export const NEXT_STATUS = { 'Wishlist': 'Applied', 'Applied': 'Interview', 'Interview': 'Offer' };

export const state = {
  apps: [],
  prep: [],
  settings: { weekly_goal: 5, stale_days: 14 },
  history: [],
  transitions: [],
  view: 'dashboard',
  mapFilter: { statuses: new Set(), query: '' },
  selectedId: null,
};

const listeners = new Set();

export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export function emit(topic) { listeners.forEach((fn) => fn(topic)); }

export async function loadAll() {
  const [apps, prepData, settings, hist] = await Promise.all([
    api.get('/api/applications'),
    api.get('/api/prep'),
    api.get('/api/settings'),
    api.get('/api/history'),
  ]);
  state.apps = apps.applications;
  state.prep = prepData.prep;
  state.settings = { ...state.settings, ...settings };
  state.history = hist.history;
  state.transitions = hist.transitions;
  emit('data');
}

export async function refreshApps() {
  const [apps, hist] = await Promise.all([api.get('/api/applications'), api.get('/api/history')]);
  state.apps = apps.applications;
  state.history = hist.history;
  state.transitions = hist.transitions;
  emit('data');
}

export async function refreshPrep() {
  state.prep = (await api.get('/api/prep')).prep;
  emit('data');
}

export function getApp(id) { return state.apps.find((a) => a.id === id); }

// ---- mutations ----

export async function createApplication(fields) {
  const rec = await api.post('/api/applications', fields);
  await refreshApps();
  return rec;
}

export async function patchApplication(id, patch, { optimistic = false } = {}) {
  if (optimistic) {
    const app = getApp(id);
    const before = { ...app };
    Object.assign(app, patch);
    emit('data');
    try {
      await api.patch(`/api/applications/${id}`, patch);
    } catch (err) {
      Object.assign(app, before);
      emit('data');
      throw err;
    }
    await refreshApps();
    return;
  }
  await api.patch(`/api/applications/${id}`, patch);
  await refreshApps();
}

export async function deleteApplication(id) {
  await api.del(`/api/applications/${id}`);
  if (state.selectedId === id) state.selectedId = null;
  await refreshApps();
}

export async function undo() {
  const result = await api.post('/api/undo');
  await Promise.all([refreshApps(), refreshPrep()]);
  return result;
}

// ---- helpers ----

export function daysSince(iso) {
  if (!iso) return null;
  const then = new Date(String(iso).slice(0, 10));
  if (Number.isNaN(then.getTime())) return null;
  return Math.max(0, Math.round((Date.now() - then.getTime()) / 86400000));
}

export function fmtDate(iso) {
  if (!iso) return '—';
  return String(iso).slice(0, 10);
}

export function esc(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}
