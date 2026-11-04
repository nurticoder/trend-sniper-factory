import json
import os
from time import monotonic

from PIL.Image import DecompressionBombError as ImageError

from ..core import digest, write_json
from ..render import render
from ..web.formats import build, frame
from . import commons
from .covers import cover_set
from .editor import write_and_select
from .materials import library, plan, public_record, soundtrack, visual_renderer
from .narration import mix, prepare
from .release import proposal


def run_recipe(card, folder, inputs, stage, options=None):
    """Develop a topic plan by default; render only explicitly selected reporting formats."""
    if (options or {}).get('production_format','content') != 'analytics':
        stage('Writing an original topic story and visual plan')
        topic=build(card)
        folder.mkdir(parents=True,exist_ok=True)
        write_json(folder/'content-plan.json',topic)
        write_json(folder/'script.json',topic)
        return topic
    started = monotonic()
    audit = folder.with_name(folder.name + "-work")
    audit.mkdir(parents=True, exist_ok=True)
    stages = []

    def mark(name):
        stages.append(
            {"stage": name, "elapsed_seconds": round(monotonic() - started, 2)}
        )
        stage(name)
        write_json(audit / "stages.json", stages)

    mark("Collecting source facts")
    write_json(audit / "observation.json", card)
    mark("Writing and comparing scripts")
    topic = build(card, analytics=True)
    if topic["format"] in {"Countdown", "News desk"}:
        topic, editor = write_and_select(card, topic, analytics=True)
    else:
        from .stories import story_pool

        topic, editor = story_pool(topic, card)
    write_json(audit / "script-options.json", editor)

    mark("Preparing narration")
    topic, narration = prepare(
        topic, audit, inputs, (options or {}).get("narration", "auto"), mark
    )
    if narration["state"] == "ready":
        topic["description"] += (
            "\n\nSynthetic narration: Piper LJ Speech. Model source: "
            + narration["source"]
        )
    mark("Selecting scene materials")
    assets, skipped = library(inputs / "media-library")
    retrieval = []
    # External queries use observed public titles only, never private scripts or notes.
    if os.environ.get("TSF_COMMONS", "1") == "1" and topic["format"] in {
        "Countdown",
        "News desk",
    }:
        for item in card["examples"][:2]:
            try:
                source = "https://www.youtube.com/watch?v=" + item["video"]
                lengths = [
                    s["seconds"] for s in topic["scenes"] if s.get("source") == source
                ]
                found = commons.search(
                    item["title"], inputs / "media-cache", max(lengths, default=6)
                )
                assets.extend(found)
                retrieval.append({"query": item["title"], "eligible_files": len(found)})
            except (OSError, ValueError, KeyError, ImageError) as exc:
                retrieval.append(
                    {
                        "query": item["title"],
                        "status": "unavailable",
                        "reason": type(exc).__name__,
                    }
                )
    materials = plan(topic, assets)
    used = [
        a for shot in materials["scenes"] for a in (shot["visual"], shot["effect"]) if a
    ]
    if materials["music"]:
        used.append(materials["music"])
    credits = list(
        dict.fromkeys(
            f"{a['description']} — {a['credit']} — {a['license']} — {a['source']} (trimmed or reframed)"
            for a in used
        )
    )
    if credits:
        topic["description"] += "\n\nMedia credits\n" + "\n".join(credits)
    base_draw = frame
    if "research" in editor:
        from .graphics import evidence_graphic

        base_draw = evidence_graphic(editor["research"])
    draw = visual_renderer(base_draw, materials)
    mark("Generating and choosing covers")
    opening, covers = cover_set(topic, draw, audit)

    def with_opening(t, i, local, elapsed, duration):
        return opening if elapsed < 0.5 else draw(t, i, local, elapsed, duration)

    mark("Compiling and decoding MP4")
    bed = soundtrack(materials)

    def audio(path, edit):
        bed(path, edit)
        if narration["state"] == "ready":
            mix(path, audit / "narration.wav", narration)

    render(topic, folder, draw_frame=with_opening, make_audio=audio)
    mark("Planning release")
    report = {
        "schema_version": 1,
        "script_count": len(editor["drafts"]),
        "winning_script": editor["winner"],
        "writer": editor["method"],
        "judge": editor.get("judge", "Editorial rubric"),
        "batch_status": editor.get("batch_status", "Complete"),
        "script_assessment": next(
            d.get("assessment", {})
            for d in editor["drafts"]
            if d["id"] == editor["winner"]
        ),
        "materials": public_record(materials),
        "narration": narration,
        "rejected_assets": skipped,
        "online_search": retrieval,
        "covers": covers,
        "release": proposal(inputs / "channel-history.json", topic["format"]),
        "stages": stages,
        "paid_api_usd": 0,
        "runtime_seconds": round(monotonic() - started, 2),
    }
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest.update(
        cover_sha256=digest(audit / "cover.jpg"),
        narration=narration,
        assets=public_record(used),
        visuals="Original motion graphics plus selected cleared media",
        rights="See per-asset source, evidence, license, credit and hash.",
        audio="Original synthesized soundtrack, cleared cues and local narration"
        if narration["state"] == "ready"
        else "Original synthesized soundtrack plus any credited music and cues",
    )
    write_json(folder / "manifest.json", manifest)
    write_json(folder / "production-report.json", report)
    for name in (
        "cover.jpg",
        "cover-options.jpg",
        "script-options.json",
        "observation.json",
    ):
        (audit / name).replace(folder / name)
    write_json(folder / "narration.json", narration)
    if narration["state"] == "ready":
        (audit / "narration.wav").replace(folder / "narration.wav")
    return topic
