"""Write and compare source-constrained editorial cuts before spending a render."""

import math

from ..web.formats import recipe


def research(card):
    records = []
    seen = set()
    for item in card["examples"]:
        if item["video"] in seen:
            continue
        seen.add(item["video"])
        records.append(
            {**item, "source": "https://www.youtube.com/watch?v=" + item["video"]}
        )
    return {
        "subject": card["name"],
        "channel": card["channel"],
        "observed": card["observed"],
        "format": recipe(card)[0],
        "records": records,
    }


def beat(heading, text, caption, source, role):
    words = len((text + " " + caption).split())
    return {
        "heading": heading,
        "value": text,
        "caption": caption,
        "source": source,
        "role": role,
        "seconds": max(2, min(10, math.ceil(words / 3))),
        "mode": "reveal" if role == "payoff" else "choice",
    }


def cut(packet, lens, treatment, opening):
    news = packet["format"] == "News desk"
    facts = packet["records"]
    if not news:
        facts = [r for r in facts if r["views"] is not None]
    if not facts:
        raise ValueError("No usable source facts for this script")
    metric = "published" if news else "views"
    ranked = sorted(facts, key=lambda r: r[metric], reverse=True)
    lead, tail = ranked[0], ranked[-1]
    count = len(ranked)
    channel = packet["channel"]
    date = packet["observed"][:10]
    if news:
        clue = lead["published"][:10]
        hooks = [
            "Which sampled report appeared latest?",
            "Catch up on the dispatches.",
            "Start with the date.",
            "Which report came last?",
            "Follow the news timeline.",
        ]
        angles = [
            f"{count} recent reports",
            "The latest dispatch",
            "From earliest to latest",
            "One newsroom in focus",
            "The publication timeline",
        ]
        order = list(reversed(ranked)) if lens != 1 else [lead]
        answer = f"Latest in this sample: {clue}"
    else:
        clue = f"{lead['views']:,} views"
        hooks = [
            "Which upload led this sample?",
            "Guess the most watched.",
            "Remember this number.",
            "Which title takes first place?",
            "Who finished first?",
        ]
        angles = [
            f"{count} uploads by views",
            "The front-runner",
            "From last to first",
            "The lead in numbers",
            "A head-to-head finish",
        ]
        order = list(reversed(ranked))
        if lens == 1:
            order = [lead]
        elif lens == 4:
            order = [tail, lead] if count > 1 else [lead]
        answer = f"{lead['views'] - tail['views']:,} views separate first and last."
    # The opening contract changes which claim the payoff needs to resolve.
    open_text = [
        hooks[opening],
        f"{clue}. {hooks[opening]}",
        f"{channel}. {hooks[opening]}",
        f"{angles[lens]}. {hooks[opening]}",
    ][treatment]
    scenes = [
        beat(angles[lens], open_text, f"{channel} · {date}", lead["source"], "hook")
    ]
    for record in order:
        pos = (
            ranked.index(record) + 1
            if news
            else 1 + sum(r["views"] > record["views"] for r in ranked)
        )
        number = (
            record["published"][:10] if news else f"#{pos} · {record['views']:,} views"
        )
        # Change the sequence of callout, subject and evidence across cuts.
        heading, text, caption = [
            (number, record["title"], channel),
            ("DISPATCH" if news else f"RANK {pos}", record["title"], number),
            ("PUBLISHED" if news else "VIEW COUNT", number, record["title"]),
            (f"{pos} / {count}", record["title"], f"{channel} · {number}"),
        ][treatment]
        scenes.append(
            beat(
                heading,
                text,
                caption,
                record["source"],
                "payoff" if record == lead else "evidence",
            )
        )
    if lens in (2, 3, 4):
        scenes.append(
            beat(
                "THE RECEIPT",
                answer,
                f"{channel} · sample of {count}",
                lead["source"],
                "payoff",
            )
        )
    return scenes


def evaluate(scenes, packet):
    valid_sources = {r["source"] for r in packet["records"]}
    if not scenes or any(s["source"] not in valid_sources for s in scenes):
        return {"eligible": False, "reason": "Missing source reference"}
    seconds = sum(s["seconds"] for s in scenes)
    density = max(
        len((s["value"] + " " + s["caption"]).split()) / s["seconds"] for s in scenes
    )
    criteria = {
        "source_coverage": round(
            25 * len({s["source"] for s in scenes}) / len(valid_sources)
        ),
        "opening_readability": max(
            0, 24 - abs(7 - len(scenes[0]["value"].split())) * 2
        ),
        "payoff": 20 if scenes[-1]["role"] == "payoff" else 0,
        "reading_time": max(0, 20 - round(max(0, density - 2.8) * 8)),
        "runtime_fit": max(0, 11 - round(abs(seconds - 20) / 2)),
    }
    return {
        "eligible": True,
        "score": sum(criteria.values()),
        "criteria": criteria,
        "seconds": seconds,
    }


def write_and_select(card, base):
    packet = research(card)
    drafts = []
    seen = set()
    for lens in range(5):
        for treatment in range(4):
            for opening in range(5):
                scenes = cut(packet, lens, treatment, opening)
                fingerprint = tuple(
                    (s["heading"], s["value"], s["caption"]) for s in scenes
                )
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                drafts.append(
                    {
                        "id": len(drafts) + 1,
                        "scenes": scenes,
                        "assessment": evaluate(scenes, packet),
                    }
                )
    winner = max(
        (d for d in drafts if d["assessment"]["eligible"]),
        key=lambda d: d["assessment"]["score"],
    )
    values = [r["views"] for r in packet["records"] if r["views"] is not None]
    channel = packet["channel"]
    if packet["format"] == "Countdown" and values:
        cover_lines = [
            ("Subject", f"{max(values):,} views"),
            ("Question", f"Who led {channel}'s sample?"),
            ("Detail", f"A {max(values) - min(values):,}-view gap"),
        ]
    else:
        cover_lines = [
            ("Subject", f"{channel} in {len(packet['records'])} reports"),
            ("Question", "Which report came latest?"),
            ("Detail", f"The {packet['observed'][:10]} briefing"),
        ]
    script = {
        **base,
        "cover_lines": cover_lines,
        "scenes": winner["scenes"],
        "method": "Source-constrained editorial selection",
    }
    return script, {
        "method": "Deterministic full cuts · 5 lenses × 4 treatments × 5 openings",
        "research": packet,
        "drafts": drafts,
        "winner": winner["id"],
    }
