// Bridge between the app's CSS design tokens and echarts options. Read at
// chart-init time (not import time) so theme toggles pick up fresh values.

export function chartTokens() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    text: v('--text'),
    textDim: v('--text-dim'),
    textFaint: v('--text-faint'),
    line: v('--line'),
    lineSoft: v('--line-soft'),
    accent: v('--accent'),
    // fallback guards against a stale-cached app.css that predates the token
    accentAlt: v('--accent-alt') || '#8f7bff',
    panel: v('--panel'),
    fontUI: v('--font-ui'),
    fontMono: v('--font-mono'),
    status: {
      'Wishlist': v('--s-wishlist'),
      'Applied': v('--s-applied'),
      'Interview': v('--s-screen'),
      'Offer': v('--s-offer'),
      'Accepted': v('--s-accepted'),
      'Declined': v('--s-declined'),
      'Rejected': v('--s-rejected'),
      'Withdrawn': v('--s-withdrawn'),
    },
  };
}

export function motionAllowed() {
  return !matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Shared skeleton merged into every chart option: transparent background
// (the glass panels supply the surface), app fonts, glass-styled tooltips.
export function baseOption(t) {
  return {
    backgroundColor: 'transparent',
    animation: motionAllowed(),
    textStyle: { fontFamily: t.fontUI, color: t.textDim },
    tooltip: {
      backgroundColor: t.panel + 'ee',
      borderColor: t.line,
      borderWidth: 1,
      padding: [7, 11],
      textStyle: { color: t.text, fontSize: 12, fontFamily: t.fontUI },
      extraCssText: 'border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.35);backdrop-filter:blur(12px)',
    },
  };
}
