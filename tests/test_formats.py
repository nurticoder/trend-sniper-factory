"""Normal application-path regressions. Never render a video in this module."""

import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from trend_sniper.production.content import ContentPlan
from trend_sniper.production.editor import write_and_select
from trend_sniper.web.app import create_app
from trend_sniper.web.discovery import SNAPSHOT
from trend_sniper.web.formats import build


def draft(topic, subject, action, narration):
    return {
        "topic": topic,
        "title": topic,
        "promise": "Understand " + topic.lower() + " with a concrete example.",
        "payoff": narration[-1],
        "scenes": [
            {
                "narration": n,
                "visual": {
                    "subject": subject,
                    "action": action,
                    "purpose": "Demonstrate the specific claim in this passage.",
                },
            }
            for n in narration
        ],
    }


PHYSICS = draft(
    "Why orbiting objects appear weightless",
    "An orbiting spacecraft and a loose object",
    "Show both following the same falling path",
    [
        "Why does an object float inside an orbiting spacecraft?",
        "Gravity still pulls the craft and the object toward Earth.",
        "They fall together, so the object appears weightless relative to the craft.",
    ],
)
GAMING = draft(
    "A Minecraft redstone torch inverter",
    "A Minecraft redstone torch connected to a lever",
    "Toggle the lever and show the torch output changing",
    [
        "Can one Minecraft switch turn another signal off?",
        "Power the block holding a redstone torch and compare the output.",
        "This inversion lets a circuit respond when its input is off.",
    ],
)


class ProductionFormats(unittest.TestCase):
    def test_two_niches_reach_targeted_plans_through_normal_select_and_produce(self):
        for category, subject, response in [
            ("Education", "Physics mysteries", PHYSICS),
            ("Gaming", "Minecraft redstone experiments", GAMING),
        ]:
            with self.subTest(category=category), tempfile.TemporaryDirectory() as tmp:
                app = create_app(Path(tmp) / "qa.db")
                with (
                    patch(
                        "trend_sniper.web.niches.collect",
                        side_effect=OSError("Offline test"),
                    ),
                    TestClient(app) as client,
                    patch(
                        "trend_sniper.production.content.generate",
                        return_value=copy.deepcopy(response),
                    ) as model,
                    patch(
                        "trend_sniper.production.topic_workflow.commons.search_footage",
                        return_value=[],
                    ),
                    patch(
                        "trend_sniper.production.topic_workflow.utterance",
                        side_effect=ValueError("No voice in this fixture"),
                    ),
                    patch("trend_sniper.production.run.render") as renderer,
                    patch("trend_sniper.production.run.write_and_select") as analytics,
                ):
                    card = next(
                        c
                        for c in json.loads(SNAPSHOT.read_text())["cards"]
                        if c["name"] == subject
                    )
                    self.assertEqual(card["category"], category)
                    params = {"key": card["id"]}
                    self.assertEqual(
                        client.post("/api/niche-production", params=params).status_code,
                        409,
                    )
                    self.assertEqual(
                        client.post("/api/niche-selection", params=params).status_code,
                        200,
                    )
                    # A selection saved before this fix must not retain Countdown routing.
                    with app.state.store.connection() as db:
                        stale = {
                            **card,
                            "format": "Countdown",
                            "pitch": "Report upload views",
                        }
                        db.execute(
                            "UPDATE chosen_niche SET snapshot=? WHERE slot=1",
                            (json.dumps(stale),),
                        )
                    saved = client.get("/api/niche-selection").json()
                    self.assertIn(saved["format"], ["Topic explainer", "Gaming guide"])
                    self.assertNotIn("upload views", saved["pitch"])
                    job = client.post("/api/niche-production", params=params).json()[
                        "id"
                    ]
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        state = next(
                            j
                            for j in client.get("/api/productions").json()
                            if j["id"] == job
                        )
                        if state["status"] not in ["queued", "running"]:
                            break
                        time.sleep(0.02)
                    self.assertEqual(state["status"], "planned", state)
                    plan = client.get(
                        f"/api/productions/{job}/content-plan.json"
                    ).json()
                    self.assertEqual(plan["topic"], response["topic"])
                    self.assertEqual(
                        plan["scenes"],
                        ContentPlan.model_validate(response).model_dump()["scenes"],
                    )
                    self.assertEqual(len(plan["preparation"]), 3)
                    self.assertTrue(all(s["attention"] for s in plan["preparation"]))
                    self.assertEqual(
                        client.get(f"/api/productions/{job}/short.mp4").status_code, 404
                    )
                    prompt = model.call_args.args[0]
                    self.assertIn(subject, prompt)
                    self.assertNotIn(card["channel"], prompt)
                    self.assertNotIn(str(card["examples"][0]["views"]), prompt)
                    renderer.assert_not_called()
                    analytics.assert_not_called()

    def test_reporting_requires_explicit_selection_and_is_not_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "qa.db")
            with (
                patch("trend_sniper.web.niches.collect", side_effect=OSError),
                TestClient(app) as client,
            ):
                app.state.production_queue.pause(True)
                card = client.get("/api/niches").json()["cards"][0]
                params = {"key": card["id"]}
                client.post("/api/niche-selection", params=params)
                content = client.post("/api/niche-production", params=params).json()[
                    "id"
                ]
                report = client.post(
                    "/api/niche-production",
                    params={**params, "production_format": "analytics"},
                ).json()["id"]
                self.assertNotEqual(content, report)
                with app.state.store.connection() as db:
                    rows = [
                        json.loads(row[0])
                        for row in db.execute(
                            "SELECT input FROM production_runs ORDER BY rowid"
                        )
                    ]
                self.assertEqual(
                    [r["production_options"]["production_format"] for r in rows],
                    ["content", "analytics"],
                )
                self.assertEqual(
                    client.post(
                        "/api/niche-production",
                        params={**params, "production_format": "bogus"},
                    ).status_code,
                    422,
                )
        with self.assertRaisesRegex(ValueError, "explicit analytics"):
            write_and_select(card, {})
        self.assertTrue(
            any("views" in s["caption"] for s in build(card, analytics=True)["scenes"])
        )

    def test_offline_writer_never_returns_a_generic_fallback_or_report(self):
        card = json.loads(SNAPSHOT.read_text())["cards"][0]
        with (
            patch("trend_sniper.production.content.generate", side_effect=OSError),
            self.assertRaisesRegex(ValueError, "no analytics or generic story"),
        ):
            build(card)
        contaminated = copy.deepcopy(PHYSICS)
        contaminated["scenes"][0]["narration"] = (
            "Compare the view counts of the most watched uploads."
        )
        with (
            patch(
                "trend_sniper.production.content.generate", return_value=contaminated
            ),
            self.assertRaises(ValueError),
        ):
            build(card)


class UnsupportedClaims(unittest.TestCase):
    def test_writer_cannot_invent_research_to_fill_a_niche(self):
        card = json.loads(SNAPSHOT.read_text())["cards"][0]
        contaminated = copy.deepcopy(GAMING)
        contaminated["scenes"][1]["narration"] = (
            "Our team has discovered a revolutionary technique."
        )
        with (
            patch(
                "trend_sniper.production.content.generate", return_value=contaminated
            ),
            self.assertRaises(ValueError),
        ):
            build(card)
