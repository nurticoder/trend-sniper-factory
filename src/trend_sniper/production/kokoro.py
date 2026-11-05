"""The selected local voice. Setup is explicit; production never downloads models."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from ..core import digest, write_json

VOICE = "af_heart"
SOURCE = "https://huggingface.co/hexgrad/Kokoro-82M"
RELEASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
)
FILES = {
    "kokoro-v1.0.int8.onnx": "6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def voice_folder(inputs):
    return inputs / "voices" / "kokoro-82m-v1.0"


def availability(inputs):
    try:
        if importlib.metadata.version("kokoro-onnx") != "0.4.7":
            raise ValueError(
                "Install the tested Kokoro runtime: pip install -e '.[voice]'."
            )
        for name, checksum in FILES.items():
            path = voice_folder(inputs) / name
            if not path.is_file() or digest(path) != checksum:
                raise ValueError(
                    "Kokoro model missing or changed. Run trend-sniper install-voice."
                )
    except (importlib.metadata.PackageNotFoundError, OSError, ValueError) as exc:
        return {"available": False, "detail": str(exc)}
    return {
        "available": True,
        "detail": "Kokoro-82M · af_heart · local ONNX 0.4.7",
        "voice": VOICE,
        "source": SOURCE,
        "model_license": "Apache-2.0",
        "runner_license": "MIT",
    }


def install(inputs):
    destination = voice_folder(inputs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if all(
            (destination / n).is_file() and digest(destination / n) == sha
            for n, sha in FILES.items()
        ):
            return destination
        raise ValueError(
            "Existing Kokoro directory is incomplete or changed; preserve it before reinstalling."
        )
    with TemporaryDirectory(dir=destination.parent, prefix=".kokoro-") as tmp:
        folder = Path(tmp) / "model"
        folder.mkdir()
        for name, checksum in FILES.items():
            with (
                urlopen(RELEASE + name, timeout=40) as response,
                (folder / name).open("wb") as output,
            ):
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 100_000_000:
                        raise ValueError("Kokoro download exceeds model budget")
                    output.write(block)
            if digest(folder / name) != checksum:
                raise ValueError("Downloaded Kokoro model failed checksum verification")
        write_json(
            folder / "provenance.json",
            {
                "source": SOURCE,
                "release": RELEASE,
                "sha256": FILES,
                "model_license": "Apache-2.0",
                "runner_license": "MIT",
                "selected_voice": VOICE,
            },
        )
        folder.rename(destination)
    return destination


def synthesize(text, destination, inputs, speed=0.95):
    if not 0.8 <= float(speed) <= 1.2 or not 1 <= len(text) <= 450:
        raise ValueError("Speech request outside the supported delivery budget")
    info = availability(inputs)
    if not info["available"]:
        raise ValueError(info["detail"])
    # A bounded child keeps model memory out of the HTTP process. Text travels via stdin.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "trend_sniper.production.kokoro",
            str(voice_folder(inputs)),
            str(destination),
            str(speed),
        ],
        input=text,
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )


if __name__ == "__main__":
    import onnxruntime

    onnxruntime.disable_telemetry_events()
    import soundfile
    from kokoro_onnx import Kokoro

    folder = Path(sys.argv[1])
    engine = Kokoro(
        str(folder / "kokoro-v1.0.int8.onnx"), str(folder / "voices-v1.0.bin")
    )
    audio, rate = engine.create(
        sys.stdin.read(), voice=VOICE, speed=float(sys.argv[3]), lang="en-us"
    )
    soundfile.write(sys.argv[2], audio, rate, subtype="PCM_16")
