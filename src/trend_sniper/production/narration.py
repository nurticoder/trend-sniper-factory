"""Local Kokoro speech, measured timing, normalization and audio mixing."""

import copy
import math
import re
import subprocess
import sys
import wave
from array import array

import imageio_ffmpeg

from ..core import digest, write_json

# Kokoro is the creator-selected production voice. Piper remains an explicit legacy tool.
from .kokoro import FILES, SOURCE, VOICE, availability, synthesize

ENGINE_VERSION = "0.4.7"
RATE = 24000


def samples(path):
    with wave.open(str(path), "rb") as stream:
        if (
            stream.getnchannels() != 1
            or stream.getsampwidth() != 2
            or stream.getframerate() != RATE
        ):
            raise ValueError("Narration must be mono 24 kHz PCM")
        if not 0 < stream.getnframes() <= RATE * 90:
            raise ValueError("Narration audio exceeds its duration limit")
        result = array("h", stream.readframes(stream.getnframes()))
    if sys.byteorder != "little":
        result.byteswap()
    return result


def save_wav(path, data):
    output = array("h", data)
    if sys.byteorder != "little":
        output.byteswap()
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        stream.writeframes(output.tobytes())


def normalized(source, output):
    # Force PCM at the mix rate and bound decoder runtime/output even for a broken provider.
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-t",
            "21",
            "-ar",
            str(RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    data = samples(output)
    peak = max(abs(value) for value in data)
    if len(data) < RATE * 0.15 or len(data) >= RATE * 20 or peak < 100:
        raise ValueError("Speech is silent, too short, or longer than 20 seconds")
    gain = 0.64 * 32767 / peak
    save_wav(output, (round(value * gain) for value in data))
    return len(data) / RATE


def spoken(scene, format_name):
    text = scene.get("value", "").strip()
    if format_name == "News desk" and scene.get("role") == "evidence":
        text = "Reported headline. " + text
    if format_name == "Countdown" and scene.get("role") == "evidence":
        text = scene["heading"] + ". " + text
    # Keep exact counts on screen; speak explicitly rounded large metrics so the hook stays readable.
    if scene.get("role") in {"hook", "payoff"}:

        def metric(match):
            count = int(match.group().replace(",", ""))
            for scale, unit in (
                (1_000_000_000, "billion"),
                (1_000_000, "million"),
                (1_000, "thousand"),
            ):
                if count >= max(scale, 10_000):
                    return f"about {count / scale:.1f} {unit}"
            return match.group()

        text = re.sub(r"\b\d{1,3}(?:,\d{3})+\b", metric, text)
    # Keep bracket directives out of spoken source copy.
    text = text.replace("[", "").replace("]", "").replace("#", "number ")
    return " ".join(text.split())


def prepare(topic, audit, inputs, mode="auto", stage=lambda name: None, engine=None):
    if mode not in {"auto", "off", "required"}:
        raise ValueError("Unknown narration mode")
    info = (
        availability(inputs)
        if mode != "off"
        else {"available": False, "detail": "Narration switched off."}
    )
    fallback = {
        "state": "off" if mode == "off" else "fallback",
        "mode": mode,
        "reason": info["detail"],
        "clips": [],
        "paid_api_usd": 0,
    }
    if not info["available"]:
        if mode == "required":
            raise ValueError("Narration required: " + info["detail"])
        return topic, fallback
    result, clips, at = copy.deepcopy(topic), [], 0
    try:
        for index, scene in enumerate(result["scenes"]):
            stage(f"Recording narration {index + 1}/{len(result['scenes'])}")
            text = spoken(scene, result["format"])
            if not text or len(text) > 450:
                raise ValueError("Spoken scene text is empty or too long")
            raw, output = audit / f"voice-{index}.raw.wav", audit / f"voice-{index}.wav"
            (engine or synthesize)(text, raw, inputs)
            seconds = normalized(raw, output)
            raw.unlink()
            lead = 0.55 if index == 0 else 0.12
            duration = math.ceil(max(scene["seconds"], lead + seconds + 0.2) * 24) / 24
            scene.update(seconds=duration, narration=text)
            clips.append(
                {
                    "scene": index + 1,
                    "text": text,
                    "start": round(at + lead, 4),
                    "duration": seconds,
                    "file": output.name,
                    "sha256": digest(output),
                }
            )
            at += duration
            if at > 90:
                raise ValueError("Narrated edit exceeds the 90-second factory limit")
        # Recheck the model/config at completion so changed files cannot inherit the recorded provenance.
        if not availability(inputs)["available"]:
            raise ValueError("Voice files changed during production")
    except (OSError, ValueError, subprocess.SubprocessError, wave.Error) as error:
        if mode == "required":
            raise ValueError(
                "Required narration failed: " + type(error).__name__
            ) from error
        fallback["reason"] = (
            "Local speech failed ("
            + type(error).__name__
            + "). Entire edit uses captions and music."
        )
        return topic, fallback
    voice = array("h", [0]) * round(at * RATE)
    for clip in clips:
        data = samples(audit / clip["file"])
        offset = round(clip["start"] * RATE)
        voice[offset : offset + len(data)] = data
    save_wav(audit / "narration.wav", voice)
    report = {
        "state": "ready",
        "mode": mode,
        "voice": VOICE,
        "engine": "Kokoro ONNX " + ENGINE_VERSION,
        "model_license": "Apache-2.0",
        "runner_license": "MIT",
        "source": SOURCE,
        "voice_profile": "af_heart",
        "model_sha256": FILES["kokoro-v1.0.int8.onnx"],
        "voices_sha256": FILES["voices-v1.0.bin"],
        "clips": clips,
        "duration_seconds": at,
        "paid_api_usd": 0,
        "audio_sha256": digest(audit / "narration.wav"),
        "timing": "Measured utterance duration; scene-aligned captions, not word-level alignment",
    }
    write_json(audit / "narration.json", report)
    return result, report


def mix(path, voice_path, report):
    """Duck all background audio around measured utterances with 100/180ms ramps."""
    bed, voice = samples(path), samples(voice_path)
    if abs(len(bed) - len(voice)) > len(report["clips"]):
        raise ValueError("Speech and edit durations disagree")
    intervals = [
        (clip["start"], clip["start"] + clip["duration"]) for clip in report["clips"]
    ]
    mixed = array("h")
    for i, value in enumerate(bed):
        t = i / RATE
        activity = max(
            (
                max(0, min(1, (t - start + 0.1) / 0.1, (end + 0.18 - t) / 0.18))
                for start, end in intervals
            ),
            default=0,
        )
        gain = 0.7 - 0.5 * activity
        total = value * gain + (voice[i] if i < len(voice) else 0)
        mixed.append(round(max(-0.95 * 32767, min(0.95 * 32767, total))))
    save_wav(path, mixed)
