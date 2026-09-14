from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from expense_ai_copilot.models import ExpenseInput, TripInput, cents


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self, seed=True):
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS trips(
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, city TEXT NOT NULL,
                    currency TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
                    budget_cents INTEGER NOT NULL, hotel_limit_cents INTEGER NOT NULL,
                    meal_limit_cents INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews(
                    id TEXT PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id),
                    receipt_hash TEXT NOT NULL, result_json TEXT NOT NULL, status TEXT NOT NULL,
                    expense_id TEXT, created_at TEXT NOT NULL,
                    UNIQUE(trip_id, receipt_hash));
                CREATE TABLE IF NOT EXISTS expenses(
                    id TEXT PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id),
                    review_id TEXT UNIQUE REFERENCES reviews(id), vendor TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), currency TEXT NOT NULL,
                    date TEXT NOT NULL, category TEXT NOT NULL, units INTEGER NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id),
                    kind TEXT NOT NULL, object_id TEXT NOT NULL, details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL);
            """)
            if seed and not db.execute("SELECT 1 FROM trips LIMIT 1").fetchone():
                db.execute(
                    "INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        "london-weekend",
                        "London weekend",
                        "London",
                        "GBP",
                        "2026-08-14",
                        "2026-08-16",
                        65000,
                        18000,
                        6000,
                    ),
                )
                samples = [
                    ("Garden House Hotel", 16000, "2026-08-14", "hotel"),
                    ("Harbour Café", 2750, "2026-08-14", "meal"),
                    ("City Rail", 1420, "2026-08-14", "transport"),
                    ("Garden House Hotel", 15500, "2026-08-15", "hotel"),
                    ("Market Kitchen", 2100, "2026-08-15", "meal"),
                    ("Design Museum", 3500, "2026-08-15", "activity"),
                    ("Morning Coffee", 1750, "2026-08-16", "meal"),
                    ("City Taxi", 2400, "2026-08-16", "transport"),
                ]
                for index, (vendor, amount, day, category) in enumerate(samples):
                    db.execute(
                        "INSERT INTO expenses VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            f"sample-{index}",
                            "london-weekend",
                            None,
                            vendor,
                            amount,
                            "GBP",
                            day,
                            category,
                            1,
                            now(),
                        ),
                    )
                self.event(
                    db,
                    "london-weekend",
                    "demo_seeded",
                    "london-weekend",
                    {"note": "Eight fictional expenses; no company or customer data."},
                )

    @staticmethod
    def event(db, trip_id, kind, object_id, details):
        db.execute(
            "INSERT INTO events(trip_id,kind,object_id,details_json,created_at) VALUES(?,?,?,?,?)",
            (trip_id, kind, object_id, json.dumps(details), now()),
        )

    def create_trip(self, value: TripInput) -> dict:
        trip_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    trip_id,
                    value.title,
                    value.city,
                    value.currency,
                    value.start_date.isoformat(),
                    value.end_date.isoformat(),
                    cents(value.budget),
                    cents(value.hotel_nightly_limit),
                    cents(value.meal_daily_limit),
                ),
            )
            self.event(db, trip_id, "trip_created", trip_id, {})
        return self.trip(trip_id)

    def trip(self, trip_id, db=None) -> dict:
        if db is None:
            with self.connect() as connection:
                return self.trip(trip_id, connection)
        row = db.execute(
            "SELECT t.*, COALESCE(SUM(e.amount_cents),0) spent_cents, COUNT(e.id) expense_count "
            "FROM trips t LEFT JOIN expenses e ON e.trip_id=t.id WHERE t.id=? GROUP BY t.id",
            (trip_id,),
        ).fetchone()
        if row is None:
            raise KeyError("Trip not found.")
        return dict(row)

    def trips(self):
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM trips ORDER BY start_date DESC,id")]
            return [self.trip(trip_id, db) for trip_id in ids]

    def expenses(self, trip_id):
        with self.connect() as db:
            self.trip(trip_id, db)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM expenses WHERE trip_id=? ORDER BY date DESC,created_at DESC,id", (trip_id,)
                )
            ]

    def daily_spend(self, trip_id, category, day, db=None) -> int:
        if db is None:
            with self.connect() as connection:
                return self.daily_spend(trip_id, category, day, connection)
        return db.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE trip_id=? AND category=? AND date=?",
            (trip_id, category, str(day)),
        ).fetchone()[0]

    @staticmethod
    def receipt_hash(text):
        return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()

    def existing_review(self, trip_id, text):
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM reviews WHERE trip_id=? AND receipt_hash=?",
                (trip_id, self.receipt_hash(text)),
            ).fetchone()
            return self.review(row[0], db) if row else None

    def create_review(self, trip_id, text, result):
        review_id = str(uuid.uuid4())
        with self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",
                    (review_id, trip_id, self.receipt_hash(text), json.dumps(result), "pending", None, now()),
                )
                self.event(
                    db,
                    trip_id,
                    "receipt_reviewed",
                    review_id,
                    {"mode": result["mode"], "issue_count": len(result["issues"])},
                )
            except sqlite3.IntegrityError:
                row = db.execute(
                    "SELECT id FROM reviews WHERE trip_id=? AND receipt_hash=?",
                    (trip_id, self.receipt_hash(text)),
                ).fetchone()
                if row is None:
                    raise
                review_id = row[0]
            return self.review(review_id, db)

    def review(self, review_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.review(review_id, connection)
        row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if row is None:
            raise KeyError("Review not found.")
        return {
            **json.loads(row["result_json"]),
            "id": row["id"],
            "trip_id": row["trip_id"],
            "status": row["status"],
            "expense_id": row["expense_id"],
        }

    def reviews(self, trip_id):
        with self.connect() as db:
            self.trip(trip_id, db)
            return [
                self.review(row[0], db)
                for row in db.execute(
                    "SELECT id FROM reviews WHERE trip_id=? AND status='pending' ORDER BY created_at DESC",
                    (trip_id,),
                ).fetchall()
            ]

    def confirm(self, review_id, value: ExpenseInput, acknowledged: bool):
        from expense_ai_copilot.workflow import assess

        with self.connect() as db:
            # Serialize confirmations, then recheck spend: simultaneous requests cannot use stale totals.
            db.execute("BEGIN IMMEDIATE")
            review = self.review(review_id, db)
            if review["status"] == "confirmed":
                return dict(
                    db.execute("SELECT * FROM expenses WHERE id=?", (review["expense_id"],)).fetchone()
                )
            if review["status"] != "pending":
                raise Conflict("This receipt was discarded and cannot be confirmed.")
            trip = self.trip(review["trip_id"], db)
            daily = self.daily_spend(trip["id"], value.category, value.date, db)
            issues, warnings = assess(value, trip, daily)
            if issues:
                raise Conflict(" ".join(issues))
            if warnings and not acknowledged:
                raise Conflict("Confirm the budget warnings before saving: " + " ".join(warnings))
            expense_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO expenses VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    expense_id,
                    trip["id"],
                    review_id,
                    value.vendor,
                    cents(value.amount),
                    value.currency,
                    value.date.isoformat(),
                    value.category,
                    value.units,
                    now(),
                ),
            )
            db.execute(
                "UPDATE reviews SET status='confirmed', expense_id=? WHERE id=?", (expense_id, review_id)
            )
            self.event(
                db,
                trip["id"],
                "expense_confirmed",
                expense_id,
                {"review_id": review_id, "warnings_acknowledged": bool(warnings)},
            )
            return dict(db.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone())

    def discard(self, review_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            review = self.review(review_id, db)
            if review["status"] == "confirmed":
                raise Conflict("A confirmed expense cannot be discarded as a draft.")
            if review["status"] == "pending":
                db.execute("UPDATE reviews SET status='discarded' WHERE id=?", (review_id,))
                self.event(db, review["trip_id"], "review_discarded", review_id, {})
        return {"status": "discarded"}

    def events(self, trip_id):
        with self.connect() as db:
            self.trip(trip_id, db)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM events WHERE trip_id=? ORDER BY id DESC LIMIT 100", (trip_id,)
                )
            ]
