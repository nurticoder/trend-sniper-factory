"""Choose exact visual fragments and audio cues from cleared local media."""

import json
import math
import re
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageOps

from ..core import digest
from .music import score

LICENSES = {"owned", "CC0-1.0", "CC-BY-4.0", "public-domain"}
KINDS = {"photo", "video", "music", "effect"}
STOP = {
    "this",
    "that",
    "these",
    "those",
    "what",
    "where",
    "which",
    "have",
    "with",
    "movie",
    "video",
    "episode",
    "short",
    "shorts",
    "latest",
    "from",
    "into",
    "when",
    "could",
    "about",
    "more",
    "your",
    "their",
    "watch",
    "report",
    "news",
    "views",
    "recent",
    "recorded",
    "rank",
    "channel",
    "first",
    "sample",
}


def terms(text):
    return {
        s
        for s in re.findall(r"[a-z0-9]+", text.lower())
        if len(s) >= 3 and s not in STOP
    }


def library(folder):
    index = folder / "catalog.json"
    if not index.exists():
        return [], []
    approved, skipped = [], []
    try:
        rows = json.loads(index.read_text())
        if not isinstance(rows, list):
            raise TypeError("Catalog must be an array")
    except (ValueError, TypeError, OSError) as error:
        return [], [{"file": "catalog.json", "reason": str(error)}]
    for row in rows:
        if not isinstance(row, dict):
            skipped.append({"file": "unknown", "reason": "Invalid catalog entry"})
            continue
        try:
            path = (folder / row["file"]).resolve()
            if not path.is_relative_to(folder.resolve()) or not path.is_file():
                raise ValueError("File outside library or missing")
            if row["kind"] not in KINDS or row["license"] not in LICENSES:
                raise ValueError("Unsupported license or media type")
            for field in ("evidence", "source", "credit", "description", "sha256"):
                if not isinstance(row[field], str) or not row[field].strip():
                    raise ValueError("Missing " + field)
            if digest(path) != row["sha256"]:
                raise ValueError("Asset hash changed")
            start, end = float(row.get("start", 0)), float(row.get("end", 0))
            if row["kind"] != "photo" and not (
                math.isfinite(start) and math.isfinite(end) and 0 <= start < end
            ):
                raise ValueError("Invalid fragment boundaries")
            approved.append({**row, "path": str(path), "start": start, "end": end})
        except (KeyError, OSError, ValueError, TypeError) as exc:
            skipped.append({"file": row.get("file", "unknown"), "reason": str(exc)})
    return approved, skipped


def best(assets, kinds, query, minimum_duration=0):
    matches = []
    for item in assets:
        if item["kind"] not in kinds:
            continue
        if (
            item["kind"] != "photo"
            and item["end"] - item["start"] + 0.001 < minimum_duration
        ):
            continue
        tags = terms(item["description"])
        overlap = sorted(terms(query) & tags)
        if len(overlap) < 2:
            continue
        matches.append(
            (len(overlap) / max(1, len(tags)) ** 0.5, item["file"], item, overlap)
        )
    if matches:
        _, _, asset, overlap = max(matches, key=lambda match: match[:2])
        return {**asset, "matched_terms": overlap}
    return None


def plan(topic, assets):
    scenes = []
    for scene in topic["scenes"]:
        query = " ".join([scene["value"], scene["caption"]])
        visual = best(assets, {"video", "photo"}, query, scene["seconds"])
        cue = "reveal impact" if scene["mode"] == "reveal" else "transition tick"
        effect = best(assets, {"effect"}, cue)
        scenes.append(
            {
                "query": query,
                "seconds": scene["seconds"],
                "visual": visual,
                "visual_fallback": None if visual else "Original illustrated scene",
                "cue": cue,
                "effect": effect,
            }
        )
    duration = sum(s["seconds"] for s in scenes)
    music = best(
        assets, {"music"}, topic["format"] + " rhythmic instrumental pulse", duration
    )
    return {
        "scenes": scenes,
        "music": music,
        "music_fallback": None if music else "Original synthesized pulse bed",
    }


def public_record(value):
    if isinstance(value, list):
        return [public_record(item) for item in value]
    if isinstance(value, dict):
        return {
            key: public_record(item) for key, item in value.items() if key != "path"
        }
    return value


def media_inputs(asset):
    # Fixed local files, no network protocols or user-provided filter expressions.
    return [
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        str(asset["start"]),
        "-i",
        asset["path"],
    ]


def visual_renderer(base, material_plan):
    cached_index, frames = None, []
    width, height, rate = 560, 315, 8

    def draw(topic, index, local, elapsed, duration):
        nonlocal cached_index, frames
        image = base(topic, index, local, elapsed, duration)
        shot = material_plan["scenes"][index]
        asset = shot["visual"]
        if not asset:
            return image
        if cached_index != index:
            if asset["kind"] == "photo":
                with Image.open(asset["path"]) as source:
                    frames = [ImageOps.fit(source.convert("RGB"), (width, height))]
            else:
                cmd = [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    "-v",
                    "error",
                    *media_inputs(asset),
                    "-an",
                    "-t",
                    str(shot["seconds"]),
                    "-vf",
                    f"fps={rate},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "pipe:1",
                ]
                raw = subprocess.run(
                    cmd, capture_output=True, check=True, timeout=60
                ).stdout
                stride = width * height * 3
                frames = [
                    Image.frombytes("RGB", (width, height), raw[i : i + stride])
                    for i in range(0, len(raw), stride)
                ]
                if len(frames) < max(1, int(shot["seconds"] * rate) - 1):
                    raise ValueError("Licensed clip ends before the requested fragment")
            cached_index = index
        image.paste(frames[min(int(local * rate), len(frames) - 1)], (80, 195))
        return image

    return draw


def soundtrack(material_plan):
    def compose(path, topic):
        score(path, topic)
        overlays = []
        duration = sum(s["seconds"] for s in topic["scenes"])
        if material_plan["music"]:
            overlays.append((material_plan["music"], 0, duration, 0.21))
        at = 0
        for scene in material_plan["scenes"]:
            effect = scene["effect"]
            if effect:
                overlays.append(
                    (
                        effect,
                        at,
                        min(scene["seconds"], 1.5, effect["end"] - effect["start"]),
                        0.35,
                    )
                )
            at += scene["seconds"]
        if not overlays:
            return
        cmd = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(path),
        ]
        filters = []
        for n, (asset, start, length, volume) in enumerate(overlays, 1):
            cmd.extend(media_inputs(asset))
            filters.append(
                f"[{n}:a]atrim=duration={length},asetpts=PTS-STARTPTS,volume={volume},adelay={round(start * 1000)}:all=1[a{n}]"
            )
        labels = "".join(f"[a{n}]" for n in range(1, len(overlays) + 1))
        filters.append(
            f"[0:a]{labels}amix=inputs={len(overlays) + 1}:duration=first:normalize=0,alimiter=limit=0.9[out]"
        )
        mixed = path.with_suffix(".mix.wav")
        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[out]",
                "-ar",
                "24000",
                "-ac",
                "1",
                str(mixed),
            ]
        )
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        mixed.replace(path)

    return compose
