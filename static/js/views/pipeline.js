// Pipeline kanban: Wishlist → Applied → Interview → Offer, with quick
// advance/reject buttons on every card and a closed tray below.

import { state, BOARD_STATUSES, CLOSED_STATUSES, NEXT_STATUS, STATUS_COLORS, TRACKS,
  TRACK_LABELS, STATE_LABELS, patchApplication, undo, daysSince, fmtDate, esc } from '../state.js';
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

// current_state values worth surfacing as a chip on the card.
const FLAG_STATES = ['stale', 'on_hold_employer', 'action_required', 'scheduling'];

function matchesBoardFilter(a) {
  const f = state.boardFilter;
  if (f.track && (a.track || 'career') !== f.track) return false;
  if (f.current_state && a.current_state !== f.current_state) return false;
  return true;
}

export function renderPipeline(el) {
  const staleDays = state.settings.stale_days || 14;
  const boardApps = state.apps.filter(matchesBoardFilter);
  const closed = boardApps.filter((a) => CLOSED_STATUSES.includes(a.status));
  const filterOn = !!(state.boardFilter.track || state.boardFilter.current_state);

  const card = (a) => {
    const idle = daysSince(a.last_updated || a.date_applied);
    const isStale = idle != null && idle >= staleDays && !CLOSED_STATUSES.includes(a.status) && a.status !== 'Wishlist';
    const next = NEXT_STATUS[a.status];
    const isClosed = CLOSED_STATUSES.includes(a.status);
    const dueOver = a.due && String(a.due).slice(0, 10) < new Date().toISOString().slice(0, 10);
    const actions = isClosed
      ? `<button class="card-btn" data-act="revive" title="Back to Applied">↩ Revive</button>`
      : a.status === 'Offer'
        ? `<button class="card-btn acc" data-act="accept" title="Accept the offer">✓ Accept</button>
           <button class="card-btn rej" data-act="reject" title="Offer fell through / rejected">✕ Rejected</button>
           <button class="card-btn wd" data-act="decline" title="Turn the offer down">⤺ Decline</button>`
        : `${next ? `<button class="card-btn adv" data-act="advance" title="Move to ${esc(next)}">▸ ${esc(next)}</button>` : ''}
           <button class="card-btn rej" data-act="reject" title="Mark rejected">✕ Reject</button>
           <button class="card-btn wd" data-act="withdraw" title="Withdraw your application">⤺ Withdraw</button>`;
    return `
      <div class="card" draggable="true" data-id="${a.id}" data-flip-id="app-${a.id}">
        <div class="card-company">${esc(a.company)}</div>
        <div class="card-title">${esc(a.title)}</div>
        <div class="card-meta">
          ${isClosed ? `<span><span class="dot" style="background:${STATUS_COLORS[a.status]}"></span> ${esc(a.status)}</span>` : ''}
          ${a.track && a.track !== 'career' ? `<span class="badge badge-track" title="Track">${esc(TRACK_LABELS[a.track] || a.track)}</span>` : ''}
          ${!isClosed && FLAG_STATES.includes(a.current_state) ? `<span class="badge badge-state s-${esc(a.current_state)}">${esc(STATE_LABELS[a.current_state])}</span>` : ''}
          ${a.next_action && a.due && !isClosed ? `<span class="badge badge-due ${dueOver ? 'overdue' : ''}" title="${esc(a.next_action)}">⏰ ${esc(String(fmtDate(a.due)).slice(5))}</span>` : ''}
          ${a.location ? `<span>${esc(a.location)}</span>` : ''}
          ${a.sponsorship === 'Mentioned' ? `<span title="Sponsorship mentioned">visa✓</span>` : ''}
          <span class="spacer"></span>
          <span class="${isStale ? 'stale' : ''}" title="Days since last update">${idle ?? '—'}d</span>
        </div>
        <div class="card-actions">${actions}</div>
      </div>`;
  };

  const filterChips = (key, values, labels) => values.map((v) => `
    <button class="filter-chip ${state.boardFilter[key] === v ? 'on' : ''}" data-filter="${key}" data-value="${esc(v)}">
      ${esc(labels[v] || v)}
    </button>`).join('');

  el.innerHTML = `
    <div class="board-filters">
      <span class="faint">Track:</span>
      ${filterChips('track', TRACKS, TRACK_LABELS)}
      <span class="faint" style="margin-left:12px">State:</span>
      ${filterChips('current_state', FLAG_STATES, STATE_LABELS)}
      ${filterOn ? `<button class="filter-chip clear" data-filter-clear>✕ clear</button>` : ''}
    </div>
    <div class="board">
      ${BOARD_STATUSES.map((status) => {
        const rows = boardApps.filter((a) => a.status === status);
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
      <summary><span class="dot" style="background:var(--text-faint)"></span>
        Closed · <span class="num">${closed.length}</span>
        <span class="faint">(accepted · declined · rejected · withdrawn — revive puts one back into Applied)</span>
      </summary>
      <div class="tray-list" data-status="Rejected">
        ${closed.map(card).join('') || `<div class="empty">Nothing closed yet.</div>`}
      </div>
    </details>`;

  el.querySelectorAll('[data-filter]').forEach((chip) => {
    chip.addEventListener('click', () => {
      const key = chip.dataset.filter;
      const value = chip.dataset.value;
      state.boardFilter[key] = state.boardFilter[key] === value ? '' : value;
      renderPipeline(el);
    });
  });
  const clearBtn = el.querySelector('[data-filter-clear]');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    state.boardFilter = { track: '', current_state: '' };
    renderPipeline(el);
  });

  el.querySelectorAll('.card').forEach((cardEl) => {
    const id = Number(cardEl.dataset.id);
    cardEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.card-btn');
      if (!btn) { openDetail(id); return; }
      e.stopPropagation();
      const app = state.apps.find((a) => a.id === id);
      if (!app) return;
      const to = {
        reject: 'Rejected',
        revive: 'Applied',
        accept: 'Accepted',
        decline: 'Declined',
        withdraw: 'Withdrawn',
      }[btn.dataset.act] || NEXT_STATUS[app.status];
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
      const app = state.apps.find((a) => a.id === id);
      if (!app) return;
      let to = zone.dataset.status;
      if (zone.classList.contains('tray-list')) {
        // The tray holds four outcomes, so it can't hard-assign one status:
        // closed cards dropped back onto it stay as they are, and dragging an
        // Offer there reads as the user turning it down, not the company.
        if (CLOSED_STATUSES.includes(app.status)) return;
        to = app.status === 'Offer' ? 'Declined' : 'Rejected';
      }
      const target = el.querySelector(`.card[data-id="${id}"]`);
      changeStatus(id, to, target || zone);
    });
  });
}
