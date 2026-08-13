// GSAP-powered motion (per greensock/gsap-skills guidance):
// transforms + opacity only, string eases, timelines over delay chains,
// clearProps cleanup, Flip for kanban layout moves. Everything degrades
// gracefully — the app is fully usable if the CDN or motion is unavailable.

let configured = false;

export function motionOK() {
  if (!window.gsap) return false;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  if (!configured) {
    configured = true;
    gsap.defaults({ duration: 0.5, ease: 'power2.out' });
    if (window.Flip) gsap.registerPlugin(Flip);
  }
  return true;
}

// ---- view entrances (run on navigation, not on data refreshes) ----

const STAGGER = { amount: 0.18 };

export function enterView(el, name) {
  if (!motionOK()) return;
  // Reset any interrupted entrance (rapid view switching) before starting fresh.
  const everything = el.querySelectorAll('*');
  gsap.killTweensOf(everything);
  gsap.set(everything, { clearProps: 'transform,opacity,visibility' });
  const tl = gsap.timeline();

  const panels = el.querySelectorAll(
    { pipeline: '.col, .tray', prep: '.prep-cat', map: '.map-panel' }[name] || '.panel');
  if (panels.length) {
    tl.from(panels, {
      y: 16, autoAlpha: 0, stagger: STAGGER, clearProps: 'transform,opacity,visibility',
    });
  }

  if (name === 'dashboard' || name === 'insights') {
    countUp(el);
    const fills = el.querySelectorAll('.barlist-fill, .funnel-fill');
    if (fills.length) {
      tl.from(fills, {
        scaleX: 0, duration: 0.7, ease: 'power3.out',
        stagger: { amount: 0.25 }, clearProps: 'transform',
      }, 0.15);
    }
  }
}

function countUp(el) {
  el.querySelectorAll('.kpi-value').forEach((node) => {
    const text = node.firstChild;
    if (!text || text.nodeType !== Node.TEXT_NODE) return;
    const target = Number(text.data.trim());
    if (!Number.isInteger(target) || target <= 0) return;
    const proxy = { v: 0 };
    gsap.to(proxy, {
      v: target, duration: 0.7, ease: 'power2.out',
      snap: { v: 1 },
      onUpdate: () => { text.data = String(proxy.v); },
    });
  });
}

// ---- kanban Flip: cards glide to their new column across a re-render ----

export function captureCards() {
  if (!motionOK() || !window.Flip) return null;
  const cards = document.querySelectorAll('#view-pipeline .card');
  return cards.length ? Flip.getState(cards) : null;
}

export function playFlip(state) {
  if (!state || !motionOK() || !window.Flip) return;
  Flip.from(state, {
    targets: '#view-pipeline .card',
    duration: 0.45,
    ease: 'power2.inOut',
    absolute: true,
  });
}
