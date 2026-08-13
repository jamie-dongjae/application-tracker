// Insights: a single honest page — funnel, momentum, and three breakdowns.
// The funnel is history-aware: an application that reached Interview before
// being rejected still counts as having reached Interview.

import { state, esc } from '../state.js';

const STAGE_IDX = {
  'Applied': 1, 'Interview': 2, 'Offer': 3,
  // pre-simplification stage names in old history entries
  'Phone Screen': 2, 'Technical': 2, 'Onsite': 2,
};

function furthestStage(app, transitionsById) {
  let idx = STAGE_IDX[app.status] || 0;
  for (const t of transitionsById.get(app.id) || []) {
    idx = Math.max(idx, STAGE_IDX[t.to] || 0, STAGE_IDX[t.from] || 0);
  }
  if (!idx && app.status !== 'Wishlist') idx = 1; // submitted at minimum
  return idx;
}

export function renderInsights(el) {
  const apps = state.apps;
  const goal = state.settings.weekly_goal || 5;
  const transitionsById = new Map();
  for (const t of state.transitions) {
    if (!transitionsById.has(t.id)) transitionsById.set(t.id, []);
    transitionsById.get(t.id).push(t);
  }

  const submitted = apps.filter((a) => a.status !== 'Wishlist');
  const responded = apps.filter((a) => !['Wishlist', 'Applied'].includes(a.status));
  const offers = apps.filter((a) => a.status === 'Offer').length;
  const rejected = apps.filter((a) => a.status === 'Rejected').length;

  const stages = ['Applied', 'Interview', 'Offer'];
  const reach = stages.map((_, i) => submitted.filter((a) => furthestStage(a, transitionsById) >= i + 1).length);

  // Momentum: last 12 ISO weeks.
  const weeks = [];
  const now = new Date();
  const day = (now.getDay() + 6) % 7;
  const thisMonday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day);
  for (let i = 11; i >= 0; i--) {
    const start = new Date(thisMonday); start.setDate(start.getDate() - i * 7);
    const end = new Date(start); end.setDate(end.getDate() + 7);
    const n = apps.filter((a) => {
      if (!a.date_applied) return false;
      const d = new Date(String(a.date_applied).slice(0, 10));
      return d >= start && d < end;
    }).length;
    weeks.push({ start, n });
  }
  const maxWeek = Math.max(goal, ...weeks.map((w) => w.n), 1);

  const bySource = countBy(submitted, (a) => a.source || 'Unknown');
  const byLocation = countBy(apps.filter((a) => a.location), (a) => a.location);
  const bySponsor = countBy(submitted, (a) => a.sponsorship || 'Unknown');

  el.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Insights</h1>
      <span class="page-sub">computed from your workbook — nothing is estimated</span>
    </div>

    <div class="grid-kpi" style="grid-template-columns:repeat(5,1fr)">
      ${kpi('Tracked', apps.length)}
      ${kpi('Submitted', submitted.length)}
      ${kpi('Response rate', submitted.length ? Math.round((responded.length / submitted.length) * 100) + '%' : '—')}
      ${kpi('Offers', offers)}
      ${kpi('Rejected', rejected)}
    </div>

    <div class="grid-2">
      <div class="panel">
        <h2 class="panel-title">Funnel — furthest stage reached</h2>
        <div class="funnel">
          ${stages.map((s, i) => {
            const n = reach[i];
            const pctAll = submitted.length ? (n / submitted.length) * 100 : 0;
            const conv = i === 0 ? '' : reach[i - 1] ? ` · ${Math.round((n / reach[i - 1]) * 100)}%` : '';
            return `<div class="funnel-row">
              <span class="funnel-label">${esc(s)}</span>
              <div class="funnel-track"><div class="funnel-fill" style="width:${pctAll}%"></div></div>
              <span class="funnel-value">${n}${conv}</span>
            </div>`;
          }).join('')}
        </div>
        ${state.transitions.length === 0 ? `<div class="faint" style="font-size:11.5px;margin-top:10px">
          Stage history builds up as applications move — imported rows only know their current status.</div>` : ''}
      </div>

      <div class="panel">
        <h2 class="panel-title">Momentum — applications per week vs goal (${goal})</h2>
        <svg class="spark" viewBox="0 0 480 120" preserveAspectRatio="none" aria-hidden="true">
          ${weeks.map((w, i) => {
            const h = (w.n / maxWeek) * 92;
            const met = w.n >= goal;
            return `<rect x="${8 + i * 39}" y="${104 - h}" width="26" height="${Math.max(2, h)}" rx="3"
              fill="${met ? 'var(--accent)' : 'var(--line)'}"></rect>
              <text x="${21 + i * 39}" y="116" text-anchor="middle" font-size="8.5"
                fill="var(--text-faint)" font-family="var(--font-mono)">${String(w.start.getMonth() + 1)}/${String(w.start.getDate())}</text>`;
          }).join('')}
          <line x1="4" x2="476" y1="${104 - (goal / maxWeek) * 92}" y2="${104 - (goal / maxWeek) * 92}"
            stroke="var(--accent)" stroke-dasharray="3 4" stroke-width="1" opacity=".6"></line>
        </svg>
      </div>
    </div>

    <div class="grid-3" style="margin-top:14px">
      ${barPanel('Source', bySource, submitted.length)}
      ${barPanel('Top locations', byLocation, apps.length, 8)}
      ${barPanel('Sponsorship', bySponsor, submitted.length)}
    </div>`;
}

function kpi(label, value) {
  return `<div class="panel"><div class="kpi-label">${esc(label)}</div>
    <div class="kpi-value" style="font-size:24px">${value}</div></div>`;
}

function countBy(rows, keyFn) {
  const out = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    out.set(k, (out.get(k) || 0) + 1);
  }
  return [...out.entries()].sort((a, b) => b[1] - a[1]);
}

function barPanel(title, entries, total, limit = 6) {
  const rows = entries.slice(0, limit);
  return `<div class="panel">
    <h2 class="panel-title">${esc(title)}</h2>
    ${rows.length ? `<div class="barlist">
      ${rows.map(([label, n]) => `
        <div class="barlist-row">
          <span class="barlist-label" title="${esc(label)}">${esc(label)}</span>
          <div class="barlist-track"><div class="barlist-fill" style="width:${total ? (n / total) * 100 : 0}%"></div></div>
          <span class="barlist-value">${n}</span>
        </div>`).join('')}</div>`
      : `<div class="empty">No data yet.</div>`}
  </div>`;
}
