"""Permission-aware source searches, semantic window inspection and remote-only cuts."""

import json
import re
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from ..core import digest
from ..production import commons
from ..production.explainer import command
from ..production.fragments import duration, verify_window
from .editorial import get_json


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + 2700
        self.searches = 0
        self.inspected = 0
        self.downloaded = 0

    def check(self):
        if (
            time.monotonic() > self.deadline
            or self.searches > 36
            or self.inspected > 24
            or self.downloaded > 1_000_000_000
        ):
            raise ValueError(
                "Remote job reached its search/time/storage budget; no unsuitable footage was substituted"
            )


def download(url, folder, budget, hosts, limit=45_000_000):
    budget.check()
    host = urlsplit(url).hostname or ""
    if not url.startswith("https://") or not any(
        host == h or host.endswith("." + h) for h in hosts
    ):
        raise ValueError("Unapproved source-media host")
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / (uuid4().hex + ".download")
    try:
        with (
            urlopen(
                Request(url, headers={"User-Agent": "TrendSniperFactory/0.4"}),
                timeout=20,
            ) as response,
            temp.open("wb") as output,
        ):
            redirected = urlsplit(response.url).hostname or ""
            if not any(redirected == h or redirected.endswith("." + h) for h in hosts):
                raise ValueError("Unapproved media redirect")
            size = 0
            while block := response.read(256 * 1024):
                size += len(block)
                budget.downloaded += len(block)
                if size > limit:
                    raise ValueError("Candidate exceeds remote download limit")
                budget.check()
                output.write(block)
        target = folder / digest(temp)
        temp.replace(target)
        return target
    finally:
        temp.unlink(missing_ok=True)


