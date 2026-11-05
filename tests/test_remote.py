"""Remote default, autonomous retries and streaming. No source footage is downloaded here."""

import copy
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType
from typing import ClassVar
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient
from test_formats import GAMING, PHYSICS

from trend_sniper.core import digest, write_json
from trend_sniper.production.jobs import ProductionQueue
from trend_sniper.remote import client, editorial
from trend_sniper.remote.deploy import deploy
from trend_sniper.remote.footage import Budget, youtube_cc, youtube_license
from trend_sniper.remote.producer import produce
from trend_sniper.remote.worker import create_worker
from trend_sniper.web.app import create_app
from trend_sniper.web.discovery import SNAPSHOT
from trend_sniper.web.store import Store


def wait(test, http, job):
    for _ in range(150):
        state = next(j for j in http.get("/api/productions").json() if j["id"] == job)
        if state["status"] not in {"queued", "running"}:
            return state
        time.sleep(0.01)
    test.fail("Worker did not finish the control fixture")


class DesktopRemotePath(unittest.TestCase):
    def test_two_niches_dispatch_remotely_without_local_speech_footage_or_render(self):
        for subject, story in [
            ("Physics mysteries", PHYSICS),
            ("Minecraft redstone experiments", GAMING),
        ]:
            with self.subTest(subject=subject), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                client.save_configuration(
                    root,
                    {
                        "url": "https://fixture.hf.space",
                        "key": "x" * 64,
                        "hf_token": "fixture-private",
                    },
                )
                script = {
                    "title": story["title"],
                    "format": "Narrated explainer",
                    "scenes": story["scenes"],
                }
                report = {"brief": {}, "shots": [], "attention": []}
                manifest = {"sha256": {"short.mp4": "a" * 64}}

                def remote(
                    config,
                    path,
                    method="GET",
                    body=None,
                    subject=subject,
                    script=script,
                    report=report,
                    manifest=manifest,
                    story=story,
                ):
                    if path == "/jobs":
                        self.assertEqual(
                            body["intent"],
                            {
                                "name": subject,
                                "category": "Gaming"
                                if subject.startswith("Minecraft")
                                else "Education",
                            },
                        )
                        self.assertNotIn("views", json.dumps(body))
                        return {"id": "1" * 32}
                    if "/artifacts/" in path:
                        return {
                            "script.json": script,
                            "review.json": report,
                            "manifest.json": manifest,
                            "metadata.json": {"title": story["title"]},
                        }[path.rsplit("/", 1)[1]]
                    return {
                        "id": "1" * 32,
                        "status": "ready",
                        "stage": "Finished",
                        "expires_at": "2099-01-01T00:00:00Z",
                    }

                app = create_app(root / "qa.db")
                with (
                    patch.dict(os.environ, {"TSF_LOCAL_FIXTURE_MODE": "0"}),
                    patch("trend_sniper.web.niches.collect", side_effect=OSError),
                    patch("trend_sniper.remote.client.json_call", side_effect=remote),
                    patch("trend_sniper.production.content.generate") as local_writer,
                    patch(
                        "trend_sniper.production.commons.search_footage"
                    ) as local_footage,
                    patch("trend_sniper.production.explainer.utterance") as local_voice,
                    patch(
                        "trend_sniper.production.explainer.assemble"
                    ) as local_assembly,
                    TestClient(app) as http,
                ):
                    card = next(
                        c
                        for c in json.loads(SNAPSHOT.read_text())["cards"]
                        if c["name"] == subject
                    )
                    http.post("/api/niche-selection", params={"key": card["id"]})
                    job = http.post(
                        "/api/niche-production", params={"key": card["id"]}
                    ).json()["id"]
                    self.assertEqual(wait(self, http, job)["status"], "ready")
                    folder = root / "qa-factory" / job
                    self.assertEqual(
                        json.loads((folder / "script.json").read_text())["title"],
                        story["title"],
                    )
                    self.assertFalse(list(root.rglob("*.mp4")))
                    self.assertFalse(list(root.rglob("*.wav")))
                    self.assertFalse((folder / "source-downloads").exists())
                    for component in [
                        local_writer,
                        local_footage,
                        local_voice,
                        local_assembly,
                    ]:
                        component.assert_not_called()

                    class Media(io.BytesIO):
                        status = 206
                        headers: ClassVar[dict] = {
                            "Content-Type": "video/mp4",
                            "Content-Length": "3",
                            "Content-Range": "bytes 1-3/5",
                            "Accept-Ranges": "bytes",
                        }

                    with patch(
                        "trend_sniper.remote.client.call", return_value=Media(b"bcd")
                    ) as transfer:
                        response = http.get(
                            f"/api/productions/{job}/short.mp4",
                            headers={"Range": "bytes=1-3"},
                        )
                    self.assertEqual(response.status_code, 206)
                    self.assertEqual(response.content, b"bcd")
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(
                        transfer.call_args.kwargs["headers"], {"Range": "bytes=1-3"}
                    )
                    self.assertFalse((folder / "short.mp4").exists())

    def test_missing_connection_never_falls_back_to_desktop_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "qa.db")
            with (
                patch.dict(os.environ, {"TSF_LOCAL_FIXTURE_MODE": "0"}),
                patch("trend_sniper.web.niches.collect", side_effect=OSError),
                patch("trend_sniper.production.topic_workflow.prepare") as local,
                TestClient(app) as http,
            ):
                card = http.get("/api/niches").json()["cards"][0]
                http.post("/api/niche-selection", params={"key": card["id"]})
                job = http.post(
                    "/api/niche-production", params={"key": card["id"]}
                ).json()["id"]
                state = wait(self, http, job)
                self.assertEqual(state["status"], "failed")
                self.assertIn("remote worker", state["error"])
                local.assert_not_called()
                self.assertFalse(list(Path(tmp).rglob("*.mp4")))

    def test_account_token_is_private_and_not_frozen_in_queue_or_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / "qa.db")
            with (
                patch("trend_sniper.web.niches.collect", side_effect=OSError),
                TestClient(app) as http,
            ):
                app.state.production_queue.pause(True)
                token = "hf_" + "private-test-token" * 2
                response = http.post(
                    "/api/remote-worker/connect", json={"token": token}
                )
                self.assertEqual(response.status_code, 202)
                self.assertNotIn(token, response.text)
                pending = next(Path(tmp).glob("remote-setup-*.json"))
                self.assertEqual(pending.stat().st_mode & 0o777, 0o600)
                self.assertFalse((Path(tmp) / "remote-worker.json").exists())
                with app.state.store.connection() as db:
                    self.assertNotIn(
                        token,
                        db.execute("SELECT input FROM production_runs").fetchone()[0],
                    )


