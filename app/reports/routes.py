"""Reports routes — sales report, CSV export, print view."""
import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Response, abort, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Bill, Order, OrderItem, OrderStatus, PaymentMethod
from . import bp
from .forms import SalesReportForm

ZERO = Decimal("0")


# ---------- Date-range resolution ------------------------------------------


def _resolve_range(preset: str, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    """Returns (inclusive_start, inclusive_end) datetimes for the report.

    `end` is bumped to end-of-day so a same-day range still includes the
    entire day's bills.
    """
    today = date.today()
    if preset == "today":
        s = e = today
    elif preset == "7d":
        s, e = today - timedelta(days=6), today
    elif preset == "30d":
        s, e = today - timedelta(days=29), today
    elif preset == "mtd":
        s, e = today.replace(day=1), today
    elif preset == "custom" and start and end:
        s, e = start, end
    else:
        # fallback to today
        s = e = today

    if s > e:
        s, e = e, s  # tolerate swapped dates

    return (
        datetime.combine(s, time.min),
        datetime.combine(e, time.max),
    )


# ---------- Aggregation helpers -------------------------------------------


def _aggregate(start: datetime, end: datetime) -> dict:
    """Compute report aggregates over the given window."""
    bills_q = Bill.query.filter(
        Bill.is_paid.is_(True),
        Bill.paid_at >= start,
        Bill.paid_at <= end,
    )
    bills = bills_q.all()

    total_revenue = sum((b.total for b in bills), ZERO)
    total_bills = len(bills)
    avg_bill = (total_revenue / total_bills) if total_bills else ZERO

    # Orders taken in the window (regardless of payment)
    orders_in_range = Order.query.filter(
        Order.created_at >= start, Order.created_at <= end
    ).count()

    # Top items by qty
    item_counter: Counter = Counter()
    item_revenue: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for b in bills:
        for it in b.order.items:
            item_counter[it.menu_item.name] += it.quantity
            item_revenue[it.menu_item.name] += it.line_total

    top_items = [
        (name, qty, item_revenue[name])
        for name, qty in item_counter.most_common(10)
    ]

    # Payment-method breakdown
    pm_counter: Counter = Counter()
    pm_amount: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for b in bills:
        if b.payment_method:
            pm_counter[b.payment_method] += 1
            pm_amount[b.payment_method] += b.total

    payment_breakdown = [
        (pm, pm_counter[pm], pm_amount[pm])
        for pm in [m.value for m in PaymentMethod]
    ]

    # Daily breakdown
    daily: defaultdict[date, dict] = defaultdict(
        lambda: {"bills": 0, "revenue": ZERO, "top": Counter()}
    )
    for b in bills:
        d = b.paid_at.date()
        daily[d]["bills"] += 1
        daily[d]["revenue"] += b.total
        for it in b.order.items:
            daily[d]["top"][it.menu_item.name] += it.quantity
    daily_rows = []
    for d in sorted(daily.keys()):
        info = daily[d]
        top_name, top_qty = (info["top"].most_common(1)[0] if info["top"] else ("—", 0))
        daily_rows.append((d, info["bills"], info["revenue"], top_name, top_qty))

    return {
        "total_revenue": total_revenue,
        "total_bills": total_bills,
        "avg_bill": avg_bill,
        "orders_in_range": orders_in_range,
        "top_items": top_items,
        "payment_breakdown": payment_breakdown,
        "daily_rows": daily_rows,
    }


# ---------- Routes ---------------------------------------------------------


@bp.route("/sales")
@login_required
def sales():
    if not current_user.is_manager:
        abort(403)
    form = SalesReportForm(request.args, meta={"csrf": False})
    if not form.validate():
        # fall back to defaults
        form.preset.data = form.preset.data or "7d"
    preset = form.preset.data or "7d"
    start_date = form.start.data
    end_date = form.end.data
    start, end = _resolve_range(preset, start_date, end_date)
    data = _aggregate(start, end)
    return render_template(
        "reports/sales.html",
        form=form,
        start=start,
        end=end,
        **data,
    )


@bp.route("/sales.csv")
@login_required
def sales_csv():
    if not current_user.is_manager:
        abort(403)
    preset = request.args.get("preset", "7d")
    start_date = _parse_date(request.args.get("start"))
    end_date = _parse_date(request.args.get("end"))
    start, end = _resolve_range(preset, start_date, end_date)
    data = _aggregate(start, end)

    buf = io.StringIO()
    writer = csv.writer(buf)
    # Header
    writer.writerow([f"RestoAuto sales report", f"{start.date()} to {end.date()}"])
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Bills paid", data["total_bills"]])
    writer.writerow(["Total revenue (Rs.)", f"{data['total_revenue']:.2f}"])
    writer.writerow(["Average bill (Rs.)", f"{data['avg_bill']:.2f}"])
    writer.writerow(["Orders taken", data["orders_in_range"]])
    writer.writerow([])
    writer.writerow(["Daily breakdown"])
    writer.writerow(["Date", "Bills", "Revenue (Rs.)", "Top item", "Top qty"])
    for d, bills, revenue, top_name, top_qty in data["daily_rows"]:
        writer.writerow([d, bills, f"{revenue:.2f}", top_name, top_qty])
    writer.writerow([])
    writer.writerow(["Top items"])
    writer.writerow(["Item", "Qty", "Revenue (Rs.)"])
    for name, qty, rev in data["top_items"]:
        writer.writerow([name, qty, f"{rev:.2f}"])
    writer.writerow([])
    writer.writerow(["Payment methods"])
    writer.writerow(["Method", "Count", "Total (Rs.)"])
    for pm, count, amt in data["payment_breakdown"]:
        writer.writerow([pm, count, f"{amt:.2f}"])

    filename = f"sales_{start.date()}_{end.date()}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/sales/print")
@login_required
def sales_print():
    if not current_user.is_manager:
        abort(403)
    preset = request.args.get("preset", "7d")
    start_date = _parse_date(request.args.get("start"))
    end_date = _parse_date(request.args.get("end"))
    start, end = _resolve_range(preset, start_date, end_date)
    data = _aggregate(start, end)
    return render_template(
        "reports/print.html",
        start=start,
        end=end,
        **data,
    )


# ---------- Utilities ------------------------------------------------------


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None
