"""Self-contained HTML KPI dashboard (inline SVG, no external libraries)."""
import html
from .generate_sample import PROJECTS


def _bar_chart(items, label_key, value_key, unit="", width=520, target=None):
    if not items:
        return "<p class='muted'>No data.</p>"
    vmax = max(max(i[value_key] for i in items), target or 0) * 1.1 or 1
    row, h = 30, 30 * len(items) + 10
    s = [f"<svg viewBox='0 0 {width} {h}' width='100%' role='img'>"]
    for n, i in enumerate(items):
        y = n * row + 4
        w = (width - 190) * i[value_key] / vmax
        s.append(f"<text x='0' y='{y+16}' class='lbl'>{html.escape(str(i[label_key]))}</text>"
                 f"<rect x='140' y='{y}' width='{w:.1f}' height='20' rx='3' class='bar'/>"
                 f"<text x='{146+w:.1f}' y='{y+15}' class='val'>{i[value_key]}{unit}</text>")
    if target:
        x = 140 + (width - 190) * target / vmax
        s.append(f"<line x1='{x:.1f}' x2='{x:.1f}' y1='0' y2='{h}' class='target'/>")
    return "".join(s) + "</svg>"


def _line_chart(points, width=520, height=170):
    vals = [p["plan_attainment_pct"] for p in points]
    lo, hi = min(min(vals), 100) - 5, max(max(vals), 100) + 5
    X = lambda i: 30 + i * (width - 40) / max(1, len(vals) - 1)
    Y = lambda v: 10 + (height - 40) * (hi - v) / (hi - lo)
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    dots = "".join(f"<circle cx='{X(i):.1f}' cy='{Y(v):.1f}' r='3' class='dot'><title>{points[i]['week']}: {v}%</title></circle>"
                   for i, v in enumerate(vals))
    ticks = "".join(f"<text x='{X(i):.1f}' y='{height-8}' class='tick' text-anchor='middle'>W{i+1}</text>"
                    for i in range(len(vals)))
    return (f"<svg viewBox='0 0 {width} {height}' width='100%' role='img'>"
            f"<line x1='30' x2='{width-10}' y1='{Y(100):.1f}' y2='{Y(100):.1f}' class='target'/>"
            f"<text x='{width-10}' y='{Y(100)-4:.1f}' class='tick' text-anchor='end'>plan = 100%</text>"
            f"<path d='{path}' class='line'/>{dots}{ticks}</svg>")


