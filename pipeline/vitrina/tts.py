"""Озвучка через локальный сервер VoiceStudio (OpenAI-совместимый API) или заглушка."""
import re
from pathlib import Path

import requests

from . import media


class VoiceStudio:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def health(self) -> bool:
        try:
            return requests.get(f"{self.base}/health", headers=self.headers, timeout=5).ok
        except requests.RequestException:
            return False

    def voices(self) -> list[dict]:
        r = requests.get(f"{self.base}/v1/audio/voices", headers=self.headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            data = data.get("voices") or data.get("data") or []
        return data

    def speak(self, text: str, voice: str, model: str, out_wav: Path, speed: float = 1.0) -> Path:
        body = {"model": model, "voice": voice, "input": text, "response_format": "wav", "speed": speed}
        r = requests.post(f"{self.base}/v1/audio/speech", headers=self.headers, json=body, timeout=600)
        if not r.ok:
            raise RuntimeError(f"VoiceStudio {r.status_code}: {r.text[:500]}")
        ctype = r.headers.get("content-type", "")
        if "json" in ctype or r.content[:4] not in (b"RIFF", b"fLaC", b"OggS", b"ID3\x03", b"ID3\x04") and not r.content[:2] == b"\xff\xfb":
            raise RuntimeError(f"VoiceStudio вернул не аудио ({ctype}): {r.text[:300]}")
        out_wav.write_bytes(r.content)
        return out_wav

    def transcribe(self, wav: Path, model: str) -> dict:
        with wav.open("rb") as f:
            r = requests.post(
                f"{self.base}/v1/audio/transcriptions",
                headers=self.headers,
                files={"file": (wav.name, f, "audio/wav")},
                data={"model": model, "response_format": "verbose_json", "timestamp_granularities[]": "word"},
                timeout=600,
            )
        r.raise_for_status()
        return r.json()


def _mock_wav(text: str, out_wav: Path) -> Path:
    words = len(re.findall(r"\w+", text))
    secs = max(3.0, words * 0.42)
    media.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{secs:.2f}", "-c:a", "pcm_s16le", str(out_wav),
    ])
    return out_wav


def voice_for_channel(cfg: dict, channel: str) -> str:
    return (cfg["tts"].get("voices_by_channel") or {}).get(channel) or cfg["tts"]["voice"]


def synthesize(cfg: dict, text: str, channel: str, out_wav: Path) -> Path:
    t = cfg["tts"]
    if t.get("provider") == "mock":
        return _mock_wav(text, out_wav)
    vs = VoiceStudio(t["base_url"], t.get("api_key", ""))
    if not vs.health():
        raise RuntimeError(f"VoiceStudio не отвечает на {t['base_url']}. Запустите приложение.")
    return vs.speak(text, voice_for_channel(cfg, channel), t.get("model", "tts-1"), out_wav, float(t.get("speed", 1.0)))
