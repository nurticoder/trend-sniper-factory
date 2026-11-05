"""Small authenticated control messages and streamed media, never a desktop media cache."""

import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..core import write_json

ARTIFACTS = {
    "short.mp4",
    "cover.jpg",
    "narration.wav",
    "metadata.json",
    "metadata.txt",
    "script.json",
    "review.json",
    "manifest.json",
    "captions.srt",
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def config_path(inputs):
    return inputs / "remote-worker.json"


def configuration(inputs):
    path = config_path(inputs)
    if not path.is_file():
        raise ValueError(
            "Connect a remote worker in Factory services. No footage was downloaded to this computer."
        )
    value = json.loads(path.read_text())
    url = urlsplit(value.get("url", ""))
    if (
        url.scheme != "https"
        or not url.hostname
        or not url.hostname.endswith(".hf.space")
        or url.username
        or url.password
        or url.port not in {None, 443}
    ):
        raise ValueError(
            "Worker URL must be its authenticated Hugging Face HTTPS address"
        )
    if len(value.get("key", "")) < 32:
        raise ValueError("Remote worker authentication is missing")
    return value


def save_configuration(inputs, value, pending=False):
    if pending and not re.fullmatch("[a-f0-9]{32}", str(pending)):
        raise ValueError("Invalid account-setup identity")
    path = (
        inputs / ("remote-setup-" + pending + ".json")
        if pending
        else config_path(inputs)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never rely on the caller's umask for an account credential.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output)


def call(config, path, method="GET", body=None, headers=None, timeout=20):
    if not path.startswith("/") or ".." in path:
        raise ValueError("Invalid worker route")
    auth = {
        "X-Factory-Key": config["key"],
        "Authorization": "Bearer " + config.get("hf_token", ""),
        **(headers or {}),
    }
    if body is not None:
        auth["Content-Type"] = "application/json"
    request = Request(
        config["url"].rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=auth,
        method=method,
    )
    return build_opener(NoRedirect).open(request, timeout=timeout)


def json_call(config, path, method="GET", body=None):
    with call(config, path, method, body) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Worker control response exceeds its size budget")
    return json.loads(raw)


def execute(intent, folder, inputs, stage, mode="automatic", voice="steady"):
    config = configuration(inputs)
    pointer = folder / "remote.json"
    body = {"request_id": folder.name, "intent": intent, "mode": mode, "voice": voice}
    deadline = time.monotonic() + 7200
    last_stage = None

    def control(path, method="GET", payload=None):
        nonlocal last_stage
        retry_until = min(deadline, time.monotonic() + 600)
        waiting = False
        while True:
            stage(
                None
            )  # Cancellation check without thousands of duplicate history rows.
            try:
                result = json_call(config, path, method, payload)
                if waiting:
                    last_stage = None
                return result
            except (OSError, json.JSONDecodeError) as exc:
                if isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                    exc.close()
                    raise
                if time.monotonic() >= retry_until:
                    raise
                if isinstance(exc, HTTPError):
                    exc.close()
                if not waiting:
                    stage(
                        "Waiting for the remote worker to start or reconnect; no local media fallback"
                    )
                    waiting = True
                time.sleep(3)

    def remember(value):
        if not re.fullmatch(r"[a-f0-9]{32}", value.get("id", "")):
            raise ValueError("Worker returned an invalid job identity")
        folder.mkdir(parents=True, exist_ok=True)
        write_json(
            pointer, {"id": value["id"], "url": config["url"], "local_job": folder.name}
        )
        return value["id"]

    if pointer.is_file():
        remote = json.loads(pointer.read_text())
        if remote["url"] != config["url"]:
            raise ValueError(
                "This job belongs to another worker; reconnect its original worker before resuming"
            )
        job = remote["id"]
        if not re.fullmatch(r"[a-f0-9]{32}", job):
            raise ValueError("Invalid saved worker job identity")
        if remote.get("local_job", folder.name) != folder.name:
            try:
                state = control("/jobs/" + job)
                if state["status"] in {"failed", "cancelled"}:
                    job = remember(control("/jobs/" + job + "/retry", "POST"))
                elif state["status"] == "expired":
                    job = remember(control("/jobs", "POST", body))
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                exc.close()
                job = remember(control("/jobs", "POST", body))
    else:
        stage(
            "Sending production to the remote worker; source footage stays off this computer"
        )
        job = remember(control("/jobs", "POST", body))
    if not re.fullmatch(r"[a-f0-9]{32}", job):
        raise ValueError("Worker returned an invalid job identity")
    try:
        while time.monotonic() < deadline:
            try:
                state = control("/jobs/" + job)
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                exc.close()
                stage("Remote worker restarted; restoring the saved production request")
                job = remember(control("/jobs", "POST", body))
                continue
            current_stage = state.get("stage") or state["status"]
            if current_stage != last_stage:
                stage("Remote factory: " + current_stage[:200])
                last_stage = current_stage
            if state["status"] == "ready":
                for asset in [
                    "script.json",
                    "review.json",
                    "manifest.json",
                    "metadata.json",
                ]:
                    write_json(
                        folder / asset, control(f"/jobs/{job}/artifacts/{asset}")
                    )
                script = json.loads((folder / "script.json").read_text())
                return {
                    **script,
                    "remote": {"id": job, "expires_at": state.get("expires_at")},
                }
            if state["status"] in {"failed", "cancelled", "expired"}:
                raise ValueError(
                    "Remote factory could not finish: "
                    + state.get("error", state["status"])[:500]
                )
            time.sleep(2)
    except BaseException as exc:
        from ..production.jobs import Cancelled

        if isinstance(exc, Cancelled):
            try:
                json_call(config, f"/jobs/{job}/cancel", "POST")
            except (OSError, ValueError):
                pass
        raise
    raise ValueError(
        "Remote production reached its startup/production time limit; its saved job can be inspected or retried"
    )


def artifact_response(inputs, folder, asset, range_header=None):
    if asset not in ARTIFACTS:
        raise ValueError("Unknown preview artifact")
    remote = json.loads((folder / "remote.json").read_text())
    if not re.fullmatch(r"[a-f0-9]{32}", remote["id"]):
        raise ValueError("Invalid remote job")
    headers = {}
    if range_header:
        if not re.fullmatch(r"bytes=\d*-\d*", range_header):
            raise ValueError("Only one valid media range is supported")
        headers["Range"] = range_header
    response = call(
        configuration(inputs),
        f"/jobs/{remote['id']}/artifacts/{asset}",
        headers=headers,
    )
    return response
