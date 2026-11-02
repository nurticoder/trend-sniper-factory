"""Local review queue. No network and no automatic publication."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .core import digest, write_json


def snapshot(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    hashes = manifest["sha256"]
    if set(hashes) != {"short.mp4", "metadata.json", "script.json", "captions.srt"}:
        raise ValueError("Unexpected manifest file set")
    for name, expected in hashes.items():
        if digest(folder / name) != expected:
            raise ValueError(f"Changed artifact: {name}; render again before review")
    return {**hashes, "manifest.json": digest(folder / "manifest.json")}


def approve(folder: Path, audience: str, reviewer: str):
    if audience not in {"made_for_kids", "not_made_for_kids"} or not reviewer.strip():
        raise ValueError("Explicit audience and reviewer required")
    write_json(folder / "review.json", {
        "reviewer": reviewer, "audience": audience,
        "approved_at": datetime.now(timezone.utc).isoformat(), "hashes": snapshot(folder),
        "attestation": "Reviewed video, metadata, rights, factual claims and audience designation",
    })


def enqueue(folder: Path, at: str, queue_path: Path):
    scheduled = datetime.fromisoformat(at.replace("Z", "+00:00"))
    if scheduled.tzinfo is None or scheduled <= datetime.now(timezone.utc):
        raise ValueError("Schedule requires a future ISO timestamp with timezone")
    review = json.loads((folder / "review.json").read_text())
    if review["hashes"] != snapshot(folder):
        raise ValueError("Approval stale; review changed files again")
    rows = json.loads(queue_path.read_text()) if queue_path.exists() else []
    key = review["hashes"]["short.mp4"]
    if any(r["video_sha256"] == key for r in rows):
        raise ValueError("Video already queued")
    rows.append({"folder": str(folder.resolve()), "publish_at": scheduled.isoformat(),
                 "video_sha256": key, "status": "ready_for_manual_upload", "audience": review["audience"]})
    write_json(queue_path, rows)
    return rows[-1]
