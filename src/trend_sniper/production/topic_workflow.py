"""Topic drafts → bounded footage preparation → reviewed smooth explainer assembly."""

import json
import math
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool, model_validator

from ..core import digest, write_json
from . import commons
from .content import ContentPlan
from .explainer import Brief, Passage, Shot, assemble, key, utterance
from .materials import library, terms


def plan_data(raw):
    return ContentPlan.model_validate(
        {k: raw[k] for k in ContentPlan.model_fields if k in raw}
    )


def checked_path(record, inputs):
    path = Path(record["path"]).resolve()
    if (
        not path.is_relative_to(inputs.resolve())
        or not path.is_file()
        or digest(path) != record["sha256"]
    ):
        raise ValueError(
            "Selected asset missing or changed; search again or choose a replacement"
        )
    return path


def prepare(raw, folder, inputs, stage, voice="steady"):
    plan = plan_data(raw)
    assets, skipped = library(inputs / "media-library")
    scenes = []
    searches = {}
    for index, scene in enumerate(plan.scenes):
        stage(f"Preparing scene {index + 1}/{len(plan.scenes)}")
        query = scene.visual.search_query or scene.visual.subject
        candidates = []
        for asset in assets:
            if asset["kind"] == "video" and len(
                terms(query) & terms(asset["description"])
            ) >= min(2, len(terms(query)) or 2):
                candidates.append({**asset, "id": "media-" + asset["sha256"]})
        candidates = candidates[:2]
        issues = []
        if not candidates and os.environ.get("TSF_COMMONS", "1") == "1":
            stage(f"Searching licensed footage for scene {index + 1}: {query}")
            try:
                if query not in searches:
                    searches[query] = commons.search_footage(
                        query, inputs / "media-cache"
                    )
                candidates = searches[query]
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                issues.append("Footage search unavailable: " + type(exc).__name__)
        if not candidates:
            issues.append(
                "No suitable licensed footage found. Narrow the passage/query, or add cleared footage to the local library."
            )
        speech = None
        try:
            stage(f"Measuring Kokoro narration for scene {index + 1}")
            wav, seconds, reused = utterance(scene.narration, inputs, voice)
            speech = {
                "path": str(wav),
                "seconds": seconds,
                "sha256": digest(wav),
                "reused": reused,
            }
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            issues.append(
                "Narration missing: "
                + (
                    str(exc)[:180]
                    if isinstance(exc, ValueError)
                    else type(exc).__name__
                )
                + ". Shorten long passages or check Kokoro; no silent substitute."
            )
        if (
            speech
            and candidates
            and all(
                a["end"] - a["start"] < speech["seconds"] + 0.37 for a in candidates
            )
        ):
            issues.append(
                "A single candidate interval is shorter than the spoken passage. Select several suitable shot windows, find a longer clip or narrow the narration."
            )
        scenes.append(
            {
                "query": query,
                "candidates": candidates,
                "speech": speech,
                "attention": issues,
            }
        )
    packet = {
        "plan": plan.model_dump(),
        "voice": voice,
        "plan_hash": key(plan.model_dump()),
        "scenes": scenes,
        "skipped_library": skipped,
    }
    runtime = (
        sum(math.ceil((s["speech"]["seconds"] + 0.37) * 24) / 24 for s in scenes)
        if all(s["speech"] for s in scenes)
        else None
    )
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "prepared.json", packet)
    # Public review data omits filesystem paths. Only job-scoped media routes resolve bytes.
    public = {
        **plan.model_dump(),
        "plan_hash": packet["plan_hash"],
        "delivery": "plan",
        "format": "Topic explainer",
        "voice_profile": voice,
        "skipped_library": skipped,
        "runtime_seconds": runtime,
        "attention": [
            f"Measured edit is {runtime:.1f}s. Revise narration into the 20–75 second format."
        ]
        if runtime is not None and not 20 <= runtime <= 75
        else [],
        "verification": "Review factual support and footage correspondence. No video rendered or published.",
        "preparation": [
            {
                **s,
                "candidates": [
                    {k: v for k, v in a.items() if k != "path"} for a in s["candidates"]
                ],
                "speech": {k: v for k, v in s["speech"].items() if k != "path"}
                if s["speech"]
                else None,
            }
            for s in scenes
        ],
    }
    write_json(folder / "content-plan.json", public)
    write_json(folder / "script.json", plan.model_dump())
    return public


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    scene: int = Field(ge=0, le=4)
    url: HttpUrl
    supporting_excerpt: str = Field(min_length=15, max_length=1500)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    candidate: int = Field(ge=0, le=1)
    start: float = Field(ge=0, le=80)
    end: float = Field(gt=0, le=90)
    treatment: str = Field(default="contain", pattern="^(contain|focus)$")


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_hash: str = Field(pattern="^[a-f0-9]{64}$")
    facts_reviewed: StrictBool
    footage_reviewed: StrictBool
    evidence: list[Evidence] = Field(min_length=3, max_length=10)
    shots: list[list[Selection]] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def approved(self):
        if not self.facts_reviewed or not self.footage_reviewed:
            raise ValueError(
                "Review the claims and actual footage before preview production"
            )
        if any(not 1 <= len(scene) <= 4 for scene in self.shots):
            raise ValueError("Select one to four footage shots per passage")
        return self