def render(k, dq, role, perms, stats):
    pj = k["projects"]
    cards = "".join(f"""<div class='card'><div class='muted'>{pid} · {html.escape(PROJECTS[pid])}</div>
      <div class='big'>{v['plan_attainment_pct']}%</div><div class='muted'>plan attainment</div>
      <div class='kv'><span>Rework</span><b>{v['rework_rate_pct']}%</b></div>
      <div class='kv'><span>Labour hours</span><b>{v['labour_hours']:,}</b></div>
      <div class='kv'><span>Incidents / 10k hrs</span><b>{v['incidents_per_10k_hours']}</b></div></div>"""
                    for pid, v in pj.items())
    trade_rows = "".join(
        f"<tr><td>{t['project_id']}</td><td>{t['trade']}</td><td>{t['planned_per_hr']} {t['unit']}</td>"
        f"<td>{t['actual_per_hr']} {t['unit']}</td><td class='{'neg' if t['variance_pct'] < 0 else 'pos'}'>{t['variance_pct']:+}%</td></tr>"
        for t in k["trade_productivity"])
    mod = k.get("modules")
    mod_html = ""
    if mod:
        mod_html = f"""<section><h2>Industrialized construction: prefab module pipeline</h2><div class='flow'>
          <div><b>{mod['fabricated']}</b><span>fabricated</span></div><i>→</i>
          <div><b>{mod['shipped']}</b><span>shipped</span></div><i>→</i>
          <div><b>{mod['installed']}</b><span>installed</span></div></div>
          <p class='muted'>QC failure rate {mod['qc_fail_rate_pct']}% · average {mod['avg_factory_to_install_days']} days from factory to installation</p></section>"""
    total = stats["daily_logs.csv"]
    dq_html = ""
    if perms.get("can_see_quarantine"):
        dq_rows = "".join(f"<tr><td>{html.escape(r)}</td><td>{n}</td></tr>" for r, n in dq["reasons"].items())
        audit = "".join(f"<tr><td>{r['source']}</td><td>{r['read']}</td><td>{r['loaded']}</td><td>{r['rejected']}</td>"
                        f"<td class='mono'>{r['sha256'][:12]}…</td></tr>" for r in dq["runs"])
        dq_html = f"""<section><h2>Data quality: quarantined rows by reason</h2><table><tr><th>Reason</th><th>Rows</th></tr>{dq_rows}</table>
          <h2>Audit log (records management)</h2><table><tr><th>Source</th><th>Read</th><th>Loaded</th><th>Rejected</th><th>SHA-256</th></tr>{audit}</table></section>"""
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>SitePulse Dashboard</title><style>
:root{{--bg:#f6f7f9;--fg:#1d2430;--muted:#5f6b7a;--card:#fff;--line:#dde2e8;--accent:#1f6feb;--neg:#c2410c;--pos:#15803d}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,Arial,sans-serif}}
header{{background:#14213d;color:#fff;padding:20px 28px}} header h1{{margin:0;font-size:22px}} header p{{margin:4px 0 0;color:#c9d3e3}}
main{{max-width:1100px;margin:auto;padding:20px}} section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:16px 0}}
h2{{font-size:16px;margin:4px 0 12px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}} .big{{font-size:34px;font-weight:700;color:var(--accent)}}
.muted{{color:var(--muted);font-size:13px}} .kv{{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:5px 0;font-size:14px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}
.neg{{color:var(--neg);font-weight:600}} .pos{{color:var(--pos);font-weight:600}} .mono{{font-family:monospace}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}} @media(max-width:760px){{.two{{grid-template-columns:1fr}}}}
.two section{{margin:0}} .lbl,.val,.tick{{font-size:12px;fill:var(--fg)}} .bar{{fill:var(--accent)}} .target{{stroke:var(--neg);stroke-dasharray:4 3}}
.line{{fill:none;stroke:var(--accent);stroke-width:2.5}} .dot{{fill:var(--accent)}}
.flow{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}} .flow div{{background:#eef4ff;border-radius:8px;padding:10px 18px;text-align:center}}
.flow b{{display:block;font-size:26px}} .flow span{{font-size:12px;color:var(--muted)}} .flow i{{font-style:normal;font-size:22px;color:var(--muted)}}
.badge{{display:inline-block;background:#fff3;border-radius:999px;padding:2px 10px;font-size:12px;margin-left:8px}}
</style></head><body>
<header><h1>SitePulse · Construction Productivity Dashboard <span class='badge'>role: {html.escape(role)}</span></h1>
<p>Synthetic data · {total['read']} daily log rows read, {total['loaded']} loaded, {total['rejected']} quarantined · projects visible: {', '.join(perms['projects'])}</p></header>
<main><div class='grid'>{cards}</div>
<div class='two'><section><h2>Weekly plan attainment (installed ÷ planned)</h2>{_line_chart(k['weekly'])}</section>
<section><h2>Delay causes from site diary notes (unstructured text)</h2>{_bar_chart(k['delay_causes'], 'category', 'notes', ' notes')}</section></div>
<div class='two'><section><h2>Plan attainment by weather</h2>{_bar_chart(k['weather'], 'weather', 'plan_attainment_pct', '%', target=100)}</section>
<section><h2>Labour productivity by trade (units per labour-hour)</h2><table><tr><th>Proj</th><th>Trade</th><th>Planned</th><th>Actual</th><th>Var</th></tr>{trade_rows}</table></section></div>
{mod_html}{dq_html}</main></body></html>"""
