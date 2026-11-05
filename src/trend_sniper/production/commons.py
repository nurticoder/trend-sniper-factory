"""Bounded Commons retrieval. Only source-declared CC0 stills and visually verified footage qualify."""

import hashlib
import html
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

from .fragments import locate
from .materials import terms


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def retrieve(url, limit):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in {
        "commons.wikimedia.org",
        "upload.wikimedia.org",
    }:
        raise ValueError("Unexpected Commons host")
    request = Request(
        url,
        headers={
            "User-Agent": "TrendSniperFactory/0.3 (https://github.com/nurticoder/trend-sniper-factory)"
        },
    )
    with build_opener(NoRedirect).open(request, timeout=3) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Commons response too large")
    return raw


def search(query, folder, length=6):
    words = sorted(terms(query), key=lambda word: (-len(word), word))[:4]
    if len(words) < 2:
        return []
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": " ".join(words),
        "gsrnamespace": 6,
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
    }
    response = json.loads(
        retrieve(
            "https://commons.wikimedia.org/w/api.php?" + urlencode(params), 512_000
        )
    )
    results = []
    for page in response.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})
        title = page.get("title", "").removeprefix("File:")

        def field(key, metadata=metadata):
            return html.unescape(
                re.sub("<[^>]+>", "", metadata.get(key, {}).get("value", ""))
            ).strip()

        if field("LicenseShortName") not in {"CC0", "CC0 1.0"} or field("Restrictions"):
            continue
        mime = info.get("mime")
        if mime not in {"image/jpeg", "image/png", "video/webm", "video/ogg"}:
            continue
        video = mime.startswith("video/")
        byte_limit = 12_000_000 if video else 6_000_000
        if not 0 < info.get("size", 0) <= byte_limit:
            continue
        if len(terms(title) & terms(query)) < 2 or not field("Artist"):
            continue
        raw = retrieve(info["url"], byte_limit)
        sha = hashlib.sha256(raw).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / sha
        path.write_bytes(raw)
        start, end = 0, 0
        if video:
            try:
                window = locate(path, query, length)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                window = None
            if not window:
                continue
            start, end = window
        else:
            with Image.open(path) as img:
                if img.width * img.height > 20_000_000:
                    continue
                img.verify()
        results.append(
            {
                "file": sha,
                "path": str(path),
                "description": title,
                "source": info["descriptionurl"],
                "license": "CC0-1.0",
                "credit": field("Artist"),
                "evidence": info["descriptionurl"],
                "evidence_snapshot": {
                    "license": field("LicenseShortName"),
                    "license_url": field("LicenseUrl"),
                    "artist": field("Artist"),
                    "file_url": info["url"],
                    "checked_at": datetime.now(UTC).isoformat(),
                },
                "sha256": sha,
                "kind": "video" if video else "photo",
                "start": start,
                "end": end,
            }
        )
        break
    return results


def search_footage(query, folder):
    """Return bounded licensed video candidates, never claim semantic verification.

    This path uses a scene brief, supports attribution-bearing CC BY 4.0 and
    keeps candidates available for targeted review without requiring a vision model.
    """
    from .fragments import duration

    query_terms = terms(query)
    if not query_terms:
        return []
    receipt = folder / ("query-" + hashlib.sha256(query.encode()).hexdigest() + ".json")
    if receipt.is_file():
        try:
            cached = json.loads(receipt.read_text())
            age = (
                datetime.now(UTC) - datetime.fromisoformat(cached["checked_at"])
            ).total_seconds()
            if (
                0 <= age < 86400
                and cached["candidates"]
                and all(
                    Path(a["path"]).resolve().is_relative_to(folder.resolve())
                    and digest_bytes(Path(a["path"])) == a["sha256"]
                    for a in cached["candidates"]
                )
            ):
                return cached["candidates"]
        except (ValueError, KeyError, OSError, TypeError):
            pass
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query + " filetype:video",
        "gsrnamespace": 6,
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
    }
    data = json.loads(
        retrieve(
            "https://commons.wikimedia.org/w/api.php?" + urlencode(params), 512_000
        )
    )
    candidates = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})

        def field(name, metadata=metadata):
            return html.unescape(
                re.sub("<[^>]+>", "", metadata.get(name, {}).get("value", ""))
            ).strip()

        license_name = {
            "CC0": "CC0-1.0",
            "CC0 1.0": "CC0-1.0",
            "CC BY 4.0": "CC-BY-4.0",
        }.get(field("LicenseShortName"))
        title = page.get("title", "").removeprefix("File:")
        if not license_name or field("Restrictions") or not field("Artist"):
            continue
        if (
            info.get("mime") not in {"video/webm", "video/ogg", "video/mp4"}
            or not 0 < info.get("size", 0) <= 30_000_000
        ):
            continue
        if len(query_terms & terms(title)) < min(2, len(query_terms)):
            continue
        if (
            license_name == "CC-BY-4.0"
            and field("LicenseUrl").rstrip("/")
            != "https://creativecommons.org/licenses/by/4.0"
        ):
            continue
        raw = retrieve(info["url"], 30_000_000)
        sha = hashlib.sha256(raw).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / sha
        if not path.exists() or digest_bytes(path) != sha:
            path.write_bytes(raw)
        seconds = duration(path)
        if not 0.5 <= seconds <= 600:
            continue
        candidates.append(
            {
                "id": "media-" + sha,
                "path": str(path),
                "sha256": sha,
                "source": info["descriptionurl"],
                "credit": field("Artist"),
                "license": license_name,
                "license_url": field("LicenseUrl"),
                "description": title,
                "start": 0,
                "end": min(seconds, 90),
                "evidence": info["descriptionurl"],
                "kind": "video",
                "evidence_snapshot": {
                    "license": field("LicenseShortName"),
                    "artist": field("Artist"),
                    "file_url": info["url"],
                    "checked_at": datetime.now(UTC).isoformat(),
                },
                "review_status": "Candidate only; inspect the subject, action and intended use",
            }
        )
        if len(candidates) == 2:
            break
    if candidates:
        receipt.write_text(
            json.dumps(
                {"checked_at": datetime.now(UTC).isoformat(), "candidates": candidates}
            )
        )
    return candidates


def digest_bytes(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
