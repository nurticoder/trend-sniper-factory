"""Choose a future local release window. This worker only proposes a slot."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo


def proposal(history_path: Path, format_name, now=None):
    zone = ZoneInfo("Asia/Hong_Kong")
    now = (now or datetime.now(zone)).astimezone(zone)
    buckets = defaultdict(list)
    warning = None
    if history_path.is_file():
        try:
            data = json.loads(history_path.read_text())
            if not isinstance(data, list):
                raise TypeError("Expected observations array")
        except (OSError, TypeError, ValueError):
            data = []
            warning = "Could not read channel history. Used an exploratory slot."
        seen = set()
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("video_id"), str):
                continue
            if row.get("format") != format_name or row.get("video_id") in seen:
                continue
            try:
                published = datetime.fromisoformat(row["published_at"])
                views = row["views_at_24h"]
                if (
                    not row["video_id"]
                    or published.tzinfo is None
                    or published + timedelta(hours=24) > now
                ):
                    continue
                if type(views) is not int or views < 0:
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            seen.add(row["video_id"])
            buckets[published.astimezone(zone).hour].append(views)
    measured = {hour: values for hour, values in buckets.items() if len(values) >= 3}
    tomorrow = now.date() + timedelta(days=1)
    if len(measured) >= 2:
        hour = max(sorted(measured), key=lambda h: median(measured[h]))
        reason = (
            "Highest observed median first-day views among comparable release hours."
        )
    else:
        hour = (12, 17, 20)[tomorrow.toordinal() % 3]
        reason = "Exploratory rotation. Insufficient same-format channel history."
    at = datetime.combine(tomorrow, datetime.min.time(), zone).replace(hour=hour)
    return {
        "proposed_at": at.isoformat(),
        "timezone": zone.key,
        "reason": warning or reason,
        "sample_sizes": {str(h): len(v) for h, v in measured.items()},
        "state": "proposal_only",
        "requires": ["reviewed video", "audience decision", "channel authorization"],
    }
