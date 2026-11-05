"""Readable phrase captions via FFmpeg/libass; timings follow measured speech."""


def ass_time(seconds):
    ticks = round(seconds * 100)
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def write_ass(captions, path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,39,&H00FFFFFF,&H00FFFFFF,&H00181007,&H80181007,-1,0,0,0,100,100,0,0,1,3,1,2,45,45,150,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for start, end, text in captions:
        # Render text, never ASS override instructions supplied by a writer.
        text = (
            text.replace("\\", "")
            .replace("{", "(")
            .replace("}", ")")
            .replace("\n", " ")
            .replace("\r", " ")
        )
        rows.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}\n"
        )
    path.write_text(header + "".join(rows))


def subtitle_filter(path):
    filename = (
        str(path.resolve())
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "'\\''")
    )
    return "ass=filename='" + filename + "'"
