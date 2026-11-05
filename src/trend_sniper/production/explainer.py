"""Versioned editorial briefs and a bounded, source-checked explainer pilot."""

import hashlib
import html
import json
import math
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import imageio_ffmpeg
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core import digest, write_json
from ..render import font, render, srt_time, wrapped
from . import narration
from .materials import soundtrack

POLICY = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
SOURCES = [
    "https://www.nasa.gov/science-research/astrophysics/what-is-the-fluidic-telescope/",
    "https://www.nasa.gov/centers-and-facilities/glenn/what-is-microgravity/",
]
ASSETS = ["Moving_Water_in_Space-8K", "Fluids_on_the_Space_Station"]
PROFILES = {
    "steady": {"label": "Kokoro af_heart · steady", "speed": "0.95"},
    "brisk": {"label": "Kokoro af_heart · brisk", "speed": "1.05"},
}


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fetch(url, cache, limit=2_000_000):
    """Only built-in NASA sources. Cache content plus retrieval evidence, verify reused bytes."""
    if not url.startswith(
        ("https://www.nasa.gov/", "https://images-assets.nasa.gov/video/")
    ):
        raise ValueError("Source host is not approved")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / key(url)
    receipt = target.with_suffix(".json")
    if target.exists() and receipt.exists():
        record = json.loads(receipt.read_text())
        if digest(target) == record["sha256"]:
            return target, record
    temporary = target.with_suffix(".download-" + uuid4().hex)
    try:
        with urlopen(url, timeout=30) as response, temporary.open("wb") as output:
            if not response.url.startswith(
                ("https://www.nasa.gov/", "https://images-assets.nasa.gov/")
            ):
                raise ValueError("Unexpected source redirect")
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValueError("Source exceeds download budget")
                output.write(chunk)
        temporary.replace(target)
        record = {
            "url": url,
            "sha256": digest(target),
            "bytes": size,
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
        write_json(receipt, record)
        return target, record
    finally:
        temporary.unlink(missing_ok=True)


class Shot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset: str
    start: float = Field(ge=0, le=80)
    end: float = Field(gt=0, le=90)
    focus_x: float = Field(default=0.5, ge=0.2, le=0.8)
    crop_height: float = Field(default=1, ge=0.5, le=1)
    subject: str = Field(min_length=3, max_length=300)
    action: str = Field(min_length=3, max_length=300)
    purpose: str = Field(min_length=3, max_length=500)
    treatment: str = Field(default="focus", pattern="^(contain|focus|orbit)$")

    @model_validator(mode="after")
    def bounds(self):
        if self.end <= self.start:
            raise ValueError("Shot interval must move forward")
        if self.asset not in ASSETS + ["original-orbit"] and not re.fullmatch(
            r"media-[a-f0-9]{64}", self.asset
        ):
            raise ValueError(
                "Asset identity is not a cleared collection ID or media hash"
            )
        if (self.asset == "original-orbit") != (self.treatment == "orbit"):
            raise ValueError("Diagram identity and treatment must agree")
        return self


class Passage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern="^[a-z0-9-]{1,40}$")
    narration: str = Field(min_length=10, max_length=450)
    claim_sources: list[int] = Field(min_length=1, max_length=2)
    shots: list[Shot] = Field(min_length=1, max_length=4)
    pause_after: float = Field(default=0.25, ge=0.1, le=0.8)


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    source_count: int = Field(default=2, ge=1, le=20)
    topic: str = Field(min_length=5, max_length=200)
    title: str = Field(min_length=5, max_length=100)
    promise: str = Field(min_length=10, max_length=500)
    angle: str = Field(min_length=10, max_length=500)
    payoff: str = Field(min_length=10, max_length=500)
    voice: str = Field(default="steady", pattern="^(steady|brisk)$")
    pronunciations: dict[str, str] = Field(default_factory=dict, max_length=15)
    passages: list[Passage] = Field(min_length=3, max_length=6)

    @model_validator(mode="after")
    def references(self):
        if len({p.id for p in self.passages}) != len(self.passages):
            raise ValueError("Passage IDs must be unique")
        if any(
            not 0 <= s < self.source_count
            for p in self.passages
            for s in p.claim_sources
        ):
            raise ValueError("Claim source is not in the research packet")
        footage = sum(
            s.asset != "original-orbit" for p in self.passages for s in p.shots
        )
        total = sum(len(p.shots) for p in self.passages)
        if footage < 3 or footage / total < 0.6:
            raise ValueError(
                "This format requires relevant real footage; choose a different treatment explicitly."
            )
        return self


