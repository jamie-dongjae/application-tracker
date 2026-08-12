// Right-side drawer: view + edit one application.

import { getApp, patchApplication, deleteApplication, undo, state, emit, esc, fmtDate } from '../state.js';
import { renderForm, readForm, validateForm } from './appform.js';
import { toast } from './toast.js';

const root = document.getElementById('drawer-root');

export function openDetail(id) {
  const app = getApp(id);
  if (!app) return;
  state.selectedId = id;
  root.innerHTML = `
    <div class="drawer-veil"></div>
    <div class="drawer" role="dialog" aria-modal="true" aria-label="Application detail">
      <div class="drawer-head">
        <div class="drawer-title">${esc(app.company)}</div>
        ${app.url ? `<a class="ghost-btn" href="${esc(app.url)}" target="_blank" rel="noopener">Posting ↗</a>` : ''}
        <button class="close-x" data-close aria-label="Close">✕</button>
      </div>
      <div class="drawer-body">
        ${renderForm(app)}
        <hr class="sep">
        <div class="faint mono" style="font-size:11px">
          #${app.id} · added ${esc(fmtDate(app.date_applied))} · updated ${esc(String(app.last_updated).slice(0, 16).replace('T', ' '))}
          ${app.geo_status ? ` · geo: ${esc(app.geo_status)}` : ''}
        </div>
      </div>
      <div class="drawer-foot">
        <button class="danger-btn" data-delete>Delete</button>
        <span class="spacer"></span>
        <button class="ghost-btn" data-close-2>Close</button>
        <button class="accent-btn" data-save>Save changes</button>
      </div>
    </div>`;

  const closeAll = () => closeDetail();
  root.querySelector('.drawer-veil').onclick = closeAll;
  root.querySelector('[data-close]').onclick = closeAll;
  root.querySelector('[data-close-2]').onclick = closeAll;

  root.querySelector('[data-save]').onclick = async () => {
    const bodyEl = root.querySelector('.drawer-body');
    const missing = validateForm(bodyEl);
    if (missing.length) { toast(`Missing: ${missing.join(', ')}`, { error: true }); return; }
    try {
      await patchApplication(id, readForm(bodyEl));
      closeDetail();
      toast('Saved.', { action: 'Undo', onAction: async () => { await undo(); } });
    } catch (err) {
      if (err.status !== 409) toast('Could not save. ' + err.message, { error: true });
    }
  };

  root.querySelector('[data-delete]').onclick = async () => {
    try {
      await deleteApplication(id);
      closeDetail();
      toast(`Deleted ${app.company} — ${app.title}`, {
        action: 'Undo', onAction: async () => { await undo(); toast('Restored.'); },
      });
    } catch (err) {
      if (err.status !== 409) toast('Could not delete. ' + err.message, { error: true });
    }
  };
}

export function closeDetail() {
  root.innerHTML = '';
  state.selectedId = null;
  emit('selection');
}

export function isDetailOpen() { return !!root.firstChild; }
