import json, sqlite3, tempfile, unittest
from pathlib import Path
from sitepulse import pipeline, kpis, access
from sitepulse.generate_sample import generate

GOOD = dict(date="2026-03-02", project_id="P1", trade="Drywall", crew_size="5", hours_worked="40",
            planned_units="88", installed_units="80", unit="m2", rework_units="2", safety_incidents="0", weather="Clear")


class Validation(unittest.TestCase):
    def test_good_row_passes(self):
        self.assertEqual(pipeline.validate_log(GOOD), [])

    def test_each_bad_row_is_caught(self):
        cases = {"date": ("2026/03/02", "date not ISO yyyy-mm-dd"), "project_id": ("P9", "unknown project_id"),
                 "trade": ("Plumbing??", "unknown trade"), "hours_worked": ("-40", "hours_worked must be > 0"),
                 "installed_units": ("900", "installed > 3x planned (likely typo)"),
                 "rework_units": ("99", "rework greater than installed"), "crew_size": ("", "missing or non-numeric value")}
        for field, (value, reason) in cases.items():
            with self.subTest(field=field):
                self.assertIn(reason, pipeline.validate_log({**GOOD, field: value}))


class TextClassification(unittest.TestCase):
    def test_categories_and_hours(self):
        self.assertEqual(pipeline.classify("Rain stopped crane operations after 12h. Lost 3h."), "weather")
        self.assertEqual(pipeline.classify("RFI raised on stair detail"), "design")
        self.assertEqual(pipeline.classify("Good progress today"), "none")
        self.assertEqual(pipeline.lost_hours("Excavator hydraulic leak, equipment down 2h."), 2.0)
        self.assertEqual(pipeline.lost_hours("Concrete truck arrived 3h late, pour delayed."), 3.0)
        self.assertEqual(pipeline.classify("Two framers absent, crew short-handed"), "labour")


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        generate(cls.tmp)
        cls.con, cls.stats = pipeline.run(cls.tmp, Path(cls.tmp) / "t.db")

    def test_every_row_accounted_for(self):
        s = self.stats["daily_logs.csv"]
        self.assertEqual(s["read"], s["loaded"] + s["rejected"])
        self.assertEqual(s["rejected"], 18)  # 14 injected errors + 4 duplicates

    def test_duplicates_quarantined(self):
        n = self.con.execute("SELECT COUNT(*) FROM quarantine WHERE reason='duplicate submission'").fetchone()[0]
        self.assertEqual(n, 4)

    def test_role_only_sees_its_project(self):
        k = kpis.compute(self.con, access.permissions("pm_P2")["projects"])
        self.assertEqual(list(k["projects"]), ["P2"])
        self.assertNotIn("modules", k)  # prefab modules belong to P1 only

    def test_unknown_role_denied(self):
        with self.assertRaises(PermissionError):
            access.permissions("contractor_x")

    def test_audit_log_has_checksums(self):
        runs = kpis.data_quality(self.con)["runs"]
        self.assertEqual(len(runs), 3)
        self.assertTrue(all(len(r["sha256"]) == 64 for r in runs))


if __name__ == "__main__":
    unittest.main()
