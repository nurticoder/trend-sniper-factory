"""Durable local preview queue. One application process owns one database."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
from uuid import uuid4

from ..web.store import Conflict, Missing


class Cancelled(Exception):
    pass


class ProductionQueue:
    limit = 12

    def __init__(self, store, execute):
        self.store, self.execute = store, execute
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preview")
        self.lock = Lock()
        self.scheduled = self.closed = False
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS productions (
                    id TEXT PRIMARY KEY, selection TEXT UNIQUE, script TEXT, status TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS production_steps(id TEXT PRIMARY KEY, stage TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS production_runs (
                    job TEXT PRIMARY KEY REFERENCES productions(id), input TEXT NOT NULL,
                    created_at TEXT, started_at TEXT, finished_at TEXT, parent TEXT UNIQUE,
                    attempt INTEGER NOT NULL DEFAULT 1, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    runtime_seconds REAL, paid_api_usd REAL);
                CREATE TABLE IF NOT EXISTS production_events (
                    id INTEGER PRIMARY KEY, job TEXT NOT NULL REFERENCES productions(id),
                    at TEXT NOT NULL, stage TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_job ON production_events(job,id);
                CREATE TABLE IF NOT EXISTS production_settings (
                    slot INTEGER PRIMARY KEY CHECK(slot=1), paused INTEGER NOT NULL);
                INSERT OR IGNORE INTO production_settings VALUES (1,0);
                INSERT OR IGNORE INTO production_runs(job,input)
                    SELECT id,script FROM productions;
            """)
            interrupted = db.execute(
                "SELECT id FROM productions WHERE status='running'"
            ).fetchall()
            for (job,) in interrupted:
                db.execute(
                    "UPDATE productions SET status='failed',error=? WHERE id=?",
                    (
                        "The application stopped during production. Retry uses the saved source packet.",
                        job,
                    ),
                )
                db.execute(
                    "UPDATE production_runs SET finished_at=? WHERE job=?",
                    (store.now(), job),
                )
                self.event(db, job, "Interrupted by application restart")

    def event(self, db, job, stage):
        db.execute(
            "INSERT INTO production_events(job,at,stage) VALUES (?,?,?)",
            (job, self.store.now(), stage),
        )
        db.execute("INSERT OR REPLACE INTO production_steps VALUES (?,?)", (job, stage))

    def capacity(self, db):
        count = db.execute(
            "SELECT count(*) FROM productions WHERE status IN ('queued','running')"
        ).fetchone()[0]
        if count >= self.limit:
            raise Conflict(
                f"The preview queue holds {self.limit} jobs. Finish or cancel one before adding more."
            )

    def insert(self, db, key, script, parent=None, attempt=1):
        self.capacity(db)
        job = uuid4().hex
        payload = json.dumps(script)
        db.execute(
            "INSERT INTO productions VALUES (?,?,?,?,?)",
            (job, key, payload, "queued", ""),
        )
        db.execute(
            "INSERT INTO production_runs(job,input,created_at,parent,attempt) VALUES (?,?,?,?,?)",
            (job, payload, self.store.now(), parent, attempt),
        )
        self.event(db, job, "Queued for production")
        return job

    def enqueue(self, key, script):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT id,status FROM productions WHERE selection=?", (key,)
            ).fetchone()
            if old:
                # Failed and cancelled jobs require an explicit retry, including daily runs.
                return {"id": old[0]}
            job = self.insert(db, key, script)
        self.wake()
        return {"id": job}

    def retry(self, job):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT p.selection,p.status,r.input,r.attempt FROM productions p "
                "JOIN production_runs r ON r.job=p.id WHERE p.id=?",
                (job,),
            ).fetchone()
            if row is None:
                raise Missing()
            child = db.execute(
                "SELECT job FROM production_runs WHERE parent=?", (job,)
            ).fetchone()
            if child:
                return {"id": child[0]}
            key, status, payload, attempt = row
            if status not in {"failed", "cancelled"}:
                raise Conflict("Only failed or cancelled previews can be retried.")
            db.execute("UPDATE productions SET selection=NULL WHERE id=?", (job,))
            new = self.insert(db, key, json.loads(payload), job, attempt + 1)
        self.wake()
        return {"id": new}

    def cancel(self, job):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM productions WHERE id=?", (job,)
            ).fetchone()
            if not row:
                raise Missing()
            status = row[0]
            if status == "cancelled":
                return
            if status not in {"queued", "running"}:
                raise Conflict("This preview has already finished.")
            db.execute(
                "UPDATE production_runs SET cancel_requested=1 WHERE job=?", (job,)
            )
            if status == "queued":
                db.execute(
                    "UPDATE productions SET status='cancelled' WHERE id=?", (job,)
                )
                db.execute(
                    "UPDATE production_runs SET finished_at=? WHERE job=?",
                    (self.store.now(), job),
                )
                self.event(db, job, "Cancelled before production")
            else:
                self.event(db, job, "Stop requested — finishing the current operation")

    def pause(self, value):
        with self.store.connection() as db:
            db.execute(
                "UPDATE production_settings SET paused=? WHERE slot=1", (int(value),)
            )
        if not value:
            self.wake()

    def state(self):
        with self.store.connection() as db:
            paused = bool(
                db.execute(
                    "SELECT paused FROM production_settings WHERE slot=1"
                ).fetchone()[0]
            )
            counts = dict(
                db.execute(
                    "SELECT status,count(*) FROM productions GROUP BY status"
                ).fetchall()
            )
            attention = db.execute(
                "SELECT count(*) FROM productions p LEFT JOIN production_runs child ON child.parent=p.id "
                "WHERE p.status IN ('failed','cancelled') AND child.job IS NULL"
            ).fetchone()[0]
            total = db.execute(
                "SELECT sum(runtime_seconds),sum(paid_api_usd),count(paid_api_usd) "
                "FROM production_runs"
            ).fetchone()
        return {
            "paused": paused,
            "counts": counts,
            "capacity": self.limit,
            "attention_count": attention,
            "runtime_seconds": round(total[0] or 0, 2),
            "paid_api_usd": total[1],
            "costed_runs": total[2],
        }

    def history(self, job):
        with self.store.connection() as db:
            if not db.execute(
                "SELECT 1 FROM productions WHERE id=?", (job,)
            ).fetchone():
                raise Missing()
            events = db.execute(
                "SELECT at,stage FROM production_events WHERE job=? ORDER BY id", (job,)
            ).fetchall()
        return [{"at": at, "stage": stage} for at, stage in events]

    def wake(self):
        with self.lock:
            if self.scheduled or self.closed:
                return
            self.scheduled = True
            self.executor.submit(self.drain)

    def progress(self, job, stage=None):
        with self.store.connection() as db:
            cancelled = db.execute(
                "SELECT cancel_requested FROM production_runs WHERE job=?", (job,)
            ).fetchone()[0]
            if cancelled:
                raise Cancelled()
            if stage:
                self.event(db, job, stage)

    def drain(self):
        # Hold the wake lock while deciding to go idle, so an enqueue cannot lose its wakeup.
        while True:
            with self.lock, self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                paused = db.execute(
                    "SELECT paused FROM production_settings WHERE slot=1"
                ).fetchone()[0]
                row = (
                    None
                    if paused or self.closed
                    else db.execute(
                        "SELECT p.id,r.input FROM productions p JOIN production_runs r ON p.id=r.job "
                        "WHERE p.status='queued' ORDER BY p.rowid LIMIT 1"
                    ).fetchone()
                )
                if row is None:
                    self.scheduled = False
                    return
                job, payload = row
                db.execute("UPDATE productions SET status='running' WHERE id=?", (job,))
                db.execute(
                    "UPDATE production_runs SET started_at=? WHERE job=?",
                    (self.store.now(), job),
                )
                self.event(db, job, "Starting production")
            started = monotonic()
            try:
                result = self.execute(
                    job,
                    json.loads(payload),
                    lambda name, key=job: self.progress(key, name),
                )
                # Serialize completion with cancellation. A late cancel cannot expose a ready artifact.
                with self.store.connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    cancelled = db.execute(
                        "SELECT cancel_requested FROM production_runs WHERE job=?",
                        (job,),
                    ).fetchone()[0]
                    if cancelled:
                        raise Cancelled()
                    state = "planned" if result.get("delivery") == "plan" else "ready"
                    db.execute(
                        "UPDATE productions SET status=?,script=? WHERE id=?",
                        (state, json.dumps(result), job),
                    )
                    db.execute(
                        "UPDATE production_runs SET paid_api_usd=0 WHERE job=?", (job,)
                    )
                    self.event(
                        db,
                        job,
                        "Topic plan ready; facts and footage need review"
                        if state == "planned"
                        else "Private preview ready",
                    )
            except Cancelled:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE productions SET status='cancelled' WHERE id=?", (job,)
                    )
                    self.event(db, job, "Production stopped")
            except Exception as exc:  # noqa: BLE001 -- persist worker failures and continue the queue
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE productions SET status='failed',error=? WHERE id=?",
                        (str(exc)[:300], job),
                    )
                    self.event(db, job, "Production failed")
            finally:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE production_runs SET finished_at=?,runtime_seconds=? WHERE job=?",
                        (self.store.now(), round(monotonic() - started, 2), job),
                    )

    def close(self):
        with self.lock:
            self.closed = True
        # Complete the current bounded operation. Leave unstarted jobs durable for next launch.
        self.executor.shutdown(wait=True)
