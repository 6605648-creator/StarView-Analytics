"""Analytics layer. Every function takes (db, filters) and returns JSON-ready data.
Filters: plan, city. Data ends on 2026-09-30."""
from datetime import date, timedelta
END = date(2026, 9, 30)
BASE = "FROM subscribers s JOIN plans p USING(plan_id) WHERE 1=1"
PLAN_RISK = {"Basic": 20, "Standard": 10, "Premium": 0}

def flt(f):
    sql, args = "", []
    if f.get("plan"): sql += " AND p.name=?"; args.append(f["plan"])
    if f.get("city"): sql += " AND s.city=?"; args.append(f["city"])
    return sql, args

def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]

def filters(db, f):
    return {"plans": [r["name"] for r in rows(db, "SELECT name FROM plans ORDER BY price")],
            "cities": [r["city"] for r in rows(db, "SELECT DISTINCT city FROM subscribers ORDER BY city")]}

def kpis(db, f):
    w, a = flt(f)
    r = rows(db, f"""SELECT COUNT(*) total, SUM(s.status='Active') active,
        ROUND(100.0*SUM(s.status='Churned')/COUNT(*),1) churn_rate,
        SUM(CASE WHEN s.status='Active' THEN p.price ELSE 0 END) mrr {BASE}{w}""", a)[0]
    rev = db.execute(f"SELECT COALESCE(SUM(y.amount),0) FROM payments y JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id) WHERE 1=1{w}", a).fetchone()[0]
    mins, viewers = db.execute(f"SELECT COALESCE(SUM(x.minutes),0), COUNT(DISTINCT x.sub_id) FROM watch_history x JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id) WHERE 1=1{w}", a).fetchone()
    r.update(total_revenue=rev, revenue_per_sub=round(rev / max(r["total"], 1)), hours_per_viewer=round(mins / 60 / max(viewers, 1), 1))
    return r

def revenue_by_plan(db, f):
    w, a = flt(f)
    return rows(db, f"""SELECT substr(y.pay_date,1,7) month, p.name plan, SUM(y.amount) revenue
        FROM payments y JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id) WHERE 1=1{w}
        GROUP BY month, plan ORDER BY month""", a)

def growth(db, f):
    w, a = flt(f)
    return {"signups": rows(db, f"SELECT substr(s.signup_date,1,7) month, COUNT(*) n {BASE}{w} GROUP BY month ORDER BY month", a),
            "churned": rows(db, f"SELECT substr(s.churn_date,1,7) month, COUNT(*) n {BASE}{w} AND s.churn_date IS NOT NULL GROUP BY month ORDER BY month", a)}

def top_content(db, f):
    w, a = flt(f)
    return rows(db, f"""SELECT c.title, c.genre, ROUND(SUM(x.minutes)/60.0) hours, COUNT(DISTINCT x.sub_id) viewers
        FROM watch_history x JOIN content c USING(content_id) JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id)
        WHERE 1=1{w} GROUP BY c.content_id ORDER BY hours DESC LIMIT 8""", a)

def genres(db, f):
    w, a = flt(f)
    return rows(db, f"""SELECT c.genre, ROUND(SUM(x.minutes)/60.0) hours
        FROM watch_history x JOIN content c USING(content_id) JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id)
        WHERE 1=1{w} GROUP BY c.genre ORDER BY hours DESC""", a)

def churn_plan(db, f):
    w, a = flt({"city": f.get("city")})
    return rows(db, f"SELECT p.name plan, ROUND(100.0*SUM(s.status='Churned')/COUNT(*),1) churn_pct {BASE}{w} GROUP BY p.name ORDER BY p.price", a)

def cohort(db, f):
    """Retention: % of each signup-quarter cohort still subscribed after N months."""
    w, a = flt(f); MS = [1, 3, 6, 9, 12]; out = {}
    for s in rows(db, f"SELECT s.signup_date, s.churn_date {BASE}{w}", a):
        d = date.fromisoformat(s["signup_date"]); q = f"{d.year}-Q{(d.month - 1)//3 + 1}"
        c = out.setdefault(q, {"cohort": q, "size": 0, **{m: [0, 0] for m in MS}}); c["size"] += 1
        for m in MS:
            if d + timedelta(days=30 * m) <= END:
                c[m][1] += 1
                if not s["churn_date"] or date.fromisoformat(s["churn_date"]) >= d + timedelta(days=30 * m): c[m][0] += 1
    res = []
    for q in sorted(out):
        c = out[q]; row = {"cohort": q, "size": c["size"]}
        for m in MS: row[f"m{m}"] = round(100 * c[m][0] / c[m][1]) if c[m][1] == c["size"] else None
        res.append(row)
    return res

