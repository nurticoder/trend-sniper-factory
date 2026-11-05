"""Thin routes for topic preparation, candidate playback and reviewed preview jobs."""

from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..production.content import ContentPlan
from ..production.explainer import key
from ..production.narration import FILES
from ..production.topic_workflow import (
    Review,
    checked_path,
    load_packet,
    reviewed_packet,
)


def install(app, store):
    root = store.path.parent / (store.path.stem + "-factory")

    def packet(job):
        with store.connection() as db:
            row = db.execute(
                "SELECT status FROM productions WHERE id=?", (job,)
            ).fetchone()
        if not row or row[0] != "planned":
            raise HTTPException(
                409, "Open a completed topic plan before preparing or reviewing footage"
            )
        try:
            return load_packet(root / job)
        except FileNotFoundError as exc:
            raise HTTPException(
                409,
                "This saved plan predates footage preparation. Use Find footage to prepare it.",
            ) from exc

    @app.post("/api/content-plans/{job}/prepare", status_code=202)
    def prepare(job: str, body: ContentPlan):
        with store.connection() as db:
            row = db.execute(
                "SELECT status FROM productions WHERE id=?", (job,)
            ).fetchone()
        if not row or row[0] != "planned":
            raise HTTPException(409, "Open a completed topic plan first")
        plan = body.model_dump()
        voice = app.state.production_preferences()["voice"]
        return app.state.enqueue(
            "topic-prepare/" + key([job, plan, FILES, voice]),
            {
                "title": plan["title"],
                "topic_prepare": plan,
                "production_options": {"voice": voice},
            },
        )

    @app.get("/api/content-plans/{job}/media/{scene}/{candidate}")
    def media(job: str, scene: int, candidate: int):
        data = packet(job)
        try:
            if scene < 0 or candidate < -1:
                raise IndexError()
            row = data["scenes"][scene]
            asset = row["speech"] if candidate == -1 else row["candidates"][candidate]
            path = checked_path(asset, store.path.parent)
        except (IndexError, KeyError, TypeError, ValueError, OSError) as exc:
            raise HTTPException(
                404, "Candidate unavailable or changed; prepare this scene again"
            ) from exc
        with path.open("rb") as source:
            header = source.read(12)
        kind = (
            "webm"
            if header.startswith(b"\x1aE\xdf\xa3")
            else "ogg"
            if header.startswith(b"OggS")
            else "mp4"
        )
        return FileResponse(
            path, media_type="audio/wav" if candidate == -1 else "video/" + kind
        )

    @app.post("/api/content-plans/{job}/produce", status_code=202)
    def produce(job: str, body: Review):
        try:
            payload = reviewed_packet(packet(job), body, store.path.parent)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc
        payload["source_job"] = job
        return app.state.enqueue(
            "topic-preview/" + key(payload),
            {"title": payload["brief"]["title"], "topic_render": payload},
        )
