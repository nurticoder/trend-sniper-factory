"""Local account connection and streaming: media bytes never become desktop files."""

import json
import secrets
from typing import Literal
from urllib.error import HTTPError

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..remote import client


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr
    hosting: Literal["cpu-basic", "zero-gradio"] = "zero-gradio"
    space_name: str = Field(
        default="trend-sniper-worker", pattern="^[a-z0-9][a-z0-9-]{3,60}$"
    )


def streamed(inputs, folder, asset, range_header=None):
    try:
        response = client.artifact_response(inputs, folder, asset, range_header)
    except HTTPError as exc:
        exc.close()
        raise HTTPException(
            410 if exc.code in {404, 410} else 503,
            "Remote preview unavailable or expired; rebuild automatically from its saved subject",
        ) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            503, "Remote worker unavailable; no media was downloaded to this computer"
        ) from exc

    def chunks():
        try:
            while part := response.read(64 * 1024):
                yield part
        finally:
            response.close()

    headers = {
        k: response.headers[k]
        for k in ["Content-Length", "Content-Range", "Accept-Ranges", "ETag"]
        if response.headers.get(k)
    }
    headers["Cache-Control"] = "no-store"
    return StreamingResponse(
        chunks(),
        status_code=response.status,
        media_type=response.headers.get("Content-Type", "application/octet-stream"),
        headers=headers,
    )


def install(app, store):
    inputs = store.path.parent

    @app.get("/api/remote-worker")
    def status():
        try:
            config = client.configuration(inputs)
        except (OSError, ValueError):
            return {
                "connected": False,
                "detail": "Remote worker not connected. Production media will stay off this computer.",
            }
        try:
            health = client.json_call(config, "/health")
            if health.get("service") != "trend-sniper-worker":
                raise ValueError("Unexpected service")
            return {
                "connected": True,
                "configured": True,
                "space_id": config.get("space_id"),
                "detail": "Private remote worker ready. Source footage, cuts and rendering stay in the cloud.",
            }
        except (OSError, ValueError):
            return {
                "connected": False,
                "configured": True,
                "space_id": config.get("space_id"),
                "detail": "Worker is starting, asleep or unavailable. Check deployment status; no local download fallback.",
            }

    @app.post("/api/remote-worker/connect", status_code=202)
    def connect(body: Connection):
        token = body.token.get_secret_value().strip()
        if not token.startswith("hf_") or not 10 < len(token) < 256:
            raise HTTPException(
                422,
                "Use a Hugging Face write token in this local password field; never paste it in chat",
            )
        config = {
            "hf_token": token,
            "space_name": body.space_name,
            "key": secrets.token_hex(32),
            "url": "",
            "hosting": body.hosting,
        }
        path = client.config_path(inputs)
        if path.is_file():
            previous = json.loads(path.read_text())
            config.update(key=previous.get("key") or config["key"])
        setup_id = secrets.token_hex(16)
        client.save_configuration(inputs, config, pending=setup_id)
        return app.state.enqueue(
            "remote-setup/" + secrets.token_hex(16),
            {"title": "Connect remote factory", "remote_setup": setup_id},
        )

    @app.post("/api/content-plans/{job}/automatic", status_code=202)
    def finish(job: str):
        with store.connection() as db:
            row = db.execute(
                "SELECT r.input,p.script FROM production_runs r JOIN productions p ON p.id=r.job WHERE p.id=?",
                (job,),
            ).fetchone()
        if not row:
            raise HTTPException(404)
        original, result = json.loads(row[0]), json.loads(row[1])
        card = original.get("recipe_card")
        intent = original.get("remote_intent") or (
            {"name": card["name"], "category": card["category"]}
            if card
            else {
                "topic": result.get("topic")
                or result.get("title")
                or original.get("title")
            }
        )
        # An unsupported draft is feedback, never factual evidence. The remote writer researches it again.
        return app.state.enqueue(
            "remote-finish/" + job,
            {"title": intent.get("name") or intent["topic"], "remote_intent": intent},
        )
