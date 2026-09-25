"""Render the "FY26 Pipeline State" markdown snapshot.

Pure function over store data — no I/O. The snapshot is pushed into a Claude
Doc after every sync so external Claude conversations can reference current
pipeline state.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ..excel import schema

# Live states in report order (closed/stale get their own sections).
_LIVE_ORDER = ["awaiting_decision", "scheduling", "action_required",
               "on_hold_employer", "awaiting_response"]

_STATE_TITLES = {
    "awaiting_decision": "Awaiting decision",
    "scheduling": "Scheduling",
    "action_required": "Action required",
    "on_hold_employer": "On hold (employer)",
    "awaiting_response": "Awaiting response",
}


def _d(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _line(app: dict, *, with_next: bool = True) -> str:
    bits = [f"- **{app.get('company')} — {app.get('title')}**"]
    meta = [m for m in (app.get("track"), app.get("stage_reached")) if m]
    if meta:
        bits.append(f"[{' / '.join(meta)}]")
    if app.get("gates"):
        bits.append(f"gates: {app['gates']}")
    if with_next and app.get("next_action"):
        due = f" (due {str(app['due'])[:10]})" if app.get("due") else ""
        bits.append(f"— next: {app['next_action']}{due}")
    return " ".join(bits)


def render_pipeline_state(apps: list[dict], employers: list[dict],
                          settings: dict, today: date | None = None) -> str:
    today = today or date.today()
    live = [a for a in apps if a.get("current_state") not in ("closed", "stale", "")]
    closed = [a for a in apps if a.get("current_state") == "closed"]
    stale = [a for a in apps if a.get("current_state") == "stale"]

    out = [f"# FY26 Pipeline State",
           f"_Generated {today.isoformat()} · {len(apps)} applications · "
           f"{len(live)} live · {len(closed)} closed · {len(stale)} stale_", ""]

    # Due / action required (next 7 days or state says so)
    horizon = today + timedelta(days=7)
    due_rows = []
    for a in apps:
        if a.get("current_state") in ("closed", ""):
            continue
        d = _d(a.get("due"))
        if a.get("current_state") in ("action_required", "scheduling") or (d and d <= horizon):
            due_rows.append((d or date.max, a))
    out.append("## Due / action required")
    if due_rows:
        for d, a in sorted(due_rows, key=lambda x: x[0]):
            flag = " ⚠ OVERDUE" if d != date.max and d < today else ""
            out.append(_line(a) + flag)
    else:
        out.append("- nothing due")
    out.append("")

    out.append("## Live pipeline")
    for state in _LIVE_ORDER:
        rows = [a for a in live if a.get("current_state") == state]
        if not rows:
            continue
        out.append(f"### {_STATE_TITLES[state]} ({len(rows)})")
        out.extend(_line(a) for a in rows)
        out.append("")
    if not live:
        out.append("- pipeline is empty")
        out.append("")

    out.append("## Recent outcomes (14 days)")
    window = today - timedelta(days=14)
    recent = []
    for a in closed:
        lu = _d(str(a.get("last_updated") or "")[:10])
        if lu and lu >= window:
            recent.append((lu, a))
    if recent:
        for lu, a in sorted(recent, key=lambda x: x[0], reverse=True):
            out.append(f"- {lu.isoformat()} · **{a.get('company')} — {a.get('title')}**: "
                       f"{a.get('outcome') or 'closed'} (by {a.get('closed_by') or '?'})")
    else:
        out.append("- none")
    out.append("")

    out.append(f"## Stale ({len(stale)})")
    if stale:
        out.extend(f"- {a.get('company')} — {a.get('title')}" for a in stale)
    else:
        out.append("- none")
    out.append("")

    out.append("## Employer rules")
    if employers:
        out.append("| employer | rule | status |")
        out.append("|---|---|---|")
        for e in employers:
            out.append(f"| {e.get('employer')} | {e.get('rule') or ''} | {e.get('status') or ''} |")
    else:
        out.append("- none recorded")
    out.append("")

    # KPIs
    monday = today - timedelta(days=(today.weekday()))
    this_week = sum(1 for a in apps if (_d(a.get("date_applied")) or date.min) >= monday)
    goal = settings.get("weekly_goal") or 5
    tracks: dict = {}
    stages: dict = {}
    gates: dict = {}
    for a in apps:
        tracks[a.get("track") or "?"] = tracks.get(a.get("track") or "?", 0) + 1
        if a.get("stage_reached"):
            stages[a["stage_reached"]] = stages.get(a["stage_reached"], 0) + 1
        for g in str(a.get("gates") or "").split(","):
            g = g.strip()
            if g:
                gates[g] = gates.get(g, 0) + 1
    stage_order = {s: i for i, s in enumerate(schema.STAGES)}
    out.append("## KPIs")
    out.append(f"- this week: {this_week}/{goal} applications")
    out.append("- by track: " + ", ".join(f"{k} {v}" for k, v in
                                          sorted(tracks.items(), key=lambda x: -x[1])))
    if stages:
        out.append("- furthest stage: " + ", ".join(
            f"{k} {v}" for k, v in sorted(stages.items(), key=lambda x: stage_order.get(x[0], 99))))
    if gates:
        top = sorted(gates.items(), key=lambda x: -x[1])[:6]
        out.append("- top gates: " + ", ".join(f"{k} {v}" for k, v in top))
    return "\n".join(out).rstrip() + "\n"
