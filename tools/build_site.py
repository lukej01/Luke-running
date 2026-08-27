#!/usr/bin/env python3
"""Generate the static dashboard in site/ from the CSVs in data/.

Deliberately omits name, school, and medical history: the repo is public and
GitHub Pages is indexable. The site shows training numbers only. See
site/robots.txt and the noindex meta tag.

    python3 tools/build_site.py
"""

from __future__ import annotations

import datetime as dt
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coachkit as ck  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "site"

# Terms that must never reach the published page. A Pages site is public even
# when the repository is private, so this is the boundary that actually matters.
SENSITIVE = ("Denmark", "Alpharetta", "mono", "Luke", "ophomore", "GHSA",
             "adductor", "calf", "aqua")

SERIES = {  # dataviz categorical slots 1 and 2, validated light and dark
    "run": ("#2a78d6", "#3987e5"),
    "xt": ("#eb6834", "#d95926"),
}


def fitness():
    """Both fitness reads, mirroring coachkit predict."""
    races = ck.load_races()
    latest = races[-1]
    estimates = [("Course-adjusted", latest.time - latest.course_adj)]
    anchor = next((r for r in races
                   if r.course == latest.course and r.flat_ref and r is not latest), None)
    if anchor:
        estimates.append(("Same-course delta",
                          anchor.flat_ref - (anchor.time - latest.time)))
    low = min(v for _, v in estimates)
    high = max(v for _, v in estimates)
    return estimates, low, high, (low + high) / 2


def plan_rows(today: dt.date):
    monday = today - dt.timedelta(days=today.weekday()) + dt.timedelta(days=7)
    rows = []
    while monday <= ck.STATE_MEET:
        out = max(0, (ck.STATE_MEET - monday).days // 7)
        miles, xt, phase, workout = ck.phase_for(out)
        rows.append((monday, out, min(miles, ck.MILEAGE_CEILING), xt, phase, workout))
        monday += dt.timedelta(days=7)
    return rows


def load_chart(weeks, planned) -> str:
    """Stacked bars: running miles + cross-training credit = total aerobic load.

    One measure, one axis. The divider marks today; planned weeks are hatched.
    """
    bars = []
    for w in weeks:
        bars.append((w.start, w.run_miles, w.xt_credit, False))
    for start, _out, miles, xt, _p, _w in planned:
        bars.append((start, miles, xt / ck.XT_MINUTES_PER_MILE, True))

    pad_l, pad_r, pad_t, pad_b = 44, 12, 16, 54
    bar_w, gap = 26, 8
    plot_h = 260
    width = pad_l + len(bars) * (bar_w + gap) + pad_r
    height = pad_t + plot_h + pad_b
    top = max(b[1] + b[2] for b in bars)
    scale = plot_h / (top * 1.12)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="Weekly aerobic load, running miles plus '
        f'cross-training credit">',
        '<defs><pattern id="future" width="7" height="7" '
        'patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="var(--surface-1)" '
        'stroke-width="3.5"/></pattern></defs>',
    ]

    for tick in range(0, int(top * 1.12) + 1, 20):
        y = pad_t + plot_h - tick * scale
        parts.append(f'<line class="grid" x1="{pad_l}" y1="{y:.1f}" '
                     f'x2="{width - pad_r}" y2="{y:.1f}"/>')
        parts.append(f'<text class="axis" x="{pad_l - 8}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{tick}</text>')

    for i, (start, run, xt, future) in enumerate(bars):
        x = pad_l + i * (bar_w + gap)
        base = pad_t + plot_h
        run_h = run * scale
        xt_h = xt * scale
        total = run + xt
        label = start.strftime("%b %-d")
        tip = (f"{label} &middot; {total:.0f} equiv &middot; "
               f"{run:.0f} run + {xt * 10:.0f} min XT"
               + (" (planned)" if future else ""))
        parts.append(f'<g class="bar" tabindex="0" data-tip="{tip}">')
        # invisible hit target, larger than the mark
        parts.append(f'<rect x="{x - 4}" y="{pad_t}" width="{bar_w + 8}" '
                     f'height="{plot_h}" fill="transparent"/>')
        if run_h > 0:
            parts.append(
                f'<rect class="s-run" x="{x}" y="{base - run_h:.1f}" width="{bar_w}" '
                f'height="{run_h:.1f}" rx="3"/>')
            if future:
                parts.append(
                    f'<rect class="hatch" x="{x}" y="{base - run_h:.1f}" '
                    f'width="{bar_w}" height="{run_h:.1f}" rx="3" fill="url(#future)"/>')
        # 2px surface gap between stacked segments
        y_xt = base - run_h - xt_h - 2
        if xt_h > 0:
            parts.append(
                f'<rect class="s-xt" x="{x}" y="{y_xt:.1f}" width="{bar_w}" '
                f'height="{xt_h:.1f}" rx="3"/>')
            if future:
                parts.append(
                    f'<rect class="hatch" x="{x}" y="{y_xt:.1f}" '
                    f'width="{bar_w}" height="{xt_h:.1f}" rx="3" fill="url(#future)"/>')
        parts.append('</g>')
        if i % 2 == 0:
            parts.append(f'<text class="axis" x="{x + bar_w / 2:.1f}" '
                         f'y="{base + 18}" text-anchor="middle">{label}</text>')

    divider = pad_l + len(weeks) * (bar_w + gap) - gap / 2
    parts.append(f'<line class="divider" x1="{divider:.1f}" y1="{pad_t - 6}" '
                 f'x2="{divider:.1f}" y2="{pad_t + plot_h + 6}"/>')
    parts.append(f'<text class="axis strong" x="{divider + 6:.1f}" '
                 f'y="{pad_t + 4}">planned &rarr;</text>')
    parts.append('</svg>')
    return "".join(parts)


