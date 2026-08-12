// Interview Prep: STAR question bank grouped by category, with add/edit.

import { api } from '../api.js';
import { state, refreshPrep, undo, esc } from '../state.js';
import { toast } from '../components/toast.js';

const modalRoot = document.getElementById('modal-root');

export function renderPrep(el) {
  const groups = new Map();
  for (const item of state.prep) {
    const cat = item.category || 'Uncategorized';
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(item);
  }

  el.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Interview Prep</h1>
      <button class="accent-btn" id="prep-add">+ Question</button>
    </div>
    ${[...groups.entries()].map(([cat, items]) => `
      <div class="prep-cat">
        <h2 class="prep-cat-title">${esc(cat)} <span class="faint num">${items.length}</span></h2>
        ${items.map((item) => `
          <details class="prep-item">
            <summary>
              <span style="flex:1">${esc(item.question)}</span>
              ${item.subcategory ? `<span class="status-chip">${esc(item.subcategory)}</span>` : ''}
              <span class="prep-tools">
                <button data-edit="${item.id}" title="Edit">edit</button>
                <button data-del="${item.id}" title="Delete">del</button>
              </span>
            </summary>
            <div class="prep-body">
              <div class="star-grid">
                ${starRow('S — Situation', item.situation)}
                ${starRow('T — Task', item.task)}
                ${starRow('A — Action', item.action)}
                ${starRow('R — Result', item.result)}
                ${item.tips ? starRow('Tips', item.tips) : ''}
              </div>
            </div>
          </details>`).join('')}
      </div>`).join('') || `<div class="empty" style="padding:60px 0">
        No prep questions yet. Add your first STAR story.</div>`}`;

  el.querySelector('#prep-add').onclick = () => openPrepModal();
  el.querySelectorAll('[data-edit]').forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault(); e.stopPropagation();
      openPrepModal(state.prep.find((p) => p.id === Number(btn.dataset.edit)));
    };
  });
  el.querySelectorAll('[data-del]').forEach((btn) => {
    btn.onclick = async (e) => {
      e.preventDefault(); e.stopPropagation();
      const id = Number(btn.dataset.del);
      try {
        await api.del(`/api/prep/${id}`);
        await refreshPrep();
        toast('Question deleted.', { action: 'Undo', onAction: async () => { await undo(); } });
      } catch (err) {
        if (err.status !== 409) toast('Delete failed. ' + err.message, { error: true });
      }
    };
  });
}

function starRow(key, value) {
  if (value == null) value = '';
  return `<div class="star-key">${esc(key)}</div><div class="star-val">${esc(value) || '<span class="faint">—</span>'}</div>`;
}

function openPrepModal(item) {
  const isEdit = !!item;
  const val = (k) => esc(item?.[k] ?? '');
  modalRoot.innerHTML = `
    <div class="modal-veil">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="modal-head">
          <h2 class="modal-title">${isEdit ? 'Edit question' : 'New prep question'}</h2>
          <button class="close-x" data-close>✕</button>
        </div>
        <div class="modal-body">
          <div class="form-grid">
            <div class="field"><label>Category *</label><input name="category" value="${val('category')}" placeholder="Behavioral"></div>
            <div class="field"><label>Sub-category</label><input name="subcategory" value="${val('subcategory')}"></div>
            <div class="field full"><label>Question *</label><input name="question" value="${val('question')}"></div>
            <div class="field full"><label>Situation</label><textarea name="situation" rows="2">${val('situation')}</textarea></div>
            <div class="field full"><label>Task</label><textarea name="task" rows="2">${val('task')}</textarea></div>
            <div class="field full"><label>Action</label><textarea name="action" rows="2">${val('action')}</textarea></div>
            <div class="field full"><label>Result</label><textarea name="result" rows="2">${val('result')}</textarea></div>
            <div class="field full"><label>Tips</label><textarea name="tips" rows="2">${val('tips')}</textarea></div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="ghost-btn" data-close-2>Cancel</button>
          <button class="accent-btn" data-save>${isEdit ? 'Save' : 'Add question'}</button>
        </div>
      </div>
    </div>`;
  const close = () => { modalRoot.innerHTML = ''; };
  modalRoot.querySelector('[data-close]').onclick = close;
  modalRoot.querySelector('[data-close-2]').onclick = close;
  modalRoot.querySelector('.modal-veil').addEventListener('mousedown', (e) => {
    if (e.target === e.currentTarget) close();
  });
  modalRoot.querySelector('[name="category"]').focus();
  modalRoot.querySelector('[data-save]').onclick = async () => {
    const read = (k) => modalRoot.querySelector(`[name="${k}"]`).value.trim();
    const payload = Object.fromEntries(
      ['category', 'subcategory', 'question', 'situation', 'task', 'action', 'result', 'tips']
        .map((k) => [k, read(k)]));
    if (!payload.category || !payload.question) {
      toast('Category and question are required.', { error: true });
      return;
    }
    try {
      if (isEdit) await api.patch(`/api/prep/${item.id}`, payload);
      else await api.post('/api/prep', payload);
      await refreshPrep();
      close();
      toast(isEdit ? 'Saved.' : 'Question added.');
    } catch (err) {
      if (err.status !== 409) toast('Save failed. ' + err.message, { error: true });
    }
  };
}
