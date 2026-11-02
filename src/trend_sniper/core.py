from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

MODES = {"choice", "rule", "splash", "safe", "reveal", "end"}


def load_topic(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-z0-9-]{1,80}", data.get("id", "")):
        raise ValueError("id must be a safe lowercase slug")
    for key in ("topic", "title", "description", "source_url", "trend_status"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Missing {key}")
    if len(data["title"]) > 100:
        raise ValueError("YouTube title exceeds 100 characters")
    if len(data["description"].encode("utf-8")) > 4500:
        raise ValueError("Description too long")
    tags = data.get("hashtags")
    if not isinstance(tags, list) or not 1 <= len(tags) <= 10 or any(
        not isinstance(t, str) or not re.fullmatch(r"[A-Za-z0-9_]+", t) for t in tags
    ):
        raise ValueError("Use 1–10 simple hashtags")
    if data.get("audience") not in {"needs_review", "made_for_kids", "not_made_for_kids"}:
        raise ValueError("Explicit audience field required")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 2 <= len(scenes) <= 12:
        raise ValueError("Use 2–12 scenes")
    for scene in scenes:
        duration = scene.get("seconds")
        if type(duration) not in (int, float) or not 1 <= duration <= 12:
            raise ValueError("Scene duration must be 1–12 seconds")
        if scene.get("mode") not in MODES:
            raise ValueError("Unknown scene mode")
        for key, limit in (("heading", 60), ("caption", 150)):
            if not isinstance(scene.get(key), str) or not 1 <= len(scene[key]) <= limit:
                raise ValueError(f"Invalid {key}")
    if sum(s["seconds"] for s in scenes) > 60:
        raise ValueError("MVP supports at most 60 seconds")
    return data


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