def pilot(topic="Why does water form a ball in space?", voice="steady"):
    query = topic.lower()
    supported = (
        "microgravity" in query
        or "surface tension" in query
        or (
            "water" in query
            and any(word in query for word in ("space", "orbit", "ball"))
        )
    )
    if not supported:
        raise ValueError(
            "This first collection covers water in microgravity. Narrow to that topic, or supply a researched brief for editorial review. No generic video will be substituted."
        )

    def shot(asset, start, end, subject, action, purpose, treatment="focus"):
        return {
            "asset": asset,
            "start": start,
            "end": end,
            "subject": subject,
            "action": action,
            "purpose": purpose,
            "treatment": treatment,
        }

    a, b = ASSETS
    brief = Brief(
        topic=topic,
        voice=voice,
        title="Why water becomes a ball in space",
        promise="Understand why a large drop stays round, and why floating is a different effect.",
        angle="Separate two visible effects that are often confused: shape and apparent weightlessness.",
        payoff="Free fall explains floating. Surface tension explains the rounded shape.",
        passages=[
            Passage(
                id="hook",
                narration="This is liquid water, not a glass ball. In microgravity, a large drop can stay rounded instead of flattening under its own weight.",
                claim_sources=[0],
                shots=[
                    shot(
                        a,
                        66,
                        74,
                        "Large water globule held at a straw",
                        "The rounded water remains together",
                        "Establish the real phenomenon, not a simulated ball",
                    ),
                    shot(
                        b,
                        50,
                        58,
                        "Water globule in a different station demonstration",
                        "The globule deforms as it moves",
                        "Show that the object is liquid, not glass",
                    ),
                ],
            ),
            Passage(
                id="mechanism",
                narration="Water molecules attract each other. At the surface, that attraction acts like a tightening skin. That is surface tension.",
                claim_sources=[0],
                shots=[
                    shot(
                        a,
                        58,
                        66,
                        "The same water demonstration",
                        "A tool touches and draws water from the globule",
                        "Make cohesion visible; this is not an unrelated experiment",
                    )
                ],
            ),
            Passage(
                id="shape",
                narration="Surface tension favors a compact shape. For a free drop, that shape is nearly spherical. Here, the straw also touches the water, so the shape can distort.",
                claim_sources=[0],
                shots=[
                    shot(
                        a,
                        58,
                        66,
                        "Water still touching the straw",
                        "The globule stretches near the contact point",
                        "Distinguish the free-drop explanation from this attached demonstration",
                    ),
                    shot(
                        b,
                        54,
                        62,
                        "A second attached water globule",
                        "The water moves and changes shape",
                        "Reinforce the qualification with a second observed view",
                    ),
                ],
            ),
            Passage(
                id="payoff",
                narration="But gravity has not disappeared. The station and its contents are falling around Earth together. Floating comes from free fall. The rounded shape comes from surface tension.",
                claim_sources=[0, 1],
                shots=[
                    shot(
                        "original-orbit",
                        0,
                        8,
                        "Earth and an orbiting station",
                        "A station moves around Earth with an inward arrow",
                        "Explain shared free fall; diagram is schematic, not recorded footage",
                        "orbit",
                    ),
                    shot(
                        a,
                        66,
                        74,
                        "Water globule in the original demonstration",
                        "The liquid remains gathered at the straw",
                        "Return to the opening with the distinction resolved",
                    ),
                ],
            ),
        ],
    )

    brief.passages[0].shots[0].start = 5
    brief.passages[0].shots[0].end = 13
    brief.passages[0].shots[0].crop_height = 0.65
    brief.passages[0].shots[0].focus_x = 0.49
    brief.passages[1].shots[0].start = 29
    brief.passages[1].shots[0].end = 37
    brief.passages[1].shots[0].crop_height = 0.75
    brief.passages[1].shots[0].focus_x = 0.48
    brief.passages[2].shots[0].start = 2
    brief.passages[2].shots[0].end = 10
    brief.passages[2].shots[0].crop_height = 0.65
    brief.passages[2].shots[0].focus_x = 0.49
    brief.passages[3].shots[1].start = 70
    brief.passages[3].shots[1].end = 78
    brief.passages[3].shots[1].focus_x = 0.70
    brief.passages[2].shots[
        0
    ].action = "The rounded water remains in contact with the straw"
    return brief


