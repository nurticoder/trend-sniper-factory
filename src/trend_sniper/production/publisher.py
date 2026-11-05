"""Optional owner-OAuth transport. Only an explicit reviewed release runs this."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import copyfile
from tempfile import NamedTemporaryFile, TemporaryDirectory

from ..queue import snapshot

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def save_secret(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, encoding="utf-8"
    ) as tmp:
        os.chmod(tmp.name, 0o600)
        tmp.write(content)
    os.replace(tmp.name, path)


def identify(service):
    items = service.channels().list(part="id,snippet", mine=True).execute()["items"]
    if len(items) != 1:
        raise ValueError("Select exactly one creator channel during authorization")
    return {"id": items[0]["id"], "name": items[0]["snippet"]["title"]}


def connect(client_file, folder):
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    credentials = flow.run_local_server(host="127.0.0.1", port=0)
    channel = identify(
        build("youtube", "v3", credentials=credentials, cache_discovery=False)
    )
    save_secret(folder / "token-youtube.json", credentials.to_json())
    save_secret(folder / "channel.json", json.dumps(channel))
    return channel


def request_body(folder, at, made_for_kids, synthetic):
    if at.tzinfo is None or at <= datetime.now(UTC):
        raise ValueError("Choose a future release time with a timezone")
    meta = json.loads((folder / "metadata.json").read_text())
    desc = (
        meta["description"] + "\n\n" + " ".join("#" + tag for tag in meta["hashtags"])
    )
    if len(desc.encode()) > 5000 or len(meta["title"]) > 100:
        raise ValueError(
            "Upload copy exceeds the platform limit. Review and regenerate."
        )
    return {
        "snippet": {
            "title": meta["title"],
            "description": desc,
            "tags": meta["hashtags"],
            "categoryId": "24",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": at.astimezone(UTC).isoformat(),
            "selfDeclaredMadeForKids": made_for_kids,
            "containsSyntheticMedia": synthetic,
        },
    }


def prepare_transport(auth_dir, expected_channel):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token = auth_dir / "token-youtube.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds.expired:
        creds.refresh(Request())
        save_secret(token, creds.to_json())
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    if identify(service)["id"] != expected_channel:
        raise ValueError("Connected channel changed. Review the destination again.")

    def upload(movie, body):
        media = MediaFileUpload(
            str(movie), mimetype="video/mp4", resumable=True, chunksize=4 * 1024 * 1024
        )
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        result = None
        while result is None:
            _, result = request.next_chunk(num_retries=0)
        return result

    return upload


def release_worker(store, folder, job, auth_dir, approved, transport=None):
    """Persist the ambiguous window before submitting bytes. Never blind-retry."""
    with store.connection() as db:
        claim = db.execute(
            "UPDATE releases SET state='preparing' WHERE job=? AND state='awaiting_upload'",
            (job,),
        )
        if claim.rowcount != 1:
            return
    state = "preflight_failed"
    try:
        uploader = (transport or prepare_transport)(auth_dir, approved["channel"])
        # Freeze exactly the approved bytes before the external write. Changes
        # in the source folder during a later upload cannot alter the payload.
        with TemporaryDirectory(prefix="tsf-release-") as tmp:
            frozen = Path(tmp)
            for name in (
                "short.mp4",
                "script.json",
                "metadata.json",
                "captions.srt",
                "manifest.json",
            ):
                copyfile(folder / name, frozen / name)
            if snapshot(frozen) != approved["hashes"]:
                raise ValueError("Reviewed artifacts changed")
            at = datetime.fromisoformat(approved["at"])
            if at < datetime.now(UTC) + timedelta(minutes=10):
                raise ValueError("Insufficient time left for a scheduled upload")
            body = request_body(frozen, at, approved["kids"], approved["synthetic"])
            with store.connection() as db:
                db.execute("UPDATE releases SET state='submitting' WHERE job=?", (job,))
            state = "check_youtube_studio"
            receipt = uploader(frozen / "short.mp4", body)
        video_id = receipt["id"]
        remote_status = receipt.get("status", {})
        if not video_id:
            raise ValueError("Missing remote video ID")
        with store.connection() as db:
            db.execute("UPDATE releases SET remote_id=? WHERE job=?", (video_id, job))
        returned_time = remote_status.get("publishAt")
        confirmed = bool(
            returned_time
            and remote_status.get("privacyStatus") == "private"
            and datetime.fromisoformat(returned_time)
            == datetime.fromisoformat(approved["at"])
        )
        state = "scheduled" if confirmed else "verify_remote_schedule"
        with store.connection() as db:
            db.execute(
                "UPDATE releases SET state=?,remote_id=? WHERE job=?",
                (state, video_id, job),
            )
    except Exception as exc:  # noqa: BLE001 -- persist every ambiguous transport outcome
        # Provider exceptions can contain token-bearing URLs. Store only safe failure classes.
        with store.connection() as db:
            db.execute(
                "UPDATE releases SET state=?,error=? WHERE job=?",
                (state, type(exc).__name__, job),
            )
            if state == "preflight_failed":
                db.execute("UPDATE releases SET day=NULL,sha=NULL WHERE job=?", (job,))
