// Shared application form: used by the add-flow review step and the detail drawer.

import { STATUSES, WORK_TYPES, esc } from '../state.js';

const FIELDS = [
  { key: 'company', label: 'Company', required: true },
  { key: 'title', label: 'Job Title', required: true },
  { key: 'status', label: 'Status', type: 'select', options: STATUSES },
  { key: 'date_applied', label: 'Date Applied', type: 'date' },
  { key: 'location', label: 'Location', placeholder: 'City, Country' },
  { key: 'work_type', label: 'Work Type', type: 'select', options: WORK_TYPES },
  { key: 'source', label: 'Source', placeholder: 'LinkedIn, Company site…' },
  { key: 'sponsorship', label: 'Sponsorship', placeholder: 'Mentioned / Not offered' },
  { key: 'referral', label: 'Referral' },
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
        `<option value="${esc(o)}" ${o === value ? 'selected' : ''}>${esc(o) || '—'}</option>`).join('');
      control = `<select name="${f.key}">${opts}</select>`;
    } else if (f.type === 'textarea') {
      control = `<textarea name="${f.key}" rows="3">${esc(value)}</textarea>`;
    } else {
      const type = f.type || 'text';
      control = `<input name="${f.key}" type="${type}" value="${esc(value)}"
        placeholder="${esc(f.placeholder || '')}" ${f.required ? 'required' : ''}
        ${type === 'number' ? 'min="0" step="1000"' : ''}>`;
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
