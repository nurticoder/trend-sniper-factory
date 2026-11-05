from __future__ import annotations

import math
import os
import struct
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from .core import digest, write_json

W, H = 720, 1280
BG = (9, 17, 32)
CYAN = (79, 230, 221)
GOLD = (255, 211, 104)
STONES = [(210, 865), (180, 770), (205, 675), (180, 580), (255, 490), (360, 455)]


def font(size):
    custom = os.environ.get("TSF_FONT")
    return ImageFont.truetype(custom, size) if custom else ImageFont.load_default(size=size)


def wrapped(draw, text, y, size, fill, width=590):
    face = font(size)
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=face) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    for line in lines:
        draw.text((W / 2, y), line, font=face, fill=fill, anchor="mt")
        y += size * 1.3
    return y


def frame(topic, index, local, elapsed, duration):
    scene = topic["scenes"][index]
    mode = scene["mode"]
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((52, 65), "TREND SNIPER  /  POOL LOGIC 01", font=font(20), fill=CYAN)
    wrapped(d, scene["heading"], 125, 43, "white")
    d.text((360, 265), "ORIGINAL ANIMATION / NOT GAMEPLAY", font=font(17), fill=(144, 164, 190), anchor="mt")
    # Entire scene is drawn from primitive geometry, without game assets.
    d.rounded_rectangle((65, 360, 655, 970), 38, fill=(27, 51, 71), outline=(55, 88, 105), width=3)
    d.rounded_rectangle((100, 395, 620, 935), 24, fill=(13, 68, 94))
    for row in range(12):
        yy = 410 + row * 44
        points = [(x, yy + 4 * math.sin(x / 38 + elapsed * 1.7 + row)) for x in range(112, 610, 6)]
        d.line(points, fill=(24, 88, 112), width=2)
    for x, y in STONES:
        d.rounded_rectangle((x - 36, y - 25, x + 36, y + 25), 12, fill=(91, 119, 130), outline=(152, 183, 183), width=2)
    d.rounded_rectangle((305, 410, 415, 470), 10, fill=CYAN)
    d.text((360, 428), "EXIT", font=font(22), fill=BG, anchor="mt")
    # Route A has a water landing, B has only stone landings.
    a = [(360, 895), (435, 680), (360, 455)]
    b = [(360, 895)] + STONES
    if mode in {"choice", "rule", "splash"}:
        d.line(a, fill=(247, 116, 135), width=5)
    if mode in {"choice", "safe", "reveal", "end"}:
        d.line(b, fill=CYAN, width=5)
    d.text((480, 735), "A", font=font(38), fill=(255, 145, 157))
    d.text((125, 700), "B", font=font(38), fill=CYAN)
    phase = min(local / scene["seconds"], 0.999)
    if mode == "splash":
        route = a
    elif mode in {"safe", "reveal", "end"}:
        route = b
    else:
        route = [(360, 895), (360, 895)]
    p = phase * (len(route) - 1)
    j = min(int(p), len(route) - 2)
    f = p - j
    x = route[j][0] * (1 - f) + route[j + 1][0] * f
    y = route[j][1] * (1 - f) + route[j + 1][1] * f - 23 * math.sin(f * math.pi)
    if mode == "splash" and phase >= 0.45:
        for k in range(4):
            radius = 12 + ((local * 55 + k * 30) % 120)
            d.ellipse((435-radius, 680-radius/2, 435+radius, 680+radius/2), outline=(255, 133, 150), width=3)
        d.text((505, 610), "SPLASH", font=font(21), fill=(255, 145, 157), anchor="mt")
    d.ellipse((x-15, y-15, x+15, y+15), fill=GOLD, outline="white", width=3)
    wrapped(d, scene["caption"], 1010, 31, "white")
    d.text((52, 1170), f"{index+1:02d} / {len(topic['scenes']):02d}     FICTIONAL PUZZLE", font=font(18), fill=(144,164,190))
    d.rounded_rectangle((52, 1210, 668, 1216), 3, fill=(38, 55, 75))
    d.rounded_rectangle((52, 1210, 52 + max(6, 616 * elapsed / duration), 1216), 3, fill=CYAN)
    return im


