"""Main routes — landing page, dashboard, search."""
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import abort, render_template, request
from flask_login import current_user, login_required

from ..models import Bill, MenuItem, Order, OrderStatus
from . import bp


def _start_of_today() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


@bp.route("/")
def index():
    """Public landing page."""
    if current_user.is_authenticated:
        return dashboard()
    return render_template("landing.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    today_start = _start_of_today()

    # Today's bills
    todays_bills = Bill.query.filter(
        Bill.is_paid.is_(True), Bill.paid_at >= today_start
    ).all()
    todays_revenue = sum((b.total for b in todays_bills), Decimal("0"))
    todays_bill_count = len(todays_bills)
    todays_avg = (todays_revenue / todays_bill_count) if todays_bill_count else Decimal("0")

    # Today's orders
    todays_orders = Order.query.filter(Order.created_at >= today_start).all()
    todays_orders_count = len(todays_orders)

    # Open orders by status
    open_statuses = [
        OrderStatus.PENDING.value,
        OrderStatus.PREPARING.value,
        OrderStatus.READY.value,
        OrderStatus.SERVED.value,
    ]
    open_orders = Order.query.filter(Order.status.in_(open_statuses)).all()
    by_status = Counter(o.status for o in open_orders)

    # 7-day revenue series (for text bar chart)
    series = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        start = datetime.combine(d, datetime.min.time())
        end = datetime.combine(d, datetime.max.time())
        day_total = sum(
            (b.total for b in Bill.query.filter(
                Bill.is_paid.is_(True),
                Bill.paid_at >= start, Bill.paid_at <= end,
            )),
            Decimal("0"),
        )
        series.append((d, day_total))

    # Top 5 items over the last 7 days (by quantity)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_orders = (
        Order.query.filter(Order.created_at >= week_ago).all()
    )
    item_counter: Counter = Counter()
    for o in recent_orders:
        for it in o.items:
            item_counter[it.menu_item.name] += it.quantity
    top_items = item_counter.most_common(5)

    # 86'd items (manager: full list with quick un-86; everyone: count)
    unavailable = MenuItem.query.filter_by(is_available=False).order_by(MenuItem.name).all()

    # Recent bills
    recent_bills = (
        Bill.query.filter(Bill.is_paid.is_(True))
        .order_by(Bill.paid_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "main/dashboard.html",
        todays_revenue=todays_revenue,
        todays_bill_count=todays_bill_count,
        todays_avg=todays_avg,
        todays_orders_count=todays_orders_count,
        by_status=by_status,
        open_orders_count=sum(by_status.values()),
        series=series,
        top_items=top_items,
        unavailable=unavailable,
        recent_bills=recent_bills,
    )


# ---------- Global search (manager+) ---------------------------------------


@bp.route("/search")
@login_required
def search():
    if not current_user.is_manager:
        abort(403)
    q = (request.args.get("q") or "").strip()
    results = {"menu": [], "orders": [], "bills": []}
    if q:
        like = f"%{q}%"
        results["menu"] = (
            MenuItem.query.filter(MenuItem.name.ilike(like))
            .order_by(MenuItem.name)
            .limit(20)
            .all()
        )
        # orders: match by id or notes
        try:
            oid = int(q)
            order_hits = Order.query.filter(Order.id == oid).all()
        except ValueError:
            order_hits = []
        note_hits = Order.query.filter(Order.notes.ilike(like)).limit(20).all()
        # de-dup
        seen = set()
        merged = []
        for o in order_hits + note_hits:
            if o.id in seen:
                continue
            seen.add(o.id)
            merged.append(o)
        results["orders"] = merged[:20]

        # bills: match by id
        try:
            bid = int(q)
            results["bills"] = Bill.query.filter(Bill.id == bid).all()
        except ValueError:
            results["bills"] = []

    return render_template("search/results.html", q=q, results=results)
