// Central store: server data + UI state, with a tiny pub/sub.

import { api } from './api.js';

export const STATUSES = ['Wishlist', 'Applied', 'Interview', 'Offer', 'Accepted', 'Declined', 'Rejected', 'Withdrawn'];
export const BOARD_STATUSES = STATUSES.slice(0, 4);
export const CLOSED_STATUSES = ['Accepted', 'Declined', 'Rejected', 'Withdrawn'];
export const ACTIVE_STATUSES = ['Applied', 'Interview', 'Offer'];
// Accepted/Declined both mean the application reached an offer.
export const REACHED_OFFER = ['Offer', 'Accepted', 'Declined'];

// History-aware "reached offer": current offer-stage statuses plus apps whose
// transition history ever touched the stage — an offer that later fell
// through to Rejected/Withdrawn still reached it. Keeps the KPI counts
// consistent with the history-aware funnel/sankey in Insights.
export function reachedOfferCount() {
  const ids = new Set();
  const alive = new Set();
  for (const a of state.apps) {
    alive.add(a.id);
    if (REACHED_OFFER.includes(a.status)) ids.add(a.id);
  }
  for (const t of state.transitions) {
    if (alive.has(t.id) && (REACHED_OFFER.includes(t.from) || REACHED_OFFER.includes(t.to))) ids.add(t.id);
  }
  return ids.size;
}
export const WORK_TYPES = ['', 'Onsite', 'Hybrid', 'Remote'];

// ---- v4 categorization enums (mirror tracker/excel/schema.py) ----
export const TRACKS = ['career', 'bridge', 'lottery', 'referral', 'inbound', 'nurture'];
export const STAGES = ['applied', 'confirmed', 'recruiter_screen', 'assessment', 'hiring_manager', 'final', 'offer'];
export const CURRENT_STATES = ['awaiting_response', 'awaiting_decision', 'scheduling', 'action_required', 'on_hold_employer', 'stale', 'closed'];
export const OUTCOMES = ['rejected_ats', 'rejected_cv', 'rejected_after_screen', 'rejected_after_interview',
  'rejected_visa', 'rejected_language', 'redirected', 'withdrawn_by_me', 'role_closed', 'void'];
export const CLOSED_BY = ['employer', 'me', 'system'];
export const GATES = ['ind_confirmed', 'ind_unknown', 'no_sponsorship', 'dutch_required',
  'masters_required', 'years_gap', 'onsite_5d', 'commute_risk', 'cap_slot'];
// Tracks that never count toward pipeline KPIs.
export const NON_PIPELINE_TRACKS = ['bridge', 'nurture'];

export const STAGE_LABELS = {
  applied: 'Applied', confirmed: 'Confirmed', recruiter_screen: 'Recruiter screen',
  assessment: 'Assessment', hiring_manager: 'Hiring manager', final: 'Final round', offer: 'Offer',
};
export const STATE_LABELS = {
  awaiting_response: 'Awaiting response', awaiting_decision: 'Awaiting decision',
  scheduling: 'Scheduling', action_required: 'Action required',
  on_hold_employer: 'On hold (employer)', stale: 'Stale', closed: 'Closed',
};
export const OUTCOME_LABELS = {
  rejected_ats: 'ATS cut', rejected_cv: 'CV screen', rejected_after_screen: 'After screen',
  rejected_after_interview: 'After interview', rejected_visa: 'Visa', rejected_language: 'Language',
  redirected: 'Redirected', withdrawn_by_me: 'Withdrew', role_closed: 'Role closed', void: 'Void',
};
export const TRACK_LABELS = {
  career: 'Career', bridge: 'Bridge', lottery: 'Lottery',
  referral: 'Referral', inbound: 'Inbound', nurture: 'Nurture',
};

export function splitGates(value) {
  return String(value || '').split(',').map((g) => g.trim()).filter(Boolean);
}

// Employer rule lookup: matches when either name contains the other.
export function employerRuleFor(company) {
  const c = String(company || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  if (!c) return null;
  return state.employers.find((e) => {
    const n = String(e.employer || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    return n && n !== 'global' && (c.includes(n) || n.includes(c));
  }) || null;
}

export const STATUS_COLORS = {
  'Wishlist': 'var(--s-wishlist)',
  'Applied': 'var(--s-applied)',
  'Interview': 'var(--s-screen)',
  'Offer': 'var(--s-offer)',
  'Accepted': 'var(--s-accepted)',
  'Declined': 'var(--s-declined)',
  'Rejected': 'var(--s-rejected)',
  'Withdrawn': 'var(--s-withdrawn)',
};

// Next stage on the "advance" quick action (Offer is the end of the line).
export const NEXT_STATUS = { 'Wishlist': 'Applied', 'Applied': 'Interview', 'Interview': 'Offer' };

export const state = {
  apps: [],
  prep: [],
  employers: [],
  reviewQueue: [],
  settings: { weekly_goal: 5, stale_days: 14 },
  history: [],
  transitions: [],
  view: 'dashboard',
  mapFilter: { statuses: new Set(), query: '' },
  boardFilter: { track: '', current_state: '' },
  selectedId: null,
};

const listeners = new Set();

export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export function emit(topic) { listeners.forEach((fn) => fn(topic)); }

export async function loadAll() {
  const [apps, prepData, settings, hist, employers, review] = await Promise.all([
    api.get('/api/applications'),
    api.get('/api/prep'),
    api.get('/api/settings'),
    api.get('/api/history'),
    api.get('/api/employers'),
    api.get('/api/sync/review'),
  ]);
  state.apps = apps.applications;
  state.prep = prepData.prep;
  state.settings = { ...state.settings, ...settings };
  state.history = hist.history;
  state.transitions = hist.transitions;
  state.employers = employers.employers;
  state.reviewQueue = review.items;
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

export async function refreshReview() {
  state.reviewQueue = (await api.get('/api/sync/review')).items;
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