def build() -> Path:
    today = dt.date.today()
    weeks = ck.load_weeks()
    planned = plan_rows(today)
    estimates, low, high, mid = fitness()
    prs = ck.load_prs()
    flags = ck.evaluate(weeks)
    days = (ck.STATE_MEET - today).days

    recent = weeks[-1]
    peak = max(weeks, key=lambda w: w.load)
    target = planned[0]
    target_load = target[2] + target[3] / ck.XT_MINUTES_PER_MILE

    def tile(value, label, note=""):
        return (f'<div class="tile"><div class="v">{value}</div>'
                f'<div class="l">{label}</div>'
                + (f'<div class="n">{note}</div>' if note else "") + '</div>')

    tiles = "".join([
        tile(f"{ck.format_time(low)}&ndash;{ck.format_time(high)}", "Current 5K",
             "flat-course equivalent"),
        tile(ck.format_time(mid - 13), "State projection",
             f"range {ck.format_time(mid - 20)}&ndash;{ck.format_time(high - 10)}"),
        tile(f"{days / 7:.1f}", "Weeks to state", ck.STATE_MEET.strftime("%a %d %b %Y")),
        tile(f"{recent.load:.0f} &rarr; {target_load:.0f}", "Aerobic load",
             f"summer peak {peak.load:.0f} equiv"),
    ])

    # Free-text notes stay off the published page: they carry medical and
    # identifying detail, and a Pages site is public even from a private repo.
    pr_rows = "".join(
        f"<tr><td>{p.label}</td><td class='num'>{ck.format_time(p.time)}</td>"
        f"<td class='num'>{ck.format_time(ck.riegel(p.time, p.distance, 5000))}</td></tr>"
        for p in prs)

    fitness_rows = "".join(
        f"<tr><td>{html.escape(name)}</td>"
        f"<td class='num'>{ck.format_time(value)}</td></tr>"
        for name, value in estimates)

    plan_body = "".join(
        f"<tr{' class=state' if out == 0 else ''}>"
        f"<td>{start.strftime('%b %-d')}</td><td class='num'>{out}</td>"
        f"<td class='num'>{miles:.0f}</td><td class='num'>{xt:.0f}</td>"
        f"<td class='num strong'>{miles + xt / ck.XT_MINUTES_PER_MILE:.0f}</td>"
        f"<td>{html.escape(phase)}</td><td class='muted'>{html.escape(workout)}</td></tr>"
        for start, out, miles, xt, phase, workout in planned)

    week_body = "".join(
        f"<tr><td>{w.start.strftime('%b %-d')}</td>"
        f"<td class='num'>{w.run_miles:.0f}</td>"
        f"<td class='num'>{w.xt_minutes:.0f}</td>"
        f"<td class='num strong'>{w.load:.0f}</td>"
        f"<td class='num'>{w.hard_days}</td>"
        f"<td>{w.symptoms or '&mdash;'}</td></tr>"
        for w in weeks)

    status = ("<p class='ok'>No rule violations.</p>" if not flags else
              "<ul class='flags'>" + "".join(
                  f"<li>{html.escape(f)}</li>" for f in flags) + "</ul>")

    chart = load_chart(weeks, planned)

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>XC Season Dashboard &mdash; Fall 2026</title>
<style>
:root {{
  color-scheme: light;
  --surface-0: #f4f4f2; --surface-1: #fcfcfb; --border: #dedcd5;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7a786f;
  --series-run: {SERIES['run'][0]}; --series-xt: {SERIES['xt'][0]};
  --grid: #e7e5df; --accent: #2a78d6;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #35342f;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8d83;
    --series-run: {SERIES['run'][1]}; --series-xt: {SERIES['xt'][1]};
    --grid: #2a2a26; --accent: #3987e5;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #35342f;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8f8d83;
  --series-run: {SERIES['run'][1]}; --series-xt: {SERIES['xt'][1]};
  --grid: #2a2a26; --accent: #3987e5;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 72px; }}
header h1 {{ font-size: 1.6rem; margin: 0 0 4px; letter-spacing: -0.02em; }}
header p {{ margin: 0 0 28px; color: var(--text-secondary); }}
h2 {{ font-size: 1.05rem; margin: 40px 0 6px; letter-spacing: -0.01em; }}
h2 + p.sub {{ margin: 0 0 14px; color: var(--text-secondary); font-size: 0.9rem; }}
.tiles {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
.tile {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }}
.tile .v {{ font-size: 1.7rem; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
.tile .l {{ color: var(--text-secondary); font-size: 0.86rem; margin-top: 2px; }}
.tile .n {{ color: var(--text-muted); font-size: 0.78rem; margin-top: 6px; }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
.scroll {{ overflow-x: auto; }}
svg {{ display: block; color: var(--surface-1); }}
.grid {{ stroke: var(--grid); stroke-width: 1; }}
.axis {{ fill: var(--text-muted); font-size: 10px; }}
.axis.strong {{ fill: var(--text-secondary); }}
.divider {{ stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; }}
.s-run {{ fill: var(--series-run); }}
.s-xt {{ fill: var(--series-xt); }}
.hatch {{ opacity: 0.62; }}
.bar {{ cursor: default; outline: none; }}
.bar:hover rect:not([fill="transparent"]), .bar:focus-visible rect:not([fill="transparent"]) {{ opacity: 0.78; }}
.legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin: 0 0 12px; font-size: 0.85rem; color: var(--text-secondary); }}
.legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
.swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.87rem; }}
th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
th {{ color: var(--text-secondary); font-weight: 500; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }}
th.num {{ text-align: right; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.muted {{ color: var(--text-muted); }}
td.strong {{ font-weight: 600; }}
tr.state td {{ background: color-mix(in srgb, var(--accent) 12%, transparent); font-weight: 600; }}
.ok {{ color: var(--text-secondary); }}
.flags {{ margin: 0; padding-left: 18px; }}
.note {{ color: var(--text-muted); font-size: 0.82rem; border-top: 1px solid var(--border); margin-top: 44px; padding-top: 16px; }}
#tip {{
  position: fixed; pointer-events: none; opacity: 0; transition: opacity .12s;
  background: var(--text-primary); color: var(--surface-1); font-size: 0.78rem;
  padding: 6px 9px; border-radius: 6px; white-space: nowrap; z-index: 10;
}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>XC Season Dashboard</h1>
  <p>{days} days to the state meet &middot; {ck.STATE_MEET.strftime('%A %d %B %Y')}</p>
</header>

<div class="tiles">{tiles}</div>

<h2>Weekly aerobic load</h2>
<p class="sub">Running miles plus cross-training credit at
{ck.XT_MINUTES_PER_MILE:.0f}&nbsp;min/mile. Hatched bars are planned.
Running miles are capped at {ck.MILEAGE_CEILING:.0f}; aerobic load is not.</p>
<div class="card">
  <div class="legend">
    <span><i class="swatch" style="background:var(--series-run)"></i>Running miles</span>
    <span><i class="swatch" style="background:var(--series-xt)"></i>Cross-training credit</span>
  </div>
  <div class="scroll">{chart}</div>
</div>

<h2>Plan to state</h2>
<p class="sub">Racing every Saturday uses one of two permitted hard days, so one
workout midweek &mdash; Tuesday, clear of the 48-hour rule both ways.</p>
<div class="card scroll">
<table>
<thead><tr><th>Week of</th><th class="num">Out</th><th class="num">Miles</th>
<th class="num">XT min</th><th class="num">Load</th><th>Phase</th><th>Tuesday workout</th></tr></thead>
<tbody>{plan_body}</tbody>
</table>
</div>

<h2>Race-time equivalents</h2>
<p class="sub">The spread slopes one way: the shorter the race, the better he
looks. The 3200 is the honest anchor &mdash; it agrees with the actual 5K.</p>
<div class="card scroll">
<table>
<thead><tr><th>PR</th><th class="num">Time</th><th class="num">5K equivalent</th></tr></thead>
<tbody>{pr_rows}</tbody>
</table>
</div>

<h2>Current fitness</h2>
<div class="card scroll">
<table>
<thead><tr><th>Method</th><th class="num">Flat 5K</th></tr></thead>
<tbody>{fitness_rows}</tbody>
</table>
</div>

<h2>Training weeks</h2>
<div class="card scroll">
<table>
<thead><tr><th>Week of</th><th class="num">Run mi</th><th class="num">XT min</th>
<th class="num">Load</th><th class="num">Hard</th><th>Felt</th></tr></thead>
<tbody>{week_body}</tbody>
</table>
</div>

<h2>Rule check</h2>
<div class="card">{status}</div>

<p class="note">
Generated from the CSVs in <code>data/</code> by <code>tools/build_site.py</code>
on {today.isoformat()}. Estimates are equivalents, not promises.
This page is marked <code>noindex</code> and carries no identifying details.
</p>
</div>
<div id="tip" role="status"></div>
<script>
const tip = document.getElementById('tip');
function show(e, el) {{
  tip.innerHTML = el.dataset.tip;
  tip.style.opacity = '1';
  const r = tip.getBoundingClientRect();
  const x = (e.clientX ?? el.getBoundingClientRect().left) + 12;
  tip.style.left = Math.min(x, window.innerWidth - r.width - 8) + 'px';
  tip.style.top = ((e.clientY ?? el.getBoundingClientRect().top) - r.height - 10) + 'px';
}}
for (const bar of document.querySelectorAll('.bar')) {{
  bar.addEventListener('mousemove', e => show(e, bar));
  bar.addEventListener('focus', e => show(e, bar));
  for (const ev of ['mouseleave', 'blur']) bar.addEventListener(ev, () => tip.style.opacity = '0');
}}
</script>
</body>
</html>
"""

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(doc, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    return OUT / "index.html"


def audit(text: str) -> list[str]:
    """Terms from SENSITIVE that leaked into the rendered page."""
    return [t for t in SENSITIVE if t.lower() in text.lower()]


if __name__ == "__main__":
    path = build()
    leaked = audit(path.read_text(encoding="utf-8"))
    if leaked:
        raise SystemExit("refusing to ship: sensitive terms in page: %s" % leaked)
    print("wrote %s (%.1f KB)" % (path, path.stat().st_size / 1024))
