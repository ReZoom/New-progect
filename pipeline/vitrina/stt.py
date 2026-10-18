"""Тайминги слов для субтитров: транскрипция через VoiceStudio или равномерная раскладка."""
import re
from pathlib import Path

from . import media
from .tts import VoiceStudio

WORD = re.compile(r"[\w\-']+", re.U)


def _uniform(text: str, total: float) -> list[dict]:
    words = WORD.findall(text)
    if not words:
        return []
    step = total / len(words)
    return [{"word": w, "start": i * step, "end": (i + 1) * step} for i, w in enumerate(words)]


def _from_verbose(resp: dict) -> list[dict]:
    words = resp.get("words")
    if words:
        return [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])} for w in words]
    out = []
    for seg in resp.get("segments", []):
        seg_words = WORD.findall(seg.get("text", ""))
        if not seg_words:
            continue
        s, e = float(seg["start"]), float(seg["end"])
        step = (e - s) / len(seg_words)
        out += [{"word": w, "start": s + i * step, "end": s + (i + 1) * step} for i, w in enumerate(seg_words)]
    return out


def word_timings(cfg: dict, wav: Path, text: str) -> list[dict]:
    total = media.duration(wav)
    s = cfg.get("stt", {})
    if s.get("provider", "none") != "voicestudio" or cfg["tts"].get("provider") == "mock":
        return _uniform(text, total)
    vs = VoiceStudio(cfg["tts"]["base_url"], cfg["tts"].get("api_key", ""))
    try:
        timed = _from_verbose(vs.transcribe(wav, s.get("model", "whisper-1")))
    except Exception:
        timed = []
    if not timed:
        return _uniform(text, total)
    # Если число слов совпало, берём орфографию из сценария, а время из транскрипции.
    src = WORD.findall(text)
    if len(src) == len(timed):
        for w, t in zip(src, timed):
            t["word"] = w
    return timed
