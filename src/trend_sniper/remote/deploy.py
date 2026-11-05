"""Deploy eligible zero-hourly-cost HF hardware only. Never buy a plan or credits."""

import base64
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .client import save_configuration


def hf(token, path, method="GET", body=None, ndjson=False):
    request = Request(
        "https://huggingface.co/api/" + path,
        method=method,
        data=(body if ndjson else json.dumps(body).encode())
        if body is not None
        else None,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/x-ndjson" if ndjson else "application/json",
        },
    )
    with urlopen(request, timeout=40) as response:
        return json.loads(response.read(2_000_000))


def deploy(config, inputs, stage):
    token = config["hf_token"]
    stage(
        "Checking free hosting eligibility; no paid plan, credits or hardware will be purchased"
    )
    account = hf(token, "whoami-v2")
    free_gradio = config.get("hosting") == "zero-gradio"
    hardware_name = "zero-a10g" if free_gradio else "cpu-basic"
    sdk = "gradio" if free_gradio else "docker"
    name = account["name"]
    space_id = name + "/" + config["space_name"]
    try:
        info = hf(token, "spaces/" + space_id)
        tags = (info.get("cardData") or {}).get("tags") or []
        if "trend-sniper-factory-worker" not in tags:
            raise ValueError(
                "This Space already contains another project; it will not be overwritten"
            )
        hardware = (info.get("runtime") or {}).get("hardware") or {}
        if any(
            hardware.get(k) not in {None, hardware_name}
            for k in ["current", "requested"]
        ):
            raise ValueError(
                "Existing Space uses different or paid hardware. Choose a matching free worker; billing was not changed"
            )
    except HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        try:
            # Let the provider check account eligibility, including existing/grandfathered entitlements.
            # Both allowed hardware choices have no hourly price. No plan/credit API is called.
            hf(
                token,
                "repos/create",
                "POST",
                {
                    "type": "space",
                    "name": config["space_name"],
                    "private": True,
                    "sdk": sdk,
                    "hardware": hardware_name,
                },
            )
        except HTTPError as error:
            if error.code in {402, 403}:
                error.close()
                raise ValueError(
                    "This account cannot create the requested free worker Space under current Hugging Face eligibility rules. No plan was purchased. Use an eligible Space or another remote host."
                ) from error
            raise
    stage("Installing the private worker secret and uploading application code only")
    hf(
        token,
        "spaces/" + space_id + "/secrets",
        "POST",
        {"key": "TSF_WORKER_KEY", "value": config["key"]},
    )
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "src"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    files = {
        name: root / name
        for name in tracked
        if name
        and not (root / name).is_symlink()
        and (root / name).resolve().is_relative_to((root / "src").resolve())
        and (root / name).suffix in {".py", ".js", ".css", ".html", ".svg", ".json"}
    }
    for filename in ["pyproject.toml", "LICENSE", "THIRD_PARTY_NOTICES.md"]:
        files[filename] = root / filename
    files["Dockerfile"] = root / "deploy" / "worker.Dockerfile"
    files["README.md"] = root / "deploy" / "space-README.md"
    if free_gradio:
        del files["Dockerfile"]
        files.update(
            {
                "README.md": root / "deploy/gradio-README.md",
                "app.py": root / "deploy/gradio-app.py",
                "requirements.txt": root / "deploy/gradio-requirements.txt",
                "packages.txt": root / "deploy/gradio-packages.txt",
            }
        )
    rows = [{"key": "header", "value": {"summary": "Deploy autonomous footage worker"}}]
    total = 0
    for path, file in files.items():
        raw = file.read_bytes()
        total += len(raw)
        if total > 5_000_000:
            raise ValueError(
                "Worker source bundle unexpectedly large; no local media will be uploaded"
            )
        rows.append(
            {
                "key": "file",
                "value": {
                    "content": base64.b64encode(raw).decode(),
                    "path": path,
                    "encoding": "base64",
                },
            }
        )
    hf(
        token,
        "spaces/" + space_id + "/commit/main",
        "POST",
        b"\n".join(json.dumps(r).encode() for r in rows) + b"\n",
        ndjson=True,
    )
    info = hf(token, "spaces/" + space_id)
    url = info.get("host")
    if not url:
        raise ValueError(
            "Space is building but its worker address is not available yet; reconnect to check deployment"
        )
    config.update(
        url=url if url.startswith("https://") else "https://" + url, space_id=space_id
    )
    save_configuration(inputs, config)
    return {
        "title": "Remote worker deployed; waiting for startup",
        "delivery": "configuration",
        "space_id": space_id,
    }
