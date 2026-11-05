import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from trend_sniper.core import digest, write_json
from trend_sniper.production.daily import DailyPreviews
from trend_sniper.production.editor import write_and_select
from trend_sniper.production.materials import library, plan, visual_renderer
from trend_sniper.production.publisher import release_worker
from trend_sniper.production.release import proposal
from trend_sniper.production.stories import story_pool
from trend_sniper.queue import snapshot
from trend_sniper.web.app import create_app
from trend_sniper.web.discovery import SNAPSHOT
from trend_sniper.web.formats import legacy_build as build, legacy_recipe
from trend_sniper.web.store import Store


def sample(kind="Countdown"):
    return next(
        c
        for c in json.loads(SNAPSHOT.read_text())["cards"]
        if legacy_recipe(c)[0] == kind
    )


class WorkerChecks(unittest.TestCase):
    def test_factual_drafts_keep_sources_and_winner_is_actual_compiler_input(self):
        for kind in ("Countdown", "News desk"):
            card = sample(kind)
            script, report = write_and_select(card, build(card), analytics=True)
            self.assertEqual(len(report["drafts"]), 100)
            winner = max(report["drafts"], key=lambda d: d["assessment"]["score"])
            self.assertEqual(winner["id"], report["winner"])
            self.assertEqual(script["scenes"], winner["scenes"])
            refs = {r["source"] for r in report["research"]["records"]}
            for draft in report["drafts"]:
                self.assertTrue(all(s["source"] in refs for s in draft["scenes"]))

    def test_fiction_exhausted_model_keeps_actual_count_and_distinct_scripts(self):
        card = sample("Family drama")
        with patch("trend_sniper.web.formats.urlopen", side_effect=OSError):
            base = build(card)
        base["method"] = "Local AI fiction"
        story = [
            "At ten I buried the key.",
            "My brother dug it up.",
            "We unlocked the birdhouse.",
            "Inside was our old map.",
        ]
        with patch(
            "trend_sniper.production.stories.generate",
            side_effect=[{"stories": [story] * 5}, OSError(), OSError()],
        ):
            selected, report = story_pool(base, card)
        self.assertEqual(len(report["drafts"]), 2)
        self.assertTrue(selected["scenes"])
        self.assertIn("unavailable", report["batch_status"])

    def test_clearance_and_per_scene_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            photo = path / "photo.png"
            Image.new("RGB", (60, 40), "red").save(photo)
            asset = {
                "file": "photo.png",
                "kind": "photo",
                "description": "telescope optical mirror",
                "license": "owned",
                "sha256": digest(photo),
                "evidence": "test fixture",
                "source": "test",
                "credit": "test",
            }
            write_json(
                path / "catalog.json",
                [
                    asset,
                    {**asset, "license": "unknown"},
                    {**asset, "sha256": "wrong"},
                    {**asset, "file": "../outside"},
                ],
            )
            files, rejected = library(path)
            self.assertEqual(len(files), 1)
            self.assertEqual(len(rejected), 3)
            scene = {
                "seconds": 2,
                "value": "A telescope mirror",
                "caption": "alignment",
                "mode": "choice",
            }
            topic = {
                "format": "News desk",
                "scenes": [scene, {**scene, "value": "Unrelated swimming race"}],
            }
            shots = plan(topic, files)
            self.assertEqual(
                shots["scenes"][0]["visual"]["matched_terms"], ["mirror", "telescope"]
            )
            self.assertIsNone(shots["scenes"][1]["visual"])
            draw = visual_renderer(lambda *args: Image.new("RGB", (720, 1280)), shots)
            self.assertEqual(draw(topic, 0, 0, 0, 4).getpixel((100, 260)), (255, 0, 0))

    def test_planner_requires_real_comparisons(self):
        now = datetime(2026, 11, 4, 5, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            rows = [
                {
                    "video_id": f"{hour}-{i}",
                    "format": "Countdown",
                    "views_at_24h": hour * 100 + i,
                    "published_at": f"2026-10-0{i + 1}T{hour}:00:00+08:00",
                }
                for i in range(3)
                for hour in (12, 20)
            ]
            write_json(path, rows[:2] * 9)
            self.assertIn("Exploratory", proposal(path, "Countdown", now)["reason"])
            write_json(path, rows)
            result = proposal(path, "Countdown", now)
            self.assertEqual(result["proposed_at"], "2026-11-05T20:00:00+08:00")
            self.assertEqual(result["sample_sizes"], {"12": 3, "20": 3})

    def test_daily_previews_skip_duplicate_content(self):
        now = datetime.now(UTC)
        with tempfile.TemporaryDirectory() as tmp:
            service = DailyPreviews(Store(Path(tmp) / "db"))
            card = {**sample(), "observed": now.isoformat()}
            calls = []

            def enqueue(key, body):
                calls.append(key)
                return {"id": "test-job"}

            service.tick([card], enqueue, now)
            service.set(card["id"])
            service.tick([card], enqueue, now)
            service.tick([card], enqueue, now)
            service.tick(
                [{**card, "observed": (now + timedelta(days=1)).isoformat()}],
                enqueue,
                now + timedelta(days=1),
            )
            self.assertEqual(len(calls), 1)


class PublisherChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.app = create_app(self.path / "qa.db")
        self.store = self.app.state.store
        self.client = TestClient(self.app)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.client.close)
        self.folder = self.path / "qa-factory" / "job"
        self.folder.mkdir()
        write_json(
            self.folder / "metadata.json",
            {"title": "QA preview", "description": "Example", "hashtags": ["Shorts"]},
        )
        for name in ("short.mp4", "script.json", "captions.srt"):
            (self.folder / name).write_text("test-only fixture")
        write_json(
            self.folder / "manifest.json",
            {
                "sha256": {
                    name: digest(self.folder / name)
                    for name in (
                        "metadata.json",
                        "short.mp4",
                        "script.json",
                        "captions.srt",
                    )
                }
            },
        )
        with self.store.connection() as db:
            db.execute("INSERT INTO productions VALUES ('job','key','{}','ready','')")
        self.at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        self.review = {
            "manifest_hash": digest(self.folder / "manifest.json"),
            "channel_id": "test-channel",
            "publish_at": self.at,
            "audience": "made_for_kids",
            "synthetic": False,
            "reviewed": True,
        }
        self.approved = {
            "channel": "test-channel",
            "at": self.at,
            "kids": True,
            "synthetic": False,
            "hashes": snapshot(self.folder),
        }

    def connect_fake(self):
        auth = self.path / "youtube"
        auth.mkdir()
        write_json(
            auth / "channel.json", {"id": "test-channel", "name": "Test fixture"}
        )
        write_json(auth / "token-youtube.json", {})

    def test_review_gate_and_idempotency(self):
        url = "/api/releases/job"
        self.assertEqual(self.client.post(url, json=self.review).status_code, 409)
        self.connect_fake()
        self.assertEqual(
            self.client.post(
                url, json={**self.review, "manifest_hash": "stale"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(url, json={**self.review, "reviewed": False}).status_code,
            422,
        )
        with patch("trend_sniper.web.releases.release_worker"):
            self.assertEqual(self.client.post(url, json=self.review).status_code, 202)
            self.assertEqual(self.client.post(url, json=self.review).status_code, 409)

    def test_mocked_upload_and_uncertain_submission(self):
        self.connect_fake()
        with patch("trend_sniper.web.releases.release_worker"):
            self.client.post("/api/releases/job", json=self.review)

        def transport(auth, channel):
            def upload(movie, body):
                self.assertNotEqual(movie, self.folder / "short.mp4")
                self.assertEqual(
                    movie.read_bytes(), (self.folder / "short.mp4").read_bytes()
                )
                self.assertTrue(body["status"]["selfDeclaredMadeForKids"])
                return {"id": "fixture", "status": body["status"]}

            return upload

        release_worker(self.store, self.folder, "job", None, self.approved, transport)
        info = self.client.get("/api/releases/job").json()
        self.assertEqual((info["state"], info["video_id"]), ("scheduled", "fixture"))

        # Simulate a fresh request whose remote upload may have been accepted.
        with self.store.connection() as db:
            db.execute(
                "UPDATE releases SET state='awaiting_upload',remote_id=NULL WHERE job='job'"
            )

        def uncertain(auth, channel):
            def upload(*args):
                raise TimeoutError()

            return upload

        release_worker(self.store, self.folder, "job", None, self.approved, uncertain)
        self.assertEqual(
            self.client.get("/api/releases/job").json()["state"], "check_youtube_studio"
        )
        self.assertEqual(
            self.client.post("/api/releases/job", json=self.review).status_code, 409
        )
