// Interview Prep: question → answer bank grouped by category.

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
              <span class="prep-tools">
                <button data-edit="${item.id}" title="Edit">edit</button>
                <button data-del="${item.id}" title="Delete">del</button>
              </span>
            </summary>
            <div class="prep-body">
              <div class="prep-answer">${esc(item.answer) || '<span class="faint">No answer yet.</span>'}</div>
            </div>
          </details>`).join('')}
      </div>`).join('') || `<div class="empty" style="padding:60px 0">
        No prep questions yet. Add your first one.</div>`}`;

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
            <div class="field"><label>Category *</label><input name="category" value="${val('category')}" placeholder="Behavioral, Technical, Motivation…"></div>
            <div class="field full"><label>Question *</label><input name="question" value="${val('question')}"></div>
            <div class="field full"><label>Answer</label><textarea name="answer" rows="7" placeholder="Your answer — bullet points or a short story.">${val('answer')}</textarea></div>
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
    const payload = { category: read('category'), question: read('question'), answer: read('answer') };
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
