// Status-change effects: synthesized WebAudio chimes (no audio files) and
// small visual reactions. Sounds only ever fire right after a user gesture,
// which keeps browser autoplay rules satisfied.

let ctx = null;
let soundOn = localStorage.getItem('apptracker-sound') !== '0';

function audio() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

function note(freq, start, dur, { type = 'sine', gain = 0.07 } = {}) {
  const ac = audio();
  const osc = ac.createOscillator();
  const amp = ac.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  const t0 = ac.currentTime + start;
  amp.gain.setValueAtTime(0, t0);
  amp.gain.linearRampToValueAtTime(gain, t0 + 0.015);
  amp.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(amp).connect(ac.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.05);
}

export function isSoundOn() { return soundOn; }

export function toggleSound() {
  soundOn = !soundOn;
  localStorage.setItem('apptracker-sound', soundOn ? '1' : '0');
  if (soundOn) note(880, 0, 0.12);
  return soundOn;
}

export function playAdvance() {
  if (!soundOn) return;
  note(659.25, 0, 0.14);          // E5
  note(880, 0.09, 0.22);          // A5
}

export function playOffer() {
  if (!soundOn) return;
  [523.25, 659.25, 783.99, 1046.5].forEach((f, i) =>
    note(f, i * 0.09, 0.28, { type: 'triangle', gain: 0.06 }));
}

export function playReject() {
  if (!soundOn) return;
  note(220, 0, 0.18, { type: 'sine', gain: 0.06 });
  note(164.81, 0.11, 0.3, { type: 'sine', gain: 0.05 });
}

export function playAccepted() {
  if (!soundOn) return;
  // A proper fanfare: rising C-major run, sustained chord, then a sparkle.
  note(523.25, 0.0, 0.16, { type: 'triangle', gain: 0.06 });   // C5
  note(659.25, 0.1, 0.16, { type: 'triangle', gain: 0.06 });   // E5
  note(783.99, 0.2, 0.18, { type: 'triangle', gain: 0.06 });   // G5
  note(1046.5, 0.3, 0.35, { type: 'triangle', gain: 0.06 });   // C6
  note(1046.5, 0.55, 0.9, { type: 'triangle', gain: 0.05 });   // C6 chord
  note(1318.5, 0.55, 0.9, { type: 'triangle', gain: 0.05 });   // E6
  note(1568.0, 0.55, 0.9, { type: 'triangle', gain: 0.05 });   // G6
  note(2637.0, 0.7, 0.4, { type: 'sine', gain: 0.03 });        // E7 sparkle
}

export function playDeclined() {
  if (!soundOn) return;
  // A soft, resolved descent — a choice, not a loss (clearly warmer than reject).
  note(440, 0, 0.25, { type: 'sine', gain: 0.05 });            // A4
  note(369.99, 0.18, 0.45, { type: 'sine', gain: 0.045 });     // F#4
}

// ---- visuals ----

export function pulse(el, kind) {
  if (!el) return;
  const cls = { reject: 'fx-reject', offer: 'fx-offer', accept: 'fx-accept', declined: 'fx-declined' }[kind] || 'fx-advance';
  el.classList.remove('fx-advance', 'fx-offer', 'fx-reject', 'fx-accept', 'fx-declined');
  void el.offsetWidth; // restart the animation
  el.classList.add(cls);
  setTimeout(() => el.classList.remove(cls), 1300);
}

export function confetti(originEl, { count = 28, colors = ['#4dd6ff', '#46c98d', '#e8eef9', '#d9a441'] } = {}) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const rect = originEl ? originEl.getBoundingClientRect()
    : { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 };
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const useGsap = !!window.gsap;
  for (let i = 0; i < count; i++) {
    const p = document.createElement('span');
    p.className = 'fx-particle';
    p.style.background = colors[i % colors.length];
    p.style.left = cx + 'px';
    p.style.top = cy + 'px';
    document.body.appendChild(p);
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
    const dist = 70 + Math.random() * 120;
    if (useGsap) {
      // burst outward, then gravity takes over
      gsap.to(p, {
        x: Math.cos(angle) * dist,
        duration: 1.1 + Math.random() * 0.4,
        ease: 'power2.out',
      });
      gsap.to(p, {
        y: Math.sin(angle) * dist * 0.5 - 70,
        duration: 0.45,
        ease: 'power2.out',
        onComplete: () => gsap.to(p, { y: '+=260', duration: 0.9, ease: 'power1.in' }),
      });
      gsap.to(p, {
        rotation: (Math.random() - 0.5) * 540,
        scale: 0.35,
        autoAlpha: 0,
        duration: 1.3,
        ease: 'power1.in',
        onComplete: () => p.remove(),
      });
    } else {
      p.animate([
        { transform: 'translate(0,0) scale(1)', opacity: 1 },
        { transform: `translate(${Math.cos(angle) * dist}px, ${Math.sin(angle) * dist + 60}px) scale(.4) rotate(${Math.random() * 300}deg)`, opacity: 0 },
      ], { duration: 700 + Math.random() * 500, easing: 'cubic-bezier(.15,.6,.3,1)' })
        .onfinish = () => p.remove();
    }
  }
}

function screenFlash(kind) {
  const cls = `fx-screen-${kind}`;
  document.body.classList.remove('fx-screen-offer', 'fx-screen-reject', 'fx-screen-advance', 'fx-screen-accept');
  void document.body.offsetWidth;
  document.body.classList.add(cls);
  setTimeout(() => document.body.classList.remove(cls), 1350);
}

// One call site for "status changed" feedback.
export function statusFx(el, toStatus) {
  if (toStatus === 'Accepted') {
    pulse(el, 'accept');
    confetti(el, { count: 84, colors: ['#ffd166', '#ffe9a8', '#3ecf95', '#ffffff'] });
    screenFlash('accept');
    playAccepted();
  }
  else if (toStatus === 'Offer') { pulse(el, 'offer'); confetti(el); screenFlash('offer'); playOffer(); }
  else if (toStatus === 'Declined') { pulse(el, 'declined'); playDeclined(); }
  else if (toStatus === 'Rejected' || toStatus === 'Withdrawn') { pulse(el, 'reject'); screenFlash('reject'); playReject(); }
  else { pulse(el, 'advance'); playAdvance(); }
}
