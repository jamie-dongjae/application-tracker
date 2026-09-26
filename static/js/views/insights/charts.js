// One echarts option builder per Insights panel. Builders take (data, tokens)
// and return a full option object — no chart instances or DOM in here.

import { baseOption, motionAllowed } from './theme.js';

function merge(t, option) {
  return Object.assign(baseOption(t), option);
}

// Where should I apply: the bar IS the screen rate — the best channel is the
// longest bar, full stop. Volume rides along as the label ("75% (3/4)").
export function sourceBarOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (ps) => {
        const row = data[ps[0].dataIndex];
        return `${row.source}<br><b>${row.screenRate}%</b> screen rate — ` +
          `${row.screened} of ${row.submitted} applications reached a human` +
          (row.smallSample ? '<br><i>small sample</i>' : '');
      },
    }),
    grid: { left: 8, right: 76, top: 10, bottom: 4, containLabel: true },
    xAxis: {
      type: 'value', min: 0, max: 100,
      splitLine: { lineStyle: { color: t.lineSoft } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono, formatter: '{value}%' },
    },
    yAxis: {
      type: 'category', data: data.map((d) => d.source),
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
      axisLabel: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    series: [{
      type: 'bar', barMaxWidth: 18,
      showBackground: true,
      backgroundStyle: { color: t.lineSoft, borderRadius: [0, 4, 4, 0], opacity: 0.35 },
      itemStyle: {
        color: t.accent, borderRadius: [0, 4, 4, 0],
        opacity: 0.95,
      },
      label: {
        show: true, position: 'right', color: t.textDim,
        fontSize: 10.5, fontFamily: t.fontMono,
        formatter: (p) => {
          const row = data[p.dataIndex];
          return `${row.screenRate}% (${row.screened}/${row.submitted})`;
        },
      },
      data: data.map((d) => ({
        value: d.screenRate,
        itemStyle: d.smallSample ? { color: t.accent, opacity: 0.45 } : undefined,
      })),
    }],
  });
}

// Weekly cohorts: bars = applications, line = % of that cohort screened.
export function cohortComboOption(weeks, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, {
      trigger: 'axis',
      formatter: (ps) => {
        const w = weeks[ps[0].dataIndex];
        return `wk ${w.label}: ${w.applied} applied · ${w.screened} screened` +
          (w.screenRate != null ? ` (<b>${w.screenRate}%</b>)` : '');
      },
    }),
    legend: {
      top: 0, icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { color: t.textDim, fontSize: 10.5, fontFamily: t.fontUI },
    },
    grid: { left: 8, right: 14, top: 30, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category', data: weeks.map((w) => w.label),
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
    },
    yAxis: [
      {
        type: 'value', minInterval: 1, name: '',
        splitLine: { lineStyle: { color: t.lineSoft } },
        axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
      },
      {
        type: 'value', min: 0, max: 100,
        splitLine: { show: false },
        axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono, formatter: '{value}%' },
      },
    ],
    series: [
      {
        name: 'applied', type: 'bar', barMaxWidth: 18,
        itemStyle: { color: t.lineSoft, borderRadius: [4, 4, 0, 0] },
        data: weeks.map((w) => w.applied),
      },
      {
        name: 'screen rate', type: 'line', yAxisIndex: 1, smooth: true,
        symbol: 'circle', symbolSize: 5, connectNulls: true,
        lineStyle: { width: 2, color: t.accent },
        itemStyle: { color: t.accent },
        data: weeks.map((w) => w.screenRate),
      },
    ],
  });
}

// Rejection speed histogram: same-batch ATS cuts vs slow human reviews.
export function speedHistOption(data, t) {
  return merge(t, {
    tooltip: Object.assign(baseOption(t).tooltip, { trigger: 'axis', axisPointer: { type: 'shadow' } }),
    grid: { left: 8, right: 14, top: 26, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category', data: data.buckets.map((b) => b.label),
      axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
      axisLabel: { color: t.textDim, fontSize: 10, fontFamily: t.fontMono },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: t.lineSoft } },
      axisLabel: { color: t.textFaint, fontSize: 9.5, fontFamily: t.fontMono },
    },
    series: [{
      type: 'bar', barMaxWidth: 28,
      itemStyle: { color: t.status.Rejected, borderRadius: [4, 4, 0, 0], opacity: 0.85 },
      label: { show: true, position: 'top', color: t.textDim, fontSize: 10, fontFamily: t.fontMono },
      data: data.buckets.map((b) => b.n),
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
