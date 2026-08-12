// Pipeline kanban: drag between stage columns; closed tray for Rejected/Withdrawn.

import { state, BOARD_STATUSES, CLOSED_STATUSES, STATUS_COLORS, patchApplication, undo, daysSince, esc } from '../state.js';
import { openDetail } from '../components/detail.js';
import { toast } from '../components/toast.js';

export function renderPipeline(el) {
  const staleDays = state.settings.stale_days || 14;
  const closed = state.apps.filter((a) => CLOSED_STATUSES.includes(a.status));

  const card = (a) => {
    const idle = daysSince(a.last_updated || a.date_applied);
    const isStale = idle != null && idle >= staleDays && !CLOSED_STATUSES.includes(a.status) && a.status !== 'Wishlist';
    return `
      <div class="card" draggable="true" data-id="${a.id}">
        <div class="card-company">${esc(a.company)}</div>
        <div class="card-title">${esc(a.title)}</div>
        <div class="card-meta">
          ${a.location ? `<span>${esc(a.location)}</span>` : ''}
          ${a.sponsorship === 'Mentioned' ? `<span title="Sponsorship mentioned">visa✓</span>` : ''}
          <span class="spacer"></span>
          <span class="${isStale ? 'stale' : ''}" title="Days since last update">${idle ?? '—'}d</span>
        </div>
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
        <span class="faint">(drag a card here to close it — or drag one out to revive)</span>
      </summary>
      <div class="tray-list" data-status="Rejected">
        ${closed.map(card).join('') || `<div class="empty">Nothing closed yet.</div>`}
      </div>
    </details>`;

  // Click → detail; drag → status change.
  el.querySelectorAll('.card').forEach((cardEl) => {
    const id = Number(cardEl.dataset.id);
    cardEl.addEventListener('click', () => openDetail(id));
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
    zone.addEventListener('drop', async (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const id = Number(e.dataTransfer.getData('text/plain'));
      const app = state.apps.find((a) => a.id === id);
      const to = zone.dataset.status;
      if (!app || app.status === to) return;
      const from = app.status;
      try {
        await patchApplication(id, { status: to }, { optimistic: true });
        toast(`${app.company}: ${from} → ${to}`, {
          action: 'Undo', onAction: async () => { await undo(); },
        });
      } catch (err) {
        if (err.status !== 409) toast('Move failed. ' + err.message, { error: true });
      }
    });
  });
}
