"""Normal app intake, auditions, reusable briefs, and exact-preview review."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from ..core import digest, write_json
from ..production.explainer import PROFILES, Brief, key, pilot, utterance
from ..production.narration import FILES
from ..queue import snapshot


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=5, max_length=200)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: str = Field(pattern="^(steady|brisk)$")


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    brief: Brief


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_hash: str
    watched: bool


def install(app, store):
    root = store.path.parent / (store.path.stem + "-factory")
    auditions = store.path.parent / "explainer-cache" / "auditions"
    auditions.mkdir(parents=True, exist_ok=True)
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audition")
    app.state.audition_executor = worker
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS explainer_briefs(id TEXT PRIMARY KEY,revision INTEGER,payload TEXT)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS explainer_voice(slot INTEGER PRIMARY KEY,voice TEXT)"
        )
        db.execute("INSERT OR IGNORE INTO explainer_voice VALUES (1,'steady')")
        db.execute(
            "CREATE TABLE IF NOT EXISTS voice_auditions(id TEXT PRIMARY KEY,status TEXT,error TEXT)"
        )
        db.execute(
            "UPDATE voice_auditions SET status='failed',error='Interrupted; request auditions again.' WHERE status IN ('running','queued')"
        )

    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS audition_engine(slot INTEGER PRIMARY KEY, signature TEXT)"
        )
        signature = key(FILES)
        previous = db.execute(
            "SELECT signature FROM audition_engine WHERE slot=1"
        ).fetchone()
        if not previous or previous[0] != signature:
            db.execute(
                "UPDATE voice_auditions SET status='failed',error='Voice changed to Kokoro; generate new delivery auditions.'"
            )
            db.execute(
                "INSERT OR REPLACE INTO audition_engine VALUES (1,?)", (signature,)
            )
        db.execute(
            "CREATE TABLE IF NOT EXISTS explainer_runs(project TEXT,revision INTEGER,voice TEXT,job TEXT,PRIMARY KEY(project,revision,voice))"
        )

    def selected():
        with store.connection() as db:
            return db.execute(
                "SELECT voice FROM explainer_voice WHERE slot=1"
            ).fetchone()[0]

    @app.get("/api/explainer-studio")
    def studio():
        with store.connection() as db:
            projects = [
                {"id": r[0], "revision": r[1], "brief": json.loads(r[2])}
                for r in db.execute(
                    "SELECT * FROM explainer_briefs ORDER BY rowid DESC"
                )
            ]
            voices = [
                {"id": r[0], "state": r[1], "error": r[2]}
                for r in db.execute("SELECT * FROM voice_auditions")
            ]
        with store.connection() as db:
            runs = [
                {"project": r[0], "revision": r[1], "voice": r[2], "job": r[3]}
                for r in db.execute("SELECT * FROM explainer_runs")
            ]
        return {
            "runs": runs,
            "projects": projects,
            "selected_voice": selected(),
            "profiles": PROFILES,
            "auditions": voices,
            "scope": "Kokoro af_heart is selected. Create curated water-in-microgravity briefs here; use Discover for other topic plans, footage searches and scene review. Auditions compare steady and brisk delivery.",
        }

    @app.put("/api/explainer-voice")
    def choose(body: Selection):
        with store.connection() as db:
            db.execute("UPDATE explainer_voice SET voice=? WHERE slot=1", (body.voice,))
        return {"voice": body.voice}

    def audition(profile):
        try:
            with store.connection() as db:
                db.execute(
                    "UPDATE voice_auditions SET status='running' WHERE id=?", (profile,)
                )
            path, _, _ = utterance(
                "This is liquid water, not a glass ball. Floating and shape have different explanations.",
                store.path.parent,
                profile,
            )
            (auditions / (profile + ".wav")).write_bytes(path.read_bytes())
            with store.connection() as db:
                db.execute(
                    "UPDATE voice_auditions SET status='ready',error='' WHERE id=?",
                    (profile,),
                )
        except Exception as exc:  # noqa: BLE001 -- persist safe worker diagnostics
            with store.connection() as db:
                db.execute(
                    "UPDATE voice_auditions SET status='failed',error=? WHERE id=?",
                    (
                        type(exc).__name__
                        + ": local voice unavailable; check Factory services.",
                        profile,
                    ),
                )

    @app.post("/api/explainer-auditions", status_code=202)
    def generate_auditions():
        for profile in PROFILES:
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT status FROM voice_auditions WHERE id=?", (profile,)
                ).fetchone()
                if row and row[0] in {"queued", "running", "ready"}:
                    continue
                db.execute(
                    "INSERT OR REPLACE INTO voice_auditions VALUES (?,'queued','')",
                    (profile,),
                )
            worker.submit(audition, profile)
        return {"state": "queued"}

    @app.get("/api/explainer-auditions/{profile}")
    def audio(profile: str):
        if profile not in PROFILES:
            raise HTTPException(404)
        with store.connection() as db:
            row = db.execute(
                "SELECT status FROM voice_auditions WHERE id=?", (profile,)
            ).fetchone()
        if not row or row[0] != "ready":
            raise HTTPException(409, "Audition is not ready")
        return FileResponse(auditions / (profile + ".wav"), media_type="audio/wav")

    @app.post("/api/explainer-briefs", status_code=201)
    def create(body: Intake):
        try:
            brief = pilot(body.topic, selected())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        ident = uuid4().hex
        with store.connection() as db:
            db.execute(
                "INSERT INTO explainer_briefs VALUES (?,1,?)",
                (ident, brief.model_dump_json()),
            )
        return {"id": ident, "revision": 1, "brief": brief.model_dump()}

    @app.put("/api/explainer-briefs/{ident}")
    def revise(ident: str, body: Revision):
        with store.connection() as db:
            row = db.execute(
                "UPDATE explainer_briefs SET payload=?,revision=revision+1 WHERE id=? AND revision=?",
                (body.brief.model_dump_json(), ident, body.expected_revision),
            )
            if row.rowcount != 1:
                raise HTTPException(409, "Brief changed; reload before saving")
        return {"revision": body.expected_revision + 1}

    @app.post("/api/explainer-briefs/{ident}/produce", status_code=202)
    def produce(ident: str):
        with store.connection() as db:
            row = db.execute(
                "SELECT payload,revision FROM explainer_briefs WHERE id=?", (ident,)
            ).fetchone()
        if not row:
            raise HTTPException(404)
        brief = Brief.model_validate_json(row[0]).model_copy(
            update={"voice": selected()}
        )
        payload = {
            "title": brief.title,
            "explainer": {
                "brief": brief.model_dump(),
                "project": ident,
                "revision": row[1],
            },
        }
        result = app.state.enqueue(
            "explainer/" + key([payload["explainer"], FILES]), payload
        )
        with store.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO explainer_runs VALUES (?,?,?,?)",
                (ident, row[1], brief.voice, result["id"]),
            )
        return result

    @app.get("/api/explainer-review/{job}")
    def review(job: str):
        with store.connection() as db:
            row = db.execute(
                "SELECT script,status,error FROM productions WHERE id=?", (job,)
            ).fetchone()
        if not row:
            raise HTTPException(404)
        path = root / job
        report = (
            json.loads((path / "review.json").read_text())
            if row[1] == "ready" and (path / "review.json").exists()
            else None
        )
        if report:
            for shot in report["shots"]:
                if (
                    shot["passage"] == "mechanism"
                    and shot["asset"] == "Moving_Water_in_Space-8K"
                    and 28 <= shot["source_start"] <= 37
                ):
                    report["attention"].append(
                        {
                            "scene": "mechanism",
                            "reason": "Curator finding: a hand partly occludes the water during the tool-contact view. Inspect it, shorten the passage, or replace it with Fluids on the Space Station at 50–58 seconds.",
                        }
                    )
        return {
            "state": row[1],
            "error": row[2],
            "report": report,
            "manifest_hash": digest(path / "manifest.json") if report else None,
            "approved": (path / "editorial-approval.json").exists()
            if report
            else False,
        }

    @app.post("/api/explainer-review/{job}")
    def approve(job: str, body: Approval):
        state = review(job)
        if (
            state["state"] != "ready"
            or not body.watched
            or body.manifest_hash != state["manifest_hash"]
        ):
            raise HTTPException(
                409, "Watch the exact completed preview and review its current manifest"
            )
        snapshot(root / job)
        write_json(
            root / job / "editorial-approval.json",
            {
                "manifest_hash": body.manifest_hash,
                "approval": "Private editorial review only; publishing remains separate",
            },
        )
        return {"state": "reviewed_private_preview"}
