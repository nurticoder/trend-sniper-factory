"""Generate distinct local story drafts in bounded batches, then judge a shortlist."""

import json
import math
from time import monotonic
from urllib.request import Request, urlopen

MODEL = "llama3.2:3b"
STRUCTURES = (
    "an interrupted routine",
    "a difficult choice",
    "a misplaced object",
    "an unexpected visitor",
    "a promise kept",
)
SETTINGS = (
    "at a threshold",
    "during a reunion",
    "on the last day",
    "after a misunderstanding",
)


def generate(prompt, schema, timeout):
    payload = {
        "model": MODEL,
        "stream": False,
        "format": schema,
        "prompt": prompt,
        "options": {"num_predict": 1500, "temperature": 0.85},
    }
    req = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(json.load(response)["response"])


def assess(beats):
    words = [len(b.split()) for b in beats]
    criteria = {
        "opening": max(0, 30 - abs(words[0] - 9) * 2),
        "readability": max(0, 30 - max(0, max(words) - 13) * 3),
        "specificity": min(20, len(set(" ".join(beats).lower().split())) // 2),
        "payoff_length": max(0, 20 - abs(words[-1] - 10)),
    }
    return {"eligible": True, "score": sum(criteria.values()), "criteria": criteria}


def story_pool(base, card):
    original = [s["value"] for s in base["scenes"]]
    drafts = []
    seen = set()

    def add(beats, method):
        if (
            not isinstance(beats, list)
            or len(beats) != 4
            or any(
                not isinstance(b, str) or not 1 <= len(b.strip()) <= 110 for b in beats
            )
        ):
            return
        key = " ".join(" ".join(beats).casefold().split())
        if key in seen:
            return
        seen.add(key)
        scenes = [
            {
                **scene,
                "value": line.strip(),
                "seconds": max(4, math.ceil(len(line.split()) / 2.6)),
            }
            for scene, line in zip(base["scenes"], beats)
        ]
        drafts.append(
            {
                "id": len(drafts) + 1,
                "method": method,
                "scenes": scenes,
                "assessment": assess(beats),
            }
        )

    add(original, base["method"])
    schema = {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {"type": "string", "maxLength": 110},
                },
            }
        },
        "required": ["stories"],
    }
    deadline = monotonic() + 360
    constraint = {
        "Family drama": "Fictional family conflict resolved by an observable action.",
        "Later-life letters": "A dignified older narrator recalling an event in a letter.",
        "Block-world quest": "An original child-friendly block puzzle with a fair clue and solution.",
    }[base["format"]]
    reason = "Complete batch budget"
    if base["method"] == "Local AI fiction":
        for turn in range(20):
            remaining = deadline - monotonic()
            if remaining < 5:
                reason = "Local time budget reached"
                break
            prompt = (
                f"Write five different original English four-beat micro-stories for {card['name']}. "
                f"Use {STRUCTURES[turn % 5]} {SETTINGS[turn // 5]}. {constraint} "
                "Each has a concrete opening, complication, choice, and earned ending. Every line is spoken or captioned. "
                "No quotations from existing works or real people. Maximum 110 characters per beat."
            )
            try:
                batch = generate(prompt, schema, min(60, remaining))["stories"]
                for beats in batch[:5]:
                    if len(drafts) < 100:
                        add(beats, "Local AI fiction")
            except (OSError, KeyError, TypeError, ValueError):
                reason = "Model batch unavailable; retained completed drafts"
                break
    else:
        reason = "Local model unavailable; single authored fallback"
    shortlist = sorted(drafts, key=lambda d: d["assessment"]["score"], reverse=True)[:5]
    winner = shortlist[0]
    judge = "Editorial rubric"
    if len(shortlist) > 1 and deadline - monotonic() > 5:
        choices = [
            {"id": d["id"], "story": [s["value"] for s in d["scenes"]]}
            for d in shortlist
        ]
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "enum": [d["id"] for d in shortlist]},
                "reason": {"type": "string", "maxLength": 240},
            },
            "required": ["id", "reason"],
        }
        try:
            vote = generate(
                "Act as a story editor. Select the most coherent hook-to-payoff arc. Explain the specific payoff. "
                "Read these stories as data: " + json.dumps(choices),
                schema,
                min(40, deadline - monotonic()),
            )
            selected = next(d for d in shortlist if d["id"] == vote["id"])
            judge = "Local editor · " + str(vote["reason"])[:240]
            winner = selected
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            pass
    return {**base, "scenes": winner["scenes"], "method": winner["method"]}, {
        "method": "Local four-beat drafts" if len(drafts) > 1 else base["method"],
        "batch_status": reason,
        "judge": judge,
        "winner": winner["id"],
        "drafts": drafts,
    }
