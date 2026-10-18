"""Сборка ролика: наезд на кадры, склейка, голос, музыка, субтитры."""
import random
from pathlib import Path

from . import media


def _segment(cfg: dict, img: Path, seconds: float, idx: int, dst: Path) -> Path:
    v = cfg["video"]
    w, h, fps = int(v["width"]), int(v["height"]), int(v["fps"])
    frames = max(1, int(round(seconds * fps)))
    z = float(v.get("zoom_per_frame", 0.0012))
    zmax = 1.0 + z * frames + 0.02
    # Чередуем направление: наезд в центр, отъезд, наезд с панорамой.
    mode = idx % 3
    if mode == 0:
        zoom = f"min(zoom+{z},{zmax})"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif mode == 1:
        zoom = f"if(eq(on,1),{zmax},max(zoom-{z},1.0))"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    else:
        zoom = f"min(zoom+{z},{zmax})"
        x, y = "(iw-iw/zoom)*on/" + str(frames), "ih/2-(ih/zoom/2)"
    vf = (
        f"scale={w * 2}:{h * 2}:flags=lanczos,"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
        f"format=yuv420p"
    )
    media.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-vf", vf,
        "-t", f"{seconds:.3f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(dst),
    ])
    return dst


def _pick_music(cfg: dict) -> Path | None:
    d = cfg["video"].get("music_dir")
    if not d:
        return None
    p = Path(d)
    if not p.is_dir():
        return None
    tracks = [f for f in p.iterdir() if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac")]
    return random.choice(tracks) if tracks else None


def build_video(cfg: dict, frames: list[Path], voice: Path, ass: Path, work: Path, dst: Path) -> Path:
    media.ensure_ffmpeg()
    v = cfg["video"]
    total = media.duration(voice) + 0.6  # хвост после последнего слова
    per = total / len(frames)
    segs = [_segment(cfg, f, per, i, work / f"seg_{i:02d}.mp4") for i, f in enumerate(frames)]

    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{s.resolve().as_posix()}'\n" for s in segs), encoding="utf-8")
    silent = work / "video_silent.mp4"
    media.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(voice)]
    music = _pick_music(cfg)
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        afilter = (
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[v];"
            f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(v.get('music_volume', 0.12))}[m];"
            f"[v][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )
        cmd += ["-filter_complex", afilter, "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += [
        "-vf", f"ass='{media.ffmpeg_filter_path(ass)}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(dst),
    ]
    media.run(cmd)
    return dst
