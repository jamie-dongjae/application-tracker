// Insights: an echarts-powered analytics dashboard. Lifecycle lives here —
// build the DOM once, init one chart per panel, push fresh data on every
// re-render, dispose everything when the user navigates away (main.js calls
// destroyInsights) so WebGL contexts never pile up.

import { state } from '../../state.js';
import { countUp } from '../../components/motion.js';
import { chartTokens } from './theme.js';
import * as derive from './derive.js';
import * as charts from './charts.js';

const registry = new Map(); // panel name -> echarts instance
let observer = null;
let rafId = 0;
const pendingResize = new Set();
let rootEl = null;
let webglOK = null;
let terrainBroken = false;

function hasWebGL() {
  if (webglOK !== null) return webglOK;
  try {
    const canvas = document.createElement('canvas');
    webglOK = !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
  } catch {
    webglOK = false;
  }
  return webglOK;
}

// The production echarts build silently DROPS unregistered series types, so
// a missing echarts-gl never throws — detect its UMD global explicitly.
function hasGL() {
  return typeof window['echarts-gl'] !== 'undefined';
}

const SKELETON = `
  <div class="page-head">
    <h1 class="page-title">Insights</h1>
    <span class="page-sub">computed from your workbook — nothing is estimated</span>
  </div>
  <div class="grid-kpi" style="grid-template-columns:repeat(5,1fr)" id="ins-kpis"></div>
  <div class="insights-grid">
    <div class="panel span-7"><h2 class="panel-title">Pipeline flow — where applications travel</h2>
      <div class="chart-box tall" data-chart="sankey"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Response rate</h2>
      <div class="chart-box tall" data-chart="gauge"></div></div>
    <div class="panel span-12"><h2 class="panel-title">Application terrain — weekly volume by current status</h2>
      <div class="chart-box terrain" data-chart="terrain"></div></div>
    <div class="panel span-7"><h2 class="panel-title">Momentum — weekly applications by source</h2>
      <div class="chart-box" data-chart="momentum"></div></div>
    <div class="panel span-5"><h2 class="panel-title">Sources</h2>
      <div class="chart-box" data-chart="rose"></div></div>
    <div class="panel span-8"><h2 class="panel-title">Daily activity — last 6 months</h2>
      <div class="chart-box short" data-chart="calendar"></div></div>
    <div class="panel span-4"><h2 class="panel-title">Work type</h2>
      <div class="chart-box short" data-chart="worktype"></div></div>
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
  const terrain = derive.terrainMatrix();
  const options = {
    sankey: charts.sankeyOption(derive.sankeyData(), t),
    gauge: charts.gaugeOption(kpis.responseRate, t),
    momentum: charts.momentumOption(derive.momentumWeeks(), t),
    rose: charts.roseOption(derive.sourceRose(), t),
    calendar: charts.calendarOption(derive.calendarData(), t),
    worktype: charts.donutOption(derive.workTypeDonut(), t),
    terrain: (!terrainBroken && hasWebGL() && hasGL())
      ? charts.terrainOption(terrain, t)
      : charts.terrainFallbackOption(terrain, t),
  };
  for (const [name, chart] of registry) {
    try {
      chart.setOption(options[name], true);
    } catch (err) {
      if (name === 'terrain' && !terrainBroken) {
        // WebGL init failed mid-setOption: fall back to a 2D heatmap of the
        // same matrix, permanently for this session. A throw can leave the
        // instance's main-process flag stuck (every later call silently
        // no-ops), so start from a fresh instance rather than reusing it.
        terrainBroken = true;
        chart.dispose();
        const box = rootEl && rootEl.querySelector('[data-chart="terrain"]');
        if (box) {
          const fresh = echarts.init(box);
          registry.set('terrain', fresh);
          fresh.setOption(charts.terrainFallbackOption(terrain, t), true);
        }
      } else {
        console.error(`insights: ${name} failed to render`, err);
      }
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
    kpi('Tracked', String(k.tracked)) +
    kpi('Submitted', String(k.submitted)) +
    kpi('Response rate', `${k.responseRate}<span class="faint" style="font-size:15px">%</span>`,
      `${k.responded} of ${k.submitted}`) +
    kpi('Reached offer', String(k.reachedOffer)) +
    kpi('Accepted', k.accepted
      ? `<span style="color:var(--s-accepted)">${k.accepted}</span>` : '0',
      k.accepted ? '🎉' : '');
  countUp(box);
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
