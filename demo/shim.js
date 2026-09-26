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
  let nextEventId = 1;
  let demoMailUsed = false;
  const undoStack = [];
  const cities = {};

  const ready = realFetch('sample-data.json')
    .then((r) => r.json())
    .then((data) => {
      db = data;
      db.history = [];
      // Seeded stage history (if bundled) feeds the history-aware KPIs;
      // in-session status changes keep appending to it.
      db.transitions = data.transitions || [];
      db.employers = data.employers || [];
      db.events = data.events || [];
      db.review_queue = data.review_queue || [];
      nextId = Math.max(0, ...db.applications.map((a) => a.id)) + 1;
      nextEventId = Math.max(0, ...db.events.map((e) => e.id || 0)) + 1;
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

    // ---- v4: employers, event timelines, mail sync + review queue ----

    if (path === '/api/employers' && method === 'GET') return json({ employers: db.employers });

    const eventsMatch = path.match(/^\/api\/applications\/(\d+)\/events$/);
    if (eventsMatch) {
      const appId = Number(eventsMatch[1]);
      if (method === 'GET') {
        const rows = db.events.filter((e) => e.app_id === appId)
          .sort((a, b) => String(a.date || '9999').localeCompare(String(b.date || '9999')));
        return json({ events: rows });
      }
      if (method === 'POST') {
        const rec = { id: nextEventId++, app_id: appId, date: body.date || '', event: body.event, note: body.note || '' };
        db.events.push(rec);
        return json(rec, 201);
      }
    }
    const eventDelMatch = path.match(/^\/api\/events\/(\d+)$/);
    if (eventDelMatch && method === 'DELETE') {
      const id = Number(eventDelMatch[1]);
      const i = db.events.findIndex((e) => e.id === id);
      if (i < 0) return json({ error: 'not found' }, 404);
      db.events.splice(i, 1);
      return json({ deleted: id });
    }

    if (path === '/api/sync/review' && method === 'GET') {
      return json({ items: db.review_queue.filter((i) => i.status === 'pending') });
    }
    const reviewMatch = path.match(/^\/api\/sync\/review\/([^/]+)\/(apply|dismiss)$/);
    if (reviewMatch && method === 'POST') {
      const item = db.review_queue.find((i) => i.id === reviewMatch[1]);
      if (!item) return json({ error: 'not found' }, 404);
      if (item.status !== 'pending') return json({ error: 'already resolved' }, 409);
      item.status = reviewMatch[2] === 'apply' ? 'applied' : 'dismissed';
      if (reviewMatch[2] === 'apply' && item.proposed?.match?.id) {
        const idx = db.applications.findIndex((a) => a.id === item.proposed.match.id);
        if (idx >= 0) {
          const before = { ...db.applications[idx] };
          Object.assign(db.applications[idx], item.proposed.patch || {});
          // Toy status sync — the real rules live server-side in schema.py.
          const p = db.applications[idx];
          if (p.current_state === 'closed') p.status = p.outcome === 'withdrawn_by_me' ? 'Withdrawn' : 'Rejected';
          else if (['recruiter_screen', 'assessment', 'hiring_manager', 'final'].includes(p.stage_reached)) p.status = 'Interview';
          record('update', 'application', p.id, before, { ...p }, `Sync: ${p.company}`);
        }
      }
      return json({ ok: true });
    }

    if (path === '/api/sync/mail/credentials' && method === 'GET') {
      return json({ configured: true, email: 'd···@example.com' });
    }
    if (path === '/api/sync/mail' && method === 'POST') {
      // Scripted demo sweep: first click "finds" one confirmation (auto-applied)
      // and one interview invite (queued for review); later clicks find nothing.
      await new Promise((r) => setTimeout(r, 800));
      if (demoMailUsed) return json({ fetched: 2, already_known: 2, applied: { updated: 0, added: 0, skipped: 0, events_added: 0, events_deduped: 0 }, queued: 0, ignored: 0, warnings: [] });
      demoMailUsed = true;
      const target = db.applications.find((a) => a.status === 'Applied' && a.stage_reached === 'applied');
      let updated = 0;
      if (target) {
        const before = { ...target };
        target.stage_reached = 'confirmed';
        record('update', 'application', target.id, before, { ...target }, `Sync: ${target.company} — confirmed`);
        db.events.push({ id: nextEventId++, app_id: target.id, date: new Date().toISOString().slice(0, 10), event: 'confirmed', note: 'ATS confirmation (demo mailbox)' });
        updated = 1;
      }
      const invite = db.applications.find((a) => a.status === 'Applied' && a.id !== target?.id);
      if (invite) {
        db.review_queue.push({
          id: 'demo-invite-1',
          added_at: new Date().toISOString().slice(0, 19),
          email: { gmail_id: 'demo-invite-1', from: 'talent@' + invite.company.toLowerCase().replace(/[^a-z]/g, '') + '.example',
                   subject: 'Interview invitation — ' + invite.title, date: new Date().toISOString().slice(0, 10),
                   snippet: 'We would love to schedule a 30-minute call next week to discuss your application…' },
          proposed: { company: invite.company, title: invite.title, match: { id: invite.id }, confidence: 'review',
                      reason: 'interview invite needs a human eye', fields: {}, patch: { stage_reached: 'recruiter_screen', current_state: 'scheduling' },
                      note: '', events: [], provenance: [] },
          status: 'pending', resolved_at: null,
        });
      }
      return json({ fetched: 3, already_known: 1, applied: { updated, added: 0, skipped: 0, events_added: updated, events_deduped: 0 }, queued: invite ? 1 : 0, ignored: 1, warnings: [] });
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
