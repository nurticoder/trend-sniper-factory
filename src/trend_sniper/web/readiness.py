"""Bounded local checks. A configured credential is not a verified connection."""

import json
import os
from pathlib import Path
from urllib.request import urlopen

import imageio_ffmpeg

from ..production.stories import MODEL


def inspect(folder):
    models, model_error = [], None
    try:
        with urlopen("http://127.0.0.1:11434/api/tags", timeout=1) as response:
            models = [
                row["name"] for row in json.loads(response.read(256_000))["models"]
            ]
    except (OSError, ValueError, KeyError, TypeError):
        model_error = "Local model service is unavailable."
    try:
        renderer = Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file()
    except RuntimeError:
        renderer = False
    auth = folder / "youtube"
    channel = None
    if (auth / "token-youtube.json").is_file():
        try:
            saved = json.loads((auth / "channel.json").read_text())
            if isinstance(saved.get("id"), str) and isinstance(saved.get("name"), str):
                channel = {"id": saved["id"], "name": saved["name"]}
        except (OSError, ValueError, AttributeError):
            pass
    catalog = folder / "media-library" / "catalog.json"
    count, catalog_error = 0, None
    try:
        rows = json.loads(catalog.read_text()) if catalog.exists() else []
        if not isinstance(rows, list):
            raise TypeError()
        count = len(rows)
    except (OSError, ValueError, TypeError):
        catalog_error = "The local catalog could not be read."
    return {
        "renderer": {
            "available": renderer,
            "detail": "Local FFmpeg encoder" if renderer else "Encoder missing",
        },
        "writer": {
            "available": MODEL in models,
            "detail": MODEL
            if MODEL in models
            else (model_error or "The story model is not installed."),
        },
        "vision": {
            "available": "moondream:latest" in models,
            "detail": "moondream:latest"
            if "moondream:latest" in models
            else "Online footage is skipped without the local vision model.",
        },
        "commons": {
            "enabled": os.environ.get("TSF_COMMONS", "1") == "1",
            "detail": "CC0 lookup runs per factual preview. Network availability is checked during production.",
        },
        "library": {
            "entries": count,
            "error": catalog_error,
            "detail": "Each file and permission record is validated before selection.",
        },
        "youtube": {
            "channel": channel,
            "detail": "Saved connection. Identity and access are checked again before upload."
            if channel
            else "No owner channel connected. Private previews work without YouTube.",
        },
        "analytics": {
            "available": False,
            "detail": "Live analytics ingestion is not connected.",
        },
        "narration": {
            "available": False,
            "detail": "Current previews use captions and timed music. Spoken narration is not connected.",
        },
    }


def install(app, store):
    @app.get("/api/factory-readiness")
    def readiness():
        return inspect(store.path.parent)
