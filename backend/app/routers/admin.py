from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import require_admin
from ..models import CartItem, Order, Product, User
from ..schemas import ImagePayload, ProductCreateRequest, ProductUpdateRequest, WalletChargeRequest
from ..services.storage import upload_product_image
from .auth import user_view
from .products import product_image, product_view

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict:
    users = await db.scalar(select(func.count()).select_from(User).where(User.role == "user"))
    products = await db.scalar(select(func.count()).select_from(Product))
    stock = await db.scalar(select(func.coalesce(func.sum(Product.quantity), 0)))
    revenue = await db.scalar(select(func.coalesce(func.sum(Order.total), Decimal("0.00"))))
    low_stock = await db.scalar(select(func.count()).select_from(Product).where(Product.quantity <= 5))
    orders = await db.scalar(select(func.count()).select_from(Order))
    return {
        "status": "success",
        "stats": {
            "users": int(users or 0),
            "products": int(products or 0),
            "stock": int(stock or 0),
            "revenue": float(revenue or Decimal("0.00")),
            "low_stock": int(low_stock or 0),
            "orders": int(orders or 0),
        },
    }


@router.get("/users")
async def users(db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.scalars(select(User).where(User.role == "user").order_by(User.username))
    return {"status": "success", "users": [user_view(user) for user in rows]}


@router.post("/wallet/add")
async def add_balance(payload: WalletChargeRequest, db: AsyncSession = Depends(get_db)) -> dict:
    async with db.begin():
        user = await db.scalar(select(User).where(User.username == payload.user_name.lower(), User.role == "user").with_for_update())
        if user is None or not user.is_active:
            raise HTTPException(status_code=404, detail="User not found")
        user.balance = Decimal(user.balance) + payload.amount
    return {"status": "success", "message": "Balance Added", "user": user_view(user)}


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    product = Product(
        name=payload.name.strip(),
        category=payload.category.strip(),
        price=payload.price,
        quantity=payload.quantity,
        brand=payload.brand.strip() or "Nova",
        description=payload.description.strip(),
        rating=payload.rating,
        badge=payload.badge.strip(),
        images=[],
    )
    db.add(product)
    await db.flush()
    if payload.image:
        product.images = [await upload_product_image(product.id, payload.image)]
    await db.commit()
    await db.refresh(product)
    return {"status": "success", "message": "Product Created", "product": product_view(product)}


@router.patch("/products/{product_id}")
async def update_product(product_id: int, payload: ProductUpdateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(product, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Product could not be updated") from exc
    await db.refresh(product)
    return {"status": "success", "message": "Product Updated", "product": product_view(product)}


@router.post("/products/{product_id}/main-image")
async def update_main_image(product_id: int, payload: ImagePayload, db: AsyncSession = Depends(get_db)) -> dict:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    image = await upload_product_image(product.id, payload)
    product.images = [image, *[existing for existing in product.images if existing.get("url") != image["url"]]]
    await db.commit()
    await db.refresh(product)
    return {"status": "success", "message": "Image Updated", "image": product_image(product), "product": product_view(product)}


@router.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    referenced = await db.scalar(select(func.count()).select_from(CartItem).where(CartItem.product_id == product_id))
    if referenced:
        await db.execute(delete(CartItem).where(CartItem.product_id == product_id))
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
    return {"status": "success", "message": "Product Deleted"}
