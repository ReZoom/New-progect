"""Общие вызовы FFmpeg и FFprobe."""
import json
import shutil
import subprocess
from pathlib import Path


def ensure_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(f"Не найден {tool}. Установите FFmpeg и добавьте в PATH.")


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("Команда завершилась ошибкой:\n" + " ".join(cmd) + "\n" + proc.stderr[-2000:])


def duration(path: str | Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def ffmpeg_filter_path(path: str | Path) -> str:
    """Экранирование пути для фильтров FFmpeg (ass=...), в том числе на Windows."""
    p = str(Path(path).resolve()).replace("\\", "/")
    return p.replace(":", "\\:").replace("'", "\\'")
