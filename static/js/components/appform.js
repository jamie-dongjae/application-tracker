// Shared application form: used by the add-flow review step and the detail drawer.

import { STATUSES, WORK_TYPES, TRACKS, STAGES, CURRENT_STATES, OUTCOMES, CLOSED_BY,
  GATES, STAGE_LABELS, STATE_LABELS, OUTCOME_LABELS, TRACK_LABELS, splitGates, esc } from '../state.js';

const FIELDS = [
  { key: 'company', label: 'Company', required: true },
  { key: 'title', label: 'Job Title', required: true },
  { key: 'status', label: 'Status', type: 'select', options: STATUSES },
  { key: 'date_applied', label: 'Date Applied', type: 'date' },
  { key: 'location', label: 'Location', placeholder: 'City, Country' },
  { key: 'work_type', label: 'Work Type', type: 'select', options: WORK_TYPES },
  { key: 'source', label: 'Source', placeholder: 'LinkedIn, Company site…', datalist: ['LinkedIn', 'Company site', 'Job board', 'Referral', 'Recruiter', 'Other'] },
  { key: 'sponsorship', label: 'Sponsorship', placeholder: 'Mentioned / Not offered' },
  { key: 'referral', label: 'Referral' },
  { key: 'track', label: 'Track', type: 'select', options: ['', ...TRACKS], labels: TRACK_LABELS },
  { key: 'stage_reached', label: 'Stage Reached', type: 'select', options: ['', ...STAGES], labels: STAGE_LABELS },
  { key: 'current_state', label: 'Current State', type: 'select', options: ['', ...CURRENT_STATES], labels: STATE_LABELS },
  { key: 'outcome', label: 'Outcome (when closed)', type: 'select', options: ['', ...OUTCOMES], labels: OUTCOME_LABELS },
  { key: 'closed_by', label: 'Closed By', type: 'select', options: ['', ...CLOSED_BY] },
  { key: 'gates', label: 'Gates', type: 'multi', options: GATES, full: true },
  { key: 'next_action', label: 'Next Action', full: true, placeholder: 'Nudge, prep, follow-up…' },
  { key: 'due', label: 'Due', type: 'date' },
  { key: 'contacts', label: 'Contacts', type: 'textarea', full: true, rows: 2 },
  { key: 'url', label: 'Job URL', full: true },
  { key: 'portal_url', label: 'Applicant Portal URL', full: true },
  { key: 'notes', label: 'Notes', type: 'textarea', full: true },
];

export function renderForm(values = {}, provenance = {}) {
  const rows = FIELDS.map((f) => {
    const value = values[f.key] ?? '';
    const prov = provenance[f.key]
      ? `<span class="prov" title="Prefilled from ${esc(provenance[f.key])}">${esc(provenance[f.key])}</span>` : '';
    let control;
    if (f.type === 'select') {
      const opts = f.options.map((o) =>
        `<option value="${esc(o)}" ${o === value ? 'selected' : ''}>${esc((f.labels && f.labels[o]) || o) || '—'}</option>`).join('');
      control = `<select name="${f.key}">${opts}</select>`;
    } else if (f.type === 'multi') {
      const selected = splitGates(value);
      const known = f.options.map((o) => `
        <label class="chip-check ${selected.includes(o) ? 'on' : ''}">
          <input type="checkbox" data-multi="${f.key}" value="${esc(o)}" ${selected.includes(o) ? 'checked' : ''}>
          ${esc(o)}
        </label>`).join('');
      // Ad-hoc gates not in the enum survive round-trips via a hidden input.
      const extra = selected.filter((g) => !f.options.includes(g));
      control = `<div class="chip-group" data-multi-group="${f.key}">${known}
        ${extra.map((g) => `
          <label class="chip-check on">
            <input type="checkbox" data-multi="${f.key}" value="${esc(g)}" checked>
            ${esc(g)}
          </label>`).join('')}
      </div>`;
    } else if (f.type === 'textarea') {
      control = `<textarea name="${f.key}" rows="${f.rows || 3}">${esc(value)}</textarea>`;
    } else {
      const type = f.type || 'text';
      const listAttr = f.datalist ? `list="dl-${f.key}"` : '';
      const datalist = f.datalist
        ? `<datalist id="dl-${f.key}">${f.datalist.map((o) => `<option value="${esc(o)}">`).join('')}</datalist>` : '';
      control = `<input name="${f.key}" type="${type}" value="${esc(value)}" ${listAttr}
        placeholder="${esc(f.placeholder || '')}" ${f.required ? 'required' : ''}
        ${type === 'number' ? 'min="0" step="1000"' : ''}>${datalist}`;
    }
    return `<div class="field ${f.full ? 'full' : ''}">
      <label>${f.label}${f.required ? ' *' : ''}</label>${prov}${control}
    </div>`;
  }).join('');
  return `<div class="form-grid">${rows}</div>`;
}

export function readForm(container) {
  const out = {};
  for (const f of FIELDS) {
    if (f.type === 'multi') {
      const boxes = container.querySelectorAll(`input[data-multi="${f.key}"]:checked`);
      out[f.key] = Array.from(boxes).map((b) => b.value).join(', ');
      continue;
    }
    const el = container.querySelector(`[name="${f.key}"]`);
    if (!el) continue;
    let value = el.value.trim();
    if (f.type === 'number') {
      out[f.key] = value === '' ? null : Number(value);
    } else {
      out[f.key] = value;
    }
  }
  return out;
}

export function validateForm(container) {
  const missing = [];
  for (const f of FIELDS.filter((x) => x.required)) {
    const el = container.querySelector(`[name="${f.key}"]`);
    if (el && !el.value.trim()) missing.push(f.label);
  }
  return missing;
}
