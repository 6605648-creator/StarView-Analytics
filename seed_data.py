"""Creates ott.db with realistic sample data and CSV exports (for Excel / Power BI)."""
import sqlite3, random, csv, os
from datetime import date, timedelta
random.seed(42)
END = date(2026, 9, 30); START = date(2024, 1, 1)
db = sqlite3.connect("ott.db"); db.executescript(open("schema.sql").read())

plans = [(1, "Basic", 149), (2, "Standard", 299), (3, "Premium", 599)]
db.executemany("INSERT INTO plans VALUES (?,?,?)", plans)
price = {p[0]: p[2] for p in plans}
churn_prob = {1: 0.45, 2: 0.28, 3: 0.15}

genres = ["Drama", "Comedy", "Thriller", "Action", "Romance", "Sci-Fi", "Documentary", "Kids"]
words = ["Midnight", "Empire", "Silent", "River", "Last", "Horizon", "Broken", "City", "Shadow", "Garden", "Storm", "Crown", "Echo", "Monsoon", "Secret"]
content = []
for i in range(1, 61):
    t = f"{random.choice(words)} {random.choice(words)}"
    content.append((i, f"{t} {i}", random.choice(genres), random.choice(["Movie", "Series"]), random.randint(2015, 2026)))
db.executemany("INSERT INTO content VALUES (?,?,?,?,?)", content)
pop = [random.random() ** 2 for _ in content]  # a few titles are hits

cities = ["Delhi", "Mumbai", "Bilaspur", "Raipur", "Pune", "Chennai", "Kolkata", "Bengaluru", "Hyderabad", "Nagpur"]
first = ["Aarav", "Riya", "Kabir", "Ananya", "Vihaan", "Isha", "Rohan", "Meera", "Arjun", "Sneha", "Dev", "Priya"]
last = ["Sharma", "Verma", "Patel", "Singh", "Yadav", "Gupta", "Joshi", "Nair", "Das", "Khan"]
span = (END - START).days
subs, watch, pays = [], [], []
for sid in range(1, 1501):
    plan = random.choices([1, 2, 3], [0.45, 0.35, 0.20])[0]
    signup = START + timedelta(days=random.randint(0, span - 30))
    churned = random.random() < churn_prob[plan]
    last_day = END
    if churned:
        last_day = min(END - timedelta(days=1), signup + timedelta(days=random.randint(30, 500)))
    cdate = last_day.isoformat() if churned else None
    subs.append((sid, f"{random.choice(first)} {random.choice(last)}", random.randint(16, 60),
                 random.choice(cities), plan, signup.isoformat(), "Churned" if churned else "Active", cdate))
    # monthly payments
    d = signup
    while d <= last_day:
        pays.append((sid, d.isoformat(), price[plan])); d += timedelta(days=30)
    # watch activity: churners watch less, 15% of active users are "fading"
    watch_end = last_day
    if not churned and random.random() < 0.15:
        watch_end = END - timedelta(days=random.randint(35, 120))
    days = max(1, (watch_end - signup).days)
    rate = random.uniform(0.02, 0.10) * (0.5 if churned else 1)
    for _ in range(int(days * rate) + 1):
        c = random.choices(content, pop)[0]
        watch.append((sid, c[0], (signup + timedelta(days=random.randint(0, days))).isoformat(), random.randint(10, 150)))

db.executemany("INSERT INTO subscribers VALUES (?,?,?,?,?,?,?,?)", subs)
db.executemany("INSERT INTO watch_history (sub_id,content_id,watch_date,minutes) VALUES (?,?,?,?)", watch)
db.executemany("INSERT INTO payments (sub_id,pay_date,amount) VALUES (?,?,?)", pays)
db.commit()
for t in ["plans", "subscribers", "content", "watch_history", "payments"]:
    cur = db.execute(f"SELECT * FROM {t}")
    with open(f"exports/{t}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow([c[0] for c in cur.description]); w.writerows(cur)
print("Done:", len(subs), "subscribers,", len(watch), "watch events,", len(pays), "payments")
