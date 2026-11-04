import json
import math
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, StrictBool

from ..production.jobs import ProductionQueue
from ..render import font, render, wrapped
from .radar import CHART, SEED, observe


def brief(card, date):
    name, rank, peak = card["name"], card["rank"], card["peak_in_game"]
    last = card["last_week_rank"]
    angle = (
        "No prior rank reported"
        if last == -1
        else f"Up {last - rank} places from #{last}"
    )
    title = (
        f"{name}: guess its Steam rank"
        if last == -1
        else f"{name} climbed {last - rank} places"
    )
    beats = [
        ("GUESS THE GAME", f"{peak:,}", "Peak players. Can you name the game?", 3),
        ("FIRST CLUE", card["niche"], angle, 3),
        ("THE REVEAL", name, f"Number {rank} in the Steam most-played chart.", 5),
        ("CHART RECEIPT", f"#{rank}", f"{name} / Steam chart dated {date}", 3),
    ]
    if last > rank:
        beats = [
            ("LAST WEEK", f"#{last}", name, 3),
            ("THE CLIMB", f"+{last - rank}", "Places gained in the Steam chart.", 3),
            ("THIS WEEK", f"#{rank}", name, 4),
            (
                "PEAK CROWD",
                f"{peak:,}",
                "Simultaneous players during the chart period.",
                4,
            ),
        ]
    return dict(
        previous=last,
        rank=rank,
        id=str(card["appid"]),
        source_url=CHART,
        trend_status=angle,
        title=title[:100],
        description=f"{name} reached #{rank} on {date}. {angle}. Source: {CHART}",
        hashtags=["Steam", "Gaming", "Shorts"],
        audience="needs_review",
        date=date,
        scenes=[
            dict(
                heading=h,
                value=v,
                caption=c,
                seconds=d,
                mode="reveal" if i == 2 else "choice",
            )
            for i, (h, v, c, d) in enumerate(beats)
        ],
    )


def frame(topic, index, local, t, duration):
    scene = topic["scenes"][index]
    im = Image.new("RGB", (720, 1280), (12, 18, 28))
    draw = ImageDraw.Draw(im)
    accent = [(144, 250, 174), (255, 186, 93), (128, 219, 255)][int(topic["id"]) % 3]
    for k in range(28):
        x, y = (k * 83 + int(t * 44)) % 880 - 80, (k * 139 - int(t * 70)) % 1440 - 80
        draw.line((x, y, x + 60, y - 90), fill=(34, 47, 59), width=4)
    draw.text((48, 76), "PLAY / INDEX", font=font(30), fill=accent)
    draw.text((48, 200), scene["heading"], font=font(40), fill="white")
    value = scene["value"]
    wrapped(draw, value, 325, 90 if len(value) < 9 else 48, accent, 580)
    if topic["previous"] > topic["rank"]:
        progress = min(1, max(0, (t - 3) / 3))
        start, end = topic["previous"], topic["rank"]
        x, y = 95 + 480 * progress, 820 - 200 * progress
        draw.line((95, 820, 575, 620), fill=(44, 58, 66), width=8)
        draw.line((95, 820, x, y), fill=accent, width=8)
        draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill="white")
        draw.text(
            (x, y - 32),
            f"#{round(start + (end - start) * progress)}",
            font=font(32),
            fill=accent,
            anchor="mb",
        )
    else:
        for k in range(5):
            r = 45 + k * 22 + 7 * math.sin(t * 3 + k)
            draw.arc(
                (345 - r, 730 - r, 345 + r, 730 + r),
                t * 55 + k * 28,
                t * 55 + k * 28 + 230,
                fill=accent,
                width=5,
            )
        draw.text(
            (345, 730),
            ["?", "?", "!", "#"][index],
            font=font(65),
            fill="white",
            anchor="mm",
        )
    wrapped(draw, scene["caption"], 930, 34, "white", 555)
    draw.text(
        (48, 1145), "STEAM CHART   /   " + topic["date"], font=font(20), fill=accent
    )
    draw.rectangle((48, 1190, 49 + 600 * t / duration, 1198), fill=accent)
    return im


class QueueSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paused: StrictBool


