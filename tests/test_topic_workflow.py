"""Application handoff regressions plus a two-second encoder fixture, never a full episode."""

import copy
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from test_formats import GAMING, PHYSICS

from trend_sniper.core import digest
from trend_sniper.production.captions import subtitle_filter, write_ass
from trend_sniper.production.commons import search_footage
from trend_sniper.production.explainer import command, prepare_shot, technical_review
from trend_sniper.production.kokoro import install
from trend_sniper.production.narration import RATE, save_wav
from trend_sniper.web.app import create_app
from trend_sniper.web.discovery import SNAPSHOT


def wait(client, job):
    until = time.monotonic() + 5
    while time.monotonic() < until:
        state = next(j for j in client.get("/api/productions").json() if j["id"] == job)
        if state["status"] not in {"queued", "running"}:
            return state
        time.sleep(0.02)
    raise AssertionError("Fixture job did not finish")


class TopicJourney(unittest.TestCase):
    def test_two_topics_prepare_review_and_reach_shared_assembler(self):
        for subject, response in [
            ("Physics mysteries", PHYSICS),
            ("Minecraft redstone experiments", GAMING),
        ]:
            with self.subTest(subject=subject), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                clip = root / "fixture.mp4"
                clip.write_bytes(b"technical fixture only, assembler mocked")
                asset = {
                    "id": "media-" + digest(clip),
                    "path": str(clip),
                    "sha256": digest(clip),
                    "description": response["scenes"][0]["visual"]["subject"],
                    "source": "https://example.com/fixture",
                    "license": "owned",
                    "credit": "Original technical fixture",
                    "start": 0,
                    "end": 20,
                }

                def voice(text, inputs, profile):
                    audio = inputs / "speech.wav"
                    save_wav(audio, [1000, -1000] * (7 * RATE // 2))
                    return audio, 7, True

                app = create_app(root / "qa.db")
                with (
                    patch("trend_sniper.web.niches.collect", side_effect=OSError),
                    patch(
                        "trend_sniper.production.content.generate",
                        return_value=copy.deepcopy(response),
                    ),
                    patch(
                        "trend_sniper.production.topic_workflow.commons.search_footage",
                        return_value=[asset],
                    ) as search,
                    patch(
                        "trend_sniper.production.topic_workflow.utterance",
                        side_effect=voice,
                    ),
                    patch(
                        "trend_sniper.production.topic_workflow.assemble",
                        return_value={
                            "title": response["title"],
                            "format": "Narrated explainer",
                        },
                    ) as assembler,
                    TestClient(app) as client,
                ):
                    client.put("/api/explainer-voice", json={"voice": "brisk"})
                    card = next(
                        c
                        for c in json.loads(SNAPSHOT.read_text())["cards"]
                        if c["name"] == subject
                    )
                    client.post("/api/niche-selection", params={"key": card["id"]})
                    job = client.post(
                        "/api/niche-production", params={"key": card["id"]}
                    ).json()["id"]
                    self.assertEqual(wait(client, job)["status"], "planned")
                    plan = client.get(
                        f"/api/productions/{job}/content-plan.json"
                    ).json()
                    self.assertEqual(plan["voice_profile"], "brisk")
                    client.put("/api/explainer-voice", json={"voice": "steady"})
                    self.assertNotIn("path", plan["preparation"][0]["candidates"][0])
                    self.assertEqual(
                        search.call_args_list[0].args[0],
                        response["scenes"][0]["visual"]["subject"],
                    )
                    self.assertEqual(
                        client.get(f"/api/content-plans/{job}/media/0/0").status_code,
                        200,
                    )
                    self.assertEqual(
                        client.get(f"/api/content-plans/{job}/media/0/-2").status_code,
                        404,
                    )
                    review = {
                        "plan_hash": plan["plan_hash"],
                        "facts_reviewed": True,
                        "footage_reviewed": True,
                        "evidence": [
                            {
                                "scene": i,
                                "url": "https://example.com/factual-source",
                                "supporting_excerpt": s["narration"],
                            }
                            for i, s in enumerate(response["scenes"])
                        ],
                        "shots": [
                            [{"candidate": 0, "start": 0, "end": 10}]
                            for _ in response["scenes"]
                        ],
                    }
                    url = f"/api/content-plans/{job}/produce"
                    self.assertEqual(
                        client.post(
                            url, json={**review, "facts_reviewed": False}
                        ).status_code,
                        422,
                    )
                    self.assertEqual(
                        client.post(
                            url, json={**review, "plan_hash": "0" * 64}
                        ).status_code,
                        422,
                    )
                    self.assertEqual(
                        client.post(
                            url, json={**review, "evidence": review["evidence"][:2]}
                        ).status_code,
                        422,
                    )
                    clip.write_bytes(b"changed")
                    self.assertEqual(client.post(url, json=review).status_code, 422)
                    clip.write_bytes(b"technical fixture only, assembler mocked")
                    rendered = client.post(url, json=review)
                    self.assertEqual(rendered.status_code, 202, rendered.text)
                    preview = rendered.json()["id"]
                    self.assertEqual(wait(client, preview)["status"], "ready")
                    self.assertEqual(
                        client.post(url, json=review).json()["id"], preview
                    )
                    brief = assembler.call_args.args[0]
                    self.assertEqual(brief.voice, "brisk")
                    self.assertEqual(brief.title, response["title"])
                    self.assertEqual(
                        brief.passages[0].narration, response["scenes"][0]["narration"]
                    )
                    self.assertEqual(
                        brief.passages[0].shots[0].purpose,
                        response["scenes"][0]["visual"]["purpose"],
                    )
                    self.assertFalse(list(root.rglob("short.mp4")))

    def test_missing_footage_and_speech_stay_visible_and_cannot_produce(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "qa.db")
            with (
                patch("trend_sniper.web.niches.collect", side_effect=OSError),
                patch(
                    "trend_sniper.production.topic_workflow.commons.search_footage",
                    return_value=[],
                ),
                patch(
                    "trend_sniper.production.topic_workflow.utterance",
                    side_effect=ValueError("Missing voice"),
                ),
                TestClient(app) as client,
            ):
                app.state.production_queue.pause(True)
                with app.state.store.connection() as db:
                    db.execute(
                        "INSERT INTO productions VALUES ('old','old','{}','planned','')"
                    )
                job = client.post(
                    "/api/content-plans/old/prepare", json=PHYSICS
                ).json()["id"]
                app.state.production_queue.pause(False)
                self.assertEqual(wait(client, job)["status"], "planned")
                plan = client.get(f"/api/productions/{job}/content-plan.json").json()
                self.assertTrue(
                    all(len(s["attention"]) == 2 for s in plan["preparation"])
                )
                self.assertEqual(
                    client.get(f"/api/productions/{job}/short.mp4").status_code, 404
                )
                body = {
                    "plan_hash": plan["plan_hash"],
                    "facts_reviewed": True,
                    "footage_reviewed": True,
                    "evidence": [
                        {
                            "scene": i,
                            "url": "https://example.com/source",
                            "supporting_excerpt": "Technical regression fixture support.",
                        }
                        for i in range(3)
                    ],
                    "shots": [[{"candidate": 0, "start": 0, "end": 10}]] * 3,
                }
                result = client.post(f"/api/content-plans/{job}/produce", json=body)
                self.assertEqual(result.status_code, 422)
                self.assertIn("narration missing", result.json()["detail"])


class NativeAssembly(unittest.TestCase):
    def test_two_second_smooth_shot_and_native_captions_decode(self):
        with tempfile.TemporaryDirectory(prefix="caption fixture ") as tmp:
            root = Path(tmp)
            clip = root / "source.mp4"
            command(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=s=320x180:r=24:d=2",
                    "-c:v",
                    "libx264",
                    str(clip),
                ]
            )
            asset = {"path": str(clip), "sha256": digest(clip)}
            edit = {
                "asset": "fixture",
                "source_start": 0,
                "duration": 2,
                "treatment": "contain",
                "focus_x": 0.5,
                "crop_height": 1,
            }
            shot = prepare_shot(edit, {"fixture": asset}, root)
            with patch("trend_sniper.production.explainer.command") as encoder:
                self.assertEqual(prepare_shot(edit, {"fixture": asset}, root), shot)
                encoder.assert_not_called()
            captions = root / "captions.ass"
            write_ass(
                [(0, 1, "The first phrase."), (1, 2, r"Literal {\\pos(1,1)} text.")],
                captions,
            )
            self.assertNotIn(r"{\\pos", captions.read_text())
            command(
                [
                    "-i",
                    str(shot),
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    "-vf",
                    subtitle_filter(captions),
                    "-t",
                    "2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-c:a",
                    "aac",
                    str(root / "short.mp4"),
                ]
            )
            command(["-xerror", "-i", str(root / "short.mp4"), "-f", "null", "-"])
            self.assertEqual(technical_review(root, 2)["fps"], 24)


class RightsAndSetup(unittest.TestCase):
    def test_commons_retains_cc_by_credit_and_rejects_uncleared_license(self):
        metadata = {
            "LicenseShortName": {"value": "CC BY 4.0"},
            "Artist": {"value": "Original creator"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
        }

        def row(license_name):
            m = copy.deepcopy(metadata)
            m["LicenseShortName"]["value"] = license_name
            return {
                "title": "File:Redstone torch inverter.webm",
                "imageinfo": [
                    {
                        "mime": "video/webm",
                        "size": 10,
                        "url": "https://upload.wikimedia.org/test.webm",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test",
                        "extmetadata": m,
                    }
                ],
            }

        response = {
            "query": {"pages": {"1": row("CC BY-SA 4.0"), "2": row("CC BY 4.0")}}
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "trend_sniper.production.commons.retrieve",
                side_effect=[json.dumps(response).encode(), b"fixture"],
            ) as network,
            patch("trend_sniper.production.fragments.duration", return_value=12),
        ):
            found = search_footage("redstone torch", Path(tmp))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["license"], "CC-BY-4.0")
            self.assertEqual(found[0]["credit"], "Original creator")
            self.assertEqual(found[0]["sha256"], digest(Path(found[0]["path"])))
            self.assertEqual(search_footage("redstone torch", Path(tmp)), found)
            self.assertEqual(network.call_count, 2)

    def test_invalid_kokoro_download_never_installs(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "trend_sniper.production.kokoro.urlopen",
                return_value=io.BytesIO(b"wrong model"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "checksum"):
                install(Path(tmp))
            self.assertFalse((Path(tmp) / "voices" / "kokoro-82m-v1.0").exists())
