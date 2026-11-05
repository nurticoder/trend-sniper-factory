"""One-off local comparison only; does not register or select application providers.

Run with the isolated audition environment (kokoro-onnx and soundfile), passing
--piper-python .venv/bin/python. Download official model files separately.
"""

import argparse
import hashlib
import json
import subprocess
import wave
from pathlib import Path

SCRIPT = (
    "This isn't a glass marble. It's water. Why doesn't it spill? "
    "In orbit, everything falls together. Surface tension pulls the drop into a rounded shape. "
    "Here's the twist: floating and roundness look connected, but two completely different effects are at work."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--piper-python", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Installed separately only for this comparison. Disable runtime telemetry.
    import onnxruntime

    onnxruntime.disable_telemetry_events()
    import soundfile as sf
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(
        str(args.models / "kokoro-v1.0.int8.onnx"), str(args.models / "voices-v1.0.bin")
    )
    audio, rate = kokoro.create(SCRIPT, voice="af_heart", speed=0.95, lang="en-us")
    sf.write(args.out / "kokoro-raw.wav", audio, rate)
    (args.out / "script.txt").write_text(SCRIPT)
    # Constant child entry point, text through stdin; no application configuration changes.
    entry = "from pathlib import Path; import sys; from trend_sniper.production.legacy_piper import synthesize; synthesize(sys.stdin.read(),Path(sys.argv[1]),Path('local-data'))"
    subprocess.run(
        [
            str(args.piper_python.absolute()),
            "-c",
            entry,
            str((args.out / "piper-raw.wav").resolve()),
        ],
        input=SCRIPT,
        text=True,
        capture_output=True,
        check=True,
        timeout=45,
    )
    ffmpeg = subprocess.run(
        [
            str(args.piper_python.absolute()),
            "-c",
            "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    results = []
    for name in ["piper", "kokoro"]:
        target = args.out / (name + ".wav")
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-i",
                str(args.out / (name + "-raw.wav")),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=7",
                "-ar",
                "24000",
                "-ac",
                "1",
                str(target),
            ],
            capture_output=True,
            check=True,
            timeout=20,
        )
        with wave.open(str(target)) as wav:
            duration = wav.getnframes() / wav.getframerate()
        results.append(
            {
                "provider": name,
                "duration_seconds": round(duration, 3),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    report = {
        "script": SCRIPT,
        "processing": "Same text, mono 24 kHz; loudnorm target -16 LUFS, no music or time stretching.",
        "piper": "Existing LJ English, length scale 0.92",
        "kokoro": "Kokoro-82M v1.0 int8 ONNX, af_heart, speed 0.95",
        "cloud": "Skipped: no configured credentials or verified free allowance.",
        "paid_api_usd": 0,
        "audition_only": True,
        "model_provenance": json.loads((args.models / "models.json").read_text()),
        "samples": results,
    }
    (args.out / "comparison.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
