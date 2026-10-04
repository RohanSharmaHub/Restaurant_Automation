"""Order routes — tables layout, new order, status flow, kitchen view.

Permissions summary (enforced inline):
- any user:    read orders, view tables
- waiter+:     create order, add items, mark own order served
- chef:        mark pending/preparing orders as ready (kitchen view)
- manager+:    all of the above + cancel any non-paid order + see all orders
"""
from datetime import datetime
from functools import wraps

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    Table,
)
from . import bp
from .forms import AddOrderItemForm, NewOrderForm, OrderStatusForm


# ---------- Permission helpers ---------------------------------------------


def _require(role_check):
    """Decorator: 403 if user fails the given check."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not role_check():
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _is_chef_or_manager():
    return current_user.is_authenticated and (
        current_user.is_chef or current_user.is_manager
    )


# ---------- Status-machine definition --------------------------------------


# Who is allowed to do each transition?
ALLOWED_TRANSITIONS: dict[tuple[str, str], str] = {
    # (from_status, to_status): required role predicate key
    (OrderStatus.PENDING.value, OrderStatus.PREPARING.value): "waiter_or_manager",
    (OrderStatus.PREPARING.value, OrderStatus.READY.value): "chef_or_manager",
    (OrderStatus.READY.value, OrderStatus.SERVED.value): "waiter_or_manager",
}


def _can_transition(order: Order, new_status: str) -> tuple[bool, str]:
    """Returns (ok, reason_if_not_ok)."""
    key = (order.status, new_status)
    rule = ALLOWED_TRANSITIONS.get(key)
    if rule is None:
        return False, f"Can't move order from {order.status} to {new_status}."

    if rule == "waiter_or_manager":
        # The waiter who created the order, or any manager.
        if current_user.is_manager or order.created_by_id == current_user.id:
            return True, ""
        return False, "Only the waiter who took this order (or a manager) can do that."

    if rule == "chef_or_manager":
        if _is_chef_or_manager():
            return True, ""
        return False, "Only the kitchen or a manager can mark items ready."

    return False, "Unknown rule."


# ---------- Routes: list & tables ------------------------------------------


@bp.route("/")
@login_required
def list_orders():
    if not current_user.is_manager:
        # Waiters and chefs only see their own active orders here.
        orders = (
            Order.query.filter_by(created_by_id=current_user.id)
            .order_by(Order.created_at.desc())
            .limit(50)
            .all()
        )
        return render_template(
            "orders/list.html",
            orders=orders,
            statuses=list(OrderStatus),
            active_status=None,
            scope="mine",
        )

    active_status = request.args.get("status") or None
    q = Order.query
    if active_status:
        q = q.filter_by(status=active_status)
    orders = q.order_by(Order.created_at.desc()).limit(100).all()
    return render_template(
        "orders/list.html",
        orders=orders,
        statuses=list(OrderStatus),
        active_status=active_status,
        scope="all",
    )


@bp.route("/tables")
@login_required
def tables():
    tables = Table.query.order_by(Table.number).all()
    return render_template("orders/tables.html", tables=tables)


@bp.route("/kitchen")
@login_required
def kitchen():
    """Chef-facing queue: all pending + preparing orders, oldest first."""
    active = Order.query.filter(
        Order.status.in_(
            [OrderStatus.PENDING.value, OrderStatus.PREPARING.value]
        )
    ).order_by(Order.created_at.asc()).all()
    return render_template("orders/kitchen.html", orders=active)


# ---------- New order ------------------------------------------------------


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_order():
    """Create a new order. The table can come from ?table=N or a form field.

    On POST, we expect a `lines` list of dicts: {menu_item_id, quantity, notes}.
    If no lines are submitted, the order is created empty and the user is
    redirected to the order detail page to add items.
    """
    table_id = request.values.get("table_id", type=int)
    table = db.session.get(Table, table_id) if table_id else None
    if table is None:
        flash("Pick a table first.", "warning")
        return redirect(url_for("orders.tables"))

    # Refuse if that table already has an open order
    if table.current_order is not None:
        flash(
            f"Table {table.number} already has an open order "
            f"(#{table.current_order.id}). Open it instead.",
            "info",
        )
        return redirect(url_for("orders.order_detail", order_id=table.current_order.id))

    form = NewOrderForm()
    if request.method == "POST":
        # The "new order" form posts parallel arrays: menu_item_id[], quantity[], notes[]
        item_ids = request.form.getlist("menu_item_id")
        quantities = request.form.getlist("quantity")
        notes_list = request.form.getlist("notes")
        lines: list[dict] = []
        for i, mid in enumerate(item_ids):
            try:
                qty_i = int(quantities[i]) if i < len(quantities) else 1
            except (ValueError, TypeError):
                qty_i = 1
            note_i = notes_list[i].strip() if i < len(notes_list) else ""
            if not mid or qty_i <= 0:
                continue
            lines.append({"menu_item_id": int(mid), "quantity": qty_i, "notes": note_i})

        # Even with zero lines we still create the order — the waiter might
        # add items from the order detail page right after.
        order = Order(
            table_id=table.id,
            created_by_id=current_user.id,
            status=OrderStatus.PENDING.value,
            notes=request.form.get("order_notes", "").strip() or None,
        )
        db.session.add(order)
        db.session.flush()  # need order.id for OrderItem rows

        for line in lines:
            mi = db.session.get(MenuItem, line["menu_item_id"])
            if mi is None or not mi.is_available:
                continue  # silently skip items that went 86'd mid-flow
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=mi.id,
                    quantity=line["quantity"],
                    unit_price=mi.price,  # snapshot at order time
                    notes=line["notes"] or None,
                )
            )

        db.session.commit()
        flash(f"Order #{order.id} created for table {table.number}.", "success")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    # GET: render the menu to pick from
    items = (
        MenuItem.query.filter_by(is_available=True)
        .order_by(MenuItem.name)
        .all()
    )
    by_cat: dict[str, list[MenuItem]] = {}
    for it in items:
        by_cat.setdefault(it.category.name, []).append(it)
    return render_template(
        "orders/new.html",
        form=form,
        table=table,
        by_cat=by_cat,
    )


# ---------- Order detail & item manipulation -------------------------------


@bp.route("/<int:order_id>")
@login_required
def order_detail(order_id: int):
    order = db.session.get(Order, order_id) or abort(404)
    add_form = AddOrderItemForm()
    status_form = OrderStatusForm()
    return render_template(
        "orders/detail.html",
        order=order,
        add_form=add_form,
        status_form=status_form,
    )


@bp.route("/<int:order_id>/items", methods=["POST"])
@login_required
def add_item(order_id: int):
    order = db.session.get(Order, order_id) or abort(404)
    if order.status in (OrderStatus.PAID.value, OrderStatus.CANCELLED.value, OrderStatus.SERVED.value):
        flash(f"Can't add items to a {order.status} order.", "danger")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    form = AddOrderItemForm()
    if form.validate_on_submit():
        mi = db.session.get(MenuItem, form.menu_item_id.data)
        if mi is None or not mi.is_available:
            flash("That item is no longer available.", "warning")
        else:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=mi.id,
                    quantity=form.quantity.data,
                    unit_price=mi.price,
                    notes=(form.notes.data or "").strip() or None,
                )
            )
            db.session.commit()
            flash(f"Added {form.quantity.data}× {mi.name}.", "success")
    else:
        flash("Could not add item. Check the form.", "danger")
    return redirect(url_for("orders.order_detail", order_id=order.id))


@bp.route("/<int:order_id>/items/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_item(order_id: int, item_id: int):
    order = db.session.get(Order, order_id) or abort(404)
    if order.status not in (OrderStatus.PENDING.value, OrderStatus.PREPARING.value):
        flash("Items can only be removed before food is ready.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    if not (current_user.is_manager or order.created_by_id == current_user.id):
        abort(403)
    item = OrderItem.query.filter_by(id=item_id, order_id=order.id).first() or abort(404)
    name = item.menu_item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Removed {name}.", "info")
    return redirect(url_for("orders.order_detail", order_id=order.id))


# ---------- Status transitions ---------------------------------------------


@bp.route("/<int:order_id>/status", methods=["POST"])
@login_required
def change_status(order_id: int):
    order = db.session.get(Order, order_id) or abort(404)
    new_status = request.form.get("new_status")
    if new_status not in {s.value for s in OrderStatus}:
        flash("Unknown status.", "danger")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    form = OrderStatusForm()
    if not form.validate_on_submit():
        abort(400)

    ok, reason = _can_transition(order, new_status)
    if not ok:
        flash(reason, "danger")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    order.status = new_status
    if new_status == OrderStatus.SERVED.value:
        order.served_at = datetime.utcnow()
    db.session.commit()
    flash(f"Order #{order.id} is now {new_status}.", "success")
    return redirect(url_for("orders.order_detail", order_id=order.id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel(order_id: int):
    order = db.session.get(Order, order_id) or abort(404)
    if order.status in (OrderStatus.PAID.value, OrderStatus.CANCELLED.value):
        flash("Order is already finalized.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    if not current_user.is_manager:
        abort(403)
    order.status = OrderStatus.CANCELLED.value
    db.session.commit()
    flash(f"Order #{order.id} cancelled.", "info")
    return redirect(url_for("orders.list_orders"))
