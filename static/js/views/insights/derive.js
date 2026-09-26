// Pure data selectors for the Insights dashboard: everything is computed
// from state and returned as plain data — no DOM, no echarts in here.

import { state, STAGES, STAGE_LABELS, OUTCOME_LABELS, NON_PIPELINE_TRACKS,
  reachedOfferCount, splitGates } from '../../state.js';

// bridge/nurture tracks never count toward pipeline KPIs or funnels.
export function pipelineApps() {
  return state.apps.filter((a) => !NON_PIPELINE_TRACKS.includes(a.track));
}

export function excludedCount() {
  return state.apps.filter((a) => NON_PIPELINE_TRACKS.includes(a.track)).length;
}

// "Screened" = a real human response: the funnel reached recruiter_screen or
// further. ATS confirmations (stage `confirmed`) are auto-replies, not signal.
const SCREEN_FLOOR = STAGES.indexOf('recruiter_screen');
const STAGE_ORDER = Object.fromEntries(STAGES.map((s, i) => [s, i]));

export function isScreened(app) {
  return (STAGE_ORDER[app.stage_reached] ?? -1) >= SCREEN_FLOOR;
}

export function kpis() {
  const apps = pipelineApps();
  const submitted = apps.filter((a) => a.status !== 'Wishlist');
  const responded = apps.filter((a) => !['Wishlist', 'Applied'].includes(a.status));
  const screened = submitted.filter(isScreened);
  return {
    tracked: state.apps.length,
    excluded: excludedCount(),
    submitted: submitted.length,
    responded: responded.length,
    responseRate: submitted.length ? Math.round((responded.length / submitted.length) * 100) : 0,
    screened: screened.length,
    screenRate: submitted.length ? Math.round((screened.length / submitted.length) * 100) : 0,
    reachedOffer: reachedOfferCount(),
    accepted: apps.filter((a) => a.status === 'Accepted').length,
  };
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

// ---- Insights v3 selectors ----

// Where should I apply: per canonical source, volume vs real-response rate.
export function sourceEffectiveness() {
  const submitted = pipelineApps().filter((a) => a.status !== 'Wishlist');
  const by = new Map();
  for (const a of submitted) {
    const key = a.source || 'Unknown';
    if (!by.has(key)) by.set(key, { source: key, submitted: 0, screened: 0 });
    const row = by.get(key);
    row.submitted += 1;
    if (isScreened(a)) row.screened += 1;
  }
  return [...by.values()]
    .map((r) => ({ ...r, screenRate: r.submitted ? Math.round((r.screened / r.submitted) * 100) : 0 }))
    .sort((x, y) => x.submitted - y.submitted); // horizontal bar: biggest on top
}

// Weekly cohorts: is the CV/strategy improving over time? Apps grouped by the
// week they were APPLIED, with the share of that cohort that reached a screen.
export function weeklyCohorts(weeksBack = 12) {
  const thisMonday = mondayOf(new Date());
  const submitted = pipelineApps().filter((a) => a.date_applied && a.status !== 'Wishlist');
  const weeks = [];
  for (let i = weeksBack - 1; i >= 0; i--) {
    const start = new Date(thisMonday); start.setDate(start.getDate() - i * 7);
    const end = new Date(start); end.setDate(end.getDate() + 7);
    const cohort = submitted.filter((a) => {
      const d = new Date(String(a.date_applied).slice(0, 10));
      return d >= start && d < end;
    });
    const screened = cohort.filter(isScreened).length;
    weeks.push({
      label: `${start.getMonth() + 1}/${start.getDate()}`,
      applied: cohort.length,
      screened,
      screenRate: cohort.length ? Math.round((screened / cohort.length) * 100) : null,
    });
  }
  return weeks;
}

const _CLOSED_NOTE = /closed (\d{4}-\d{2}-\d{2})/;

// How fast do rejections come? Days from applied to close, where the close
// date is recorded (backfill notes; mail sync events grow this over time).
export function rejectionSpeed() {
  const buckets = [
    { label: '0–1d', min: 0, max: 1, n: 0 },   // same-batch ATS cut
    { label: '2–7d', min: 2, max: 7, n: 0 },
    { label: '1–2w', min: 8, max: 14, n: 0 },
    { label: '2–4w', min: 15, max: 30, n: 0 },
    { label: '1mo+', min: 31, max: Infinity, n: 0 },
  ];
  let known = 0;
  for (const a of pipelineApps()) {
    if (a.current_state !== 'closed' || !String(a.outcome || '').startsWith('rejected')) continue;
    const m = _CLOSED_NOTE.exec(a.notes || '');
    if (!m || !a.date_applied) continue;
    const days = Math.round((new Date(m[1]) - new Date(String(a.date_applied).slice(0, 10))) / 86400000);
    if (Number.isNaN(days) || days < 0) continue;
    known += 1;
    const bucket = buckets.find((b) => days >= b.min && days <= b.max);
    if (bucket) bucket.n += 1;
  }
  return { buckets, known };
}