def sound(path, topic, rate=24000):
    duration = sum(s["seconds"] for s in topic["scenes"])
    boundaries, t = [], 0
    for scene in topic["scenes"]:
        boundaries.append((t, scene["mode"], scene["seconds"]))
        t += scene["seconds"]
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        samples = bytearray()
        for i in range(round(duration * rate)):
            t = i / rate
            # Original quiet pulse bed and scene cue, no samples/music imports.
            beat = t % 0.5
            value = 0.08 * math.sin(2 * math.pi * 110 * t) * math.exp(-beat * 15)
            for start, mode, seconds in boundaries:
                dt = t - start
                if 0 <= dt < .22:
                    hz = 660 if mode in {"safe", "reveal"} else 330
                    value += .12 * math.sin(2 * math.pi * hz * dt) * (1-dt/.22)
                dt = t - start - seconds/2
                if mode == "splash" and 0 <= dt < .6:
                    value += .08 * math.sin(2*math.pi*(180*dt+70*dt*dt)) * (1-dt/.6)
            samples.extend(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))
        out.writeframes(samples)


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def render(topic, out: Path, fps=24, draw_frame=frame, make_audio=sound):
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output folder must be empty; choose a new folder")
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    duration = sum(s["seconds"] for s in topic["scenes"])
    audio = out / "soundtrack.wav"
    make_audio(audio, topic)
    movie = out / "short.mp4"
    command = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0", "-i", str(audio), "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", str(movie)]
    captions, elapsed = [], 0.0
    try:
        # File avoids a stderr pipe filling while frames are being written.
        with (out / "ffmpeg.log").open("w+") as log:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
            try:
                global_frame = 0
                for idx, scene in enumerate(topic["scenes"]):
                    end = elapsed + scene["seconds"]
                    copy = '\n'.join(str(scene[k]) for k in ('heading','value','caption') if scene.get(k))
                    captions.append(f"{idx+1}\n{srt_time(elapsed)} --> {srt_time(end)}\n{copy}\n")
                    while global_frame / fps < end - 1e-8:
                        t = global_frame / fps
                        im = draw_frame(topic, idx, t-elapsed, t, duration)
                        if idx == 0 and t == 0:
                            im.save(out / "poster.png")
                        proc.stdin.write(im.tobytes())
                        global_frame += 1
                    elapsed = end
                proc.stdin.close()
                if proc.wait() != 0:
                    raise RuntimeError("FFmpeg failed; see ffmpeg.log")
            except BaseException:
                proc.kill()
                proc.wait()
                raise
        # Decode the entire deliverable, not just its header.
        subprocess.run([ffmpeg, "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], check=True, capture_output=True)
    except BaseException:
        movie.unlink(missing_ok=True)
        raise
    (out / "captions.srt").write_text("\n".join(captions), encoding="utf-8")
    write_json(out / "script.json", topic)
    metadata = {k: topic[k] for k in ("title", "description", "hashtags", "audience")}
    metadata.update({"privacyStatus": "private", "review_status": "pending", "containsSyntheticMedia": True})
    write_json(out / "metadata.json", metadata)
    (out / "metadata.txt").write_text(topic["title"] + "\n\n" + topic["description"] + "\n\n" + " ".join('#'+t for t in topic['hashtags']) + "\n", encoding="utf-8")
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout
    (out / "ffmpeg-version.txt").write_text(version)
    write_json(out / "manifest.json", {
        "schema_version": 1, "topic_id": topic["id"], "source_url": topic["source_url"],
        "trend_status": topic["trend_status"], "duration_seconds": duration,
        "width": W, "height": H, "fps": fps, "audio": "original procedural PCM → AAC; no voice",
        "visuals": "original Python geometry; Pillow bundled font or TSF_FONT override",
        "assets": [], "rights": "No external game art, clips, logos, music, or character assets",
        "sha256": {name: digest(out / name) for name in ("short.mp4", "script.json", "metadata.json", "captions.srt")},
        "cost": {"paid_api_usd": 0, "wall_seconds": round(time.monotonic()-started, 2), "electricity_and_hardware": "not measured"},
        "validation": "entire MP4 decoded by FFmpeg with -xerror",
    })
    return movie
