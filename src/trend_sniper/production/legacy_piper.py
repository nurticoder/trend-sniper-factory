"""Optional offline speech via a separately installed Piper command-line engine."""

import importlib.metadata
import subprocess
import sys

from ..core import digest

VOICE = "en_US-ljspeech-medium"
REVISION = "e7229f7d33a10e145e109b886d661984201ac3c4"
SOURCE = f"https://huggingface.co/rhasspy/piper-voices/tree/{REVISION}/en/en_US/ljspeech/medium"
RATE = 24000
# Pinned upstream bytes; never accept arbitrary executable/model paths from an HTTP request.
FILES = {
    VOICE
    + ".onnx.json": "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860",
    "MODEL_CARD": "fbee1529c89d36b3fe76d7e9f3f832dce17f44900a52d76a9bda735654766b4d",
    VOICE + ".onnx": "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
}
ENGINE_VERSION = "1.8.0"


def voice_folder(inputs):
    return inputs / "voices" / VOICE


def availability(inputs):
    try:
        version = importlib.metadata.version("piper-tts")
    except importlib.metadata.PackageNotFoundError:
        return {"available": False, "detail": "Optional Piper engine is not installed."}
    if version != ENGINE_VERSION:
        return {
            "available": False,
            "detail": "Install the tested Piper engine version " + ENGINE_VERSION + ".",
        }
    folder = voice_folder(inputs)
    for name, expected in FILES.items():
        path = folder / name
        if not path.is_file():
            return {
                "available": False,
                "detail": "The licensed local voice has not been installed.",
            }
        try:
            matches = digest(path) == expected
        except OSError:
            return {
                "available": False,
                "detail": "Voice files cannot be read. Check the local installation.",
            }
        if not matches:
            return {
                "available": False,
                "detail": "Voice files changed. Reinstall the pinned voice before using narration.",
            }
    return {
        "available": True,
        "detail": "LJ Speech · English · local Piper " + version,
        "voice": VOICE,
        "source": SOURCE,
        "model_license": "MIT",
        "dataset_license": "public-domain (US)",
    }


def synthesize(text, destination, inputs):
    folder = voice_folder(inputs)
    # Disable the runtime's telemetry in the child. No scripts or text are sent to a service.
    entry = "import onnxruntime; onnxruntime.disable_telemetry_events(); import runpy; runpy.run_module('piper', run_name='__main__')"
    subprocess.run(
        [
            sys.executable,
            "-c",
            entry,
            "-m",
            str(folder / (VOICE + ".onnx")),
            "-c",
            str(folder / (VOICE + ".onnx.json")),
            "-f",
            str(destination),
            "--length-scale",
            "0.92",
            "--sentence-silence",
            "0.08",
        ],
        input=text,
        text=True,
        capture_output=True,
        check=True,
        timeout=40,
    )
