// Add-application flow: URL → fetch → prefilled review form → save.
// Falls back to paste-the-description parsing when a site blocks fetching.

import { api } from '../api.js';
import { createApplication, undo, esc } from '../state.js';
import { renderForm, readForm, validateForm } from './appform.js';
import { toast } from './toast.js';

const root = document.getElementById('modal-root');

export function openAddFlow() {
  if (root.firstChild) return;
  root.innerHTML = `
    <div class="modal-veil">
      <div class="modal" role="dialog" aria-modal="true" aria-label="New application">
        <div class="modal-head">
          <h2 class="modal-title">New application</h2>
          <button class="close-x" data-close aria-label="Close">✕</button>
        </div>
        <div class="modal-body" id="addflow-body"></div>
        <div class="modal-foot" id="addflow-foot"></div>
      </div>
    </div>`;
  root.querySelector('.modal-veil').addEventListener('mousedown', (e) => {
    if (e.target === e.currentTarget) close();
  });
  root.querySelector('[data-close]').onclick = close;
  stepUrl();
}

export function close() { root.innerHTML = ''; }

export function isOpen() { return !!root.firstChild; }

function body() { return root.querySelector('#addflow-body'); }
function foot() { return root.querySelector('#addflow-foot'); }

// ---- step 1: URL ----

function stepUrl() {
  body().innerHTML = `
    <div class="field">
      <label>Job posting URL</label>
      <div class="url-row">
        <input id="af-url" type="url" placeholder="https://…" autocomplete="off" spellcheck="false">
        <button class="accent-btn" id="af-fetch">Fetch details</button>
      </div>
    </div>
    <div class="fetch-note faint">Company, title, location, salary and more are prefilled from the posting.
      <span class="spacer"></span><span class="link" id="af-manual">Fill manually</span>
    </div>
    <div id="af-status"></div>`;
  foot().innerHTML = '';
  const input = body().querySelector('#af-url');
  input.focus();
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') fetchUrl(); });
  body().querySelector('#af-fetch').onclick = fetchUrl;
  body().querySelector('#af-manual').onclick = () => stepReview({ fields: {}, provenance: {}, warnings: [] });
}

async function fetchUrl() {
  const input = body().querySelector('#af-url');
  const url = input.value.trim();
  if (!url) { input.focus(); return; }
  const statusEl = body().querySelector('#af-status');
  const btn = body().querySelector('#af-fetch');
  btn.disabled = true;
  statusEl.innerHTML = `<div class="fetch-note"><span class="spinner"></span>Fetching the posting…</div>`;
  try {
    const result = await Promise.race([
      api.post('/api/prefill', { url }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 20000)),
    ]);
    if (result.blocked) {
      stepPaste(url, result);
    } else if (result.fetch_error && !result.fields?.title) {
      stepPaste(url, result, `Could not reach the page (${esc(result.fetch_error)}).`);
    } else {
      stepReview(result);
    }
  } catch (err) {
    stepPaste(url, { fields: {}, provenance: {}, warnings: [] },
      err.message === 'timeout' ? 'The site took too long to respond.' : 'Fetching failed.');
  } finally {
    btn.disabled = false;
  }
}

// ---- fallback: paste description ----

function stepPaste(url, result, reason) {
  const message = reason || 'This site blocks automated access (common for LinkedIn and Indeed).';
  body().innerHTML = `
    <div class="notice">${esc(message)} Paste the job description below — it is parsed locally.</div>
    <div class="field full">
      <label>Job description</label>
      <textarea id="af-paste" rows="9" placeholder="Paste the full posting text — title, company, location, salary…"></textarea>
    </div>`;
  foot().innerHTML = `
    <button class="ghost-btn" id="af-back">Back</button>
    <button class="ghost-btn" id="af-skip">Skip — fill manually</button>
    <button class="accent-btn" id="af-parse">Parse text</button>`;
  body().querySelector('#af-paste').focus();
  foot().querySelector('#af-back').onclick = stepUrl;
  foot().querySelector('#af-skip').onclick = () =>
    stepReview({ fields: { ...result.fields, url }, provenance: result.provenance || {}, warnings: [] });
  foot().querySelector('#af-parse').onclick = async () => {
    const text = body().querySelector('#af-paste').value.trim();
    if (text.length < 10) return;
    const parsed = await api.post('/api/prefill/text', { text, url });
    parsed.fields = { ...result.fields, ...parsed.fields, url };
    parsed.provenance = { ...result.provenance, ...parsed.provenance };
    stepReview(parsed);
  };
}

// ---- step 2: review & save ----

function stepReview(result) {
  const { fields = {}, provenance = {}, warnings = [], evidence = {}, method } = result;
  fields.status = fields.status || 'Applied';
  const warningHtml = warnings.length
    ? `<div class="notice">${warnings.map(esc).join('<br>')}</div>` : '';
  const evidenceHtml = evidence.sponsorship_snippet
    ? `<blockquote class="evidence">${esc(evidence.sponsorship_snippet)}</blockquote>` : '';
  const methodHtml = method && method !== 'URL'
    ? `<div class="fetch-note faint">Prefilled via ${esc(method)} — review before saving.</div>` : '';
  body().innerHTML = `${methodHtml}${warningHtml}${renderForm(fields, provenance)}${evidenceHtml}`;
  foot().innerHTML = `
    <button class="ghost-btn" data-back>Back</button>
    <button class="accent-btn" data-save>Save application</button>`;
  foot().querySelector('[data-back]').onclick = stepUrl;
  foot().querySelector('[data-save]').onclick = save;
  const first = body().querySelector('[name="company"]');
  if (first && !first.value) first.focus();

  async function save() {
    const missing = validateForm(body());
    if (missing.length) {
      toast(`Missing: ${missing.join(', ')}`, { error: true });
      return;
    }
    const payload = readForm(body());
    const btn = foot().querySelector('[data-save]');
    btn.disabled = true;
    btn.textContent = 'Saving…';
    try {
      const rec = await createApplication(payload);
      close();
      toast(`Added ${rec.company} — ${rec.title}`, {
        action: 'Undo',
        onAction: async () => { await undo(); toast('Removed again.'); },
      });
    } catch (err) {
      btn.disabled = false;
      btn.textContent = 'Save application';
      if (err.status !== 409) toast('Could not save. ' + err.message, { error: true });
    }
  }
}
