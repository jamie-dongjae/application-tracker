// Generative ambient background music — synthesized live with WebAudio.
// No audio files, nothing copyrighted: a slow lo-fi chord loop (soft detuned
// pads through a lowpass filter + gentle echo) with sparse pentatonic plucks.
// Off by default; the toggle persists. Browsers require a user gesture before
// audio, so if it was left on we start at the first click/keypress.

let ctx = null;
let master = null;
let delaySend = null;
let running = false;
let schedulerId = null;
let chordAt = 0;
let chordIdx = 0;
let pluckAt = 0;
let enabled = localStorage.getItem('apptracker-music') === '1';

// Cmaj7 → Am7 → Fmaj7 → G7 (low, warm voicings)
const CHORDS = [
  [130.81, 196.00, 246.94, 329.63],
  [110.00, 164.81, 196.00, 261.63],
  [87.31, 130.81, 164.81, 220.00],
  [98.00, 146.83, 174.61, 246.94],
];
const CHORD_SECONDS = 9;
const PLUCKS = [261.63, 293.66, 329.63, 392.00, 440.00, 523.25, 587.33, 659.25];

function setup() {
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  master = ctx.createGain();
  master.gain.value = 0;
  const filter = ctx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.value = 1400;
  master.connect(filter).connect(ctx.destination);

  // gentle echo for space
  delaySend = ctx.createGain();
  delaySend.gain.value = 0.35;
  const delay = ctx.createDelay(1.0);
  delay.delayTime.value = 0.38;
  const feedback = ctx.createGain();
  feedback.gain.value = 0.3;
  delaySend.connect(delay);
  delay.connect(feedback).connect(delay);
  delay.connect(master);
}

function padVoice(freq, t0, dur) {
  for (const detune of [-4, 3]) {
    const osc = ctx.createOscillator();
    const amp = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = freq;
    osc.detune.value = detune;
    amp.gain.setValueAtTime(0, t0);
    amp.gain.linearRampToValueAtTime(0.028, t0 + 2.4);
    amp.gain.setValueAtTime(0.028, t0 + dur - 3);
    amp.gain.linearRampToValueAtTime(0, t0 + dur);
    osc.connect(amp).connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.1);
  }
}

function pluck(t0) {
  const osc = ctx.createOscillator();
  const amp = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = PLUCKS[Math.floor(Math.random() * PLUCKS.length)];
  amp.gain.setValueAtTime(0, t0);
  amp.gain.linearRampToValueAtTime(0.05, t0 + 0.02);
  amp.gain.exponentialRampToValueAtTime(0.0001, t0 + 1.8);
  osc.connect(amp).connect(master);
  amp.connect(delaySend);
  osc.start(t0);
  osc.stop(t0 + 2);
}

function tick() {
  const horizon = ctx.currentTime + 2.5;
  while (chordAt < horizon) {
    const chord = CHORDS[chordIdx % CHORDS.length];
    // slight overlap so chords crossfade
    for (const freq of chord) padVoice(freq, chordAt, CHORD_SECONDS + 2.5);
    chordAt += CHORD_SECONDS;
    chordIdx += 1;
  }
  while (pluckAt < horizon) {
    if (Math.random() < 0.75) pluck(pluckAt);
    pluckAt += 2.2 + Math.random() * 3.2;
  }
}

function start() {
  if (running) return;
  if (!ctx) setup();
  if (ctx.state === 'suspended') ctx.resume();
  running = true;
  chordAt = ctx.currentTime + 0.15;
  pluckAt = ctx.currentTime + 4;
  chordIdx = 0;
  master.gain.cancelScheduledValues(ctx.currentTime);
  master.gain.setValueAtTime(0, ctx.currentTime);
  master.gain.linearRampToValueAtTime(1, ctx.currentTime + 3);
  tick();
  schedulerId = setInterval(tick, 800);
}

function stop() {
  if (!running) return;
  running = false;
  clearInterval(schedulerId);
  master.gain.cancelScheduledValues(ctx.currentTime);
  master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
  master.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.2);
}

export function isMusicOn() { return enabled; }

export function toggleMusic() {
  enabled = !enabled;
  localStorage.setItem('apptracker-music', enabled ? '1' : '0');
  enabled ? start() : stop();
  return enabled;
}

// If music was left on, begin at the first user gesture (autoplay policy).
if (enabled) {
  const kick = () => { if (enabled) start(); };
  window.addEventListener('pointerdown', kick, { once: true });
  window.addEventListener('keydown', kick, { once: true });
}
