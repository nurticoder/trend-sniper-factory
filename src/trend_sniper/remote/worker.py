"""Authenticated remote service, reusing the platform's durable single-worker queue."""

import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from ..core import digest
from ..production.jobs import ProductionQueue
from ..queue import snapshot
from ..web.store import Store
from .client import ARTIFACTS
from .producer import produce


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    intent: dict
    mode: str = Field(default="automatic", pattern="^(automatic|curated)$")
    voice: str = Field(default="steady", pattern="^(steady|brisk)$")


def models_ready():
    from .editorial import WRITER

    # These downloads happen only on the remote machine, at most once per container lifecycle.
    for model in [WRITER, "moondream:latest"]:
        subprocess.run(
            ["ollama", "pull", model], check=True, capture_output=True, timeout=900
        )


def create_worker(root=None, executor=None):
    root = Path(root or os.environ.get("TSF_WORKER_DATA", "/tmp/trend-sniper-worker"))
    key = os.environ.get("TSF_WORKER_KEY", "")
    if len(key) < 32:
        raise ValueError(
            "A private worker key is required; service will not start unauthenticated"
        )
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root / "worker.sqlite3")

    def authorize(x_factory_key: str = Header(default="")):
        if not secrets.compare_digest(x_factory_key, key):
            raise HTTPException(401, "Worker authentication required")

    def run(job, payload, stage):
        from ..production.kokoro import install as install_voice

        stage("Checking the selected Kokoro voice on the remote host")
        install_voice(Path(os.environ.get("TSF_VOICE_DATA", "/opt/factory-voice")))
        inputs = root / job / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        voices = inputs / "voices"
        if not voices.exists():
            voices.symlink_to(
                Path(os.environ.get("TSF_VOICE_DATA", "/opt/factory-voice")) / "voices",
                target_is_directory=True,
            )
        cache = inputs / "explainer-cache"
        cache.mkdir(exist_ok=True)
        for name in ["speech", "shots"]:
            shared = root / "shared-cache" / name
            shared.mkdir(parents=True, exist_ok=True)
            if not (cache / name).exists():
                (cache / name).symlink_to(shared.resolve(), target_is_directory=True)
        if payload["mode"] == "curated":
            from ..production.explainer import produce as curated

            return curated(payload["intent"], root / job / "output", inputs, stage)
        stage("Loading remote writing and visual-inspection models")
        models_ready()
        return produce(
            payload["intent"], root / job / "output", inputs, stage, payload["voice"]
        )

    queue = ProductionQueue(store, executor or run)
    queue.limit = 3

    def cleanup():
        with store.connection() as db:
            completed = db.execute(
                "SELECT p.id,r.finished_at FROM productions p JOIN production_runs r ON r.job=p.id WHERE p.status IN ('ready','failed','cancelled') AND r.finished_at IS NOT NULL ORDER BY r.finished_at DESC",
            ).fetchall()
            for index, (job, finished) in enumerate(completed):
                if index < 3 and datetime.fromisoformat(finished) >= datetime.now(
                    UTC
                ) - timedelta(hours=12):
                    continue
                shutil.rmtree(root / job, ignore_errors=True)
                db.execute(
                    "UPDATE productions SET status='expired',error='Remote preview expired; rebuild automatically from saved intent' WHERE id=?",
                    (job,),
                )
            active = db.execute(
                "SELECT count(*) FROM productions WHERE status='running'"
            ).fetchone()[0]
        if not active:
            cached = sorted(
                (
                    p
                    for p in (root / "shared-cache").rglob("*")
                    if p.suffix in {".mp4", ".wav"} and p.is_file()
                ),
                key=lambda p: p.stat().st_mtime,
            )
            total = sum(p.stat().st_size for p in cached)
            for path in cached:
                if (
                    total <= 1_000_000_000
                    and time.time() - path.stat().st_mtime < 12 * 3600
                ):
                    continue
                total -= path.stat().st_size
                path.unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)

    @asynccontextmanager
    async def lifespan(_):
        queue.wake()

        async def janitor():
            while True:
                await asyncio.sleep(300)
                await asyncio.to_thread(cleanup)

        task = asyncio.create_task(janitor())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.to_thread(queue.close)

    app = FastAPI(
        lifespan=lifespan,
        dependencies=[Depends(authorize)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.queue = queue

    @app.get("/health")
    def health():
        return {
            "service": "trend-sniper-worker",
            "execution": "remote",
            "pipeline_version": 1,
            "paid_services": False,
        }

    @app.post("/jobs", status_code=202)
    def create(body: Job):
        cleanup()
        if len(json.dumps(body.intent)) > 30_000:
            raise HTTPException(413, "Intent exceeds worker input budget")
        return queue.enqueue(body.request_id, body.model_dump())

    @app.get("/jobs/{job}")
    def status(job: str):
        cleanup()
        with store.connection() as db:
            row = db.execute(
                "SELECT p.status,p.error,s.stage,r.finished_at FROM productions p LEFT JOIN production_steps s ON s.id=p.id JOIN production_runs r ON r.job=p.id WHERE p.id=?",
                (job,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Worker restarted or job unavailable")
        if row[0] == "ready" and not (root / job / "output" / "short.mp4").is_file():
            with store.connection() as db:
                db.execute(
                    "UPDATE productions SET status='expired',error='Remote preview lost after a worker restart; rebuild from saved intent' WHERE id=?",
                    (job,),
                )
            return {
                "id": job,
                "status": "expired",
                "error": "Remote preview lost after a worker restart; rebuild from saved intent",
                "stage": "expired",
                "expires_at": None,
            }
        return {
            "id": job,
            "status": row[0],
            "error": row[1],
            "stage": row[2],
            "expires_at": (
                datetime.fromisoformat(row[3]) + timedelta(hours=12)
            ).isoformat()
            if row[3]
            else None,
        }

    @app.post("/jobs/{job}/cancel")
    def cancel(job: str):
        queue.cancel(job)
        return {"id": job}

    @app.post("/jobs/{job}/retry", status_code=202)
    def retry(job: str):
        return queue.retry(job)

    @app.post("/jobs/{job}/verify")
    def verify(job: str):
        if status(job)["status"] != "ready":
            raise HTTPException(410, "Remote preview unavailable")
        snapshot(root / job / "output")
        return {"manifest_hash": digest(root / job / "output" / "manifest.json")}

    @app.get("/jobs/{job}/artifacts/{asset}")
    def artifact(job: str, asset: str):
        if not re.fullmatch("[a-f0-9]{32}", job) or asset not in ARTIFACTS | {
            "automation.json"
        }:
            raise HTTPException(404)
        state = status(job)
        if state["status"] != "ready":
            raise HTTPException(
                410 if state["status"] == "expired" else 409,
                state["error"] or "Preview is not ready",
            )
        path = root / job / "output" / asset
        if not path.is_file():
            raise HTTPException(404)
        manifest = json.loads((root / job / "output" / "manifest.json").read_text())
        expected = manifest.get("sha256", {}).get(asset)
        if expected and digest(path) != expected:
            raise HTTPException(409, "Artifact changed; remote preview must be rebuilt")
        return FileResponse(path)

    return app


def main():
    if os.environ.get("TSF_WORKER_PROCESS") != "1":
        raise SystemExit("This entry point runs only in the remote worker container")
    if os.environ.get("TSF_FREE_GRADIO") == "1":
        from .runtime import ensure_ollama

        executable = ensure_ollama(os.environ["TSF_WORKER_DATA"])
        os.environ["PATH"] = (
            str(Path(executable).parent) + os.pathsep + os.environ["PATH"]
        )
    ollama = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL)
    import uvicorn

    try:
        for _ in range(30):
            if ollama.poll() is not None:
                raise RuntimeError("Remote model service stopped")
            from urllib.request import urlopen

            try:
                with urlopen("http://127.0.0.1:11434/api/tags", timeout=1):
                    break
            except OSError:
                time.sleep(1)
        app = create_worker()
        if os.environ.get("TSF_FREE_GRADIO") == "1":
            import gradio as gr

            with gr.Blocks() as info:
                gr.Markdown(
                    "# Trend Sniper Factory\nPrivate remote production worker. Use the local factory dashboard to submit jobs and review previews. No GPU allocation or paid inference calls are enabled."
                )
            # On HF, automatic SSR can start a Node server on 7860 before Uvicorn binds it.
            app = gr.mount_gradio_app(
                app,
                info,
                path="/",
                ssr_mode=False,
                blocked_paths=[str(Path(os.environ["TSF_WORKER_DATA"]).resolve())],
                run_history=False,
                mcp_server=False,
            )
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
    finally:
        ollama.terminate()


if __name__ == "__main__":
    main()
