"""Bounded Commons retrieval. Only source-declared CC0 stills and visually verified footage qualify."""

import hashlib
import html
import json
import re
import subprocess
from datetime import UTC, datetime
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
