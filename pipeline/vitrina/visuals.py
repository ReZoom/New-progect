"""Подготовка кадров 9:16 из фото товара и обложки."""
import hashlib
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/impact.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fetch(src: str, cache_dir: Path) -> Path:
    p = Path(src)
    if p.exists():
        return p
    if src.startswith(("http://", "https://")):
        name = hashlib.sha1(src.encode()).hexdigest()[:16] + ".img"
        dst = cache_dir / name
        if not dst.exists():
            r = requests.get(src, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            dst.write_bytes(r.content)
        return dst
    raise FileNotFoundError(src)


def to_vertical(src: Path, dst: Path, w: int, h: int) -> Path:
    """Размытый фон из того же фото плюс само фото по центру без обрезки."""
    img = Image.open(src).convert("RGB")
    bg = img.copy()
    scale = max(w / bg.width, h / bg.height)
    bg = bg.resize((int(bg.width * scale) + 1, int(bg.height * scale) + 1), Image.LANCZOS)
    left, top = (bg.width - w) // 2, (bg.height - h) // 2
    bg = bg.crop((left, top, left + w, top + h)).filter(ImageFilter.GaussianBlur(28))
    bg = Image.eval(bg, lambda v: int(v * 0.55))

    pad = int(w * 0.07)
    box_w, box_h = w - 2 * pad, int(h * 0.62)
    fg = img.copy()
    fg.thumbnail((box_w, box_h), Image.LANCZOS)
    x, y = (w - fg.width) // 2, (h - fg.height) // 2 - int(h * 0.04)
    bg.paste(fg, (x, y))
    dst.parent.mkdir(parents=True, exist_ok=True)
    bg.save(dst, "PNG")
    return dst


def placeholder(title: str, dst: Path, w: int, h: int) -> Path:
    img = Image.new("RGB", (w, h), (24, 26, 32))
    d = ImageDraw.Draw(img)
    for i in range(h):
        d.line([(0, i), (w, i)], fill=(24 + i * 30 // h, 26 + i * 20 // h, 32 + i * 60 // h))
    _draw_wrapped(d, title, _font(72), w, h // 2 - 100, (240, 240, 240))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "PNG")
    return dst


def prepare_images(cfg: dict, product: dict, sources: list[str], out_dir: Path) -> list[Path]:
    v = cfg["video"]
    w, h = int(v["width"]), int(v["height"])
    cache = Path(cfg["project"]["data_dir"]) / "images"
    frames: list[Path] = []
    for i, src in enumerate(sources[: int(v.get("max_images", 5))]):
        try:
            frames.append(to_vertical(_fetch(src, cache), out_dir / f"frame_{i:02d}.png", w, h))
        except Exception as e:  # битая картинка не должна ронять сборку
            print(f"  пропускаю {src}: {e}")
    if not frames:
        frames.append(placeholder(product["title"], out_dir / "frame_00.png", w, h))
    while len(frames) < 3:
        frames.append(frames[len(frames) % len(frames)])
    return frames


def _draw_wrapped(d: ImageDraw.ImageDraw, text: str, font, w: int, y: int, fill, max_width_ratio=0.86):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=font) <= w * max_width_ratio:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for line in lines:
        tw = d.textlength(line, font=font)
        x = (w - tw) / 2
        d.text((x, y), line, font=font, fill=fill, stroke_width=6, stroke_fill=(0, 0, 0))
        y += int(font.size * 1.2)


def make_cover(cfg: dict, frame: Path, title: str, dst: Path) -> Path:
    img = Image.open(frame).convert("RGB")
    d = ImageDraw.Draw(img)
    _draw_wrapped(d, title.upper(), _font(int(cfg["video"].get("font_size", 78)) + 14), img.width, int(img.height * 0.70), (255, 215, 0))
    img.save(dst, "PNG")
    return dst
