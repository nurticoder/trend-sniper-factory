"""Explicit, pinned model setup. Production never downloads a speech model."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from ..core import digest
from .narration import FILES, REVISION, SOURCE, VOICE, voice_folder


def install(inputs):
    destination = voice_folder(inputs)
    if destination.exists():
        if all(
            (destination / name).is_file() and digest(destination / name) == checksum
            for name, checksum in FILES.items()
        ):
            return destination
        raise ValueError(
            "Existing voice directory is incomplete or changed. Preserve/remove it before reinstalling."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent, prefix=".download-") as tmp:
        folder = Path(tmp) / VOICE
        folder.mkdir()
        for name, expected in FILES.items():
            url = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_US/ljspeech/medium/{name}"
            size = 0
            limit = 65_000_000 if name.endswith(".onnx") else 20_000
            with (
                urlopen(url, timeout=40) as response,
                (folder / name).open("wb") as output,
            ):
                while block := response.read(1024 * 1024):
                    size += len(block)
                    if size > limit:
                        raise ValueError("Voice download exceeds the pinned size limit")
                    output.write(block)
            if digest(folder / name) != expected:
                raise ValueError("Downloaded voice failed checksum verification")
        (folder / "provenance.json").write_text(
            json.dumps(
                {
                    "source": SOURCE,
                    "revision": REVISION,
                    "sha256": FILES,
                    "model_license": "MIT (upstream repository declaration)",
                    "dataset_license": "Public domain in the US; see exact MODEL_CARD",
                    "dataset_source": "https://keithito.com/LJ-Speech-Dataset/",
                    "engine_source": "https://github.com/OHF-Voice/piper1-gpl",
                    "engine_license": "GPL-3.0-or-later; installed separately, not redistributed",
                },
                indent=2,
            )
        )
        folder.rename(destination)
    return destination
