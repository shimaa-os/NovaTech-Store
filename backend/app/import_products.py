from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from .config import PROJECT_ROOT
from .db import SessionLocal
from .models import Product

ALLOWED_IMAGE_PREFIX = "images/products/"


def _decimal(value: object, places: str = "0.01") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"Non-finite decimal value: {value!r}")
    return amount.quantize(Decimal(places))


def _clean_images(product: dict) -> list[dict]:
    images = product.get("images") or []
    safe: list[dict] = []
    for item in images:
        path = str(item.get("path", "")).replace("\\", "/")
        url = str(item.get("url", ""))
        if path and path.startswith(ALLOWED_IMAGE_PREFIX):
            safe.append({"path": path})
        elif url:
            parsed = urlparse(url)
            if parsed.scheme == "https" and parsed.netloc:
                safe.append({"url": url})
    return safe[:5]


async def import_file(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("products", [])
    else:
        rows = data
    count = 0
    async with SessionLocal() as db:
        async with db.begin():
            for item in rows:
                await _upsert_product(db, item)
                count += 1
    return count


async def _upsert_product(db: AsyncSession, item: dict) -> None:
    product_id = int(item["id"])
    product = await db.get(Product, product_id)
    if product is None:
        product = Product(id=product_id)
        db.add(product)
    product.name = str(item["name"]).strip()
    product.category = str(item["category"]).strip()
    product.price = _decimal(item["price"])
    product.quantity = int(item.get("quantity", item.get("stock", 0)))
    product.brand = str(item.get("brand") or "Nova").strip()
    product.description = str(item.get("description") or "").strip()
    product.rating = _decimal(item.get("rating", "4.5"), "0.1")
    product.badge = str(item.get("badge") or "").strip()
    product.images = _clean_images(item)
    if product.price <= 0 or product.quantity < 0 or product.rating < 0 or product.rating > 5:
        raise ValueError(f"Invalid product values for product {product_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import NovaTech catalog products idempotently.")
    parser.add_argument("path", nargs="?", default=str(PROJECT_ROOT / "seed" / "products.json"))
    args = parser.parse_args()
    count = asyncio.run(import_file(Path(args.path)))
    print(f"Imported {count} products")


if __name__ == "__main__":
    main()
