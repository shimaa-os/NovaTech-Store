from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "202608180001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("mfa_secret", sa.Text(), nullable=True),
        sa.Column("mfa_confirmed", sa.Boolean(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role in ('user', 'admin')", name="users_role_valid"),
        sa.CheckConstraint("balance >= 0", name="users_balance_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("users_email_idx", "users", ["email"], unique=True)
    op.create_index("users_username_idx", "users", ["username"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("badge", sa.String(length=50), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price > 0", name="products_price_positive"),
        sa.CheckConstraint("quantity >= 0", name="products_quantity_nonnegative"),
        sa.CheckConstraint("rating >= 0 and rating <= 5", name="products_rating_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("products_category_idx", "products", ["category"])

    op.create_table(
        "carts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total > 0", name="orders_total_positive"),
        sa.CheckConstraint("remaining_balance >= 0", name="orders_balance_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="orders_user_idempotency_key"),
    )
    op.create_index("orders_user_id_created_at_idx", "orders", ["user_id", "created_at"])

    op.create_table(
        "cart_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cart_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="cart_items_quantity_positive"),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "product_id", name="cart_items_cart_product_key"),
    )
    op.create_index("cart_items_cart_id_idx", "cart_items", ["cart_id"])
    op.create_index("cart_items_product_id_idx", "cart_items", ["product_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("price > 0", name="order_items_price_positive"),
        sa.CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
        sa.CheckConstraint("subtotal > 0", name="order_items_subtotal_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("order_items_order_id_idx", "order_items", ["order_id"])
    op.create_index("order_items_product_id_idx", "order_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("order_items_product_id_idx", table_name="order_items")
    op.drop_index("order_items_order_id_idx", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("cart_items_product_id_idx", table_name="cart_items")
    op.drop_index("cart_items_cart_id_idx", table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index("orders_user_id_created_at_idx", table_name="orders")
    op.drop_table("orders")
    op.drop_table("carts")
    op.drop_index("products_category_idx", table_name="products")
    op.drop_table("products")
    op.drop_index("users_username_idx", table_name="users")
    op.drop_index("users_email_idx", table_name="users")
    op.drop_table("users")


def _unused_type_check() -> Sequence[str]:
    return ()
