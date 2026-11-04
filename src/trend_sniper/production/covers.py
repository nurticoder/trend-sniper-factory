"""Generate alternate covers from the winning edit and select a mobile-readable frame."""

from PIL import Image, ImageDraw, ImageStat

from ..render import font

PALETTES = [
    ((18, 20, 40), (250, 201, 80), (250, 250, 246)),
    ((24, 46, 57), (99, 229, 216), (249, 250, 247)),
    ((60, 24, 46), (255, 152, 151), (255, 250, 247)),
    ((37, 31, 70), (187, 165, 255), (253, 250, 242)),
]


def lines_for(text, face, width):
    lines = []
    for word in text.split():
        if lines and face.getlength(lines[-1] + " " + word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def fit(text, width, height, initial):
    for size in range(initial, 15, -2):
        face = font(size)
        lines = lines_for(text, face, width)
        if (
            len(lines) * (size + 8) <= height
            and max((face.getlength(line) for line in lines), default=0) <= width
        ):
            return face, lines, size
    raise ValueError("Cover text exceeds layout bounds")


def brightness(rgb):
    linear = [
        (v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4)
        for v in rgb
    ]
    return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def cover_set(topic, draw_frame, out):
    scenes = topic["scenes"]
    duration = sum(s["seconds"] for s in scenes)
    # Three truthful offers: subject, opening question, and a sourced clue.
    concepts = [
        ("Subject", topic["title"].split("|")[-1].strip()),
        ("Question", scenes[0]["value"]),
        ("Detail", scenes[-1]["heading"] + " / " + scenes[-1]["caption"]),
    ]
    concepts = topic.get("cover_lines", concepts)
    candidates = []
    folder = out / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (4 * 144, 3 * 256))
    for row, (name, text) in enumerate(concepts):
        for col, (bg, accent, fg) in enumerate(PALETTES):
            image = Image.new("RGB", (720, 1280), bg)
            draw = ImageDraw.Draw(image)
            index = min(col, len(scenes) - 1)
            previous = sum(s["seconds"] for s in scenes[:index])
            still = draw_frame(topic, index, 0.5, previous + 0.5, duration)
            art = still.crop((80, 195, 640, 510))
            art = art.resize((624, 351))
            y = 200 if col % 2 == 0 else 660
            image.paste(art, (48, y))
            draw.rectangle((48, y + 351, 672, y + 359), fill=accent)
            draw.text((50, 78), topic["format"].upper(), font=font(28), fill=accent)
            face, lines, size = fit(text, 600, 330, 84)
            line_y = 605 if col % 2 == 0 else 222
            for line in lines:
                draw.text((54, line_y), line, font=face, fill=fg, anchor="lt")
                line_y += size + 8
            draw.text((52, 1110), topic["date"], font=font(24), fill=accent)
            number = row * 4 + col + 1
            path = folder / f"cover-{number:02}.jpg"
            image.save(path, quality=88)
            sheet.paste(image.resize((144, 256)), (col * 144, row * 256))
            contrast = (brightness(fg) + 0.05) / (brightness(bg) + 0.05)
            detail = min(1, ImageStat.Stat(art.convert("L")).stddev[0] / 55)
            score = round(
                size / 84 * 48
                + min(contrast / 12, 1) * 25
                + detail * 12
                + (15 if name == "Question" else 10),
                1,
            )
            candidates.append(
                {
                    "number": number,
                    "concept": name,
                    "text": text,
                    "font_px": size,
                    "contrast": round(contrast, 2),
                    "image_detail": round(detail, 2),
                    "score": score,
                    "file": path.name,
                }
            )
    winner = max(candidates, key=lambda c: c["score"])
    (out / "cover.jpg").write_bytes((folder / winner["file"]).read_bytes())
    sheet.save(out / "cover-options.jpg", quality=88)
    with Image.open(out / "cover.jpg") as selected:
        opening = selected.convert("RGB")
    return opening, {
        "winner": winner,
        "candidates": candidates,
        "selection_basis": "Text fit, contrast, visual detail, hook agreement. Editorial heuristic.",
    }
