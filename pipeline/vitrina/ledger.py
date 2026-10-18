"""Таблица товаров в CSV. Статусы: new -> scripted -> built -> published, либо rejected."""
import csv
from pathlib import Path

FIELDS = [
    "id", "channel", "title", "description", "price", "affiliate_url", "images",
    "category", "commission_pct", "status", "notes",
    "script_path", "video_path", "cover_path", "published_at",
]
STATUSES = ("new", "scripted", "built", "published", "rejected")


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.rows: list[dict] = []
        if self.path.exists():
            with self.path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    self.rows.append({k: row.get(k, "") or "" for k in FIELDS})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(self.rows)

    def get(self, product_id: str) -> dict:
        for r in self.rows:
            if r["id"] == product_id:
                return r
        raise KeyError(f"Товар {product_id} не найден в {self.path}")

    def items(self, status: str | None = None, channel: str | None = None) -> list[dict]:
        out = self.rows
        if status:
            out = [r for r in out if r["status"] == status]
        if channel:
            out = [r for r in out if r["channel"] == channel]
        return out

    def update(self, product_id: str, **fields) -> dict:
        row = self.get(product_id)
        for k, v in fields.items():
            if k not in FIELDS:
                raise KeyError(k)
            row[k] = "" if v is None else str(v)
        self.save()
        return row

    def add(self, **fields) -> dict:
        row = {k: "" for k in FIELDS}
        row["status"] = "new"
        row.update({k: str(v) for k, v in fields.items()})
        if not row["id"]:
            raise ValueError("Нужен id товара")
        self.rows.append(row)
        self.save()
        return row

    @staticmethod
    def images_of(row: dict) -> list[str]:
        return [s.strip() for s in row.get("images", "").split(";") if s.strip()]
