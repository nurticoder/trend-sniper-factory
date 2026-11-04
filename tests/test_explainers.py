import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from trend_sniper.core import digest
from trend_sniper.production.explainer import (
    Brief,
    fetch,
    pilot,
    technical_review,
    utterance,
)
from trend_sniper.production.narration import RATE, save_wav
from trend_sniper.web.app import create_app


class ExplainerContracts(unittest.TestCase):
    def test_sourced_scene_plan_is_not_upload_countdown(self):
        brief = pilot()
        self.assertEqual(len(brief.passages), 4)
        self.assertIn("surface tension", brief.payoff.lower())
        self.assertGreater(len(brief.passages[0].shots), 1)
        self.assertTrue(all(p.claim_sources for p in brief.passages))
        self.assertTrue(
            all(
                s.subject and s.action and s.purpose
                for p in brief.passages
                for s in p.shots
            )
        )
        self.assertNotIn("views", brief.model_dump_json())

    def test_unsupported_topic_does_not_generate_generic_video(self):
        with self.assertRaisesRegex(ValueError, "collection covers water"):
            pilot("Latest smartphone releases")
        with self.assertRaises(ValueError):
            pilot("How underwater volcanoes form")

    def test_invalid_claim_source_and_shot_intervals_fail(self):
        raw = pilot().model_dump()
        raw["passages"][0]["claim_sources"] = [9]
        with self.assertRaises(ValidationError):
            Brief.model_validate(raw)
        raw = pilot().model_dump()
        raw["passages"][0]["shots"][0]["end"] = 0
        with self.assertRaises(ValidationError):
            Brief.model_validate(raw)

    def test_graphics_cannot_silently_replace_required_footage(self):
        raw = pilot().model_dump()
        for p in raw["passages"]:
            for shot in p["shots"]:
                shot.update(asset="original-orbit", treatment="orbit")
        with self.assertRaisesRegex(ValidationError, "real footage"):
            Brief.model_validate(raw)

    def test_source_download_is_bounded_and_reused_bytes_are_verified(self):
        class Response(io.BytesIO):
            url = "https://www.nasa.gov/example/"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "trend_sniper.production.explainer.urlopen",
                side_effect=lambda *a, **k: Response(b"source"),
            ) as network:
                path, receipt = fetch(Response.url, root)
                self.assertEqual(receipt["sha256"], digest(path))
                fetch(Response.url, root)
                self.assertEqual(network.call_count, 1)
                path.write_text("tampered")
                fetch(Response.url, root)
                self.assertEqual(network.call_count, 2)
                with self.assertRaisesRegex(ValueError, "budget"):
                    fetch("https://www.nasa.gov/large", root, 2)
            with self.assertRaisesRegex(ValueError, "not approved"):
                fetch("https://example.com/file", root)

    def test_unchanged_speech_reuses_cache_changed_passage_does_not(self):
        def engine(text, path, inputs, voice):
            save_wav(path, [1000, -1000] * (RATE // 2))

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "trend_sniper.production.explainer.narration.availability",
                return_value={"available": True},
            ),
            patch(
                "trend_sniper.production.explainer.speech", side_effect=engine
            ) as provider,
        ):
            root = Path(tmp)
            self.assertFalse(utterance("A supported explanation.", root, "steady")[2])
            self.assertTrue(utterance("A supported explanation.", root, "steady")[2])
            utterance("A revised explanation.", root, "steady")
            self.assertEqual(provider.call_count, 2)

    def test_encoded_timing_and_dimensions_are_checked(self):
        with patch("trend_sniper.production.explainer.subprocess.run") as probe:
            probe.return_value.stderr = (
                "Duration: 00:00:37.54 Video: h264 720x1280 24 fps"
            )
            self.assertEqual(technical_review(Path("/tmp"), 37.5416)["fps"], 24)
            with self.assertRaisesRegex(ValueError, "duration disagrees"):
                technical_review(Path("/tmp"), 20)
            probe.return_value.stderr = (
                "Duration: 00:00:37.54 Video: h264 1280x720 8 fps"
            )
            with self.assertRaises(ValueError):
                technical_review(Path("/tmp"), 37.54)

    def test_missing_voice_is_visible_not_a_silent_fallback(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "trend_sniper.production.explainer.narration.availability",
                return_value={"available": False},
            ),
            self.assertRaisesRegex(ValueError, "Narration missing"),
        ):
            utterance("Some explanation.", Path(tmp), "steady")


class ExplainerJourney(unittest.TestCase):
    def test_intake_revision_voice_and_production_input_are_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "qa.db")
            with TestClient(app) as client:
                app.state.production_queue.pause(True)
                self.assertEqual(
                    client.post(
                        "/api/explainer-briefs",
                        json={"topic": "A random unsupported topic"},
                    ).status_code,
                    422,
                )
                project = client.post(
                    "/api/explainer-briefs",
                    json={"topic": "Water shapes in microgravity"},
                ).json()
                base = "/api/explainer-briefs/" + project["id"]
                result = client.post(base + "/produce")
                self.assertEqual(result.status_code, 202)
                first = result.json()["id"]
                self.assertEqual(client.post(base + "/produce").json()["id"], first)
                client.put("/api/explainer-voice", json={"voice": "brisk"})
                second = client.post(base + "/produce").json()["id"]
                self.assertNotEqual(first, second)
                project["brief"]["passages"][0]["narration"] = (
                    "Water keeps a rounded shape in this demonstration."
                )
                body = {"expected_revision": 1, "brief": project["brief"]}
                self.assertEqual(client.put(base, json=body).status_code, 200)
                self.assertEqual(client.put(base, json=body).status_code, 409)
                info = client.get("/api/explainer-studio").json()
                self.assertEqual(info["selected_voice"], "brisk")
                self.assertEqual(info["projects"][0]["revision"], 2)
                with app.state.store.connection() as db:
                    frozen = json.loads(
                        db.execute(
                            "SELECT input FROM production_runs WHERE job=?", (first,)
                        ).fetchone()[0]
                    )
                self.assertEqual(frozen["explainer"]["brief"]["voice"], "steady")
                self.assertNotEqual(
                    frozen["explainer"]["brief"]["passages"][0]["narration"],
                    body["brief"]["passages"][0]["narration"],
                )
                self.assertEqual(
                    client.post(
                        "/api/explainer-review/" + first,
                        json={"manifest_hash": "wrong", "watched": True},
                    ).status_code,
                    409,
                )
                self.assertEqual(
                    client.get("/api/explainer-auditions/absent").status_code, 404
                )


class PrivatePilotRelease(unittest.TestCase):
    def test_pilot_upload_is_blocked_even_for_an_explicit_release_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root / "qa.db")
            with TestClient(app) as client:
                with app.state.store.connection() as db:
                    db.execute(
                        "INSERT INTO productions VALUES ('pilot','pilot-key','{}','ready','')"
                    )
                folder = root / "qa-factory" / "pilot"
                folder.mkdir()
                (folder / "review.json").write_text("{}")
                response = client.post(
                    "/api/releases/pilot",
                    json={
                        "manifest_hash": "fixture",
                        "channel_id": "fixture",
                        "publish_at": (
                            datetime.now(UTC) + timedelta(days=1)
                        ).isoformat(),
                        "audience": "not_made_for_kids",
                        "synthetic": True,
                        "reviewed": True,
                    },
                )
                self.assertEqual(response.status_code, 409)
                self.assertIn("Publishing is disabled", response.json()["detail"])
