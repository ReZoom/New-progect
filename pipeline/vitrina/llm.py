"""Генерация сценария через OpenAI-совместимый API (OpenRouter) или шаблоном без нейросети."""
import json
import re
from pathlib import Path

import requests

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "script_ru.txt"


def _prompt(cfg: dict, product: dict) -> str:
    tpl = PROMPT_PATH.read_text(encoding="utf-8")
    return tpl.format(
        title=product["title"],
        price=product.get("price", ""),
        description=product.get("description", ""),
        channel=product.get("channel", ""),
        cta=cfg["cta"]["text"],
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Модель вернула не JSON: {text[:200]}")
    return json.loads(text[start:end + 1])


def _validate(s: dict, cta: str) -> dict:
    facts = [f.strip() for f in s.get("facts", []) if str(f).strip()][:3]
    if len(facts) < 3 or not s.get("hook"):
        raise ValueError("В сценарии нет хука или трёх фактов")
    return {
        "hook": str(s["hook"]).strip(),
        "facts": facts,
        "price_line": str(s.get("price_line", "")).strip(),
        "cta": cta,
        "cover_title": str(s.get("cover_title", s["hook"]))[:40].strip(),
    }


def template_script(cfg: dict, product: dict) -> dict:
    """Запасной сценарий без нейросети: для проверки установки и как черновик."""
    sentences = [x.strip() for x in re.split(r"[.!?]\s*", product.get("description", "")) if x.strip()]
    facts = (sentences + ["Работает как заявлено", "Доставка быстрая", "Отзывы хорошие"])[:3]
    return _validate({
        "hook": "Вы точно об этом не знали",
        "facts": facts,
        "price_line": f"Стоит около {product.get('price', '')} рублей",
        "cover_title": product["title"][:40],
    }, cfg["cta"]["text"])


def generate_scripts(cfg: dict, product: dict) -> list[dict]:
    llm = cfg["llm"]
    if llm.get("provider", "none") == "none" or not llm.get("api_key"):
        return [template_script(cfg, product)]

    url = llm["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {llm['api_key']}", "Content-Type": "application/json"}
    variants: list[dict] = []
    errors: list[str] = []
    for _ in range(int(llm.get("variants", 3))):
        body = {
            "model": llm["model"],
            "temperature": float(llm.get("temperature", 0.8)),
            "messages": [{"role": "user", "content": _prompt(cfg, product)}],
        }
        r = requests.post(url, headers=headers, json=body, timeout=90)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        try:
            variants.append(_validate(_parse_json(content), cfg["cta"]["text"]))
        except (ValueError, json.JSONDecodeError) as e:
            errors.append(str(e))
    if not variants:
        raise RuntimeError("Ни один вариант сценария не прошёл проверку: " + "; ".join(errors))
    return variants


def script_to_text(script: dict) -> str:
    parts = [script["hook"], *script["facts"]]
    if script.get("price_line"):
        parts.append(script["price_line"])
    parts.append(script["cta"])
    return " ".join(p.rstrip(".!?") + "." for p in parts)
