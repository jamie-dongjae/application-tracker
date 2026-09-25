// Pure data selectors for the Insights dashboard: everything is computed
// from state and returned as plain data — no DOM, no echarts in here.

import { state, STATUSES, STAGES, STAGE_LABELS, OUTCOME_LABELS, NON_PIPELINE_TRACKS,
  reachedOfferCount, splitGates } from '../../state.js';

// bridge/nurture tracks never count toward pipeline KPIs or funnels.
export function pipelineApps() {
  return state.apps.filter((a) => !NON_PIPELINE_TRACKS.includes(a.track));
}

export function excludedCount() {
  return state.apps.filter((a) => NON_PIPELINE_TRACKS.includes(a.track)).length;
}

const STAGE_IDX = {
  'Applied': 1, 'Interview': 2, 'Offer': 3, 'Accepted': 3, 'Declined': 3,
  // pre-simplification stage names in old history entries
  'Phone Screen': 2, 'Technical': 2, 'Onsite': 2,
};
const STAGE_NAME = { 1: 'Applied', 2: 'Interview', 3: 'Offer' };

function transitionsById() {
  const map = new Map();
  for (const t of state.transitions) {
    if (!map.has(t.id)) map.set(t.id, []);
    map.get(t.id).push(t);
  }
  return map;
}

// History-aware: an app that reached Interview before being rejected still
// counts as having reached Interview. Imported rows without history fall
// back to their current status (submitted at minimum).
function furthestStage(app, tmap) {
  let idx = STAGE_IDX[app.status] || 0;
  for (const t of tmap.get(app.id) || []) {
    idx = Math.max(idx, STAGE_IDX[t.to] || 0, STAGE_IDX[t.from] || 0);
  }
  if (!idx && app.status !== 'Wishlist') idx = 1;
  return idx;
}

export function kpis() {
  const apps = pipelineApps();
  const submitted = apps.filter((a) => a.status !== 'Wishlist');
  const responded = apps.filter((a) => !['Wishlist', 'Applied'].includes(a.status));
  return {
    tracked: state.apps.length,
    excluded: excludedCount(),
    submitted: submitted.length,
    responded: responded.length,
    responseRate: submitted.length ? Math.round((responded.length / submitted.length) * 100) : 0,
    reachedOffer: reachedOfferCount(),
    accepted: apps.filter((a) => a.status === 'Accepted').length,
  };
}

// Sankey flows via a "monotonic hull": Revive creates backward transitions
// (Rejected → Applied) and echarts sankeys reject cycles, so instead of
// chaining raw transitions we emit the furthest forward path per app plus
// one terminal link for its current closed status.
export function sankeyData() {
  const tmap = transitionsById();
  const links = new Map();
  const addLink = (from, to) => {
    const key = `${from} ${to}`;
    links.set(key, (links.get(key) || 0) + 1);
  };

  let sawWishlistOrigin = false;
  for (const app of pipelineApps()) {
    if (app.status === 'Wishlist') continue; // shown in the KPI row instead
    const furthest = furthestStage(app, tmap);
    const fromWishlist = (tmap.get(app.id) || []).some((t) => t.from === 'Wishlist');
    if (fromWishlist) { addLink('Wishlist', 'Applied'); sawWishlistOrigin = true; }
    if (furthest >= 2) addLink('Applied', 'Interview');
    if (furthest >= 3) addLink('Interview', 'Offer');
    if (app.status === 'Accepted') addLink('Offer', 'Accepted');
    else if (app.status === 'Declined') addLink('Offer', 'Declined');
    else if (app.status === 'Rejected' || app.status === 'Withdrawn') {
      addLink(STAGE_NAME[furthest], app.status);
    }
    // Active apps (Applied/Interview/Offer) emit no terminal link: node
    // inflow > outflow reads as "still in play".
  }

  const names = new Set();
  const linkArr = [...links.entries()].map(([key, value]) => {
    const [source, target] = key.split(' ');
    names.add(source); names.add(target);
    return { source, target, value };
  });
  const depthOf = (name) => {
    const stage = { 'Wishlist': 0, 'Applied': 1, 'Interview': 2, 'Offer': 3 }[name];
    if (stage !== undefined) return sawWishlistOrigin ? stage : stage - 1;
    return sawWishlistOrigin ? 4 : 3; // terminal outcomes share the last column
  };
  const nodes = STATUSES.filter((s) => names.has(s)).map((name) => ({ name, depth: depthOf(name) }));
  return { nodes, links: linkArr };
}

function localDateStr(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// GitHub-style contribution calendar: applications per day, last ~6 months.
export function calendarData() {
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth(), end.getDate() - 182);
  const counts = new Map();
  for (const a of state.apps) {
    if (!a.date_applied) continue;
    const key = String(a.date_applied).slice(0, 10);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const days = [];
  let max = 1;
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const key = localDateStr(d);
    const n = counts.get(key) || 0;
    if (n > max) max = n;
    days.push([key, n]);
  }
  return { days, max, range: [localDateStr(start), localDateStr(end)] };
}

function countBy(rows, keyFn) {
  const out = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    out.set(k, (out.get(k) || 0) + 1);
  }
  return [...out.entries()].sort((a, b) => b[1] - a[1]);
}

