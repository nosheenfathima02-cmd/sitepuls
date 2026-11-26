"""Generate a reproducible SYNTHETIC construction dataset (no real company data).

Three fictional projects, 60 working days. Produces:
  daily_logs.csv   structured site production logs (with realistic data-quality problems)
  modules.csv      industrialized (prefab) construction: factory -> shipped -> installed
  site_diary.jsonl unstructured free-text notes written by site staff
"""
import csv, json, random, datetime as dt
from pathlib import Path

PROJECTS = {
    "P1": "Modular Residential, 6 storeys",
    "P2": "School Addition",
    "P3": "Mid-rise Retrofit",
}
TRADES = {  # trade: (unit, planned units per crew-hour)
    "Framing": ("m2", 1.6),
    "Drywall": ("m2", 2.2),
    "Concrete": ("m3", 0.45),
    "Module Install": ("modules", 0.05),
}
NOTES = [
    ("Rain stopped crane operations after {h}h. Lost {d}h.", "weather"),
    ("High winds, crane stood down for {d}h.", "weather"),
    ("Concrete truck arrived {d}h late, pour delayed.", "material"),
    ("Drywall delivery short 40 sheets, waiting on supplier.", "material"),
    ("Inspection failed on level {l} firestopping, rework scheduled.", "inspection"),
    ("Module M-{m} arrived with damaged window frame, sent back to factory.", "quality"),
    ("Two framers absent, crew short-handed for the day.", "labour"),
    ("Excavator hydraulic leak, equipment down {d}h.", "equipment"),
    ("RFI raised on stair detail, work paused pending architect response.", "design"),
    ("Near miss reported: unsecured load on level {l}. Toolbox talk held.", "safety"),
    ("Good progress today, all crews on plan.", "none"),
]


def generate(out_dir="sample_data", seed=7, days=60):
    rnd = random.Random(seed)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    start = dt.date(2026, 3, 2)
    dates = [start + dt.timedelta(d) for d in range(days * 7 // 5 + 7)]
    dates = [d for d in dates if d.weekday() < 5][:days]

    rows = []
    for d in dates:
        for pid in PROJECTS:
            for trade, (unit, rate) in TRADES.items():
                if trade == "Module Install" and pid != "P1":
                    continue
                crew = rnd.randint(3, 9)
                hours = round(crew * rnd.choice([7.5, 8, 8, 8, 9]), 1)
                planned = round(hours * rate, 1)
                weather = rnd.choices(["Clear", "Cloudy", "Rain", "Wind"], [5, 3, 1.2, 0.6])[0]
                eff = rnd.gauss(0.95, 0.12) * (0.7 if weather in ("Rain", "Wind") else 1)
                installed = round(max(0, planned * eff), 1)
                rework = round(installed * max(0, rnd.gauss(0.03, 0.03)), 1)
                incidents = 1 if rnd.random() < 0.012 else 0
                rows.append([d.isoformat(), pid, trade, crew, hours, planned, installed, unit, rework, incidents, weather])

    # Inject realistic data-quality problems so validation has something to catch
    bad = rnd.sample(range(len(rows)), 14)
    for i, idx in enumerate(bad):
        r = rows[idx]
        kind = i % 7
        if kind == 0: r[3] = ""                      # missing crew size
        elif kind == 1: r[4] = -r[4]                  # negative hours
        elif kind == 2: r[0] = r[0].replace("-", "/")  # wrong date format
        elif kind == 3: r[1] = "P9"                    # unknown project
        elif kind == 4: r[6] = r[5] * 12               # impossible output (typo)
        elif kind == 5: r[8] = r[6] + 5                # rework greater than installed
        elif kind == 6: r[2] = "Plumbing??"            # unknown trade
    for idx in rnd.sample(range(len(rows)), 4):       # exact duplicate submissions
        rows.append(list(rows[idx]))

    with open(out / "daily_logs.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "project_id", "trade", "crew_size", "hours_worked", "planned_units",
                    "installed_units", "unit", "rework_units", "safety_incidents", "weather"])
        w.writerows(rows)

    # Prefab modules for P1: factory -> shipped -> installed
    with open(out / "modules.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["module_id", "project_id", "fabricated", "shipped", "installed", "qc_status"])
        for m in range(1, 49):
            fab = start + dt.timedelta(rnd.randint(-20, 50))
            ship = fab + dt.timedelta(rnd.randint(2, 9))
            inst = ship + dt.timedelta(rnd.randint(1, 6))
            qc = rnd.choices(["Pass", "Pass", "Pass", "Pass", "Fail"], k=1)[0]
            last = dates[-1]
            w.writerow([f"M-{m:03d}", "P1", fab.isoformat(),
                        ship.isoformat() if ship <= last else "",
                        inst.isoformat() if inst <= last and qc == "Pass" else "", qc])

    with open(out / "site_diary.jsonl", "w") as f:
        for d in dates:
            for pid in PROJECTS:
                if rnd.random() < 0.55:
                    text, _ = rnd.choice(NOTES)
                    text = text.format(h=rnd.randint(10, 14), d=rnd.randint(1, 4),
                                       l=rnd.randint(1, 6), m=rnd.randint(1, 48))
                    f.write(json.dumps({"date": d.isoformat(), "project_id": pid,
                                        "author_role": rnd.choice(["Superintendent", "Foreman", "Site Engineer"]),
                                        "note": text}) + "\n")
    return out


if __name__ == "__main__":
    print("Wrote synthetic data to", generate())