class CloudProtocol(unittest.TestCase):
    def test_gpu_checker_requires_remote_setup_and_propagates_free_quota_refusal(self):
        from trend_sniper.remote import gpu_vision

        with (
            patch.dict(os.environ, {"TSF_WORKER_PROCESS": "0"}),
            self.assertRaisesRegex(ValueError, "restricted"),
        ):
            gpu_vision.load()
        with (
            patch.object(
                gpu_vision, "verify_frame", side_effect=RuntimeError("Quota exceeded")
            ),
            self.assertRaisesRegex(ValueError, "quota exhausted"),
        ):
            gpu_vision.inspect(b"fixture", "Requested subject and action")

    def test_free_gradio_requests_only_zero_cost_host_without_billing_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def network(token, path, method="GET", body=None, ndjson=False):
                calls.append((path, method, body))
                if path == "whoami-v2":
                    return {"name": "creator"}
                if path == "spaces/creator/worker" and len(calls) == 2:
                    raise HTTPError(
                        "https://huggingface.co/api/" + path, 404, "missing", {}, None
                    )
                if path == "spaces/creator/worker":
                    return {"host": "creator-worker.hf.space"}
                return {}

            with (
                patch("trend_sniper.remote.deploy.hf", side_effect=network),
                patch(
                    "trend_sniper.remote.deploy.subprocess.run",
                    return_value=type(
                        "Tracked", (), {"stdout": "src/trend_sniper/remote/client.py\0"}
                    )(),
                ),
            ):
                deploy(
                    {
                        "hf_token": "fixture",
                        "space_name": "worker",
                        "key": "x" * 64,
                        "hosting": "zero-gradio",
                    },
                    Path(tmp),
                    lambda _: None,
                )
            creation = next(body for path, _, body in calls if path == "repos/create")
            self.assertEqual(
                (creation["sdk"], creation["hardware"], creation["private"]),
                ("gradio", "zero-a10g", True),
            )
            commit = next(body for path, _, body in calls if "/commit/" in path)
            paths = [
                json.loads(row)["value"].get("path") for row in commit.splitlines()
            ]
            self.assertIn("app.py", paths)
            self.assertIn("requirements.txt", paths)
            self.assertNotIn("Dockerfile", paths)
            self.assertFalse(
                any("billing" in path or "credits" in path for path, _, _ in calls)
            )

    def test_gradio_runtime_cannot_install_on_desktop(self):
        from trend_sniper.remote.runtime import ensure_ollama

        with (
            patch.dict(os.environ, {"TSF_WORKER_PROCESS": "0"}),
            self.assertRaisesRegex(ValueError, "restricted"),
        ):
            ensure_ollama("/unused")

    def test_deployment_uploads_only_source_and_activates_private_cpu_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def network(token, path, method="GET", body=None, ndjson=False):
                calls.append((path, method, body))
                if path == "whoami-v2":
                    return {"name": "creator"}
                if method == "GET":
                    return {
                        "host": "creator-worker.hf.space",
                        "cardData": {"tags": ["trend-sniper-factory-worker"]},
                        "runtime": {"hardware": {"current": "cpu-basic"}},
                    }
                return {}

            with (
                patch("trend_sniper.remote.deploy.hf", side_effect=network),
                patch(
                    "trend_sniper.remote.deploy.subprocess.run",
                    return_value=type(
                        "Tracked", (), {"stdout": "src/trend_sniper/remote/client.py\0"}
                    )(),
                ),
            ):
                result = deploy(
                    {
                        "hf_token": "hf_private_fixture",
                        "space_name": "worker",
                        "key": "x" * 64,
                    },
                    Path(tmp),
                    lambda _: None,
                )
            self.assertEqual(result["delivery"], "configuration")
            config = client.configuration(Path(tmp))
            self.assertEqual(config["url"], "https://creator-worker.hf.space")
            commit = next(body for path, _, body in calls if "/commit/" in path)
            self.assertNotIn(b"hf_private_fixture", commit)
            paths = [
                json.loads(row)["value"].get("path") for row in commit.splitlines()
            ]
            self.assertIn("src/trend_sniper/remote/client.py", paths)
            self.assertNotIn("local-data", repr(paths))

    def test_desktop_restart_requeues_remote_work_instead_of_losing_the_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(root / "qa.db")
            queue = ProductionQueue(store, lambda *args: {})
            queue.pause(True)
            job = queue.enqueue("restart-fixture", {"title": "Remote fixture"})["id"]
            queue.close()
            with store.connection() as db:
                db.execute("UPDATE productions SET status='running' WHERE id=?", (job,))
            folder = root / "qa-factory" / job
            folder.mkdir(parents=True)
            write_json(folder / "remote.json", {"id": "a" * 32})
            recovered = ProductionQueue(store, lambda *args: {})
            try:
                with store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM productions WHERE id=?", (job,)
                        ).fetchone()[0],
                        "queued",
                    )
            finally:
                recovered.close()

    def test_transient_remote_failure_reconnects_without_resubmitting_or_caching_video(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / ("c" * 32)
            folder.mkdir()
            client.save_configuration(
                root, {"url": "https://fixture.hf.space", "key": "x" * 64}
            )
            write_json(
                folder / "remote.json",
                {
                    "id": "a" * 32,
                    "url": "https://fixture.hf.space",
                    "local_job": folder.name,
                },
            )
            calls = []

            def request(config, path, method="GET", body=None):
                calls.append((path, method))
                if len(calls) == 1:
                    raise HTTPError(
                        "https://fixture.hf.space/jobs/" + ("a" * 32),
                        503,
                        "starting",
                        {},
                        io.BytesIO(),
                    )
                if "/artifacts/" in path:
                    return {"title": "Remote fixture"}
                return {"status": "ready", "stage": "Finished"}

            with (
                patch("trend_sniper.remote.client.json_call", side_effect=request),
                patch("trend_sniper.remote.client.time.sleep"),
            ):
                result = client.execute(
                    {"topic": "Physics"}, folder, root, lambda _: None
                )
            self.assertEqual(result["remote"]["id"], "a" * 32)
            self.assertTrue(all(method == "GET" for _, method in calls))
            self.assertFalse((folder / "short.mp4").exists())

    def test_authentication_ranges_exact_artifact_check_and_remote_expiry(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"TSF_WORKER_KEY": "a" * 64}),
        ):
            root = Path(tmp)

            def executor(job, payload, stage):
                out = root / job / "output"
                out.mkdir(parents=True)
                for name in [
                    "short.mp4",
                    "metadata.json",
                    "script.json",
                    "captions.srt",
                ]:
                    (out / name).write_bytes(b"abcde")
                write_json(
                    out / "manifest.json",
                    {
                        "sha256": {
                            n: digest(out / n)
                            for n in [
                                "short.mp4",
                                "metadata.json",
                                "script.json",
                                "captions.srt",
                            ]
                        }
                    },
                )
                return {"title": "Protocol fixture"}

            app = create_worker(root, executor=executor)
            with TestClient(app) as http:
                self.assertEqual(http.get("/health").status_code, 401)
                headers = {"X-Factory-Key": "a" * 64}
                self.assertEqual(http.get("/health", headers=headers).status_code, 200)
                body = {
                    "request_id": "b" * 32,
                    "intent": {"topic": "Technical fixture"},
                }
                job = http.post("/jobs", json=body, headers=headers).json()["id"]
                for _ in range(100):
                    if (
                        http.get("/jobs/" + job, headers=headers).json()["status"]
                        == "ready"
                    ):
                        break
                    time.sleep(0.01)
                self.assertEqual(
                    http.post("/jobs", json=body, headers=headers).json()["id"], job
                )
                media = http.get(
                    f"/jobs/{job}/artifacts/short.mp4",
                    headers={**headers, "Range": "bytes=1-3"},
                )
                self.assertEqual(media.status_code, 206)
                self.assertEqual(media.content, b"bcd")
                self.assertEqual(
                    http.post(f"/jobs/{job}/verify", headers=headers).status_code, 200
                )
                (root / job / "output" / "short.mp4").write_bytes(b"changed")
                self.assertEqual(
                    http.get(
                        f"/jobs/{job}/artifacts/short.mp4", headers=headers
                    ).status_code,
                    409,
                )
                with app.state.queue.store.connection() as db:
                    db.execute(
                        "UPDATE production_runs SET finished_at='2000-01-01T00:00:00+00:00' WHERE job=?",
                        (job,),
                    )
                self.assertEqual(
                    http.get("/jobs/" + job, headers=headers).json()["status"],
                    "expired",
                )
                self.assertFalse((root / job).exists())

    def test_deployment_refuses_paid_eligibility_and_never_purchases_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = [
                {"name": "creator", "isPro": False},
                HTTPError(
                    "https://huggingface.co/api/spaces/creator/worker",
                    404,
                    "missing",
                    {},
                    None,
                ),
                HTTPError(
                    "https://huggingface.co/api/repos/create",
                    402,
                    "plan required",
                    {},
                    None,
                ),
            ]
            with (
                patch("trend_sniper.remote.deploy.hf", side_effect=response) as network,
                self.assertRaisesRegex(ValueError, "No plan was purchased"),
            ):
                deploy(
                    {"hf_token": "fixture", "space_name": "worker", "key": "x" * 64},
                    Path(tmp),
                    lambda _: None,
                )
            self.assertEqual(network.call_args.args[1:3], ("repos/create", "POST"))
            self.assertEqual(network.call_args.args[3]["hardware"], "cpu-basic")
            self.assertFalse((Path(tmp) / "remote-worker.json").exists())


