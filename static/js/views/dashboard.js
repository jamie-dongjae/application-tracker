// Dashboard: weekly goal, KPIs, pipeline snapshot, next actions, activity.

import { state, ACTIVE_STATUSES, BOARD_STATUSES, STATUS_COLORS, daysSince, esc } from '../state.js';
import { openDetail } from '../components/detail.js';

function startOfWeek() {
  const now = new Date();
  const day = (now.getDay() + 6) % 7; // Monday = 0
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - day);
  return monday;
}

export function renderDashboard(el) {
  const apps = state.apps;
  const goal = state.settings.weekly_goal || 5;
  const staleDays = state.settings.stale_days || 14;

  const monday = startOfWeek();
  const thisWeek = apps.filter((a) => a.date_applied && new Date(String(a.date_applied).slice(0, 10)) >= monday).length;
  const active = apps.filter((a) => ACTIVE_STATUSES.includes(a.status)).length;
  const submitted = apps.filter((a) => a.status !== 'Wishlist').length;
  const responded = apps.filter((a) => !['Wishlist', 'Applied'].includes(a.status)).length;
  const responseRate = submitted ? Math.round((responded / submitted) * 100) : 0;
  const offers = apps.filter((a) => a.status === 'Offer').length;

  const pct = Math.min(1, thisWeek / goal);
  const C = 2 * Math.PI * 26;

  const stale = apps
    .filter((a) => ['Applied', 'Interview'].includes(a.status))
    .map((a) => ({ ...a, idle: daysSince(a.last_updated || a.date_applied) ?? 0 }))
    .filter((a) => a.idle >= staleDays)
    .sort((x, y) => y.idle - x.idle)
    .slice(0, 6);
  const wishlist = apps.filter((a) => a.status === 'Wishlist').slice(0, 4);

  const snapshot = BOARD_STATUSES.map((s) => ({
    status: s,
    n: apps.filter((a) => a.status === s).length,
  }));
  const maxN = Math.max(1, ...snapshot.map((r) => r.n));

  el.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Dashboard</h1>
      <span class="page-sub num">${apps.length} tracked</span>
    </div>

    <div class="grid-kpi">
      <div class="panel" style="display:flex;gap:16px;align-items:center">
        <svg class="ring" width="64" height="64" viewBox="0 0 64 64" aria-hidden="true">
          <circle class="ring-bg" cx="32" cy="32" r="26" stroke-width="6"></circle>
          <circle class="ring-fg" cx="32" cy="32" r="26" stroke-width="6"
            stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}"></circle>
        </svg>
        <div>
          <div class="kpi-label">This week</div>
          <div class="kpi-value">${thisWeek}<span class="faint" style="font-size:16px">/${goal}</span></div>
          <div class="kpi-sub">${pct >= 1 ? 'Weekly goal met' : `${goal - thisWeek} to go`}
            · <span class="link" id="edit-goal">goal</span></div>
        </div>
      </div>
      <div class="panel">
        <div class="kpi-label">Active pipeline</div>
        <div class="kpi-value">${active}</div>
        <div class="kpi-sub">applications in play</div>
      </div>
      <div class="panel">
        <div class="kpi-label">Response rate</div>
        <div class="kpi-value">${responseRate}<span class="faint" style="font-size:16px">%</span></div>
        <div class="kpi-sub">${responded} of ${submitted} submitted</div>
      </div>
      <div class="panel">
        <div class="kpi-label">Offers</div>
        <div class="kpi-value ${offers ? 'kpi-accent' : ''}">${offers}</div>
        <div class="kpi-sub">${offers ? 'congratulations' : 'keep going'}</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3 class="panel-title">Pipeline snapshot</h3>
        <div class="barlist">
          ${snapshot.map((r) => `
            <div class="barlist-row">
              <span class="barlist-label"><span class="dot" style="background:${STATUS_COLORS[r.status]}"></span> ${r.status}</span>
              <div class="barlist-track"><div class="barlist-fill" style="width:${(r.n / maxN) * 100}%;background:${STATUS_COLORS[r.status]}"></div></div>
              <span class="barlist-value">${r.n}</span>
            </div>`).join('')}
        </div>
      </div>

      <div class="panel">
        <h3 class="panel-title">Next actions</h3>
        <div class="row-list">
          ${stale.map((a) => `
            <div class="row-item" data-open="${a.id}">
              <span class="dot" style="background:${STATUS_COLORS[a.status]}"></span>
              <div class="row-main">
                <div class="row-title">${esc(a.company)} — ${esc(a.title)}</div>
                <div class="row-sub">${esc(a.status)} · no movement for ${a.idle}d — follow up?</div>
              </div>
              <span class="row-aside">${a.idle}d</span>
            </div>`).join('')}
          ${wishlist.map((a) => `
            <div class="row-item" data-open="${a.id}">
              <span class="dot" style="background:${STATUS_COLORS.Wishlist}"></span>
              <div class="row-main">
                <div class="row-title">${esc(a.company)} — ${esc(a.title)}</div>
                <div class="row-sub">Wishlist — ready to apply?</div>
              </div>
            </div>`).join('')}
          ${!stale.length && !wishlist.length ? `<div class="empty">Nothing needs attention. Add your next application.</div>` : ''}
        </div>
      </div>
    </div>

    <div class="panel" style="margin-top:14px">
      <h3 class="panel-title">Recent activity</h3>
      <div class="row-list">
        ${state.history.slice(0, 8).map((h) => `
          <div class="row-item" style="cursor:default">
            <div class="row-main"><div class="row-title" style="font-weight:400">${esc(h.label || h.action)}</div></div>
            <span class="row-aside">${esc(String(h.ts).slice(5, 16).replace('T', ' '))}</span>
          </div>`).join('') || `<div class="empty">No activity yet.</div>`}
      </div>
    </div>`;

  el.querySelectorAll('[data-open]').forEach((row) => {
    row.onclick = () => openDetail(Number(row.dataset.open));
  });
  el.querySelector('#edit-goal').onclick = async () => {
    const input = prompt('Weekly application goal:', String(goal));
    const n = Number(input);
    if (input && Number.isInteger(n) && n >= 1 && n <= 100) {
      const { api } = await import('../api.js');
      state.settings = await api.put('/api/settings', { weekly_goal: n });
      renderDashboard(el);
    }
  };
}