def speech(text, output, inputs, profile):
    narration.synthesize(text, output, inputs, speed=float(PROFILES[profile]["speed"]))


def utterance(text, inputs, profile):
    if not narration.availability(inputs)["available"]:
        raise ValueError(
            "Narration missing: install the local voice or choose another available provider. This explainer requires speech."
        )
    cache = inputs / "explainer-cache" / "speech"
    cache.mkdir(parents=True, exist_ok=True)
    signature = key([text, profile, narration.FILES, "kokoro-speech-v1"])
    output = cache / (signature + ".wav")
    receipt = cache / (signature + ".json")
    if (
        output.exists()
        and receipt.exists()
        and digest(output) == json.loads(receipt.read_text())["sha256"]
    ):
        return output, len(narration.samples(output)) / narration.RATE, True
    raw = cache / (uuid4().hex + ".raw.wav")
    try:
        speech(text, raw, inputs, profile)
        seconds = narration.normalized(raw, output)
        write_json(receipt, {"sha256": digest(output), "text": text, "voice": profile})
        return output, seconds, False
    finally:
        raw.unlink(missing_ok=True)


def command(args, timeout=None):
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", *args],
        check=True,
        capture_output=True,
        timeout=timeout or (480 if os.environ.get('TSF_WORKER_PROCESS') == '1' else 90),
    )


def overlay(text, label, path):
    image = Image.new("RGBA", (720, 1280))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((30, 945, 690, 1190), 22, fill=(9, 16, 27, 225))
    wrapped(d, text, 972, 35, "white", 600)
    d.text(
        (40, 70),
        label,
        font=font(23),
        fill="white",
        stroke_width=2,
        stroke_fill="black",
    )
    image.save(path)


def diagram(path, seconds):
    # Reuse the actual engine for an explicitly labelled explanatory animation.
    topic = {
        "id": "orbit-explainer",
        "title": "Shared free fall",
        "description": "Original schematic",
        "hashtags": [],
        "audience": "needs_review",
        "source_url": SOURCES[1],
        "trend_status": "Schematic, not to scale",
        "scenes": [
            {
                "heading": "",
                "value": "",
                "caption": "",
                "seconds": seconds,
                "mode": "choice",
            }
        ],
    }

    def draw(t, i, local, elapsed, duration):
        image = Image.new("RGB", (720, 1280), (9, 20, 37))
        d = ImageDraw.Draw(image)
        d.text((40, 90), "SHARED FREE FALL", font=font(37), fill="white")
        d.ellipse((100, 360, 620, 880), outline=(83, 117, 146), width=4)
        d.ellipse((215, 475, 505, 765), fill=(28, 101, 151))
        d.text((360, 620), "EARTH", anchor="mm", font=font(30), fill="white")
        angle = elapsed * 0.55 - 1.4
        x = 360 + 260 * math.cos(angle)
        y = 620 + 260 * math.sin(angle)
        d.line(
            (x, y, x + (360 - x) * 0.28, y + (620 - y) * 0.28),
            fill=(255, 194, 124),
            width=7,
        )
        d.rectangle((x - 17, y - 12, x + 17, y + 12), fill="white")
        wrapped(d, "Station and contents fall together", 940, 34, "white")
        d.text(
            (40, 1180),
            "ORIGINAL DIAGRAM / NOT TO SCALE",
            font=font(20),
            fill=(154, 180, 201),
        )
        return image

    render(topic, path, fps=24, draw_frame=draw)
    return path / "short.mp4"


