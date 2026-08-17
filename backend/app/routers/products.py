from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Product

router = APIRouter(prefix="/api", tags=["products"])


def product_view(product: Product) -> dict:
    images = []
    for image in product.images or []:
        item = dict(image)
        path = str(item.get("path", "")).replace("\\", "/")
        if path and not item.get("url"):
            item["url"] = "/" + path.lstrip("/")
        images.append(item)
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "price": float(product.price),
        "quantity": product.quantity,
        "brand": product.brand,
        "description": product.description,
        "rating": float(product.rating),
        "badge": product.badge,
        "images": images,
    }


def product_image(product: Product) -> str:
    images = product_view(product)["images"]
    if not images:
        return "/images/products/product-placeholder.svg"
    main = next((item for item in images if item.get("is_main")), images[0])
    return str(main.get("url") or main.get("path") or "/images/products/product-placeholder.svg")


@router.get("/products")
async def products(
    search: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    statement = select(Product).order_by(Product.id)
    if search:
        term = f"%{search.lower()}%"
        statement = statement.where(
            func.lower(Product.name).like(term)
            | func.lower(Product.category).like(term)
            | func.lower(Product.brand).like(term)
            | func.lower(Product.description).like(term)
        )
    if category:
        statement = statement.where(func.lower(Product.category) == category.lower())
    rows = list((await db.scalars(statement)).all())
    return {"status": "success", "products": [product_view(item) for item in rows]}


@router.get("/categories")
async def categories(db: AsyncSession = Depends(get_db)) -> dict:
    values = list((await db.scalars(select(Product.category).distinct().order_by(Product.category))).all())
    return {"status": "success", "categories": values}
