-- OTT Analytics database schema (SQLite)
DROP TABLE IF EXISTS payments; DROP TABLE IF EXISTS watch_history;
DROP TABLE IF EXISTS subscribers; DROP TABLE IF EXISTS content; DROP TABLE IF EXISTS plans;

CREATE TABLE plans (plan_id INTEGER PRIMARY KEY, name TEXT, price REAL);
CREATE TABLE subscribers (
  sub_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT,
  plan_id INTEGER REFERENCES plans(plan_id),
  signup_date TEXT, status TEXT CHECK(status IN ('Active','Churned')), churn_date TEXT);
CREATE TABLE content (content_id INTEGER PRIMARY KEY, title TEXT, genre TEXT, type TEXT, release_year INTEGER);
CREATE TABLE watch_history (
  watch_id INTEGER PRIMARY KEY, sub_id INTEGER REFERENCES subscribers(sub_id),
  content_id INTEGER REFERENCES content(content_id), watch_date TEXT, minutes INTEGER);
CREATE TABLE payments (
  payment_id INTEGER PRIMARY KEY, sub_id INTEGER REFERENCES subscribers(sub_id),
  pay_date TEXT, amount REAL);
CREATE INDEX idx_watch_sub ON watch_history(sub_id);
CREATE INDEX idx_pay_date ON payments(pay_date);
