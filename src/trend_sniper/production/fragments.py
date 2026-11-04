"""Verify candidate CC0 footage against the shot request before accepting a window."""

import base64
import json
import re
import subprocess
from urllib.request import Request, urlopen

import imageio_ffmpeg


def duration(path):
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=8, check=False)
    match = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", result.stderr)
    if not match:
        return 0
    h, m, s = map(float, match.groups())
    return h * 3600 + m * 60 + s


def verify_window(path, start, length, query):
    """Two sampled frames must visibly depict the requested subject."""
    images = []
    for fraction in (0.2, 0.8):
        cmd = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-ss",
            str(start + length * fraction),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=256:-2",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        jpeg = subprocess.run(cmd, check=True, capture_output=True, timeout=8).stdout
        if not jpeg:
            return False
        images.append(base64.b64encode(jpeg).decode())
    # Evaluate each sample separately for compatibility with single-image models.
    for image in images:
        payload = {
            "model": "moondream:latest",
            "stream": False,
            "images": [image],
            "options": {"num_predict": 6},
            "prompt": "Is the specific subject of the following title clearly visible? "
            "Answer yes only when visually identifiable. Title: " + query,
        }
        req = Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=12) as response:
            answer = json.load(response)["response"].strip().lower()
        if not re.match(r"^yes\b", answer):
            return False
    return True


def locate(path, query, min_length):
    total = duration(path)
    if not min_length <= total <= 600:
        return None
    # Each accepted fragment covers the entire requested shot. Never loop a short clip.
    for fraction in (0.15, 0.55):
        start = round((total - min_length) * fraction, 3)
        if verify_window(path, start, min_length, query):
            return start, start + min_length
    return None
