// Insights: an echarts-powered analytics dashboard. Lifecycle lives here —
// build the DOM once, init one chart per panel, push fresh data on every
// re-render, dispose everything when the user navigates away (main.js calls
// destroyInsights) so WebGL contexts never pile up.

import { state, esc } from '../../state.js';
import { openDetail } from '../../components/detail.js';
import { countUp } from '../../components/motion.js';
import { chartTokens } from './theme.js';
import * as derive from './derive.js';
import * as charts from './charts.js';

const registry = new Map(); // panel name -> echarts instance
let observer = null;
let rafId = 0;
const pendingResize = new Set();
let rootEl = null;

const SKELETON = `
  <div class="page-head">
    <h1 class="page-title">Insights</h1>
    <span class="page-sub">computed from your workbook — nothing is estimated</span>
  </div>
  <div class="grid-kpi" style="grid-template-columns:repeat(6,1fr)" id="ins-kpis"></div>
  <div class="insights-grid">
    <div class="panel span-7"><h2 class="panel-title">Source effectiveness — screen rate by channel</h2>
      <div class="chart-box tall" data-chart="sources"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Response rate</h2>
      <div class="chart-box tall" data-chart="gauge"></div></div>
    <div class="panel span-12"><h2 class="panel-title">Weekly cohorts — applications vs screen rate</h2>
      <div class="chart-box" data-chart="cohorts"></div></div>
    <div class="panel span-7"><h2 class="panel-title">Momentum — weekly applications by source</h2>
      <div class="chart-box" data-chart="momentum"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Sources — volume</h2>
      <div class="chart-box" data-chart="rose"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Funnel — furthest stage reached</h2>
      <div class="chart-box" data-chart="funnel"></div></div>
    <div class="panel span-7"><h2 class="panel-title">Closed outcomes — how applications end</h2>
      <div class="chart-box" data-chart="outcomes"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Rejection speed <span class="faint" id="ins-speed-n"></span></h2>
      <div class="chart-box" data-chart="speed"></div></div>
    <div class="panel span-7"><h2 class="panel-title">Gates — known blockers on postings</h2>
      <div class="chart-box" data-chart="gates"></div></div>
    <div class="panel span-8"><h2 class="panel-title">Daily activity — last 6 months</h2>
      <div class="chart-box short" data-chart="calendar"></div></div>
    <div class="panel span-4"><h2 class="panel-title">Work type</h2>
      <div class="chart-box short" data-chart="worktype"></div></div>
    <div class="panel span-6"><h2 class="panel-title">Next actions — due list</h2>
      <div class="row-list" id="ins-next-actions"></div></div>
    <div class="panel span-6 ins-employers"><h2 class="panel-title">Employer rules</h2>
      <div id="ins-employers"></div></div>
  </div>`;

export function renderInsights(el) {
  rootEl = el;
  if (typeof echarts === 'undefined') {
    el.innerHTML = `<div class="page-head"><h1 class="page-title">Insights</h1></div>
      <div class="empty" style="padding:60px 0">Charts library not loaded — check vendor/echarts.min.js, then reload.</div>`;
    return;
  }
  if (!state.apps.length) {
    if (el.dataset.built) destroyInsights();
    rootEl = el;
    el.innerHTML = `<div class="page-head"><h1 class="page-title">Insights</h1></div>
      <div class="empty" style="padding:60px 0">Nothing to chart yet — add your first application.</div>`;
    return;
  }
  if (!el.dataset.built) {
    el.dataset.built = '1';
    el.innerHTML = SKELETON;
    initCharts(el);
  }
  paintKpis(el);
  paintNextActions(el);
  paintEmployers(el);
  applyData();
}

function initCharts(el) {
  observer = new ResizeObserver((entries) => {
    entries.forEach((e) => pendingResize.add(e.target));
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      rafId = 0;
      pendingResize.forEach((box) => registry.get(box.dataset.chart)?.resize());
      pendingResize.clear();
    });
  });
  el.querySelectorAll('[data-chart]').forEach((box) => {
    registry.set(box.dataset.chart, echarts.init(box));
    observer.observe(box);
  });
}