def archive(query, folder, budget):
    licenses = {
        "https://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
        "https://creativecommons.org/licenses/by/4.0/": "CC-BY-4.0",
        "https://creativecommons.org/licenses/by/3.0/": "CC-BY-3.0",
    }
    safe_query = " ".join(re.findall(r"[\w-]+", query))
    search = get_json(
        "https://archive.org/advancedsearch.php?"
        + urlencode(
            {
                "q": safe_query + " AND mediatype:movies AND licenseurl:*",
                "output": "json",
                "rows": 4,
            }
        )
    )
    for row in search.get("response", {}).get("docs", []):
        identifier = row.get("identifier", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", identifier):
            continue
        data = get_json("https://archive.org/metadata/" + identifier)
        meta = data.get("metadata", {})
        declared = meta.get("licenseurl", "")
        if isinstance(declared, list):
            declared = declared[0] if declared else ""
        declared = declared.replace("http://", "https://").rstrip("/") + "/"
        if declared not in licenses or not meta.get("creator"):
            continue
        files = [
            f
            for f in data.get("files", [])
            if f.get("name", "").endswith(".mp4")
            and 0 < int(f.get("size", 0)) <= 45_000_000
        ]
        if not files:
            continue
        item = min(files, key=lambda f: int(f["size"]))
        path = download(
            "https://archive.org/download/"
            + identifier
            + "/"
            + quote(item["name"], safe=""),
            folder,
            budget,
            {"archive.org"},
        )
        credit = meta["creator"]
        if isinstance(credit, list):
            credit = ", ".join(credit)
        yield {
            "path": str(path),
            "sha256": digest(path),
            "source": "https://archive.org/details/" + identifier,
            "description": str(meta.get("title", identifier)),
            "credit": str(credit),
            "license": licenses[declared],
            "license_url": declared,
            "evidence": {"licenseurl": meta["licenseurl"], "creator": credit},
            "source_start": 0,
        }


def nasa(query, folder, budget):
    result = get_json(
        "https://images-api.nasa.gov/search?"
        + urlencode({"q": query, "media_type": "video", "page_size": 3})
    )
    for item in result.get("collection", {}).get("items", [])[:3]:
        info = item.get("data", [{}])[0]
        identity = info.get("nasa_id", "")
        if not re.fullmatch(r"[\w-]{1,160}", identity):
            continue
        base = "https://images-assets.nasa.gov/video/" + identity + "/"
        metadata = get_json(base + "metadata.json")
        if metadata.get("AVAIL:SecondaryCreator") or not metadata.get("AVAIL:Center"):
            continue
        collection = get_json("https://images-api.nasa.gov/asset/" + identity)
        urls = [
            r.get("href", "") for r in collection.get("collection", {}).get("items", [])
        ]
        video = next((u for u in urls if u.endswith("~medium.mp4")), None)
        if not video:
            continue
        path = download(video, folder, budget, {"images-assets.nasa.gov"}, 85_000_000)
        yield {
            "path": str(path),
            "sha256": digest(path),
            "source": "https://images.nasa.gov/details/" + identity,
            "description": info.get("description", info.get("title", identity)),
            "credit": "NASA / " + metadata["AVAIL:Center"],
            "license": "NASA informational/editorial use under media guidelines",
            "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
            "evidence": {
                k: metadata.get(k)
                for k in [
                    "AVAIL:Center",
                    "AVAIL:SecondaryCreator",
                    "AVAIL:Copyright",
                    "AVAIL:UsageTerms",
                    "AVAIL:Credit",
                ]
            },
            "source_start": 0,
            "restrictions": [
                "No endorsement; review identifiable people and third-party rights before release"
            ],
        }


def youtube_license(meta):
    """Preserve the source's actual CC BY version; an unversioned label is insufficient."""
    identity = meta.get("id", "")
    if not re.fullmatch(r"[\w-]{11}", identity):
        return None
    with urlopen(
        Request(
            "https://www.youtube.com/watch?v=" + identity,
            headers={"User-Agent": "Mozilla/5.0"},
        ),
        timeout=15,
    ) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        return None
    # YouTube has used different CC BY versions. Never infer one from upload date.
    page = (
        raw.decode("utf-8", errors="replace")
        .replace("\\/", "/")
        .replace("\\u0026", "&")
    )
    versions = set(re.findall(r"creativecommons\.org/licenses/by/(3\.0|4\.0)/", page))
    if len(versions) != 1:
        return None
    version = versions.pop()
    return (
        "CC-BY-" + version,
        "https://creativecommons.org/licenses/by/" + version + "/",
    )


def youtube_cc(query, folder, budget):
    """Only source-declared Creative Commons footage. No cookies, protected media or DRM bypass."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func

    folder.mkdir(parents=True, exist_ok=True)
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 15,
        "retries": 0,
        "ignoreerrors": True,
        "noplaylist": True,
    }
    with YoutubeDL(options) as client:
        result = client.extract_info(
            "ytsearch3:" + query + " creative commons", download=False
        )
    for meta in (result or {}).get("entries", []):
        if (
            not meta
            or not str(meta.get("license", "")).startswith(
                "Creative Commons Attribution"
            )
            or meta.get("is_live")
            or meta.get("age_limit", 0) > 0
        ):
            continue
        seconds = meta.get("duration") or 0
        if not 5 <= seconds <= 1200 or not meta.get("uploader"):
            continue
        declared = youtube_license(meta)
        if not declared:
            continue
        # Download a bounded section, not the full source video. Frame inspection chooses the actual cut later.
        chapter = next(
            (
                c
                for c in meta.get("chapters") or []
                if any(w in c.get("title", "").lower() for w in query.lower().split())
            ),
            None,
        )
        start = float(chapter["start_time"]) if chapter else max(0, seconds * 0.15 - 5)
        end = min(seconds, start + 40)
        target = folder / (uuid4().hex + ".mp4")
        opts = {
            **options,
            "skip_download": False,
            "format": "bestvideo[height<=480][ext=mp4]/best[height<=480][ext=mp4]",
            "outtmpl": str(target),
            "download_ranges": download_range_func(None, [(start, end)]),
            "max_filesize": 45_000_000,
            "overwrites": True,
            "ffmpeg_location": "/usr/bin/ffmpeg",
        }
        try:
            budget.check()
            with YoutubeDL(opts) as client:
                client.download([meta["webpage_url"]])
            if not target.is_file() or target.stat().st_size > 45_000_000:
                continue
            budget.downloaded += target.stat().st_size
            yield {
                "path": str(target),
                "sha256": digest(target),
                "source": meta["webpage_url"],
                "description": meta.get("title", query),
                "credit": meta["uploader"],
                "license": declared[0],
                "license_url": declared[1],
                "source_start": start,
                "evidence": {
                    "license": meta["license"],
                    "uploader_url": meta.get("uploader_url"),
                    "video_id": meta.get("id"),
                },
            }
        finally:
            target.unlink(missing_ok=True)
            for partial in folder.glob(target.name + "*part*"):
                partial.unlink(missing_ok=True)


def candidates(query, folder, budget, audit):
    for provider in ["Commons", "Internet Archive", "NASA", "YouTube CC"]:
        budget.check()
        budget.searches += 1
        entry = {"provider": provider, "query": query, "candidates": 0}
        audit.append(entry)
        try:
            if provider == "Commons":
                results = commons.search_footage(query, folder)
                for asset in results:
                    budget.downloaded += Path(asset["path"]).stat().st_size
            else:
                results = {
                    "Internet Archive": archive,
                    "NASA": nasa,
                    "YouTube CC": youtube_cc,
                }[provider](query, folder, budget)
            for asset in results:
                entry["candidates"] += 1
                budget.check()
                yield asset
        except Exception as exc:  # noqa: BLE001 -- bounded provider failures are audit data, then another source is tried
            entry["error"] = type(exc).__name__


def inspect_and_cut(asset, scene, seconds, count, selected, budget, stage):
    budget.check()
    budget.inspected += 1
    path = Path(asset["path"])
    total = duration(path)
    if not seconds <= total <= 1200:
        return []
    query = json.dumps(
        {
            "subject": scene.visual.subject,
            "action": scene.visual.action,
            "purpose": scene.visual.purpose,
            "narration": scene.narration,
        }
    )
    found = []
    for fraction in [0, 0.2, 0.4, 0.6, 0.8, 1]:
        budget.check()
        start = round((total - seconds) * fraction, 3)
        if any(abs(start - f["origin_start"]) < seconds for f in found):
            continue
        stage(
            "Inspecting candidate frames against the scene's subject, action and meaning"
        )
        if not verify_window(path, start, seconds, query, timeout=90):
            continue
        selected.mkdir(parents=True, exist_ok=True)
        clip = selected / (uuid4().hex + ".mp4")
        command(
            [
                "-protocol_whitelist",
                "file,pipe",
                "-ss",
                str(start),
                "-i",
                str(path),
                "-t",
                str(seconds),
                "-an",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-preset",
                "fast",
                "-crf",
                "22",
                str(clip),
            ]
        )
        sha = digest(clip)
        found.append(
            {
                **asset,
                "path": str(clip),
                "sha256": sha,
                "id": "media-" + sha,
                "origin_sha256": asset["sha256"],
                "origin_start": start,
                "origin_window": [
                    round(asset.get("source_start", 0) + start, 3),
                    round(asset.get("source_start", 0) + start + seconds, 3),
                ],
                "start": 0,
                "end": seconds,
                "match": "Two sampled frames passed automated subject/action review; final editorial approval still required",
            }
        )
        if len(found) == count:
            break
    return found
