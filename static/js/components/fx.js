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

// ---- visuals ----

export function pulse(el, kind) {
  if (!el) return;
  const cls = kind === 'reject' ? 'fx-reject' : kind === 'offer' ? 'fx-offer' : 'fx-advance';
  el.classList.remove('fx-advance', 'fx-offer', 'fx-reject');
  void el.offsetWidth; // restart the animation
  el.classList.add(cls);
  setTimeout(() => el.classList.remove(cls), 900);
}

export function confetti(originEl) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const rect = originEl ? originEl.getBoundingClientRect()
    : { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 };
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const colors = ['#4dd6ff', '#46c98d', '#e8eef9', '#d9a441'];
  const useGsap = !!window.gsap;
  for (let i = 0; i < 28; i++) {
    const p = document.createElement('span');
    p.className = 'fx-particle';
    p.style.background = colors[i % colors.length];
    p.style.left = cx + 'px';
    p.style.top = cy + 'px';
    document.body.appendChild(p);
    const angle = (Math.PI * 2 * i) / 28 + Math.random() * 0.5;
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
  document.body.classList.remove('fx-screen-offer', 'fx-screen-reject', 'fx-screen-advance');
  void document.body.offsetWidth;
  document.body.classList.add(cls);
  setTimeout(() => document.body.classList.remove(cls), 950);
}

// One call site for "status changed" feedback.
export function statusFx(el, toStatus) {
  if (toStatus === 'Offer') { pulse(el, 'offer'); confetti(el); screenFlash('offer'); playOffer(); }
  else if (toStatus === 'Rejected' || toStatus === 'Withdrawn') { pulse(el, 'reject'); screenFlash('reject'); playReject(); }
  else { pulse(el, 'advance'); playAdvance(); }
}
