"""Субтитры в формате ASS: по 2–3 слова крупно по центру."""
from pathlib import Path


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(cfg: dict, words: list[dict], dst: Path, highlight_first: bool = True) -> Path:
    v = cfg["video"]
    per = int(v.get("words_per_line", 3))
    font = v.get("font_name", "Arial Black")
    size = int(v.get("font_size", 78))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {v['width']}
PlayResY: {v['height']}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{size},{v.get('primary_color', '&H00FFFFFF')},&H000000FF,{v.get('outline_color', '&H00000000')},&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,70,70,{int(int(v['height']) * 0.22)},1
Style: Hi,{font},{size},{v.get('highlight_color', '&H0000D7FF')},&H000000FF,{v.get('outline_color', '&H00000000')},&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,70,70,{int(int(v['height']) * 0.22)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    max_chars = int(v.get("max_chars_per_line", 18))
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        cur_len = sum(len(x["word"]) for x in cur) + len(cur)
        if cur and (len(cur) >= per or cur_len + len(w["word"]) > max_chars):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    for gi, g in enumerate(groups):
        start, end = g[0]["start"], g[-1]["end"]
        if gi + 1 < len(groups):
            end = min(end + 0.05, groups[gi + 1][0]["start"])
        text = " ".join(w["word"] for w in g).replace("{", "").replace("}", "")
        style = "Hi" if (highlight_first and gi == 0) else "Main"
        lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},{style},,0,0,0,,{text}")
    dst.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return dst
