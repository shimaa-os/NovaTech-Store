from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Cart, CartItem, Order, OrderItem, Product, User


def order_payload(order: Order, items: list[OrderItem]) -> dict:
    return {
        "status": "success",
        "message": "Checkout Completed Successfully",
        "order_id": str(order.id),
        "items": [
            {
                "product_id": item.product_id,
                "name": item.name,
                "price": float(item.price),
                "quantity": item.quantity,
                "subtotal": float(item.subtotal),
            }
            for item in items
        ],
        "total": float(order.total),
        "remaining_balance": float(order.remaining_balance),
    }


async def _existing_order(db: AsyncSession, user_id, idempotency_key: str) -> tuple[Order, list[OrderItem]] | None:
    order = await db.scalar(
        select(Order).where(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
    )
    if order is None:
        return None
    items = list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all())
    return order, items


async def checkout(db: AsyncSession, user_id, idempotency_key: str) -> dict:
    if not idempotency_key or len(idempotency_key) > 128:
        raise HTTPException(status_code=400, detail="A valid Idempotency-Key header is required")
    async with db.begin():
        user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Authentication required")

        existing = await _existing_order(db, user.id, idempotency_key)
        if existing:
            return order_payload(*existing)

        cart = await db.scalar(select(Cart).where(Cart.user_id == user.id).with_for_update())
        if cart is None:
            raise HTTPException(status_code=400, detail="Cart Is Empty")
        cart_items = list(
            (
                await db.scalars(
                    select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.product_id).with_for_update()
                )
            ).all()
        )
        if not cart_items:
            raise HTTPException(status_code=400, detail="Cart Is Empty")

        product_ids = sorted({item.product_id for item in cart_items})
        products = list(
            (
                await db.scalars(
                    select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
                )
            ).all()
        )
        by_id = {product.id: product for product in products}
        total = Decimal("0.00")
        prepared: list[tuple[CartItem, Product, Decimal]] = []
        for item in cart_items:
            product = by_id.get(item.product_id)
            if product is None:
                raise HTTPException(status_code=409, detail=f"Product {item.product_id} is no longer available")
            if item.quantity <= 0 or item.quantity > product.quantity:
                raise HTTPException(status_code=409, detail=f"Not Enough Stock For {product.name}")
            subtotal = (product.price * item.quantity).quantize(Decimal("0.01"))
            total += subtotal
            prepared.append((item, product, subtotal))

        total = total.quantize(Decimal("0.01"))
        if user.balance < total:
            raise HTTPException(status_code=409, detail="Insufficient Balance")

        user.balance = (user.balance - total).quantize(Decimal("0.01"))
        order = Order(
            user_id=user.id,
            idempotency_key=idempotency_key,
            total=total,
            remaining_balance=user.balance,
        )
        db.add(order)
        await db.flush()
        order_items: list[OrderItem] = []
        for item, product, subtotal in prepared:
            product.quantity -= item.quantity
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                name=product.name,
                price=product.price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
            db.add(order_item)
            order_items.append(order_item)
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.flush()
        return order_payload(order, order_items)