class AutonomousEditorial(unittest.TestCase):
    def test_youtube_license_version_is_preserved_and_ambiguous_versions_rejected(self):
        for version in ["3.0", "4.0", None]:
            raw = (
                f"https://creativecommons.org/licenses/by/{version}/".encode()
                if version
                else b"Creative Commons Attribution license (reuse allowed)"
            )
            with patch(
                "trend_sniper.remote.footage.urlopen", return_value=io.BytesIO(raw)
            ):
                result = youtube_license({"id": "abcdefghijk"})
            self.assertEqual(
                result[0] if result else None, "CC-BY-" + version if version else None
            )

    def test_unlicensed_youtube_upload_is_never_downloaded(self):
        module = ModuleType("yt_dlp")
        utils = ModuleType("yt_dlp.utils")
        utils.download_range_func = MagicMock()
        downloader = MagicMock()
        downloader.__enter__.return_value = downloader
        downloader.extract_info.return_value = {
            "entries": [
                {
                    "title": "A relevant redstone circuit",
                    "license": "Standard YouTube License",
                    "duration": 60,
                    "uploader": "Fixture",
                }
            ]
        }
        module.YoutubeDL = MagicMock(return_value=downloader)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("sys.modules", {"yt_dlp": module, "yt_dlp.utils": utils}),
        ):
            self.assertEqual(
                list(youtube_cc("redstone circuit", Path(tmp), Budget())), []
            )
            downloader.download.assert_not_called()

    def test_query_rewrite_uses_failed_search_feedback(self):
        from trend_sniper.remote.producer import adaptive_queries

        with patch(
            "trend_sniper.remote.producer.editorial.queries",
            side_effect=[
                ["first query"],
                ["first query", "second query"],
                ["second query", "third query"],
            ],
        ) as writer:
            generated = adaptive_queries("fixture")
            self.assertEqual(next(generated), "first query")
            self.assertEqual(next(generated), "second query")
            self.assertEqual(writer.call_args.args[1], ["first query"])
            self.assertEqual(next(generated), "third query")

    def test_invented_source_quotes_are_rejected_and_rewritten(self):
        raw = copy.deepcopy(PHYSICS)
        for scene in raw["scenes"]:
            scene.update(
                source_index=0,
                supporting_quote="This quotation does not exist in the source.",
            )
        focus = editorial.Focus(
            question="Why do objects float in orbit?",
            research_query="orbital free fall",
        )
        plan = editorial.SourcedPlan.model_validate(raw)
        with (
            patch(
                "trend_sniper.remote.editorial.generate",
                side_effect=[focus, plan, plan],
            ) as writer,
            patch(
                "trend_sniper.remote.editorial.research",
                return_value=[
                    {
                        "url": "https://example.com/source",
                        "title": "Fixture",
                        "text": "A completely different statement is in this reference.",
                    }
                ],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "rejected the script"):
                editorial.draft({"name": "Physics"}, "", lambda _: None)
            self.assertEqual(writer.call_count, 3)

    def test_wrong_footage_causes_automatic_revision_then_compilation_without_manual_selection(
        self,
    ):
        raw = copy.deepcopy(PHYSICS)
        for scene in raw["scenes"]:
            scene.update(
                source_index=0,
                supporting_quote="Source-grounded technical fixture quotation.",
            )
        plan = editorial.SourcedPlan.model_validate(raw)
        source = [
            {
                "url": "https://example.com/reference",
                "title": "Fixture reference",
                "verification": "Fixture",
            }
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"TSF_WORKER_PROCESS": "1"}),
        ):
            root = Path(tmp)
            inputs = root / "inputs"
            folder = root / "output"

            def candidates(query, cache, budget, audit):
                cache.mkdir(parents=True, exist_ok=True)
                path = cache / "fixture"
                path.write_bytes(b"fixture")
                yield {
                    "path": str(path),
                    "source": "https://example.com/original",
                    "sha256": digest(path),
                }

            inspections = 0

            def inspect(asset, scene, seconds, count, selected, budget, stage):
                nonlocal inspections
                inspections += 1
                if inspections == 2:
                    return []
                selected.mkdir(parents=True, exist_ok=True)
                path = selected / str(inspections)
                path.write_bytes(b"selected fixture")
                sha = digest(path)
                return [
                    {
                        **asset,
                        "path": str(path),
                        "sha256": sha,
                        "id": "media-" + sha,
                        "end": seconds,
                        "origin_window": [0, seconds],
                        "license": "owned",
                        "credit": "Fixture",
                    }
                    for _ in range(count)
                ]

            with (
                patch(
                    "trend_sniper.remote.producer.editorial.draft",
                    return_value=(plan, source),
                ) as writer,
                patch(
                    "trend_sniper.remote.producer.editorial.queries",
                    return_value=["orbital station"],
                ),
                patch(
                    "trend_sniper.remote.producer.utterance",
                    return_value=(root / "speech.wav", 8, True),
                ),
                patch(
                    "trend_sniper.remote.producer.footage.candidates",
                    side_effect=candidates,
                ),
                patch(
                    "trend_sniper.remote.producer.footage.inspect_and_cut",
                    side_effect=inspect,
                ),
                patch(
                    "trend_sniper.remote.producer.assemble",
                    return_value={"title": "A complete preview"},
                ) as compiler,
            ):
                result = produce({"name": "Physics"}, folder, inputs, lambda _: None)
            self.assertEqual(result["title"], "A complete preview")
            self.assertEqual(writer.call_count, 2)
            self.assertEqual(inspections, 4)
            self.assertIn("lacks verified footage", writer.call_args.args[1])
            compiler.assert_called_once()
            self.assertFalse((inputs / "source-downloads").exists())
            self.assertTrue((inputs / "selected-clips").is_dir())

    def test_remote_producer_cannot_execute_as_a_desktop_fallback(self):
        with (
            patch.dict(os.environ, {"TSF_WORKER_PROCESS": "0"}),
            self.assertRaisesRegex(ValueError, "never on the desktop"),
        ):
            produce(
                {"name": "Physics"}, Path("/unused"), Path("/unused"), lambda _: None
            )
