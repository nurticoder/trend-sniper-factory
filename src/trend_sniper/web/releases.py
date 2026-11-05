import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictBool

from ..production.publisher import release_worker, request_body
from ..queue import snapshot


class ReviewedRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_hash: str
    channel_id: str
    publish_at: AwareDatetime
    audience: Literal["made_for_kids", "not_made_for_kids"]
    synthetic: StrictBool
    reviewed: Literal[True]


def install(app, store, root, executor):
    auth = store.path.parent / "youtube"
    with store.connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS releases (
            job TEXT PRIMARY KEY, sha TEXT UNIQUE, channel TEXT, day TEXT,
            approval TEXT, state TEXT, remote_id TEXT, error TEXT, UNIQUE(channel,day))""")
        db.execute(
            "UPDATE releases SET state='check_youtube_studio' WHERE state='submitting'"
        )
        db.execute(
            "UPDATE releases SET state='preflight_failed',day=NULL,sha=NULL WHERE state IN ('awaiting_upload','preparing')"
        )

    def ready(key):
        with store.connection() as db:
            row = db.execute(
                "SELECT id FROM productions WHERE id=? AND status='ready'", (key,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Finished preview required")
        return root / row[0]

    def channel():
        if (auth / "channel.json").is_file() and (
            auth / "token-youtube.json"
        ).is_file():
            return json.loads((auth / "channel.json").read_text())
        return None

    @app.get("/api/releases/{key}")
    def release_info(key: str):
        folder = ready(key)
        try:
            hashes = snapshot(folder)
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(
                409,
                "Preview artifacts are missing or changed. Regenerate before review.",
            ) from exc
        with store.connection() as db:
            row = db.execute(
                "SELECT state,remote_id,error FROM releases WHERE job=?", (key,)
            ).fetchone()
        return {
            "channel": channel(),
            "manifest_hash": hashes["manifest.json"],
            "state": row[0] if row else "awaiting_review",
            "video_id": row[1] if row else None,
            "error": row[2] if row else None,
        }

    @app.post("/api/releases/{key}", status_code=202)
    def schedule(key: str, review: ReviewedRelease):
        folder = ready(key)
        if (folder / "review.json").exists():
            raise HTTPException(409, "This bounded explainer pilot is private review only. Publishing is disabled.")
        destination = channel()
        if not destination or destination["id"] != review.channel_id:
            raise HTTPException(409, "Connect and verify the destination channel first")
        if review.publish_at < datetime.now(UTC) + timedelta(minutes=15):
            raise HTTPException(
                422, "Allow at least 15 minutes before the scheduled time"
            )
        try:
            hashes = snapshot(folder)
            request_body(
                folder,
                review.publish_at,
                review.audience == "made_for_kids",
                review.synthetic,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if review.manifest_hash != hashes["manifest.json"]:
            raise HTTPException(409, "The preview changed. Review this version again.")
        approved = {
            "hashes": hashes,
            "channel": destination["id"],
            "at": review.publish_at.isoformat(),
            "kids": review.audience == "made_for_kids",
            "synthetic": review.synthetic,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        day = (
            review.publish_at.astimezone(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
        )
        try:
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "DELETE FROM releases WHERE job=? AND state='preflight_failed'",
                    (key,),
                )
                db.execute(
                    "INSERT INTO releases VALUES (?,?,?,?,?,?,?,?)",
                    (
                        key,
                        hashes["short.mp4"],
                        destination["id"],
                        day,
                        json.dumps(approved),
                        "awaiting_upload",
                        None,
                        None,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                409, "This video or channel release day is already reserved"
            ) from exc
        executor.submit(release_worker, store, folder, key, auth, approved)
        return {"state": "awaiting_upload"}
