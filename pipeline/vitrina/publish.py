"""Публикация в Telegram-витрину через Bot API. VK и YouTube добавляются на 3-й неделе."""
from pathlib import Path

import requests


def telegram_video(cfg: dict, video: Path, caption: str) -> dict:
    tg = cfg.get("telegram", {})
    token, chat = tg.get("bot_token"), tg.get("channel_id")
    if not token or not chat:
        raise RuntimeError("Не заданы telegram.bot_token и telegram.channel_id")
    with video.open("rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={"chat_id": chat, "caption": caption[:1024], "supports_streaming": "true"},
            files={"video": (video.name, f, "video/mp4")},
            timeout=300,
        )
    r.raise_for_status()
    return r.json()


def caption_for(product: dict, script: dict) -> str:
    lines = [script.get("cover_title") or product["title"], ""]
    lines += [f"— {f}" for f in script.get("facts", [])]
    if product.get("price"):
        lines.append(f"\nЦена около {product['price']} ₽")
    if product.get("affiliate_url"):
        lines.append(f"Купить: {product['affiliate_url']}")
    return "\n".join(lines)
