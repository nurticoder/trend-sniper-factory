"""Install only the official CPU runtime on the remote Gradio host, without root."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen


def ensure_ollama(root):
    if os.environ.get("TSF_WORKER_PROCESS") != "1" or not os.environ.get("SPACE_ID"):
        raise ValueError(
            "Runtime setup is restricted to the remote Hugging Face worker"
        )
    existing = shutil.which("ollama")
    if existing:
        return existing
    root = Path(root) / "runtime"
    binary = root / "bin" / "ollama"
    if binary.is_file():
        return str(binary)
    root.mkdir(parents=True, exist_ok=True)
    request = Request(
        "https://api.github.com/repos/ollama/ollama/releases/latest",
        headers={"User-Agent": "TrendSniperFactory"},
    )
    with urlopen(request, timeout=30) as response:
        release = json.loads(response.read(2_000_000))
    asset = next(
        a for a in release["assets"] if a["name"] == "ollama-linux-amd64.tar.zst"
    )
    checksum = asset.get("digest", "").removeprefix("sha256:")
    if len(checksum) != 64 or asset["size"] > 2_000_000_000:
        raise ValueError("Official runtime metadata lacks a supported size/checksum")
    url = asset["browser_download_url"]
    if not url.startswith("https://github.com/ollama/ollama/releases/download/"):
        raise ValueError("Unexpected runtime publisher")
    archive = root / "runtime.tar.zst"
    digest = hashlib.sha256()
    try:
        with (
            urlopen(
                Request(url, headers={"User-Agent": "TrendSniperFactory"}), timeout=60
            ) as source,
            archive.open("wb") as output,
        ):
            size = 0
            while block := source.read(1024 * 1024):
                size += len(block)
                if size > asset["size"]:
                    raise ValueError("Remote runtime download exceeds declared size")
                digest.update(block)
                output.write(block)
        if size != asset["size"] or digest.hexdigest() != checksum:
            raise ValueError("Remote runtime checksum failed")
        subprocess.run(
            ["tar", "--zstd", "-xf", str(archive), "-C", str(root)],
            check=True,
            capture_output=True,
            timeout=180,
        )
        if not binary.is_file():
            raise ValueError("Official runtime binary missing after extraction")
        (root / "provenance.json").write_text(
            json.dumps({"source": url, "sha256": checksum})
        )
    finally:
        archive.unlink(missing_ok=True)
    return str(binary)
