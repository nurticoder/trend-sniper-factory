from datetime import datetime

from PIL import ImageDraw

from ..render import font
from ..web.formats import frame


def evidence_graphic(packet):
    """The bar lengths encode sourced values. In news mode positions encode time."""
    news = packet["format"] == "News desk"
    rows = [r for r in packet["records"] if news or r["views"] is not None]
    rows.sort(key=lambda r: r["published"] if news else r["views"], reverse=True)

    def draw(topic, index, local, elapsed, duration):
        im = frame(topic, index, local, elapsed, duration)
        d = ImageDraw.Draw(im)
        scene = topic["scenes"][index]
        d.rectangle((25, 170, 695, 525), fill=(15, 20, 44))
        d.text(
            (56, 192),
            "DISPATCH TIMELINE" if news else "VIEWS IN THIS SAMPLE",
            font=font(20),
            fill=(170, 182, 215),
        )
        maximum = max(1, max(r["views"] or 0 for r in rows))
        for i, r in enumerate(rows):
            y = 264 + i * 72
            highlight = r["source"] == scene["source"] and scene["role"] != "hook"
            color = (255, 200, 125) if highlight else (96, 137, 208)
            if news:
                time = datetime.fromisoformat(r["published"])
                d.ellipse((65, y + 4, 81, y + 20), fill=color)
                d.text(
                    (101, y),
                    time.strftime("%d %b  %H:%M UTC"),
                    font=font(25),
                    fill=color,
                )
            else:
                fill = min(1, local * 3 + 0.08)
                width = round(372 * r["views"] / maximum * fill)
                d.text((56, y), f"#{i + 1}", font=font(23), fill=color)
                d.rectangle((115, y + 6, 490, y + 25), fill=(37, 47, 78))
                d.rectangle((115, y + 6, 115 + width, y + 25), fill=color)
                d.text((512, y), f"{r['views']:,}", font=font(20), fill=color)
        return im

    return draw
