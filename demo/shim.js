// Static-demo API shim: intercepts /api/* fetches and serves them from
// bundled sample data, entirely in memory. Loaded (as a classic script)
// before the app's module scripts so the override is in place first.
(function () {
  // Showcase defaults, enforced on every visit: dark theme, music on,
  // land on the space globe. In-session toggles still work; stale
  // preferences from earlier visits must not dull the first impression.
  window.APPTRACKER_DEFAULTS = { music: true };
  localStorage.setItem('apptracker-theme', 'dark');
  localStorage.setItem('apptracker-music', '1');
  document.documentElement.dataset.theme = 'dark';
  if (!location.hash) location.hash = '#/map';
  const realFetch = window.fetch.bind(window);
  let db = null;
  let nextId = 1;
  const undoStack = [];
  const cities = {};

  const ready = realFetch('sample-data.json')
    .then((r) => r.json())
    .then((data) => {
      db = data;
      db.history = [];
      db.transitions = [];
      nextId = Math.max(0, ...db.applications.map((a) => a.id)) + 1;
      for (const a of db.applications) {
        if (a.location && a.latitude !== '' && a.latitude != null) {
          cities[a.location.toLowerCase()] = { lat: a.latitude, lng: a.longitude };
        }
      }
    });

  const json = (data, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

  const record = (action, entity, id, before, after, label) => {
    const entry = { ts: new Date().toISOString().slice(0, 19), action, entity, id, before, after, label };
    db.history.push(entry);
    undoStack.push(entry);
    if (action === 'update' && entity === 'application' && before?.status !== after?.status) {
      db.transitions.push({ ts: entry.ts, id, from: before.status, to: after.status });
    }
  };

  const CANNED_PREFILL = {
    fields: {
      company: 'Northwind Analytics', title: 'Senior Data Analyst',
      location: 'Amsterdam, Netherlands', work_type: 'Hybrid',
      source: 'Company site', sponsorship: 'Mentioned',
      date_applied: new Date().toISOString().slice(0, 10),
    },
    provenance: {
      company: 'Demo', title: 'Demo', location: 'Demo', work_type: 'Demo', sponsorship: 'Demo',
    },
    method: 'Demo mode',
    warnings: ['Static demo: these are canned values. Run the app locally for real posting parsing.'],
    evidence: { sponsorship_snippet: '…we are a recognised sponsor and offer visa sponsorship…' },
  };

  window.fetch = async (url, opts = {}) => {
    const path = String(url);
    if (!path.startsWith('/api/')) return realFetch(url, opts);
    await ready;
    const method = (opts.method || 'GET').toUpperCase();
    const body = opts.body ? JSON.parse(opts.body) : {};

    if (path === '/api/health') return json({ ok: true, demo: true, app_count: db.applications.length });
    if (path === '/api/settings' && method === 'GET') return json(db.settings);
    if (path === '/api/settings') { Object.assign(db.settings, body); return json(db.settings); }
    if (path === '/api/applications' && method === 'GET') return json({ applications: db.applications });
    if (path === '/api/prep' && method === 'GET') return json({ prep: db.prep });
    if (path.startsWith('/api/history')) return json({ history: [...db.history].reverse(), transitions: db.transitions });

    if (path === '/api/applications' && method === 'POST') {
      const rec = { latitude: '', longitude: '', geo_status: '', notes: '', ...body, id: nextId++ };
      const geo = cities[(rec.location || '').toLowerCase()];
      if (geo) { rec.latitude = geo.lat; rec.longitude = geo.lng; rec.geo_status = 'ok'; }
      else if (/remote/i.test(rec.location || '')) rec.geo_status = 'remote';
      else if (rec.location) rec.geo_status = 'pending';
      rec.last_updated = new Date().toISOString().slice(0, 19);
      db.applications.push(rec);
      record('create', 'application', rec.id, null, rec, `Added ${rec.company} — ${rec.title}`);
      return json(rec, 201);
    }

    const appMatch = path.match(/^\/api\/applications\/(\d+)$/);
    if (appMatch) {
      const id = Number(appMatch[1]);
      const idx = db.applications.findIndex((a) => a.id === id);
      if (idx < 0) return json({ error: 'not found' }, 404);
      if (method === 'PATCH') {
        const before = { ...db.applications[idx] };
        Object.assign(db.applications[idx], body, { last_updated: new Date().toISOString().slice(0, 19) });
        record('update', 'application', id, before, { ...db.applications[idx] },
          before.status !== db.applications[idx].status
            ? `${before.company}: ${before.status} → ${db.applications[idx].status}` : `Updated ${before.company}`);
        return json(db.applications[idx]);
      }
      if (method === 'DELETE') {
        const [removed] = db.applications.splice(idx, 1);
        record('delete', 'application', id, removed, null, `Deleted ${removed.company} — ${removed.title}`);
        return json({ deleted: id });
      }
    }

    if (path === '/api/prep' && method === 'POST') {
      const rec = { ...body, id: nextId++ };
      db.prep.push(rec);
      record('create', 'prep', rec.id, null, rec, `Added prep: ${rec.question.slice(0, 60)}`);
      return json(rec, 201);
    }
    const prepMatch = path.match(/^\/api\/prep\/(\d+)$/);
    if (prepMatch) {
      const id = Number(prepMatch[1]);
      const idx = db.prep.findIndex((p) => p.id === id);
      if (idx < 0) return json({ error: 'not found' }, 404);
      if (method === 'PATCH') {
        const before = { ...db.prep[idx] };
        Object.assign(db.prep[idx], body);
        record('update', 'prep', id, before, { ...db.prep[idx] }, 'Updated prep');
        return json(db.prep[idx]);
      }
      if (method === 'DELETE') {
        const [removed] = db.prep.splice(idx, 1);
        record('delete', 'prep', id, removed, null, 'Deleted prep');
        return json({ deleted: id });
      }
    }

    if (path === '/api/undo') {
      const entry = undoStack.pop();
      if (!entry) return json({ error: 'nothing to undo' }, 404);
      const list = entry.entity === 'application' ? db.applications : db.prep;
      if (entry.action === 'create') {
        const i = list.findIndex((r) => r.id === entry.id);
        if (i >= 0) list.splice(i, 1);
      } else if (entry.action === 'delete') {
        list.push(entry.before);
      } else {
        const i = list.findIndex((r) => r.id === entry.id);
        if (i >= 0) list[i] = entry.before;
      }
      return json({ undone: entry.label, entity: entry.entity, id: entry.id });
    }

    if (path === '/api/prefill' || path === '/api/prefill/text') {
      await new Promise((r) => setTimeout(r, 600));
      return json({ ...CANNED_PREFILL, fields: { ...CANNED_PREFILL.fields, url: body.url || '' } });
    }

    if (path === '/api/geocode' && method === 'POST') {
      const hit = cities[(body.query || '').toLowerCase()];
      return hit ? json({ ...hit, display_name: body.query, cached: true })
                 : json({ error: 'demo geocoder only knows the sample cities' }, 404);
    }
    if (path.startsWith('/api/geocode/backfill')) {
      return json({ running: false, done: 0, total: 0, ok: 0, failed: [] });
    }

    return json({ error: 'not available in the static demo' }, 404);
  };

  document.addEventListener('DOMContentLoaded', () => {
    const chip = document.createElement('span');
    chip.textContent = 'Static demo · sample data · run locally for URL prefill';
    chip.style.cssText = 'position:fixed;left:14px;bottom:14px;z-index:200;font:11px "JetBrains Mono",monospace;' +
      'color:#4dd6ff;background:rgba(13,20,37,.92);border:1px solid #1b2640;border-radius:8px;padding:6px 10px;';
    document.body.appendChild(chip);
  });
})();
