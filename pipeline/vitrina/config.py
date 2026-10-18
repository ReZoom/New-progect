"""Загрузка настроек из config.yaml с подстановкой переменных окружения вида ${VAR}."""
import os
import re
from pathlib import Path

import yaml

_ENV = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def _expand(value):
    if isinstance(value, str):
        return _ENV.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def find_config(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    for name in ("config.yaml", "config.yml", "config.example.yaml"):
        p = Path(name)
        if p.exists():
            return p
    raise FileNotFoundError("Не найден config.yaml. Скопируйте config.example.yaml в config.yaml.")


def load(explicit: str | None = None) -> dict:
    path = find_config(explicit)
    with path.open(encoding="utf-8") as f:
        cfg = _expand(yaml.safe_load(f) or {})
    cfg["_config_path"] = str(path)
    base = Path(cfg.get("project", {}).get("data_dir", "data"))
    base.mkdir(parents=True, exist_ok=True)
    (base / "out").mkdir(exist_ok=True)
    (base / "images").mkdir(exist_ok=True)
    return cfg


def out_dir(cfg: dict, product_id: str) -> Path:
    d = Path(cfg["project"]["data_dir"]) / "out" / product_id
    d.mkdir(parents=True, exist_ok=True)
    return d