def install(app, store):
    root = store.path.parent / (store.path.stem + "-factory")
    root.mkdir(exist_ok=True)
    cache = root / "radar.json"

    @app.get("/api/radar")
    def feed():
        return json.loads((cache if cache.exists() else SEED).read_text())

    @app.post("/api/radar/refresh")
    def refresh():
        try:
            result = observe()
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(
                503, "Scan unavailable. Last dated observations are still available."
            ) from exc
        temp = root / (uuid4().hex + ".tmp")
        temp.write_text(json.dumps(result))
        temp.replace(cache)
        return result

    def run(job, script, progress):
        if "recipe_card" in script:
            from ..production.run import run_recipe

            return run_recipe(
                script["recipe_card"],
                root / job,
                store.path.parent,
                progress,
                script.get("production_options", {"narration": "off"}),
            )
        progress("Compiling and decoding MP4")
        render(script, root / job, draw_frame=frame)
        return script

    queue = ProductionQueue(store, run)
    app.state.production_queue = queue

    def enqueue(key, script):
        return queue.enqueue(
            key, {**script, "production_options": app.state.production_preferences()}
        )

    # Publish transport has its own executor so a long preview cannot consume its release window.
    publisher = ThreadPoolExecutor(max_workers=1, thread_name_prefix="publisher")
    app.state.publisher_executor = publisher

    @app.get("/api/production-desk")
    def desk():
        return queue.state()

    @app.put("/api/production-desk")
    def configure(body: QueueSettings):
        queue.pause(body.paused)
        return queue.state()

    @app.post("/api/productions/{job}/retry", status_code=202)
    def retry(job: str):
        return queue.retry(job)

    @app.post("/api/productions/{job}/cancel", status_code=202)
    def cancel(job: str):
        queue.cancel(job)
        return {"id": job}

    @app.get("/api/productions/{job}/history")
    def history(job: str):
        return queue.history(job)

    @app.post("/api/radar/{appid}/produce", status_code=202)
    def produce(appid: int):
        data = feed()
        card = next((c for c in data["cards"] if c["appid"] == appid), None)
        if card is None:
            raise HTTPException(404, "Recommendation expired")
        script = brief(card, data["date"])
        key = f"{appid}/{data['date']}"
        return enqueue(key, script)

    from .releases import install as install_releases

    install_releases(app, store, root, publisher)
    app.state.enqueue = enqueue

    @app.get("/api/productions")
    def jobs():
        with store.connection() as db:
            rows = db.execute("""SELECT p.id,p.script,p.status,p.error,s.stage,
                r.created_at,r.started_at,r.finished_at,r.parent,r.attempt,r.cancel_requested,
                r.runtime_seconds,r.paid_api_usd,child.job,l.state,l.remote_id
                FROM productions p LEFT JOIN production_steps s ON p.id=s.id
                LEFT JOIN production_runs r ON p.id=r.job
                LEFT JOIN production_runs child ON child.parent=p.id
                LEFT JOIN releases l ON l.job=p.id ORDER BY p.rowid DESC""").fetchall()
        keys = (
            "id",
            "script",
            "status",
            "error",
            "stage",
            "created_at",
            "started_at",
            "finished_at",
            "parent",
            "attempt",
            "cancel_requested",
            "runtime_seconds",
            "paid_api_usd",
            "retry_id",
            "release_state",
            "remote_id",
        )
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            script = json.loads(item.pop("script"))
            item.update(
                title=script.get("title", "Untitled preview"),
                format=script.get("format")
                or script.get("recipe_card", {}).get("format", "Steam chart"),
                has_report=item["status"] == "ready"
                and (root / item["id"] / "production-report.json").is_file(),
            )
            result.append(item)
        return result

    @app.get("/api/productions/{job}/{asset}")
    def artifact(job: str, asset: str):
        if asset not in {
            "short.mp4",
            "metadata.txt",
            "script.json",
            "production-report.json",
            "script-options.json",
            "cover.jpg",
            "cover-options.jpg",
            "observation.json",
            "narration.wav",
            "narration.json",
        }:
            raise HTTPException(404)
        with store.connection() as db:
            ready = db.execute(
                "SELECT id FROM productions WHERE id=? AND status='ready'", (job,)
            ).fetchone()
        if not ready:
            raise HTTPException(404)
        path = root / ready[0] / asset
        if not path.is_file():
            raise HTTPException(404, "This run has no such artifact")
        return FileResponse(path)