def _risk_rows(db, f):
    """Churn-risk score 0-100 = inactivity (max 60) + plan weakness (max 20) + low recent viewing (max 20)."""
    w, a = flt(f); out = []
    for r in rows(db, f"""SELECT s.sub_id, s.name, s.city, p.name plan, p.price, s.signup_date, MAX(x.watch_date) last_watch,
        COALESCE(SUM(CASE WHEN x.watch_date>='2026-08-01' THEN x.minutes END),0)/60.0 recent_hours
        FROM subscribers s JOIN plans p USING(plan_id) LEFT JOIN watch_history x USING(sub_id)
        WHERE s.status='Active'{w} GROUP BY s.sub_id""", a):
        idle = (END - date.fromisoformat(r["last_watch"] or r["signup_date"])).days
        score = round(min(60, idle * 60 / 90) + PLAN_RISK[r["plan"]] + (20 if r["recent_hours"] < 2 else 10 if r["recent_hours"] < 5 else 0))
        r.update(days_idle=idle, score=score, level="High" if score >= 70 else "Medium" if score >= 40 else "Low", recent_hours=round(r["recent_hours"], 1))
        out.append(r)
    return sorted(out, key=lambda r: (-r["score"], -r["price"]))

def risk(db, f):
    allr = _risk_rows(db, f)
    cnt = lambda l: sum(1 for r in allr if r["level"] == l)
    return {"summary": {"high": cnt("High"), "medium": cnt("Medium"), "low": cnt("Low"),
                        "revenue_at_risk": sum(r["price"] for r in allr if r["level"] == "High")},
            "rows": allr[:12]}

def subscriber(db, f):
    sid = int(f.get("id") or 0)
    info = rows(db, "SELECT s.*, p.name plan, p.price FROM subscribers s JOIN plans p USING(plan_id) WHERE sub_id=?", (sid,))
    if not info: return {"error": "No subscriber with that ID. Try a number from 1 to 1500."}
    g = rows(db, "SELECT c.genre, ROUND(SUM(x.minutes)/60.0,1) hours FROM watch_history x JOIN content c USING(content_id) WHERE x.sub_id=? GROUP BY c.genre ORDER BY hours DESC", (sid,))
    rec = rows(db, """SELECT c.title, c.genre, ROUND(SUM(x.minutes)/60.0) hours FROM content c JOIN watch_history x USING(content_id)
        WHERE c.genre=? AND c.content_id NOT IN (SELECT content_id FROM watch_history WHERE sub_id=?)
        GROUP BY c.content_id ORDER BY hours DESC LIMIT 3""", (g[0]["genre"], sid)) if g else []
    recent = rows(db, "SELECT c.title, x.watch_date, x.minutes FROM watch_history x JOIN content c USING(content_id) WHERE x.sub_id=? ORDER BY x.watch_date DESC LIMIT 5", (sid,))
    paid = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE sub_id=?", (sid,)).fetchone()[0]
    rk = next((r for r in _risk_rows(db, {}) if r["sub_id"] == sid), None)
    return {"info": info[0], "genres": g, "recommended": rec, "recent": recent, "total_paid": paid, "risk": rk and {"score": rk["score"], "level": rk["level"], "days_idle": rk["days_idle"]}}

def catalog(db, f):
    """Every title with total hours watched and number of viewers (feeds the hero and the rails)."""
    w, a = flt(f)
    return rows(db, f"""SELECT c.content_id, c.title, c.genre, c.type, c.release_year,
        ROUND(SUM(x.minutes)/60.0) hours, COUNT(DISTINCT x.sub_id) viewers
        FROM watch_history x JOIN content c USING(content_id) JOIN subscribers s USING(sub_id) JOIN plans p USING(plan_id)
        WHERE 1=1{w} GROUP BY c.content_id ORDER BY hours DESC""", a)

API = {"catalog": catalog, "filters": filters, "kpis": kpis, "revenue_by_plan": revenue_by_plan, "growth": growth, "top_content": top_content,
       "genres": genres, "churn_plan": churn_plan, "cohort": cohort, "risk": risk, "subscriber": subscriber}
