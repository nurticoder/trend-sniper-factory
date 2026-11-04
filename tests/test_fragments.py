"""Exercise the actual FFmpeg trim and mix paths with synthetic, cleared fixtures."""

import math
import subprocess
import tempfile
import unittest
import wave
from array import array
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

from trend_sniper.production.materials import plan, soundtrack, visual_renderer


class FragmentChecks(unittest.TestCase):
    def test_chosen_video_window_and_delayed_sound_reach_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            movie = root / "fixture.mp4"
            cmd = [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=red:s=48x48:r=8:d=1",
                "-f",
                "lavfi",
                "-i",
                "color=blue:s=48x48:r=8:d=2",
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[out]",
                "-map",
                "[out]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(movie),
            ]
            subprocess.run(cmd, check=True)
            hit = root / "hit.wav"
            rate = 24000
            samples = array(
                "h",
                (
                    int(15500 * math.sin(math.tau * 1200 * i / rate))
                    if i >= rate
                    else 0
                    for i in range(2 * rate)
                ),
            )
            with wave.open(str(hit), "wb") as stream:
                stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                stream.writeframes(samples.tobytes())
            assets = [
                {
                    "kind": "video",
                    "file": "fixture.mp4",
                    "path": str(movie),
                    "start": 1,
                    "end": 3,
                    "description": "blue paint sample",
                },
                {
                    "kind": "effect",
                    "file": "hit.wav",
                    "path": str(hit),
                    "start": 1,
                    "end": 2,
                    "description": "reveal impact",
                },
            ]
            topic = {
                "format": "Countdown",
                "scenes": [
                    {
                        "value": "Setup",
                        "caption": "Dry brush",
                        "seconds": 1,
                        "mode": "choice",
                    },
                    {
                        "value": "Blue paint",
                        "caption": "Final test",
                        "seconds": 1,
                        "mode": "reveal",
                    },
                ],
            }
            shots = plan(topic, assets)
            draw = visual_renderer(lambda *args: Image.new("RGB", (720, 1280)), shots)
            red, _green, blue = draw(topic, 1, 0.4, 1.4, 2).getpixel((200, 275))
            self.assertGreater(blue, 220)
            self.assertLess(red, 20)
            mixed = root / "mixed.wav"
            soundtrack(shots)(mixed, topic)
            with wave.open(str(mixed), "rb") as stream:
                self.assertEqual(stream.getnframes(), 2 * rate)
                pcm = array("h", stream.readframes(2 * rate))

            def energy(at):
                start = int(at * rate)
                return abs(
                    sum(
                        v * math.cos(math.tau * 1200 * i / rate)
                        for i, v in enumerate(pcm[start : start + 2400])
                    )
                ) + abs(
                    sum(
                        v * math.sin(math.tau * 1200 * i / rate)
                        for i, v in enumerate(pcm[start : start + 2400])
                    )
                )

            self.assertGreater(energy(1.45), 20 * energy(0.45))
