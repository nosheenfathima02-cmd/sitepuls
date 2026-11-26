"""Ingest -> validate -> quarantine -> load (SQLite) -> audit log."""
import csv, json, hashlib, sqlite3, datetime as dt
from pathlib import Path
from .generate_sample import PROJECTS, TRADES

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_log(
  date TEXT, project_id TEXT, trade TEXT, crew_size INTEGER, hours_worked REAL,
  planned_units REAL, installed_units REAL, unit TEXT, rework_units REAL,
  safety_incidents INTEGER, weather TEXT,
  PRIMARY KEY(date, project_id, trade));
CREATE TABLE IF NOT EXISTS module(
  module_id TEXT PRIMARY KEY, project_id TEXT, fabricated TEXT, shipped TEXT, installed TEXT, qc_status TEXT);
CREATE TABLE IF NOT EXISTS diary(
  date TEXT, project_id TEXT, author_role TEXT, note TEXT, category TEXT, lost_hours REAL);
CREATE TABLE IF NOT EXISTS quarantine(
  source TEXT, line INTEGER, reason TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS run_log(
  run_at TEXT, source TEXT, sha256 TEXT, rows_read INTEGER, rows_loaded INTEGER, rows_rejected INTEGER);
"""

# Rule-based text classification for unstructured site notes
CATEGORIES = {
    "weather": ["rain", "wind", "snow", "storm"],
    "labour": ["absent", "short-handed"],
    "material": ["delivery", "supplier", "truck"],
    "inspection": ["inspection", "rework"],
    "quality": ["damaged", "defect", "sent back"],
    "equipment": ["hydraulic", "equipment down", "breakdown"],
    "design": ["rfi", "architect", "drawing"],
    "safety": ["near miss", "incident", "toolbox"],
}


def classify(note):
    n = note.lower()
    for cat, words in CATEGORIES.items():
        if any(w in n for w in words):
            return cat
    return "none"


def lost_hours(note):
    import re
    n = note.lower()
    m = re.search(r"(?:lost|for|down)\s+(\d+(?:\.\d+)?)h", n) or re.search(r"(\d+(?:\.\d+)?)h\s+late", n)
    return float(m.group(1)) if m else 0.0


def validate_log(r):
    """Return a list of reasons the row is invalid (empty list = valid)."""
    errs = []
    try:
        dt.date.fromisoformat(r["date"])
    except ValueError:
        errs.append("date not ISO yyyy-mm-dd")
    if r["project_id"] not in PROJECTS:
        errs.append("unknown project_id")
    if r["trade"] not in TRADES:
        errs.append("unknown trade")
    try:
        crew = int(r["crew_size"]); hrs = float(r["hours_worked"])
        planned = float(r["planned_units"]); inst = float(r["installed_units"]); rew = float(r["rework_units"])
    except ValueError:
        return errs + ["missing or non-numeric value"]
    if crew <= 0: errs.append("crew_size must be > 0")
    if hrs <= 0: errs.append("hours_worked must be > 0")
    if hrs > crew * 14: errs.append("hours exceed 14 per worker")
    if planned > 0 and inst > planned * 3: errs.append("installed > 3x planned (likely typo)")
    if rew > inst: errs.append("rework greater than installed")
    return errs


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(data_dir="sample_data", db_path="sitepulse.db"):
    data = Path(data_dir)
    Path(db_path).unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    now = dt.datetime.now().isoformat(timespec="seconds")
    stats = {}

    # 1) Structured daily logs
    src = data / "daily_logs.csv"
    read = loaded = rejected = 0
    with open(src) as f:
        for line, r in enumerate(csv.DictReader(f), start=2):
            read += 1
            errs = validate_log(r)
            if not errs:
                try:
                    con.execute("INSERT INTO daily_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (r["date"], r["project_id"], r["trade"], int(r["crew_size"]),
                                 float(r["hours_worked"]), float(r["planned_units"]), float(r["installed_units"]),
                                 r["unit"], float(r["rework_units"]), int(r["safety_incidents"]), r["weather"]))
                    loaded += 1
                    continue
                except sqlite3.IntegrityError:
                    errs = ["duplicate submission"]
            rejected += 1
            con.execute("INSERT INTO quarantine VALUES (?,?,?,?)", (src.name, line, "; ".join(errs), json.dumps(r)))
    con.execute("INSERT INTO run_log VALUES (?,?,?,?,?,?)", (now, src.name, sha256(src), read, loaded, rejected))
    stats[src.name] = dict(read=read, loaded=loaded, rejected=rejected)

    # 2) Prefab modules
    src = data / "modules.csv"
    with open(src) as f:
        rows = list(csv.DictReader(f))
    con.executemany("INSERT INTO module VALUES (?,?,?,?,?,?)",
                    [(r["module_id"], r["project_id"], r["fabricated"], r["shipped"] or None,
                      r["installed"] or None, r["qc_status"]) for r in rows])
    con.execute("INSERT INTO run_log VALUES (?,?,?,?,?,?)", (now, src.name, sha256(src), len(rows), len(rows), 0))
    stats[src.name] = dict(read=len(rows), loaded=len(rows), rejected=0)

    # 3) Unstructured diary notes -> classified records
    src = data / "site_diary.jsonl"
    n = 0
    with open(src) as f:
        for line in f:
            d = json.loads(line); n += 1
            con.execute("INSERT INTO diary VALUES (?,?,?,?,?,?)",
                        (d["date"], d["project_id"], d["author_role"], d["note"], classify(d["note"]), lost_hours(d["note"])))
    con.execute("INSERT INTO run_log VALUES (?,?,?,?,?,?)", (now, src.name, sha256(src), n, n, 0))
    stats[src.name] = dict(read=n, loaded=n, rejected=0)

    con.commit()
    return con, stats
