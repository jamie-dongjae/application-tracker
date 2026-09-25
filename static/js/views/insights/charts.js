// One echarts option builder per Insights panel. Builders take (data, tokens)
// and return a full option object — no chart instances or DOM in here.

import { baseOption, motionAllowed } from './theme.js';

function merge(t, option) {
  return Object.assign(baseOption(t), option);
}

export function sankeyOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, { trigger: 'item', triggerOn: 'mousemove' }),
    series: [{
      type: 'sankey',
      layoutIterations: 0, // depths are precomputed; keep columns stable
      nodeWidth: 14,
      nodeGap: 16,
      top: 10, bottom: 14, left: 4, right: 90,
      emphasis: { focus: 'adjacency' },
      data: data.nodes.map((n) => ({
        name: n.name,
        depth: n.depth,
        itemStyle: { color: t.status[n.name] || t.accent, borderColor: 'transparent' },
      })),
      links: data.links,
      lineStyle: { color: 'gradient', opacity: 0.32, curveness: 0.55 },
      label: { color: t.text, fontFamily: t.fontUI, fontSize: 11.5 },
    }],
  });
}

export function calendarOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, {
      formatter: (p) => `${p.value[0]} · <b>${p.value[1]}</b> application${p.value[1] === 1 ? '' : 's'}`,
    }),
    visualMap: {
      show: false, min: 0, max: data.max,
      inRange: { color: [t.lineSoft, t.accent] },
    },
    calendar: {
      range: data.range,
      top: 26, left: 40, right: 6, bottom: 4,
      cellSize: ['auto', 13],
      itemStyle: { color: 'transparent', borderColor: t.panel, borderWidth: 2 },
      splitLine: { lineStyle: { color: t.line, width: 1 } },
      dayLabel: { color: t.textFaint, fontSize: 9, fontFamily: t.fontMono, firstDay: 1, nameMap: ['S', 'M', 'T', 'W', 'T', 'F', 'S'] },
      monthLabel: { color: t.textFaint, fontSize: 10, fontFamily: t.fontMono },
      yearLabel: { show: false },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: data.days }],
  });
}

export function roseOption(data, t) {
  const palette = [t.accent, t.status.Interview, t.status.Offer, t.status.Accepted,
    t.status.Declined, t.status.Applied, t.textFaint, t.status.Wishlist];
  return merge(t, {
    color: palette,
    series: [{
      type: 'pie',
      roseType: 'area',
      radius: ['14%', '74%'],
      center: ['50%', '52%'],
      itemStyle: { borderRadius: 6, borderColor: t.panel, borderWidth: 2 },
      label: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
      labelLine: { lineStyle: { color: t.line } },
      data,
    }],
  });
}

export function donutOption(data, t) {
  const palette = [t.accent, t.status.Offer, t.status.Interview, t.status.Declined, t.textFaint];
  return merge(t, {
    color: palette,
    legend: {
      bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    series: [{
      type: 'pie',
      radius: ['56%', '76%'],
      center: ['50%', '46%'],
      itemStyle: { borderRadius: 6, borderColor: t.panel, borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, color: t.text, fontSize: 13, fontFamily: t.fontUI, formatter: '{b}\n{c}' } },
      data,
    }],
  });
}

export function momentumOption(data, t) {
  const palette = [t.accent, t.status.Interview, t.status.Offer, t.status.Declined, t.textFaint];
  const gradient = (hex) => ({
    type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [{ offset: 0, color: hex + 'aa' }, { offset: 1, color: hex + '0d' }],
  });
  return merge(t, {
    color: palette,
    tooltip: Object.assign(baseOption(t).tooltip, { trigger: 'axis' }),
    legend: {
      top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    grid: { left: 8, right: 14, top: 30, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category', boundaryGap: false, data: data.weeks.map((w) => w.label),
      axisLine: { lineStyle: { color: t.line } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: t.lineSoft } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
    },
    series: data.stacks.map((source, i) => ({
      name: source,
      type: 'line',
      stack: 'total',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.4 },
      areaStyle: { color: gradient(palette[i % palette.length]) },
      emphasis: { focus: 'series' },
      data: data.weeks.map((w) => w.bySource[source] || 0),
      ...(i === 0 ? {
        markLine: {
          symbol: 'none', silent: true,
          lineStyle: { color: t.accent, type: 'dashed', opacity: 0.7 },
          label: { formatter: 'goal', color: t.accent, fontSize: 10, fontFamily: t.fontMono },
          data: [{ yAxis: data.goal }],
        },
      } : {}),
    })),
  });
}

