// Mail sync button + Gmail credentials modal. One click: IMAP fetch since the
// last sync, auto-apply mechanically-certain updates, queue the rest for review.

import { api } from '../api.js';
import { refreshApps, refreshReview } from '../state.js';
import { toast } from './toast.js';

const modalRoot = document.getElementById('modal-root');

function summaryText(r) {
  const bits = [];
  const applied = (r.applied?.updated || 0) + (r.applied?.added || 0);
  bits.push(`${applied} applied`);
  if (r.queued) bits.push(`${r.queued} to review`);
  if (r.already_known) bits.push(`${r.already_known} already known`);
  if (!applied && !r.queued && !r.already_known) bits.push('nothing new');
  return bits.join(' · ');
}

export function wireSyncButton() {
  const btn = document.getElementById('sync-btn');
  if (!btn) return;
  btn.onclick = () => runSync(btn);
}

async function runSync(btn) {
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = '✉ Syncing…';
  try {
    const result = await api.post('/api/sync/mail');
    (result.warnings || []).forEach((w) => toast(w));
    toast(`Mail sync: ${summaryText(result)}`);
    await Promise.all([refreshApps(), refreshReview()]);
  } catch (err) {
    if (err.status === 428) {
      openCredentialsModal({ thenSync: true });
    } else if (err.status === 401) {
      toast('Gmail rejected the app password — update it.', { error: true });
      openCredentialsModal({ thenSync: true });
    } else if (err.status === 409) {
      toast('Close tracker.xlsx in Excel, then sync again.', { error: true });
    } else {
      toast('Mail sync failed. ' + (err.message || ''), { error: true });
    }
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

export function openCredentialsModal({ thenSync = false } = {}) {
  if (modalRoot.firstChild) return;
  modalRoot.innerHTML = `
    <div class="modal-veil">
      <div class="modal" role="dialog" aria-modal="true" aria-label="Gmail credentials">
        <div class="modal-head">
          <h2 class="modal-title">Connect Gmail</h2>
          <button class="close-x" data-close aria-label="Close">✕</button>
        </div>
        <div class="modal-body">
          <p class="faint" style="margin-top:0">The tracker reads your mailbox over IMAP
            with a Google <b>app password</b> (read-only — nothing is ever marked as read
            or sent). Create one at Google Account → Security → 2-Step Verification →
            App passwords, then paste it here. Stored only on this machine.</p>
          <div class="form-grid">
            <div class="field full"><label>Gmail address</label>
              <input name="gmail-email" type="email" placeholder="you@gmail.com"></div>
            <div class="field full"><label>App password</label>
              <input name="gmail-pass" type="password" placeholder="xxxx xxxx xxxx xxxx"></div>
          </div>
          <div class="faint" data-cred-error style="color:var(--s-rejected);min-height:16px"></div>
        </div>
        <div class="modal-foot">
          <span class="spacer"></span>
          <button class="ghost-btn" data-close-2>Cancel</button>
          <button class="accent-btn" data-cred-save>Connect</button>
        </div>
      </div>
    </div>`;
  const close = () => { modalRoot.innerHTML = ''; };
  modalRoot.querySelector('.modal-veil').addEventListener('mousedown', (e) => {
    if (e.target === e.currentTarget) close();
  });
  modalRoot.querySelector('[data-close]').onclick = close;
  modalRoot.querySelector('[data-close-2]').onclick = close;

  const saveBtn = modalRoot.querySelector('[data-cred-save]');
  saveBtn.onclick = async () => {
    const email = modalRoot.querySelector('[name="gmail-email"]').value.trim();
    const pass = modalRoot.querySelector('[name="gmail-pass"]').value;
    const errEl = modalRoot.querySelector('[data-cred-error]');
    if (!email || !pass) { errEl.textContent = 'Both fields are required.'; return; }
    saveBtn.disabled = true;
    saveBtn.textContent = 'Verifying…';
    try {
      await api.post('/api/sync/mail/credentials', { email, app_password: pass });
      close();
      toast('Gmail connected.');
      if (thenSync) {
        const btn = document.getElementById('sync-btn');
        if (btn) runSync(btn);
      }
    } catch (err) {
      errEl.textContent = err.status === 401
        ? 'Gmail rejected that app password — check it and that 2-Step Verification is on.'
        : 'Could not reach Gmail. ' + (err.message || '');
      saveBtn.disabled = false;
      saveBtn.textContent = 'Connect';
    }
  };
}

// ---- review queue actions (used by the dashboard panel) ----

export async function applyReviewItem(id) {
  const result = await api.post(`/api/sync/review/${id}/apply`);
  await Promise.all([refreshApps(), refreshReview()]);
  return result;
}

export async function dismissReviewItem(id) {
  await api.post(`/api/sync/review/${id}/dismiss`);
  await refreshReview();
}
