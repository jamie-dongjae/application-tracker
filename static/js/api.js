// Thin fetch wrapper. 409 (workbook open in Excel) raises the lock banner;
// network failures raise the offline banner.

const banner = document.getElementById('banner');
let bannerRetry = null;

export function showBanner(message, retryLabel, onRetry) {
  banner.hidden = false;
  banner.textContent = message + ' ';
  if (retryLabel) {
    const btn = document.createElement('button');
    btn.textContent = retryLabel;
    btn.onclick = () => { hideBanner(); onRetry?.(); };
    banner.appendChild(btn);
  }
  bannerRetry = onRetry;
}

export function hideBanner() {
  banner.hidden = true;
  bannerRetry = null;
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || body?.error || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request(method, path, body) {
  let resp;
  try {
    resp = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    showBanner('Server unreachable — is Waypoint still running?', 'Retry', () => location.reload());
    throw err;
  }
  let data = null;
  try { data = await resp.json(); } catch { /* empty body */ }
  if (resp.status === 409 && data?.error === 'workbook_locked') {
    showBanner('The workbook is open in Excel — close it to save changes.', 'Dismiss');
    throw new ApiError(resp.status, data);
  }
  if (!resp.ok) throw new ApiError(resp.status, data);
  hideBanner();
  return data;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
};
