import json
import tempfile
import unittest
from pathlib import Path

from trend_sniper.core import digest, load_topic, write_json
from trend_sniper.queue import approve, enqueue

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_topic_rejects_invalid_duration_and_path(self):
        data = load_topic(ROOT / "topics/dont-splash.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topic.json"
            for value in (-1, float("nan"), True, 1000):
                data["scenes"][0]["seconds"] = value
                write_json(path, data)
                with self.assertRaises(ValueError):
                    load_topic(path)
            data["id"] = "../../oops"
            write_json(path, data)
            with self.assertRaises(ValueError):
                load_topic(path)

    def artifact(self, folder):
        names = ["short.mp4", "metadata.json", "script.json", "captions.srt"]
        for name in names:
            (folder / name).write_text("fixture")
        write_json(folder / "manifest.json", {"sha256": {n: digest(folder/n) for n in names}})

    def test_review_queue_rejects_missing_duplicate_and_stale_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.artifact(folder)
            queue = folder / "queue.json"
            with self.assertRaises(FileNotFoundError):
                enqueue(folder, "2099-01-01T00:00:00Z", queue)
            approve(folder, "made_for_kids", "test")
            row = enqueue(folder, "2099-01-01T00:00:00Z", queue)
            self.assertEqual(row["status"], "ready_for_manual_upload")
            with self.assertRaises(ValueError):
                enqueue(folder, "2099-01-02T00:00:00Z", queue)
            (folder / "metadata.json").write_text("changed")
            with self.assertRaises(ValueError):
                enqueue(folder, "2099-01-03T00:00:00Z", folder/"other.json")

    def test_schedule_requires_timezone_and_future(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.artifact(folder)
            approve(folder, "not_made_for_kids", "test")
            for when in ("2099-01-01", "2000-01-01T00:00:00Z"):
                with self.assertRaises(ValueError):
                    enqueue(folder, when, folder/"queue.json")


class MediaIntegrationTests(unittest.TestCase):
    def test_mp4_roundtrip_and_no_overwrite(self):
        import imageio_ffmpeg
        from trend_sniper.render import render

        topic = load_topic(ROOT / "topics/dont-splash.json")
        topic["scenes"] = topic["scenes"][:2]
        for scene in topic["scenes"]:
            scene["seconds"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "render"
            movie = render(topic, folder)
            frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(movie))
            self.assertEqual(frames, 48)
            self.assertAlmostEqual(seconds, 2, places=1)
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(digest(movie), manifest["sha256"]["short.mp4"])
            self.assertIn("00:00:01,000 --> 00:00:02,000", (folder / "captions.srt").read_text())
            with self.assertRaises(ValueError):
                render(topic, folder)


if __name__ == "__main__":
    unittest.main()