export function gaugeOption(pct, t) {
  return merge(t, {
    series: [{
      type: 'gauge',
      startAngle: 210, endAngle: -30, min: 0, max: 100,
      radius: '96%', center: ['50%', '58%'],
      progress: { show: true, width: 13, roundCap: true, itemStyle: { color: t.accent } },
      axisLine: { roundCap: true, lineStyle: { width: 13, color: [[1, t.lineSoft]] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      pointer: { show: false }, anchor: { show: false },
      detail: {
        valueAnimation: motionAllowed(), formatter: '{value}%',
        color: t.text, fontFamily: t.fontMono, fontSize: 30, fontWeight: 600,
        offsetCenter: [0, '-14%'],
      },
      title: { offsetCenter: [0, '24%'], color: t.textFaint, fontSize: 10.5, fontFamily: t.fontUI },
      data: [{ value: pct, name: 'RESPONDED' }],
    }],
  });
}

// The centerpiece: a slowly rotating 3D bar terrain (echarts-gl).
export function terrainOption(m, t) {
  return merge(t, {
    visualMap: {
      show: false, dimension: 1,
      pieces: m.statuses.map((s, i) => ({ value: i, color: t.status[s] })),
    },
    xAxis3D: {
      type: 'category', data: m.labels, name: '',
      axisLabel: { color: t.textFaint, fontSize: 9, fontFamily: t.fontMono },
      axisLine: { lineStyle: { color: t.line } },
      splitLine: { show: false },
    },
    yAxis3D: {
      type: 'category', data: m.statuses, name: '',
      axisLabel: { color: t.textFaint, fontSize: 9, fontFamily: t.fontUI },
      axisLine: { lineStyle: { color: t.line } },
      splitLine: { show: false },
    },
    zAxis3D: {
      type: 'value', name: '', minInterval: 1,
      axisLabel: { color: t.textFaint, fontSize: 9, fontFamily: t.fontMono },
      axisLine: { lineStyle: { color: t.line } },
      splitLine: { lineStyle: { color: t.lineSoft, opacity: 0.4 } },
    },
    grid3D: {
      boxWidth: 150, boxDepth: 62, boxHeight: 46,
      // echarts-gl paints "transparent" as opaque black; use the panel token
      // so the scene blends into the glass card in both themes.
      environment: t.panel,
      light: { main: { intensity: 1.25, shadow: false, beta: 35 }, ambient: { intensity: 0.32 } },
      viewControl: {
        autoRotate: motionAllowed(), autoRotateSpeed: 5, autoRotateAfterStill: 4,
        distance: 210, alpha: 24, beta: 20, panSensitivity: 0, zoomSensitivity: 0.6,
      },
    },
    series: [{
      type: 'bar3D',
      shading: 'lambert',
      barSize: 4.4,
      bevelSize: 0.35, bevelSmoothness: 4,
      itemStyle: { opacity: 0.96 },
      emphasis: { itemStyle: { color: t.accent }, label: { show: false } },
      data: m.data,
    }],
  });
}

// Horizontal bar: closed applications by outcome bucket.
export function outcomeBarOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, { trigger: 'axis', axisPointer: { type: 'shadow' } }),
    grid: { left: 8, right: 24, top: 8, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: t.lineSoft } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
    },
    yAxis: {
      type: 'category', data: data.map((d) => d.name),
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
      axisLabel: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 14,
      itemStyle: { color: t.status.Rejected, borderRadius: [0, 4, 4, 0], opacity: 0.85 },
      label: { show: true, position: 'right', color: t.textDim, fontSize: 10, fontFamily: t.fontMono },
      data: data.map((d) => d.value),
    }],
  });
}

// Funnel: how far applications travel through the 7-stage v4 funnel.
export function funnelOption(data, t) {
  const palette = [t.status.Applied, t.accent, t.status.Interview, t.status.Wishlist,
    t.status.Offer, t.status.Declined, t.status.Accepted];
  return merge(t, {
    color: palette,
    tooltip: Object.assign(baseOption(t).tooltip, { formatter: '{b}: <b>{c}</b>' }),
    series: [{
      type: 'funnel',
      sort: 'none',
      top: 8, bottom: 8, left: '6%', width: '72%',
      gap: 3,
      minSize: '4%',
      itemStyle: { borderColor: t.panel, borderWidth: 2, opacity: 0.9 },
      label: { show: true, position: 'right', color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI, formatter: '{b}  {c}' },
      labelLine: { lineStyle: { color: t.line } },
      data,
    }],
  });
}

// Stacked horizontal bar: gate flags, closed vs still-active applications.
export function gatesBarOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, { trigger: 'axis', axisPointer: { type: 'shadow' } }),
    legend: {
      top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    grid: { left: 8, right: 24, top: 26, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: t.lineSoft } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
    },
    yAxis: {
      type: 'category', data: data.map((d) => d.gate),
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
      axisLabel: { color: t.textDim, fontSize: 10, fontFamily: t.fontMono },
    },
    series: [
      {
        name: 'active', type: 'bar', stack: 'g', barMaxWidth: 12,
        itemStyle: { color: t.accent, opacity: 0.85 },
        data: data.map((d) => d.active),
      },
      {
        name: 'closed', type: 'bar', stack: 'g', barMaxWidth: 12,
        itemStyle: { color: t.textFaint, borderRadius: [0, 4, 4, 0], opacity: 0.6 },
        data: data.map((d) => d.closed),
      },
    ],
  });
}

// 2D stand-in for the terrain when WebGL / echarts-gl is unavailable.
export function terrainFallbackOption(m, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, {
      formatter: (p) => `${m.labels[p.value[0]]} · ${m.statuses[p.value[1]]}: <b>${p.value[2]}</b>`,
    }),
    visualMap: { show: false, min: 0, max: m.max, inRange: { color: [t.lineSoft, t.accent] } },
    grid: { left: 8, right: 14, top: 12, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category', data: m.labels,
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
    },
    yAxis: {
      type: 'category', data: m.statuses,
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontUI },
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
    },
    series: [{
      type: 'heatmap',
      data: m.data,
      itemStyle: { borderColor: t.panel, borderWidth: 2, borderRadius: 3 },
    }],
  });
}
