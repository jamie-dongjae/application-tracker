const root = document.getElementById('toast-root');

export function toast(message, { action, onAction, error = false, ttl = 4500 } = {}) {
  const el = document.createElement('div');
  el.className = 'toast' + (error ? ' err' : '');
  el.innerHTML = `<span></span>`;
  el.firstChild.textContent = message;
  if (action) {
    const btn = document.createElement('button');
    btn.textContent = action;
    btn.onclick = () => { el.remove(); onAction?.(); };
    el.appendChild(btn);
  }
  root.appendChild(el);
  setTimeout(() => el.remove(), ttl);
}
