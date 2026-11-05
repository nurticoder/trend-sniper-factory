"""Opt-in single-server daily previews, keyed by the story's actual source set."""

import hashlib
import json
from datetime import UTC, datetime
from threading import Lock
from zoneinfo import ZoneInfo


def edition_key(card):
    material = [card["id"], sorted(v["video"] for v in card["examples"])]
    return "edition-v1/" + hashlib.sha256(json.dumps(material).encode()).hexdigest()


class DailyPreviews:
    def __init__(self, store):
        self.store = store
        self.lock = Lock()
        with store.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS daily_settings(slot INTEGER PRIMARY KEY, niche TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS daily_previews(day TEXT PRIMARY KEY, signature TEXT UNIQUE, job TEXT)"
            )

    def niche(self):
        with self.store.connection() as db:
            row = db.execute("SELECT niche FROM daily_settings WHERE slot=1").fetchone()
        return row[0] if row else None

    def set(self, key):
        with self.lock, self.store.connection() as db:
            db.execute("INSERT OR REPLACE INTO daily_settings VALUES (1,?)", (key,))

    def tick(self, cards, enqueue, now=None):
        now = now or datetime.now(UTC)
        day = now.astimezone(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
        with self.lock:
            key = self.niche()
            card = next((c for c in cards if c["id"] == key), None)
            if not card:
                return
            age = (now - datetime.fromisoformat(card["observed"])).total_seconds()
            if not 0 <= age <= 86400:
                return
            # Updating view counts alone must not generate a daily near-duplicate.
            signature = edition_key(card)
            with self.store.connection() as db:
                if db.execute(
                    "SELECT 1 FROM daily_previews WHERE day=? OR signature=?",
                    (day, signature),
                ).fetchone():
                    return
            job = enqueue('remote-v1/content/'+signature, {"title": card["name"], "recipe_card": card})
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO daily_previews VALUES (?,?,?)",
                    (day, signature, job["id"]),
                )
            return job