def prepare_shot(edit, assets, cache):
    """Cache one smooth shot independently of narration and other scenes."""
    signature = key(
        [
            {
                k: edit[k]
                for k in (
                    "asset",
                    "source_start",
                    "duration",
                    "treatment",
                    "focus_x",
                    "crop_height",
                )
            },
            assets.get(edit["asset"], {}).get("sha256"),
            "vertical-v2",
        ]
    )
    out = cache / (signature + ".mp4")
    receipt = out.with_suffix(".json")
    if not (
        out.exists()
        and receipt.exists()
        and digest(out) == json.loads(receipt.read_text())["sha256"]
    ):
        if edit["treatment"] == "orbit":
            generated = diagram(cache / ("diagram-" + signature), edit["duration"])
            out.write_bytes(generated.read_bytes())
        else:
            # Preserve the whole subject; blurred moving background fills the vertical canvas.
            filters = "[0:v]split=2[back][front];[back]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=24:2[bg];[front]scale=720:980:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=24,setsar=1[v]"
            if edit["treatment"] == "focus":
                filters = f"[0:v]crop=iw:trunc(ih*{edit['crop_height']}/2)*2:0:0,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:x='min(max(iw*{edit['focus_x']}-360,0),iw-720)',fps=24,setsar=1[v]"
            command(
                [
                    "-protocol_whitelist",
                    "file,pipe",
                    "-ss",
                    str(edit["source_start"]),
                    "-i",
                    assets[edit["asset"]]["path"],
                    "-t",
                    str(edit["duration"]),
                    "-filter_complex",
                    filters,
                    "-map",
                    "[v]",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(out),
                ]
            )
        write_json(receipt, {"sha256": digest(out), "edit": edit})
    return out