function applyData() {
  const t = chartTokens();
  const kpis = derive.kpis();
  const speed = derive.rejectionSpeed();
  const options = {
    sources: charts.sourceBarOption(derive.sourceEffectiveness(), t),
    gauge: charts.gaugeOption(kpis.responseRate, t),
    cohorts: charts.cohortComboOption(derive.weeklyCohorts(), t),
    momentum: charts.momentumOption(derive.momentumWeeks(), t),
    rose: charts.roseOption(derive.sourceRose(), t),
    calendar: charts.calendarOption(derive.calendarData(), t),
    worktype: charts.donutOption(derive.workTypeDonut(), t),
    funnel: charts.funnelOption(derive.stageFunnel(), t),
    outcomes: charts.outcomeBarOption(derive.outcomeBreakdown(), t),
    gates: charts.gatesBarOption(derive.gatesData(), t),
    speed: charts.speedHistOption(speed, t),
  };
  const speedN = rootEl && rootEl.querySelector('#ins-speed-n');
  if (speedN) speedN.textContent = `— days to rejection (n=${speed.known} where known)`;
  for (const [name, chart] of registry) {
    try {
      chart.setOption(options[name], true);
    } catch (err) {
      console.error(`insights: ${name} failed to render`, err);
    }
  }
}

function paintKpis(el) {
  const k = derive.kpis();
  const box = el.querySelector('#ins-kpis');
  const kpi = (label, valueHtml, sub = '') => `
    <div class="panel"><div class="kpi-label">${label}</div>
      <div class="kpi-value" style="font-size:24px">${valueHtml}</div>
      ${sub ? `<div class="kpi-sub">${sub}</div>` : ''}</div>`;
  box.innerHTML =
    kpi('Tracked', String(k.tracked), k.excluded ? `excl. ${k.excluded} bridge/nurture` : '') +
    kpi('Submitted', String(k.submitted)) +
    kpi('Response rate', `${k.responseRate}<span class="faint" style="font-size:15px">%</span>`,
      `${k.responded} of ${k.submitted}`) +
    kpi('Screen rate', `${k.screenRate}<span class="faint" style="font-size:15px">%</span>`,
      `${k.screened} reached a human`) +
    kpi('Reached offer', String(k.reachedOffer)) +
    kpi('Accepted', k.accepted
      ? `<span style="color:var(--s-accepted)">${k.accepted}</span>` : '0',
      k.accepted ? '🎉' : '');
  countUp(box);
}

function paintNextActions(el) {
  const box = el.querySelector('#ins-next-actions');
  if (!box) return;
  const items = derive.nextActionList();
  box.innerHTML = items.map((a) => `
    <div class="row-item" data-open="${a.id}">
      <span class="dot" style="background:${a.overdue ? 'var(--s-rejected)' : 'var(--accent)'}"></span>
      <div class="row-main">
        <div class="row-title">${esc(a.company)} — ${esc(a.title)}</div>
        <div class="row-sub">${esc(a.next_action)}</div>
      </div>
      <span class="row-aside ${a.overdue ? 'stale' : ''}">${a.due ? esc(a.due.slice(5)) + (a.overdue ? ' ⚠' : '') : '—'}</span>
    </div>`).join('') || `<div class="empty">Nothing due — inbox zero.</div>`;
  box.querySelectorAll('[data-open]').forEach((row) => {
    row.onclick = () => openDetail(Number(row.dataset.open));
  });
}

function paintEmployers(el) {
  const box = el.querySelector('#ins-employers');
  if (!box) return;
  const rows = state.employers;
  box.innerHTML = rows.length ? `<table><tbody>
    ${rows.map((e) => `<tr>
      <td>${esc(e.employer)}</td>
      <td>${esc(e.rule || '')}</td>
      <td class="faint">${esc(e.status || '')}</td>
    </tr>`).join('')}
  </tbody></table>` : `<div class="empty">No employer rules recorded.</div>`;
}

export function destroyInsights() {
  registry.forEach((chart) => chart.dispose());
  registry.clear();
  if (observer) { observer.disconnect(); observer = null; }
  if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
  pendingResize.clear();
  if (rootEl) {
    delete rootEl.dataset.built;
    rootEl.innerHTML = '';
    rootEl = null;
  }
}

// Theme values are baked into chart options at build time, so a theme flip
// tears the dashboard down; main.js re-renders it if it's the active view.
export function onInsightsThemeChange() {
  if (rootEl) destroyInsights();
}
