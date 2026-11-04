import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient

from trend_sniper.production.jobs import ProductionQueue
from trend_sniper.web.app import create_app
from trend_sniper.web.readiness import inspect
from trend_sniper.web.store import Conflict, Store


class QueueOperations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "qa.db")
        self.calls = []

    def create_queue(self, execute=None):
        def run(job, script, progress):
            self.calls.append((job, script))
            progress("Compiling fixture")
            return {**script, "title": "Completed fixture"}

        queue = ProductionQueue(self.store, execute or run)
        self.addCleanup(queue.close)
        return queue

    def status(self, job):
        with self.store.connection() as db:
            return db.execute(
                "SELECT status FROM productions WHERE id=?", (job,)
            ).fetchone()[0]

    def wait(self, job, status):
        deadline = time.monotonic() + 3
        while self.status(job) != status and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.status(job), status)

    def test_pause_restart_resumes_persisted_fifo(self):
        queue = self.create_queue()
        queue.pause(True)
        first = queue.enqueue("a", {"title": "First"})["id"]
        second = queue.enqueue("b", {"title": "Second"})["id"]
        queue.close()
        reopened = self.create_queue()
        self.assertTrue(reopened.state()["paused"])
        reopened.wake()
        self.assertEqual(self.status(first), "queued")
        reopened.pause(False)
        self.wait(second, "ready")
        self.assertEqual([job for job, _ in self.calls], [first, second])
        self.assertEqual(reopened.state()["costed_runs"], 2)
        self.assertEqual(reopened.state()["paid_api_usd"], 0)

    def test_cancel_waiting_then_retry_saved_input_exactly_once(self):
        queue = self.create_queue()
        queue.pause(True)
        job = queue.enqueue("a", {"title": "Frozen input", "source": "original"})["id"]
        queue.cancel(job)
        self.assertEqual(self.status(job), "cancelled")
        with ThreadPoolExecutor(max_workers=4) as executor:
            attempts = list(executor.map(lambda _: queue.retry(job)["id"], range(8)))
        self.assertEqual(len(set(attempts)), 1)
        retry = attempts[0]
        self.assertEqual(queue.enqueue("a", {"title": "New source"})["id"], retry)
        self.assertEqual(queue.state()["attention_count"], 0)
        queue.pause(False)
        self.wait(retry, "ready")
        self.assertEqual(
            self.calls, [(retry, {"title": "Frozen input", "source": "original"})]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT attempt,parent FROM production_runs WHERE job=?", (retry,)
                ).fetchone(),
                (2, job),
            )
        with self.assertRaises(Conflict):
            queue.retry(retry)

    def test_stop_running_prevents_ready_even_without_another_progress_callback(self):
        started, finish = Event(), Event()

        def run(job, script, progress):
            started.set()
            finish.wait(2)
            return script

        queue = self.create_queue(run)
        self.addCleanup(finish.set)
        job = queue.enqueue("a", {"title": "Fixture"})["id"]
        self.assertTrue(started.wait(1))
        queue.cancel(job)
        finish.set()
        self.wait(job, "cancelled")
        self.assertEqual(queue.history(job)[-1]["stage"], "Production stopped")

    def test_failure_does_not_block_next_job_and_retry_preserves_diagnostics(self):
        def run(job, script, progress):
            if script["title"] == "fail":
                progress("Writing fixture")
                raise ValueError("Missing local material")
            return script

        queue = self.create_queue(run)
        bad = queue.enqueue("bad", {"title": "fail"})["id"]
        good = queue.enqueue("good", {"title": "pass"})["id"]
        self.wait(good, "ready")
        self.assertEqual(self.status(bad), "failed")
        self.assertEqual(queue.enqueue("bad", {"title": "new"})["id"], bad)
        self.assertIn("Writing fixture", [item["stage"] for item in queue.history(bad)])

    def test_interrupted_job_requires_retry_but_waiting_job_is_preserved(self):
        queue = self.create_queue()
        queue.pause(True)
        first = queue.enqueue("a", {"title": "Interrupted"})["id"]
        second = queue.enqueue("b", {"title": "Waiting"})["id"]
        queue.close()
        with self.store.connection() as db:
            db.execute("UPDATE productions SET status='running' WHERE id=?", (first,))
        reopened = self.create_queue()
        self.assertEqual(self.status(first), "failed")
        self.assertEqual(self.status(second), "queued")
        self.assertIn("restart", reopened.history(first)[-1]["stage"])

    def test_capacity_rollback_keeps_retryable_source_selection(self):
        queue = self.create_queue()
        queue.pause(True)
        original = queue.enqueue("a", {"title": "Original"})["id"]
        queue.cancel(original)
        for n in range(queue.limit):
            queue.enqueue(str(n), {"title": str(n)})
        with self.assertRaises(Conflict):
            queue.retry(original)
        self.assertEqual(queue.enqueue("a", {"title": "Changed"})["id"], original)
        self.assertEqual(len(self.calls), 0)

    def test_legacy_rows_migrate_without_losing_ready_previews(self):
        queue = self.create_queue()
        queue.close()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO productions VALUES ('legacy','old',?, 'ready','')",
                (json.dumps({"title": "Old preview"}),),
            )
        reopened = self.create_queue()
        self.assertEqual(self.status("legacy"), "ready")
        self.assertEqual(reopened.history("legacy"), [])
        self.assertIsNone(reopened.state()["paid_api_usd"])


