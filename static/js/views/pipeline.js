// Pipeline kanban: Wishlist → Applied → Interview → Offer, with quick
// advance/reject buttons on every card and a closed tray below.

import { state, BOARD_STATUSES, CLOSED_STATUSES, NEXT_STATUS, STATUS_COLORS, patchApplication, undo, daysSince, esc } from '../state.js';
import { openDetail } from '../components/detail.js';
import { toast } from '../components/toast.js';
import { statusFx } from '../components/fx.js';
import { captureCards, playFlip } from '../components/motion.js';

async function changeStatus(id, to, cardEl) {
  const app = state.apps.find((a) => a.id === id);
  if (!app || app.status === to) return;
  const from = app.status;
  // Capture positions before any re-render; animate once the server confirm
  // has re-rendered too, so the Flip glide plays out uninterrupted.
  const flipState = captureCards();
  try {
    await patchApplication(id, { status: to }, { optimistic: true });
    playFlip(flipState);
    const fresh = document.querySelector(`#view-pipeline .card[data-id="${id}"]`);
    statusFx(fresh || cardEl, to);
    toast(`${app.company}: ${from} → ${to}`, {
      action: 'Undo', onAction: async () => { await undo(); },
    });
  } catch (err) {
    if (err.status !== 409) toast('Change failed. ' + err.message, { error: true });
  }
}

export function renderPipeline(el) {
  const staleDays = state.settings.stale_days || 14;
  const closed = state.apps.filter((a) => CLOSED_STATUSES.includes(a.status));

  const card = (a) => {
    const idle = daysSince(a.last_updated || a.date_applied);
    const isStale = idle != null && idle >= staleDays && !CLOSED_STATUSES.includes(a.status) && a.status !== 'Wishlist';
    const next = NEXT_STATUS[a.status];
    const isClosed = CLOSED_STATUSES.includes(a.status);
    const actions = isClosed
      ? `<button class="card-btn" data-act="revive" title="Back to Applied">↩ Revive</button>`
      : `${next ? `<button class="card-btn adv" data-act="advance" title="Move to ${esc(next)}">▸ ${esc(next)}</button>` : ''}
         <button class="card-btn rej" data-act="reject" title="Mark rejected">✕ Reject</button>`;
    return `
      <div class="card" draggable="true" data-id="${a.id}" data-flip-id="app-${a.id}">
        <div class="card-company">${esc(a.company)}</div>
        <div class="card-title">${esc(a.title)}</div>
        <div class="card-meta">
          ${a.location ? `<span>${esc(a.location)}</span>` : ''}
          ${a.sponsorship === 'Mentioned' ? `<span title="Sponsorship mentioned">visa✓</span>` : ''}
          <span class="spacer"></span>
          <span class="${isStale ? 'stale' : ''}" title="Days since last update">${idle ?? '—'}d</span>
        </div>
        <div class="card-actions">${actions}</div>
      </div>`;
  };

  el.innerHTML = `
    <div class="board">
      ${BOARD_STATUSES.map((status) => {
        const rows = state.apps.filter((a) => a.status === status);
        return `
          <div class="col" data-status="${esc(status)}">
            <div class="col-head">
              <span class="dot" style="background:${STATUS_COLORS[status]}"></span>
              <span class="col-name">${esc(status)}</span>
              <span class="col-count">${rows.length}</span>
            </div>
            ${rows.map(card).join('') || `<div class="empty">—</div>`}
          </div>`;
      }).join('')}
    </div>

    <details class="tray">
      <summary><span class="dot" style="background:${STATUS_COLORS.Rejected}"></span>
        Closed · <span class="num">${closed.length}</span>
        <span class="faint">(rejected & withdrawn — revive puts one back into Applied)</span>
      </summary>
      <div class="tray-list" data-status="Rejected">
        ${closed.map(card).join('') || `<div class="empty">Nothing closed yet.</div>`}
      </div>
    </details>`;

  el.querySelectorAll('.card').forEach((cardEl) => {
    const id = Number(cardEl.dataset.id);
    cardEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.card-btn');
      if (!btn) { openDetail(id); return; }
      e.stopPropagation();
      const app = state.apps.find((a) => a.id === id);
      if (!app) return;
      const to = btn.dataset.act === 'reject' ? 'Rejected'
        : btn.dataset.act === 'revive' ? 'Applied'
        : NEXT_STATUS[app.status];
      if (to) changeStatus(id, to, cardEl);
    });
    cardEl.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', String(id));
      e.dataTransfer.effectAllowed = 'move';
      cardEl.classList.add('dragging');
    });
    cardEl.addEventListener('dragend', () => cardEl.classList.remove('dragging'));
  });

  el.querySelectorAll('[data-status]').forEach((zone) => {
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const id = Number(e.dataTransfer.getData('text/plain'));
      const target = el.querySelector(`.card[data-id="${id}"]`);
      changeStatus(id, zone.dataset.status, target || zone);
    });
  });
}
