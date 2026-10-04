"""Database models for the restaurant automation system.

One file, intentional: a learning project benefits from seeing all the
relationships in one place rather than hunting across modules.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


# ---------- Enums ----------------------------------------------------------


class Role(str, Enum):
    ADMIN = "admin"      # everything
    MANAGER = "manager"  # menu, reports, all orders
    WAITER = "waiter"    # take orders, view menu
    CHEF = "chef"        # kitchen view, mark items ready


class OrderStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"


# ---------- User -----------------------------------------------------------


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.WAITER.value)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", back_populates="created_by", lazy="dynamic")

    # Password helpers
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # Role helpers
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    @property
    def is_manager(self) -> bool:
        return self.role in (Role.ADMIN.value, Role.MANAGER.value)

    @property
    def is_chef(self) -> bool:
        return self.role == Role.CHEF.value

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


# ---------- Menu -----------------------------------------------------------


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    display_order = db.Column(db.Integer, default=0)

    items = db.relationship(
        "MenuItem", back_populates="category", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500))
    is_vegetarian = db.Column(db.Boolean, default=True, nullable=False)
    prep_time_minutes = db.Column(db.Integer, default=10)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category = db.relationship("Category", back_populates="items")

    def __repr__(self) -> str:
        return f"<MenuItem {self.name} @ {self.price}>"


# ---------- Tables & Orders ------------------------------------------------


class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=4)
    location = db.Column(db.String(40))  # e.g. "Window", "Patio", "Indoor"
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    orders = db.relationship("Order", back_populates="table", lazy="dynamic")

    @property
    def current_order(self):
        return (
            self.orders.filter(
                Order.status.in_(
                    [
                        OrderStatus.PENDING.value,
                        OrderStatus.PREPARING.value,
                        OrderStatus.READY.value,
                        OrderStatus.SERVED.value,
                    ]
                )
            )
            .order_by(Order.created_at.desc())
            .first()
        )

    def __repr__(self) -> str:
        return f"<Table #{self.number} cap={self.capacity}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(
        db.String(20), nullable=False, default=OrderStatus.PENDING.value, index=True
    )
    notes = db.Column(db.Text)  # general notes from waiter
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    served_at = db.Column(db.DateTime)

    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    table = db.relationship("Table", back_populates="orders")

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_by = db.relationship("User", back_populates="orders")

    items = db.relationship(
        "OrderItem", back_populates="order", lazy="select", cascade="all, delete-orphan"
    )
    bill = db.relationship(
        "Bill", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0.00"))

    @property
    def is_open(self) -> bool:
        return self.status in (
            OrderStatus.PENDING.value,
            OrderStatus.PREPARING.value,
            OrderStatus.READY.value,
            OrderStatus.SERVED.value,
        )

    def __repr__(self) -> str:
        return f"<Order #{self.id} table={self.table_id} status={self.status}>"


class OrderItem(db.Model):
    """Snapshot of a menu item at the moment of ordering.

    `unit_price` is captured here so price changes to MenuItem don't rewrite
    history. `line_total` is computed.
    """

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    notes = db.Column(db.String(255))  # e.g. "no onions", "extra spicy"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    order = db.relationship("Order", back_populates="items")

    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False)
    menu_item = db.relationship("MenuItem")

    @property
    def line_total(self) -> Decimal:
        return Decimal(self.unit_price) * self.quantity

    def __repr__(self) -> str:
        return f"<OrderItem {self.menu_item.name} x{self.quantity}>"


# ---------- Billing --------------------------------------------------------


class Bill(db.Model):
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20))  # null until paid
    is_paid = db.Column(db.Boolean, default=False, nullable=False, index=True)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)

    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id"), unique=True, nullable=False
    )
    order = db.relationship("Order", back_populates="bill")

    def recompute(self) -> None:
        """Recalculate totals from the order's items.

        We accept `order` as an optional argument so callers can pass a
        pre-loaded order even when the relationship hasn't been refreshed
        yet (e.g. just after `db.session.flush()`).
        """
        order = getattr(self, "order", None)
        subtotal = order.total if order is not None else self.subtotal
        self.subtotal = subtotal
        self.tax_amount = (
            subtotal * Decimal(self.tax_percent) / Decimal(100)
        ).quantize(Decimal("0.01"))
        self.total = (
            subtotal + self.tax_amount - Decimal(self.discount)
        ).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<Bill order={self.order_id} total={self.total} paid={self.is_paid}>"