class OperationsHTTP(unittest.TestCase):
    def test_controls_and_history_enforce_state_and_browser_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "db")
            with TestClient(app) as client:
                self.assertEqual(
                    client.put(
                        "/api/production-desk", json={"paused": True}
                    ).status_code,
                    200,
                )
                app.state.enqueue("fixture", {"title": "HTTP fixture"})
                job = client.get("/api/productions").json()[0]
                self.assertEqual(job["attempt"], 1)
                self.assertEqual(job["status"], "queued")
                self.assertIsNone(job["paid_api_usd"])
                route = "/api/productions/" + job["id"]
                self.assertEqual(client.post(route + "/retry").status_code, 409)
                self.assertEqual(
                    client.post(
                        route + "/cancel",
                        headers={"Origin": "https://elsewhere.example"},
                    ).status_code,
                    403,
                )
                self.assertEqual(client.post(route + "/cancel").status_code, 202)
                self.assertEqual(client.post(route + "/retry").status_code, 202)
                self.assertEqual(len(client.get(route + "/history").json()), 2)
                self.assertEqual(client.get(route + "/short.mp4").status_code, 404)
                self.assertEqual(
                    client.post("/api/productions/absent/cancel").status_code, 404
                )
                self.assertEqual(
                    client.put(
                        "/api/production-desk", json={"paused": "false"}
                    ).status_code,
                    422,
                )
                page = client.get("/").text
                for name in ("desk.js", "desk.css"):
                    self.assertEqual(client.get("/static/" + name).status_code, 200)
                self.assertIn("queue-toggle", page)
                self.assertEqual(
                    client.get("/static/desk.js").headers["cache-control"], "no-store"
                )

    @patch("trend_sniper.web.readiness.urlopen", side_effect=OSError)
    def test_unavailable_services_never_claim_connection_or_read_tokens(self, _):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            result = inspect(path)
            self.assertFalse(result["writer"]["available"])
            self.assertIsNone(result["youtube"]["channel"])
            self.assertFalse(result["analytics"]["available"])
            (path / "youtube").mkdir()
            (path / "youtube" / "channel.json").write_text(
                json.dumps({"id": "test", "name": "Test channel"})
            )
            (path / "youtube" / "token-youtube.json").write_text(
                "SECRET NEVER RETURNED"
            )
            result = inspect(path)
            self.assertEqual(result["youtube"]["channel"]["id"], "test")
            self.assertNotIn("SECRET", json.dumps(result))
            self.assertIn("Saved connection", result["youtube"]["detail"])