def technical_review(folder, planned_seconds):
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-i",
            str(folder / "short.mp4"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    log = result.stderr
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    if not match or "720x1280" not in log or not re.search(r"24(?:\.0+)? fps", log):
        raise ValueError(
            "Output dimensions, frame rate or duration could not be verified"
        )
    hours, minutes, seconds = map(float, match.groups())
    actual = hours * 3600 + minutes * 60 + seconds
    if abs(actual - planned_seconds) > 0.15:
        raise ValueError("Encoded duration disagrees with the narration timeline")
    if "Audio:" not in log:
        raise ValueError("Encoded preview has no audio stream")
    return {
        "decode": "passed",
        "dimensions": [720, 1280],
        "fps": 24,
        "duration_seconds": actual,
        "duration_error_seconds": round(actual - planned_seconds, 4),
        "narration": "present",
        "caption_timing": "Estimated phrase timing within measured utterances; not forced alignment",
    }


def produce(payload, folder, inputs, stage):
    brief = Brief.model_validate(payload["brief"])
    root = inputs / "explainer-cache"
    root.mkdir(exist_ok=True)
    work = root / ("runs-" + folder.name)
    work.mkdir(exist_ok=True)
    stage("Checking subject sources and permissions")
    sources = []
    for url, required in zip(SOURCES, ["surface tension", "free-fall"]):
        path, record = fetch(url, root / "research")
        text = html.unescape(re.sub("<[^>]+>", " ", path.read_text()))
        if required not in text.lower():
            raise ValueError(
                "Source changed: supporting passage needs editorial verification"
            )
        sources.append(
            {
                **record,
                "role": "Primary subject explanation",
                "supporting_excerpt": " ".join(text.split())[
                    max(
                        0, " ".join(text.split()).lower().find(required) - 70
                    ) : " ".join(text.split()).lower().find(required) + 300
                ],
                "verification": "Expected terminology found; semantic support needs editorial review",
            }
        )
    _, policy = fetch(POLICY, root / "research")
    assets = {}
    search = []
    for asset in sorted(
        {
            s.asset
            for p in brief.passages
            for s in p.shots
            if s.asset != "original-orbit"
        }
    ):
        stage("Acquiring relevant footage: " + asset)
        base = "https://images-assets.nasa.gov/video/" + asset + "/"
        metadata, _ = fetch(base + "metadata.json", root / "assets")
        data = json.loads(metadata.read_text())
        if data.get("AVAIL:SecondaryCreator") or data.get("AVAIL:Center") != "JSC":
            raise ValueError(
                "Footage rights require review: third-party credit or unknown center"
            )
        media, record = fetch(base + asset + "~medium.mp4", root / "assets", 85_000_000)
        assets[asset] = {
            **record,
            "path": str(media),
            "metadata_sha256": digest(metadata),
            "source": "https://images.nasa.gov/details/" + asset,
            "credit": "NASA / Johnson Space Center",
            "license": "NASA informational/editorial use under media guidelines",
            "permission": policy,
            "restrictions": [
                "No endorsement; source audio removed",
                "Identifiable people: not cleared for advertisements or promotional cover art",
            ],
            "commercial_release": "Requires rights review for intended use",
            "description": data["AVAIL:Description"],
        }
        search.append(
            {
                "query": asset,
                "result": "Curated subject-matched NASA demonstration",
                "status": "acquired",
            }
        )
    return assemble(brief, assets, sources, search, folder, inputs, stage, curated=True)


def assemble(brief, assets, sources, search, folder, inputs, stage, curated=False):
    """Shared smooth assembler. Asset IDs are resolved only from a frozen reviewed packet."""
    root = inputs / "explainer-cache"
    root.mkdir(exist_ok=True)
    work = root / ("runs-" + folder.name)
    work.mkdir(exist_ok=True)
    for passage in brief.passages:
        if any(i >= len(sources) for i in passage.claim_sources):
            raise ValueError("Passage claim has no supporting source record")
        for shot in passage.shots:
            if shot.asset == "original-orbit" and curated:
                continue
            asset = assets.get(shot.asset)
            if not asset or digest(Path(asset["path"])) != asset["sha256"]:
                raise ValueError(
                    "Selected footage missing or changed; review a replacement"
                )
    stage("Recording selected narration and measuring timing")
    clips = []
    edits = []
    clock = 0
    voice_pieces = []
    for passage in brief.passages:
        stage("Narration: " + passage.id)
        text = passage.narration
        for original, replacement in brief.pronunciations.items():
            text = text.replace(original, replacement)
        text = text.replace("[", "").replace("]", "")
        wav, seconds, reused = utterance(text, inputs, brief.voice)
        duration = math.ceil((0.12 + seconds + passage.pause_after) * 24) / 24
        voice_pieces.append((wav, clock + 0.12))
        clips.append(
            {
                "start": clock + 0.12,
                "duration": seconds,
                "text": text,
                "scene": passage.id,
                "reused": reused,
                "sha256": digest(wav),
            }
        )
        # A passage may carry several purpose-specific shots, independent of caption chunks.
        frames = round(duration * 24)
        for index, shot in enumerate(passage.shots):
            slot = (
                frames // len(passage.shots)
                + (1 if index < frames % len(passage.shots) else 0)
            ) / 24
            if shot.end - shot.start < slot:
                raise ValueError(
                    "Footage interval too short for "
                    + passage.id
                    + ". Offer a narrower passage or another clip; looping is disabled."
                )
            edits.append(
                {
                    **shot.model_dump(),
                    "source_start": shot.start,
                    "timeline_start": clock,
                    "passage": passage.id,
                    "duration": slot,
                }
            )
            clock += slot
    if not 20 <= clock <= 75:
        raise ValueError(
            "Edit falls outside the 20–75 second pilot budget; revise the script."
        )
    stage("Assembling smooth full-frame footage and explanatory graphic")
    segments = []
    cache = root / "shots"
    cache.mkdir(exist_ok=True)
    for i, edit in enumerate(edits):
        segments.append(prepare_shot(edit, assets, cache))
    # Explicit timeline offsets are separate from source intervals.
    manifest_list = work / "concat.txt"
    manifest_list.write_text(
        "\n".join("file '" + str(p.resolve()) + "'" for p in segments)
    )
    base = work / "picture.mp4"
    command(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest_list),
            "-c",
            "copy",
            str(base),
        ]
    )
    voice = narration.array("h", [0]) * round(clock * narration.RATE)
    for wav, at in voice_pieces:
        data = narration.samples(wav)
        offset = round(at * narration.RATE)
        voice[offset : offset + len(data)] = data
    voice_path = work / "narration.wav"
    narration.save_wav(voice_path, voice)
    topic = {
        "format": "Explainer",
        "scenes": [
            {
                "seconds": sum(e["duration"] for e in edits if e["passage"] == p.id),
                "mode": "reveal" if i == len(brief.passages) - 1 else "choice",
            }
            for i, p in enumerate(brief.passages)
        ],
    }
    bed = work / "soundtrack.wav"
    soundtrack(
        {
            "scenes": [
                {"seconds": s["seconds"], "effect": None} for s in topic["scenes"]
            ],
            "music": None,
        }
    )(bed, topic)
    narration.mix(bed, voice_path, {"clips": clips})
    folder.mkdir(parents=True, exist_ok=True)
    captions = []
    caption_times = []
    for clip in clips:
        chunks = []
        for phrase in re.findall(r"[^,.!?]+[,.!?]?", clip["text"]):
            words = phrase.strip().split()
            chunks.extend(" ".join(words[i : i + 7]) for i in range(0, len(words), 7))
        weight = sum(len(line.split()) for line in chunks)
        at = clip["start"]
        for line in chunks:
            end = at + clip["duration"] * len(line.split()) / weight
            captions.append(
                f"{len(captions) + 1}\n{srt_time(at)} --> {srt_time(end)}\n{line}\n"
            )
            caption_times.append((at, end, line))
            at = end
    (folder / "captions.srt").write_text("\n".join(captions))
    # Native subtitle rendering avoids generating a full RGBA image for every frame.
    from .captions import subtitle_filter, write_ass

    subtitle_path = work / "captions.ass"
    write_ass(caption_times, subtitle_path)
    for asset in assets.values():
        if digest(Path(asset["path"])) != asset["sha256"]:
            raise ValueError(
                "Selected media changed; rights and selection must be reviewed again"
            )
    stage("Encoding and checking final preview")
    command(
        [
            "-i",
            str(base),
            "-i",
            str(bed),
            "-filter_complex",
            "[0:v]" + subtitle_filter(subtitle_path) + "[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-t",
            str(clock),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(folder / "short.mp4"),
        ]
    )
    command(["-xerror", "-i", str(folder / "short.mp4"), "-f", "null", "-"])
    credits = "\n".join(
        a["source"]
        + " — "
        + a["credit"]
        + " — "
        + a["license"]
        + (
            " — "
            + (a.get("license_url") or "https://creativecommons.org/licenses/by/4.0/")
            if a["license"].startswith("CC-BY-")
            else ""
        )
        for a in assets.values()
    )
    metadata = {
        "title": brief.title,
        "description": brief.promise
        + "\n\nSources:\n"
        + "\n".join(record["url"] for record in sources)
        + "\n\n"
        + credits
        + "\nOriginal synthetic narration (Kokoro af_heart). Footage trimmed and reframed; no endorsement implied.",
        "hashtags": ["Shorts"],
        "audience": "needs_review",
    }
    write_json(folder / "metadata.json", metadata)
    (folder / "metadata.txt").write_text(
        metadata["title"] + "\n\n" + metadata["description"]
    )
    script = {
        "title": brief.title,
        "format": "Narrated explainer",
        "scenes": [p.model_dump() for p in brief.passages],
    }
    write_json(folder / "script.json", script)
    write_json(folder / "brief.json", brief.model_dump())
    (folder / "narration.wav").write_bytes(voice_path.read_bytes())
    # Original, topic-specific typography avoids implying an unshown event or likeness.
    cover = Image.new("RGB", (720, 1280), (8, 23, 41))
    d = ImageDraw.Draw(cover)
    wrapped(d, brief.title.upper(), 400, 60, "white", 610)
    d.text((45, 90), "EXPLAINED", font=font(26), fill=(255, 208, 135))
    cover.save(folder / "cover.jpg", quality=93)
    review = {
        "state": "awaiting_editorial_review",
        "technical": technical_review(folder, clock),
        "brief": brief.model_dump(),
        "sources": sources,
        "assets": [
            {k: v for k, v in a.items() if k != "path"} for a in assets.values()
        ],
        "searches": search,
        "shots": edits,
        "speech": clips,
        "voice": {
            "model": narration.VOICE,
            "profile": brief.voice,
            "model_sha256": narration.FILES["kokoro-v1.0.int8.onnx"],
            "voices_sha256": narration.FILES["voices-v1.0.bin"],
            "model_license": "Apache-2.0",
            "runner_license": "MIT",
        },
        "attention": [
            {
                "scene": "all",
                "reason": "Human review required for factual support, naturalness and visual correspondence. Automated completion is not editorial approval.",
            },
            {
                "scene": "rights",
                "reason": "Review per-asset license, attribution, recognizable people and intended use before release.",
            },
        ],
        "cost": {"paid_api_usd": 0},
        "editorial_method": "Reviewed subject and shot plan; acquisition, local Kokoro speech, timing and assembly automated",
    }
    write_json(folder / "review.json", review)
    write_json(
        folder / "manifest.json",
        {
            "schema_version": 1,
            "assets": review["assets"],
            "voice": review["voice"],
            "sha256": {
                name: digest(folder / name)
                for name in [
                    "short.mp4",
                    "metadata.json",
                    "script.json",
                    "captions.srt",
                ]
            },
        },
    )
    return script
