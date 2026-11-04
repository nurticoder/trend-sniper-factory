import copy
import io
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from trend_sniper.core import digest
from trend_sniper.production.jobs import Cancelled
from trend_sniper.production.narration import (
    RATE,
    availability,
    mix,
    prepare,
    samples,
    save_wav,
    spoken,
)
from trend_sniper.production.voice_install import install
from trend_sniper.web.app import create_app


def topic():
    return {
        "format": "Countdown",
        "scenes": [
            {
                "heading": "HOOK",
                "value": "Which sample leads?",
                "caption": "Observed today",
                "seconds": 1,
                "mode": "choice",
            },
            {
                "heading": "RANK 1",
                "role": "evidence",
                "value": "A source title",
                "caption": "Source",
                "seconds": 1,
                "mode": "reveal",
            },
        ],
    }


def fake_speech(text, path, inputs):
    save_wav(
        path, (int(6000 * math.sin(math.tau * 900 * i / RATE)) for i in range(2 * RATE))
    )


class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.audit = self.folder / "audit"
        self.audit.mkdir()

    @patch(
        "trend_sniper.production.narration.availability",
        return_value={"available": True, "detail": "Fixture"},
    )
    def test_measured_speech_extends_edit_and_preserves_original(self, _):
        original = topic()
        saved = copy.deepcopy(original)
        edit, report = prepare(original, self.audit, self.folder, engine=fake_speech)
        self.assertEqual(original, saved)
        self.assertEqual(report["state"], "ready")
        self.assertGreaterEqual(edit["scenes"][0]["seconds"], 2.75)
        self.assertEqual(report["clips"][0]["start"], 0.55)
        self.assertIn("RANK 1.", edit["scenes"][1]["narration"])
        voice = samples(self.audit / "narration.wav")
        self.assertEqual(max(abs(v) for v in voice[: int(0.5 * RATE)]), 0)
        self.assertLessEqual(max(abs(v) for v in voice), round(0.64 * 32767) + 1)
        self.assertAlmostEqual(
            len(voice) / RATE, sum(s["seconds"] for s in edit["scenes"]), places=4
        )
        self.assertEqual(report["audio_sha256"], digest(self.audit / "narration.wav"))
        for clip in report["clips"]:
            self.assertLessEqual(
                clip["start"] + clip["duration"],
                sum(s["seconds"] for s in edit["scenes"][: clip["scene"]]),
            )

    @patch(
        "trend_sniper.production.narration.availability",
        return_value={"available": True, "detail": "Fixture"},
    )
    def test_partial_failure_reverts_entire_edit_and_required_mode_fails(self, _):
        calls = []

        def broken(text, path, inputs):
            calls.append(text)
            if len(calls) % 2 == 0:
                raise subprocess.TimeoutExpired("piper", 40)
            fake_speech(text, path, inputs)

        original = topic()
        edit, report = prepare(original, self.audit, self.folder, engine=broken)
        self.assertEqual(edit, original)
        self.assertEqual(report["state"], "fallback")
        self.assertEqual(report["clips"], [])
        self.assertFalse((self.audit / "narration.wav").exists())
        with self.assertRaisesRegex(ValueError, "Required narration failed"):
            prepare(original, self.audit, self.folder, mode="required", engine=broken)

    def test_spoken_metrics_are_explicitly_approximate_and_titles_preserve_numbers(
        self,
    ):
        scene = {"value": "12,582,761 views lead the sample.", "role": "hook"}
        self.assertEqual(
            spoken(scene, "Countdown"), "about 12.6 million views lead the sample."
        )
        self.assertEqual(scene["value"], "12,582,761 views lead the sample.")
        evidence = {
            "value": "A 12,000 piece puzzle",
            "role": "evidence",
            "heading": "Rank 1",
        }
        self.assertIn("12,000", spoken(evidence, "Countdown"))

    def test_missing_model_and_off_never_generate(self):
        with (
            patch(
                "trend_sniper.production.narration.availability",
                return_value={"available": False, "detail": "Missing voice"},
            ),
            patch("trend_sniper.production.narration.synthesize") as engine,
        ):
            _, report = prepare(topic(), self.audit, self.folder)
            self.assertEqual(report["state"], "fallback")
            self.assertEqual(
                prepare(topic(), self.audit, self.folder, "off")[1]["state"], "off"
            )
            with self.assertRaisesRegex(ValueError, "Narration required"):
                prepare(topic(), self.audit, self.folder, "required")
            engine.assert_not_called()

    @patch(
        "trend_sniper.production.narration.availability",
        return_value={"available": True, "detail": "Fixture"},
    )
    def test_silence_is_rejected_and_cancellation_propagates(self, _):
        def silent(text, path, inputs):
            save_wav(path, [0] * RATE)

        self.assertEqual(
            prepare(topic(), self.audit, self.folder, engine=silent)[1]["state"],
            "fallback",
        )

        def stop(stage):
            raise Cancelled()

        with self.assertRaises(Cancelled):
            prepare(topic(), self.audit, self.folder, stage=stop, engine=fake_speech)

    @patch(
        "trend_sniper.production.narration.availability",
        return_value={"available": True, "detail": "Fixture"},
    )
    def test_total_duration_budget_and_model_change_reject_voice(self, check):
        long = topic()
        long["scenes"][0]["seconds"] = 90
        edit, report = prepare(long, self.audit, self.folder, engine=fake_speech)
        self.assertEqual(report["state"], "fallback")
        self.assertEqual(edit, long)
        check.side_effect = [
            {"available": True, "detail": "Fixture"},
            {"available": False, "detail": "Changed"},
        ]
        self.assertEqual(
            prepare(topic(), self.audit, self.folder, engine=fake_speech)[1]["state"],
            "fallback",
        )

    def test_music_ducks_during_speech_and_mixer_bounds_peaks(self):
        bed, voice = self.audit / "bed.wav", self.audit / "voice.wav"
        save_wav(bed, [6000] * (3 * RATE))
        save_wav(voice, [0] * (3 * RATE))
        report = {"clips": [{"start": 1, "duration": 1}]}
        mix(bed, voice, report)
        result = samples(bed)
        self.assertEqual(result[int(0.4 * RATE)], 4200)
        self.assertEqual(result[int(1.5 * RATE)], 1200)
        self.assertTrue(1200 < result[int(0.95 * RATE)] < 4200)
        self.assertEqual(result[int(2.5 * RATE)], 4200)
        save_wav(bed, [32767] * (3 * RATE))
        save_wav(voice, [32767] * (3 * RATE))
        mix(bed, voice, report)
        self.assertLessEqual(max(samples(bed)), round(0.95 * 32767))
        save_wav(voice, [0] * RATE)
        with self.assertRaisesRegex(ValueError, "durations disagree"):
            mix(bed, voice, report)

    @patch(
        "trend_sniper.production.narration.importlib.metadata.version",
        return_value="1.8.0",
    )
    def test_changed_voice_file_cannot_inherit_rights_record(self, _):
        voice = self.folder / "voices" / "en_US-ljspeech-medium"
        voice.mkdir(parents=True)
        model = voice / "example.onnx"
        model.write_bytes(b"original")
        with patch(
            "trend_sniper.production.narration.FILES", {"example.onnx": digest(model)}
        ):
            self.assertTrue(availability(self.folder)["available"])
            model.write_bytes(b"replaced")
            self.assertFalse(availability(self.folder)["available"])
            with patch(
                "trend_sniper.production.narration.digest", side_effect=PermissionError
            ):
                self.assertFalse(availability(self.folder)["available"])

    def test_preferences_are_frozen_with_job_and_its_retry(self):
        app = create_app(self.folder / "qa.db")
        with TestClient(app) as client:
            app.state.production_queue.pause(True)
            self.assertEqual(
                client.get("/api/production-preferences").json()["narration"], "auto"
            )
            job = app.state.enqueue("voice-fixture", {"title": "Fixture"})["id"]
            self.assertEqual(
                client.put(
                    "/api/production-preferences", json={"narration": "required"}
                ).status_code,
                200,
            )
            self.assertEqual(
                client.put(
                    "/api/production-preferences", json={"narration": "unknown"}
                ).status_code,
                422,
            )
            app.state.production_queue.cancel(job)
            retry = app.state.production_queue.retry(job)["id"]
            with app.state.store.connection() as db:
                payload = json.loads(
                    db.execute(
                        "SELECT input FROM production_runs WHERE job=?", (retry,)
                    ).fetchone()[0]
                )
            self.assertEqual(payload["production_options"]["narration"], "auto")


class VoiceInstallerTests(unittest.TestCase):
    def test_invalid_download_never_creates_an_installed_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (
                patch(
                    "trend_sniper.production.voice_install.urlopen",
                    return_value=io.BytesIO(b"wrong bytes"),
                ),
                self.assertRaisesRegex(ValueError, "checksum"),
            ):
                install(folder)
            self.assertFalse((folder / "voices" / "en_US-ljspeech-medium").exists())
            self.assertEqual(list((folder / "voices").iterdir()), [])