def reviewed_packet(packet, review, inputs):
    review = Review.model_validate(review)
    if review.plan_hash != packet["plan_hash"]:
        raise ValueError("Plan changed; review its current narration and footage again")
    plan = plan_data(packet["plan"])
    if len(review.shots) != len(plan.scenes):
        raise ValueError("Every passage needs a footage decision")
    if any(e.scene >= len(plan.scenes) for e in review.evidence):
        raise ValueError("Evidence refers to an absent scene")
    assets, passages = {}, []
    for index, scene in enumerate(plan.scenes):
        prepared = packet["scenes"][index]
        if not prepared["speech"]:
            raise ValueError(
                f"Scene {index + 1}: narration missing; prepare again after checking Kokoro"
            )
        checked_path(prepared["speech"], inputs)
        refs = [
            i for i, evidence in enumerate(review.evidence) if evidence.scene == index
        ]
        if not refs:
            raise ValueError(
                f"Scene {index + 1}: provide a source and supporting passage"
            )
        shots = []
        for choice in review.shots[index]:
            if choice.candidate >= len(prepared["candidates"]):
                raise ValueError(
                    f"Scene {index + 1}: no such footage candidate; choose a replacement"
                )
            asset = prepared["candidates"][choice.candidate]
            checked_path(asset, inputs)
            if not asset["start"] <= choice.start < choice.end <= asset["end"]:
                raise ValueError(
                    f"Scene {index + 1}: trim lies outside the licensed candidate"
                )
            assets[asset["id"]] = asset
            shots.append(
                Shot(
                    asset=asset["id"],
                    start=choice.start,
                    end=choice.end,
                    treatment=choice.treatment,
                    subject=scene.visual.subject,
                    action=scene.visual.action,
                    purpose=scene.visual.purpose,
                )
            )
        frames = math.ceil((prepared["speech"]["seconds"] + 0.37) * 24)
        if any(
            s.end - s.start + 0.001 < math.ceil(frames / len(shots)) / 24 for s in shots
        ):
            raise ValueError(
                f"Scene {index + 1}: selected clips are too short for measured speech; shorten narration or select longer/more shots"
            )
        passages.append(
            Passage(
                id=f"scene-{index + 1}",
                narration=scene.narration,
                claim_sources=refs,
                shots=shots,
            )
        )
    duration = sum(
        math.ceil((s["speech"]["seconds"] + 0.37) * 24) / 24 for s in packet["scenes"]
    )
    if not 20 <= duration <= 75:
        raise ValueError(
            f"Measured edit is {duration:.1f}s. Revise narration into the 20–75 second format before producing."
        )
    brief = Brief(
        topic=plan.topic,
        title=plan.title,
        promise=plan.promise,
        angle=plan.promise,
        payoff=plan.payoff,
        source_count=len(review.evidence),
        voice=packet.get("voice", "steady"),
        passages=passages,
    )
    sources = [
        {
            "url": str(e.url),
            "supporting_excerpt": e.supporting_excerpt,
            "verification": "Creator-reviewed source support; not automated fact checking",
        }
        for e in review.evidence
    ]
    return {
        "brief": brief.model_dump(),
        "assets": assets,
        "sources": sources,
        "searches": [
            {"scene": i + 1, "query": s["query"], "candidates": len(s["candidates"])}
            for i, s in enumerate(packet["scenes"])
        ],
        "review": review.model_dump(mode="json"),
    }


def produce(payload, folder, inputs, stage):
    # Inputs were frozen from server-owned candidates at review. Recheck media bytes.
    for asset in payload["assets"].values():
        checked_path(asset, inputs)
    result = assemble(
        Brief.model_validate(payload["brief"]),
        payload["assets"],
        payload["sources"],
        payload["searches"],
        folder,
        inputs,
        stage,
    )

    return {**result, "source_plan": payload.get("source_job")}


def load_packet(folder):
    return json.loads((folder / "prepared.json").read_text())
