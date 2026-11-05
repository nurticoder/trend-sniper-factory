"""Deploy only CPU Basic to an eligible existing Hugging Face account. Never buy a plan."""

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
        "Checking account eligibility and CPU Basic hardware; no paid plan will be purchased"
    )
    account = hf(token, "whoami-v2")
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
            hardware.get(k) not in {None, "cpu-basic"} for k in ["current", "requested"]
        ):
            raise ValueError(
                "Existing Space uses paid hardware. Choose an existing CPU Basic worker; billing was not changed"
            )
    except HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        try:
            # Let the provider check account eligibility, including existing/grandfathered entitlements.
            # This requests zero-hourly-cost CPU Basic. There is no subscription/upgrade API call.
            hf(
                token,
                "repos/create",
                "POST",
                {
                    "type": "space",
                    "name": config["space_name"],
                    "private": True,
                    "sdk": "docker",
                    "hardware": "cpu-basic",
                },
            )
        except HTTPError as error:
            if error.code in {402, 403}:
                error.close()
                raise ValueError(
                    "This account cannot create a CPU Basic compute Space under current Hugging Face eligibility rules. No plan was purchased. Use an existing eligible Space or another remote host."
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
