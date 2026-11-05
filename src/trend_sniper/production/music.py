"""Original beat bed with a drop and separate accents synchronized to picture."""

import math
import sys
import wave
from array import array


def score(path, topic, rate=24000):
    samples = array("h")
    time = 0
    beat = 0.4 if topic["format"] == "Countdown" else 0.5
    notes = (
        (220, 261.63, 329.63, 392)
        if topic["format"] in {"Countdown", "News desk"}
        else (196, 246.94, 293.66, 369.99)
    )
    for scene in topic["scenes"]:
        reveal = scene["mode"] == "reveal"
        total = round(scene["seconds"] * rate)
        for i in range(total):
            local = i / rate
            t = time + local
            step = int(t / beat)
            phase = t % beat
            pulse = 0.10 * math.exp(-phase * 12) * math.sin(math.tau * 110 * t)
            arp = (
                0.065 * math.exp(-phase * 7) * math.sin(math.tau * notes[step % 4] * t)
            )
            tick = (
                0.025 * math.exp(-(t % (beat / 2)) * 60) * math.sin(math.tau * 2100 * t)
            )
            bed = (pulse + arp + tick) * (0.14 if reveal and local < 0.35 else 1)
            cue = 0
            if local < 0.36:
                frequency = 780 if reveal else 320
                cue = (
                    0.16
                    * math.exp(-local * 13)
                    * math.sin(math.tau * (frequency * local - 125 * local * local))
                )
            fade = min(1, (total - i) / (rate * 0.04), (i + 1) / (rate * 0.008))
            samples.append(int((bed + cue) * fade * 32767))
        time += scene["seconds"]
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())