export function sourceRose(limit = 8) {
  const submitted = pipelineApps().filter((a) => a.status !== 'Wishlist');
  return countBy(submitted, (a) => a.source || 'Unknown').slice(0, limit)
    .map(([name, value]) => ({ name, value }));
}

export function workTypeDonut() {
  const submitted = pipelineApps().filter((a) => a.status !== 'Wishlist');
  return countBy(submitted, (a) => a.work_type || 'Unspecified')
    .map(([name, value]) => ({ name, value }));
}

// ---- v4 selectors ----

// Closed pipeline apps bucketed by outcome type, ordered by count.
export function outcomeBreakdown() {
  const closed = pipelineApps().filter((a) => a.current_state === 'closed' && a.outcome);
  return countBy(closed, (a) => OUTCOME_LABELS[a.outcome] || a.outcome)
    .map(([name, value]) => ({ name, value }))
    .reverse(); // horizontal bar: biggest on top
}

// Cumulative funnel: how many pipeline apps reached each stage or further.
export function stageFunnel() {
  const apps = pipelineApps().filter((a) => a.stage_reached);
  const idx = Object.fromEntries(STAGES.map((s, i) => [s, i]));
  return STAGES.map((stage, i) => ({
    name: STAGE_LABELS[stage] || stage,
    value: apps.filter((a) => (idx[a.stage_reached] ?? -1) >= i).length,
  })).filter((row, i) => row.value > 0 || i < 3);
}

// Gate flags split by whether the application is closed or still in play.
export function gatesData(limit = 10) {
  const counts = new Map();
  for (const a of pipelineApps()) {
    for (const g of splitGates(a.gates)) {
      if (!counts.has(g)) counts.set(g, { gate: g, closed: 0, active: 0 });
      counts.get(g)[a.current_state === 'closed' ? 'closed' : 'active'] += 1;
    }
  }
  return [...counts.values()]
    .sort((x, y) => (y.closed + y.active) - (x.closed + x.active))
    .slice(0, limit)
    .reverse();
}

// Actionable items sorted by due date (missing due last).
export function nextActionList() {
  const today = new Date().toISOString().slice(0, 10);
  return state.apps
    .filter((a) => a.next_action && a.current_state !== 'closed')
    .map((a) => ({
      id: a.id, company: a.company, title: a.title,
      next_action: a.next_action, due: a.due ? String(a.due).slice(0, 10) : '',
      overdue: !!a.due && String(a.due).slice(0, 10) < today,
    }))
    .sort((x, y) => (x.due || '9999').localeCompare(y.due || '9999'));
}

function mondayOf(date) {
  const day = (date.getDay() + 6) % 7;
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() - day);
}

// Last 12 ISO weeks, stacked by the top submission sources.
export function momentumWeeks(topN = 4) {
  const thisMonday = mondayOf(new Date());
  const submitted = state.apps.filter((a) => a.date_applied);
  const top = countBy(submitted, (a) => a.source || 'Unknown').slice(0, topN).map(([s]) => s);
  const sourceOf = (a) => {
    const s = a.source || 'Unknown';
    return top.includes(s) ? s : 'Other';
  };
  const stacks = top.concat(submitted.some((a) => !top.includes(a.source || 'Unknown')) ? ['Other'] : []);

  const weeks = [];
  for (let i = 11; i >= 0; i--) {
    const start = new Date(thisMonday); start.setDate(start.getDate() - i * 7);
    const end = new Date(start); end.setDate(end.getDate() + 7);
    const inWeek = submitted.filter((a) => {
      const d = new Date(String(a.date_applied).slice(0, 10));
      return d >= start && d < end;
    });
    const bySource = {};
    for (const s of stacks) bySource[s] = 0;
    for (const a of inWeek) bySource[sourceOf(a)] += 1;
    weeks.push({ label: `${start.getMonth() + 1}/${start.getDate()}`, total: inWeek.length, bySource });
  }
  return { weeks, stacks, goal: state.settings.weekly_goal || 5 };
}

// 3D terrain: applications submitted in week x whose *current* status is y.
export function terrainMatrix() {
  const thisMonday = mondayOf(new Date());
  const statuses = STATUSES.filter((s) => s !== 'Wishlist');
  const labels = [];
  const starts = [];
  for (let i = 11; i >= 0; i--) {
    const start = new Date(thisMonday); start.setDate(start.getDate() - i * 7);
    starts.push(start);
    labels.push(`${start.getMonth() + 1}/${start.getDate()}`);
  }
  const data = [];
  let max = 1;
  for (let wi = 0; wi < starts.length; wi++) {
    const end = new Date(starts[wi]); end.setDate(end.getDate() + 7);
    for (let si = 0; si < statuses.length; si++) {
      const n = state.apps.filter((a) => {
        if (!a.date_applied || a.status !== statuses[si]) return false;
        const d = new Date(String(a.date_applied).slice(0, 10));
        return d >= starts[wi] && d < end;
      }).length;
      if (n > max) max = n;
      data.push([wi, si, n]);
    }
  }
  return { labels, statuses, data, max };
}
