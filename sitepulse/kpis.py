"""Productivity KPIs computed with SQL. `projects` limits results (controlled access)."""


def _in(projects):
    return "(" + ",".join("?" * len(projects)) + ")"


def compute(con, projects):
    p = list(projects)
    q = lambda sql, args=(): con.execute(sql, p + list(args)).fetchall()
    out = {"projects": {}}

    for pid, hours, planned, inst, rework, inc in q(f"""
        SELECT project_id, SUM(hours_worked), SUM(planned_units), SUM(installed_units),
               SUM(rework_units), SUM(safety_incidents)
        FROM daily_log WHERE project_id IN {_in(p)} GROUP BY project_id ORDER BY project_id"""):
        out["projects"][pid] = {
            "labour_hours": round(hours),
            "plan_attainment_pct": round(100 * inst / planned, 1),   # installed vs planned
            "rework_rate_pct": round(100 * rework / inst, 1),
            "incidents_per_10k_hours": round(10000 * inc / hours, 2),
        }

    # Labour productivity (units per labour-hour) by trade, planned vs actual
    out["trade_productivity"] = [
        {"project_id": a, "trade": b, "unit": c, "planned_per_hr": round(d, 3), "actual_per_hr": round(e, 3),
         "variance_pct": round(100 * (e - d) / d, 1)}
        for a, b, c, d, e in q(f"""
        SELECT project_id, trade, unit, SUM(planned_units)/SUM(hours_worked), SUM(installed_units)/SUM(hours_worked)
        FROM daily_log WHERE project_id IN {_in(p)} GROUP BY project_id, trade ORDER BY project_id, trade""")]

    # Weekly plan attainment trend
    out["weekly"] = [{"week": w, "plan_attainment_pct": round(v, 1)} for w, v in q(f"""
        SELECT strftime('%Y-W%W', date) AS wk, 100*SUM(installed_units)/SUM(planned_units)
        FROM daily_log WHERE project_id IN {_in(p)} GROUP BY wk ORDER BY wk""")]

    # Weather impact
    out["weather"] = [{"weather": w, "plan_attainment_pct": round(v, 1), "days": n} for w, v, n in q(f"""
        SELECT weather, 100*SUM(installed_units)/SUM(planned_units), COUNT(DISTINCT date||project_id)
        FROM daily_log WHERE project_id IN {_in(p)} GROUP BY weather ORDER BY 2 DESC""")]

    # Delay causes from unstructured notes
    out["delay_causes"] = [{"category": c, "notes": n, "lost_hours": h} for c, n, h in q(f"""
        SELECT category, COUNT(*), SUM(lost_hours) FROM diary
        WHERE project_id IN {_in(p)} AND category != 'none' GROUP BY category ORDER BY 2 DESC""")]

    # Industrialized construction: module pipeline
    mods = q(f"""SELECT COUNT(*), COUNT(shipped), COUNT(installed), SUM(qc_status='Fail'),
                 AVG(julianday(installed)-julianday(fabricated))
                 FROM module WHERE project_id IN {_in(p)}""")[0]
    if mods[0]:
        out["modules"] = {"fabricated": mods[0], "shipped": mods[1], "installed": mods[2],
                          "qc_fail_rate_pct": round(100 * mods[3] / mods[0], 1),
                          "avg_factory_to_install_days": round(mods[4], 1) if mods[4] else None}
    return out


def data_quality(con):
    reasons = {}
    for (r,) in con.execute("SELECT reason FROM quarantine"):
        for part in r.split("; "):
            reasons[part] = reasons.get(part, 0) + 1
    runs = [dict(zip(["run_at", "source", "sha256", "read", "loaded", "rejected"], row))
            for row in con.execute("SELECT * FROM run_log")]
    return {"reasons": dict(sorted(reasons.items(), key=lambda x: -x[1])), "runs": runs}
