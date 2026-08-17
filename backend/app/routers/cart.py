from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..dependencies import AuthenticatedUser, require_user
from ..models import Cart, CartItem, Product
from ..schemas import CartMutationRequest, QuantityRequest
from .products import product_image, product_view

router = APIRouter(prefix="/api/cart", tags=["cart"])


async def _get_or_create_cart(db: AsyncSession, user_id) -> Cart:
    cart = await db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.flush()
    return cart


async def _cart_for_user(db: AsyncSession, user_id) -> Cart | None:
    return await db.scalar(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
    )


@router.get("")
async def get_cart(
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cart = await _cart_for_user(db, auth.user.id)
    return cart_payload(cart)


@router.post("")
async def add_to_cart(
    payload: CartMutationRequest,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    async with db.begin():
        product = await db.scalar(
            select(Product).where(Product.id == payload.product_id).with_for_update()
        )
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.quantity <= 0:
            raise HTTPException(status_code=409, detail="Product is out of stock")
        cart = await _get_or_create_cart(db, auth.user.id)
        item = await db.scalar(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
        )
        new_quantity = payload.quantity if item is None else item.quantity + payload.quantity
        if new_quantity > product.quantity:
            raise HTTPException(status_code=409, detail="Requested quantity is not available")
        if item is None:
            db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=payload.quantity))
        else:
            item.quantity = new_quantity
    fresh_cart = await _cart_for_user(db, auth.user.id)
    return cart_payload(fresh_cart, message="Cart Updated")


@router.patch("/{item_id}")
async def update_item(
    item_id: uuid.UUID,
    payload: QuantityRequest,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    async with db.begin():
        item = await db.scalar(
            select(CartItem)
            .join(Cart)
            .join(Product)
            .where(CartItem.id == item_id, Cart.user_id == auth.user.id)
            .options(selectinload(CartItem.product))
            .with_for_update()
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Cart item not found")
        if payload.quantity > item.product.quantity:
            raise HTTPException(status_code=409, detail="Requested quantity is not available")
        item.quantity = payload.quantity
    cart = await _cart_for_user(db, auth.user.id)
    return cart_payload(cart, message="Cart Updated")


@router.delete("/{item_id}")
async def delete_item(
    item_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(
        delete(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id.in_(select(Cart.id).where(Cart.user_id == auth.user.id)),
        )
    )
    await db.commit()
    cart = await _cart_for_user(db, auth.user.id)
    return cart_payload(cart, message="Item Removed")


@router.delete("")
async def clear_cart(
    auth: AuthenticatedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(delete(CartItem).where(CartItem.cart_id.in_(select(Cart.id).where(Cart.user_id == auth.user.id))))
    await db.commit()
    return {"status": "success", "message": "Cart Cleared", "cart": [], "total": 0.0}


def cart_payload(cart: Cart | None, message: str = "Cart Loaded") -> dict:
    items = []
    total = Decimal("0.00")
    if cart:
        for item in sorted(cart.items, key=lambda row: row.product.name):
            subtotal = Decimal(item.product.price) * item.quantity
            total += subtotal
            items.append(
                {
                    "id": str(item.id),
                    "product_id": item.product_id,
                    "product": product_view(item.product),
                    "name": item.product.name,
                    "price": float(item.product.price),
                    "quantity": item.quantity,
                    "stock": item.product.quantity,
                    "subtotal": float(subtotal),
                    "image": product_image(item.product),
                }
            )
    return {"status": "success", "message": message, "cart": items, "items": items, "total": float(total)}
