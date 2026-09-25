// Right-side drawer: view + edit one application.

import { getApp, patchApplication, deleteApplication, undo, state, emit, esc, fmtDate,
  employerRuleFor, STATE_LABELS, TRACK_LABELS, STAGE_LABELS } from '../state.js';
import { api } from '../api.js';
import { renderForm, readForm, validateForm } from './appform.js';
import { toast } from './toast.js';

const root = document.getElementById('drawer-root');

const EVENT_TYPES = ['applied', 'confirmed', 'recruiter_screen', 'assessment', 'hiring_manager',
  'final', 'offer', 'inbound', 'note', 'nudge', 'redirected', 'withdrawn_by_me', 'closed'];

function headBadges(app) {
  const chips = [];
  if (app.track && app.track !== 'career') chips.push(`<span class="badge badge-track">${esc(TRACK_LABELS[app.track] || app.track)}</span>`);
  if (app.stage_reached) chips.push(`<span class="badge">${esc(STAGE_LABELS[app.stage_reached] || app.stage_reached)}</span>`);
  if (app.current_state && app.current_state !== 'closed') chips.push(`<span class="badge badge-state s-${esc(app.current_state)}">${esc(STATE_LABELS[app.current_state] || app.current_state)}</span>`);
  if (app.due) chips.push(`<span class="badge badge-due">⏰ ${esc(fmtDate(app.due))}</span>`);
  return chips.join(' ');
}

async function renderTimeline(section, appId) {
  let events = [];
  try {
    events = (await api.get(`/api/applications/${appId}/events`)).events;
  } catch { /* drawer may already be closed */ }
  const rows = events.map((e) => `
    <tr>
      <td class="mono faint">${esc(fmtDate(e.date))}</td>
      <td><span class="badge">${esc(e.event)}</span></td>
      <td>${esc(e.note || '')}</td>
      <td><button class="close-x ev-del" data-ev-del="${e.id}" title="Delete event">✕</button></td>
    </tr>`).join('');
  section.innerHTML = `
    <h3 class="panel-title">Timeline</h3>
    ${events.length ? `<table class="timeline"><tbody>${rows}</tbody></table>`
      : `<div class="empty">No events yet.</div>`}
    <div class="timeline-add">
      <input type="date" data-ev-date>
      <input list="event-types" data-ev-type placeholder="event">
      <datalist id="event-types">${EVENT_TYPES.map((t) => `<option value="${t}">`).join('')}</datalist>
      <input type="text" data-ev-note placeholder="note">
      <button class="ghost-btn" data-ev-add>Add</button>
    </div>`;
  section.querySelector('[data-ev-add]').onclick = async () => {
    const event = section.querySelector('[data-ev-type]').value.trim();
    if (!event) { toast('Event type is required.', { error: true }); return; }
    try {
      await api.post(`/api/applications/${appId}/events`, {
        date: section.querySelector('[data-ev-date]').value || null,
        event,
        note: section.querySelector('[data-ev-note]').value.trim(),
      });
      await renderTimeline(section, appId);
    } catch (err) {
      if (err.status !== 409) toast('Could not add event. ' + err.message, { error: true });
    }
  };
  section.querySelectorAll('[data-ev-del]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api.del(`/api/events/${btn.dataset.evDel}`);
        await renderTimeline(section, appId);
      } catch (err) {
        if (err.status !== 409) toast('Could not delete event. ' + err.message, { error: true });
      }
    };
  });
}

export function openDetail(id) {
  const app = getApp(id);
  if (!app) return;
  state.selectedId = id;
  const rule = employerRuleFor(app.company);
  root.innerHTML = `
    <div class="drawer-veil"></div>
    <div class="drawer" role="dialog" aria-modal="true" aria-label="Application detail">
      <div class="drawer-head">
        <div class="drawer-title">${esc(app.company)}</div>
        ${headBadges(app)}
        ${app.url ? `<a class="ghost-btn" href="${esc(app.url)}" target="_blank" rel="noopener">Posting ↗</a>` : ''}
        <button class="close-x" data-close aria-label="Close">✕</button>
      </div>
      <div class="drawer-body">
        ${rule ? `<div class="employer-banner" title="Employer rule">
            <strong>${esc(rule.employer)}</strong> — ${esc(rule.rule)}${rule.status ? ` · ${esc(rule.status)}` : ''}
          </div>` : ''}
        ${renderForm(app)}
        <hr class="sep">
        <div class="timeline-section"></div>
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

  renderTimeline(root.querySelector('.timeline-section'), id);

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
