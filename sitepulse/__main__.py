"""python -m sitepulse --role data_steward --out sample_data"""
import argparse, json, sys
from pathlib import Path
from . import pipeline, kpis, report, access
from .generate_sample import generate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sitepulse", description="Construction productivity data pipeline and KPI dashboard")
    ap.add_argument("--data", default="sample_data", help="folder with daily_logs.csv, modules.csv, site_diary.jsonl")
    ap.add_argument("--out", default="sample_data", help="where to write the dashboard and KPI files")
    ap.add_argument("--role", default="data_steward", help="access role (see sitepulse/access.py)")
    ap.add_argument("--roles-file", help="optional JSON file of roles")
    ap.add_argument("--generate", action="store_true", help="regenerate the synthetic sample data first")
    a = ap.parse_args(argv)

    try:
        perms = access.permissions(a.role, access.load_roles(a.roles_file))
    except PermissionError as e:
        print("ACCESS DENIED:", e, file=sys.stderr); return 2

    if a.generate:
        generate(a.data)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    con, stats = pipeline.run(a.data, out / "sitepulse.db")
    k = kpis.compute(con, perms["projects"])
    dq = kpis.data_quality(con)

    (out / f"dashboard_{a.role}.html").write_text(report.render(k, dq, a.role, perms, stats))
    (out / f"kpis_{a.role}.json").write_text(json.dumps(k, indent=2))
    if perms["can_see_quarantine"]:
        (out / "data_quality.json").write_text(json.dumps(dq, indent=2))

    s = stats["daily_logs.csv"]
    print(f"SitePulse  role={a.role}  projects={','.join(perms['projects'])}")
    print(f"  daily_logs.csv   read {s['read']}  loaded {s['loaded']}  quarantined {s['rejected']}")
    print(f"  modules.csv      loaded {stats['modules.csv']['loaded']}")
    print(f"  site_diary.jsonl classified {stats['site_diary.jsonl']['loaded']} free-text notes")
    for pid, v in k["projects"].items():
        print(f"  {pid}: plan attainment {v['plan_attainment_pct']}%  rework {v['rework_rate_pct']}%  "
              f"incidents/10k hrs {v['incidents_per_10k_hours']}")
    print(f"  dashboard -> {out / f'dashboard_{a.role}.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
