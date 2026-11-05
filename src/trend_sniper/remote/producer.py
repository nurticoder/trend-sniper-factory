"""An autonomous remote production attempt, with bounded research/retrieval revisions."""

import math
import os
import shutil
from pathlib import Path

from ..core import write_json
from ..production.explainer import Brief, Passage, Shot, assemble, key, utterance
from . import editorial, footage


def adaptive_queries(scene):
    failed = []
    for _ in range(3):
        query = next(
            (q for q in editorial.queries(scene, failed) if q not in failed), None
        )
        if not query:
            break
        yield query
        failed.append(query)


def produce(intent, folder, inputs, progress, voice="steady"):
    if os.environ.get("TSF_WORKER_PROCESS") != "1":
        raise ValueError(
            "Autonomous media production runs only on the remote worker, never on the desktop"
        )
    budget = footage.Budget()
    deadline_token = editorial.DEADLINE.set(budget.deadline)
    audit = []
    attempts = []
    reusable_scenes = {}
    feedback = ""
    inputs.mkdir(parents=True, exist_ok=True)
    folder.mkdir(parents=True, exist_ok=True)

    def stage(text):
        budget.check()
        progress(text)

    try:
        for round_number in range(3):
            stage(
                f"Production attempt {round_number + 1}/3: researching a producible explanation"
            )
            try:
                plan, sources = editorial.draft(intent, feedback, stage)
                write_json(inputs / "researched-plan.json", plan.model_dump())
                write_json(inputs / "research.json", sources)
                passages, assets = [], {}
                total_seconds = 0
                for index, scene in enumerate(plan.scenes):
                    signature = key(
                        [scene.model_dump(), sources[scene.source_index]["url"], voice]
                    )
                    cached = reusable_scenes.get(signature)
                    if cached and all(
                        Path(a["path"]).is_file() for a in cached["assets"].values()
                    ):
                        stage(
                            f"Reusing supported narration and selected footage for scene {index + 1}"
                        )
                        passages.append(
                            cached["passage"].model_copy(
                                update={"id": f"scene-{index + 1}"}
                            )
                        )
                        assets.update(cached["assets"])
                        total_seconds += cached["seconds"]
                        continue
                    stage(f"Recording natural narration for scene {index + 1}")
                    _, spoken_seconds, _ = utterance(scene.narration, inputs, voice)
                    frames = math.ceil((spoken_seconds + 0.37) * 24)
                    total_seconds += frames / 24
                    count = 2 if frames / 24 > 7 else 1
                    slot = math.ceil(frames / count) / 24 + 0.05
                    selected = []
                    for query in adaptive_queries(scene):
                        stage(f"Finding footage for scene {index + 1}: {query}")
                        for asset in footage.candidates(
                            query, inputs / "source-downloads", budget, audit
                        ):
                            raw = Path(asset["path"])
                            try:
                                windows = footage.inspect_and_cut(
                                    asset,
                                    scene,
                                    slot,
                                    count - len(selected),
                                    inputs / "selected-clips",
                                    budget,
                                    stage,
                                )
                                selected.extend(windows)
                                audit.append(
                                    {
                                        "source": asset["source"],
                                        "scene": index + 1,
                                        "verified_windows": [
                                            w["origin_window"] for w in windows
                                        ],
                                    }
                                )
                            finally:
                                raw.unlink(missing_ok=True)
                            if len(selected) >= count:
                                break
                        if len(selected) >= count:
                            break
                    if len(selected) < count:
                        raise ValueError(
                            f"Scene {index + 1} lacks verified footage after alternative providers/queries. Revise its visual concept while preserving supported facts: {scene.visual.model_dump()}"
                        )
                    shots = []
                    for asset in selected[:count]:
                        assets[asset["id"]] = asset
                        shots.append(
                            Shot(
                                asset=asset["id"],
                                start=0,
                                end=asset["end"],
                                treatment="contain",
                                subject=scene.visual.subject,
                                action=scene.visual.action,
                                purpose=scene.visual.purpose,
                            )
                        )
                    passages.append(
                        Passage(
                            id=f"scene-{index + 1}",
                            narration=scene.narration,
                            claim_sources=[scene.source_index],
                            shots=shots,
                        )
                    )
                    reusable_scenes[signature] = {
                        "passage": passages[-1],
                        "assets": {a["id"]: a for a in selected[:count]},
                        "seconds": frames / 24,
                    }
                if not 20 <= total_seconds <= 75:
                    raise ValueError(
                        f"Measured narration is {total_seconds:.1f}s; revise to 30–55 seconds without padding"
                    )
                brief = Brief(
                    topic=plan.topic,
                    title=plan.title,
                    promise=plan.promise,
                    angle=plan.promise,
                    payoff=plan.payoff,
                    voice=voice,
                    source_count=len(sources),
                    passages=passages,
                )
                stage("Compiling the finished footage-led video, captions and sound")
                source_records = [
                    {
                        "url": s["url"],
                        "title": s["title"],
                        "verification": s["verification"],
                        "supporting_excerpts": [
                            p.supporting_quote
                            for p in plan.scenes
                            if p.source_index == i
                        ],
                    }
                    for i, s in enumerate(sources)
                ]
                result = assemble(
                    brief, assets, source_records, audit, folder, inputs, stage
                )
                write_json(
                    folder / "automation.json",
                    {
                        "attempts": attempts,
                        "searches": audit,
                        "inspected_candidates": budget.inspected,
                        "downloaded_bytes": budget.downloaded,
                        "execution": "remote",
                        "review": "Finished preview awaits creator approval; automatic checks are not a factual or legal guarantee",
                    },
                )
                return result
            except (OSError, ValueError, KeyError) as exc:
                feedback = str(exc)[:1300]
                attempts.append({"attempt": round_number + 1, "reason": feedback})
                write_json(
                    folder / "automation.json",
                    {"attempts": attempts, "searches": audit},
                )
                stage(
                    "Revising the angle, script or shot concept after an unsuccessful attempt"
                )
        raise ValueError(
            "Factory exhausted three automatic research/footage revisions: "
            + feedback[:500]
        )
    finally:
        editorial.DEADLINE.reset(deadline_token)
        # Full sources are temporary remote data. Retain only reusable short selected clips/output until TTL expiry.
        shutil.rmtree(inputs / "source-downloads", ignore_errors=True)
