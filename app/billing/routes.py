"""Billing routes — generate, view, pay, void, PDF."""
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask import current_app, send_file

from ..extensions import db
from ..models import Bill, Order, OrderStatus, PaymentMethod
from . import bp
from .forms import GenerateBillForm, PayBillForm
from .pdf import build_bill_pdf


# ---------- Permission helpers ---------------------------------------------


def _require(fn):
    """Decorator: any authenticated user can read; for writes we check inline."""
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


def _can_pay(bill: Bill) -> bool:
    """Who can mark a bill as paid? Anyone authenticated except a chef-only
    (chef is a kitchen role; they shouldn't be touching money). Admins and
    managers always can. Waiters can pay any bill.
    """
    if not current_user.is_authenticated:
        return False
    if current_user.role == "chef":
        return False
    return True


# ---------- Bills list -----------------------------------------------------


@bp.route("/")
@login_required
def list_bills():
    show = request.args.get("show", "all")
    q = Bill.query.join(Order)

    if show == "unpaid":
        q = q.filter(Bill.is_paid.is_(False))
    elif show == "paid":
        q = q.filter(Bill.is_paid.is_(True))
    elif show == "today":
        today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        q = q.filter(Bill.issued_at >= today_start)
    elif show == "mine":
        if current_user.is_manager:
            q = q  # manager sees all even with ?show=mine
        else:
            q = q.filter(Order.created_by_id == current_user.id)

    if not current_user.is_manager and show not in ("mine",):
        # waiters default to their own bills
        q = q.filter(Order.created_by_id == current_user.id)

    bills = q.order_by(Bill.issued_at.desc()).limit(200).all()
    return render_template(
        "billing/list.html",
        bills=bills,
        show=show,
        PaymentMethod=PaymentMethod,
    )


# ---------- Generate bill from a served order ------------------------------


@bp.route("/orders/<int:order_id>/generate", methods=["GET", "POST"])
@login_required
def generate(order_id: int):
    if current_user.role == "chef":
        abort(403)
    order = db.session.get(Order, order_id) or abort(404)
    if order.bill is not None:
        flash(f"Order #{order.id} already has a bill (#{order.bill.id}).", "info")
        return redirect(url_for("billing.bill_detail", bill_id=order.bill.id))
    if order.status != OrderStatus.SERVED.value:
        flash(
            f"Order #{order.id} is '{order.status}'. Only served orders can be billed.",
            "warning",
        )
        return redirect(url_for("orders.order_detail", order_id=order.id))
    if not order.items:
        flash("Cannot bill an empty order.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))

    # Default tax from app config
    default_tax = current_app.config.get("DEFAULT_TAX_PERCENT", 0)
    form = GenerateBillForm(data={"tax_percent": default_tax})
    if form.validate_on_submit():
        bill = Bill(
            order_id=order.id,
            tax_percent=form.tax_percent.data,
            discount=form.discount.data,
        )
        # Compute subtotal/tax/total inline using the pre-loaded order
        # (avoids the need for the back-ref to be populated on a not-yet-flushed bill).
        subtotal = order.total
        tax_amount = (subtotal * form.tax_percent.data / Decimal("100")).quantize(Decimal("0.01"))
        total = (subtotal + tax_amount - form.discount.data).quantize(Decimal("0.01"))
        bill.subtotal = subtotal
        bill.tax_amount = tax_amount
        bill.total = total
        bill.payment_method = None
        db.session.add(bill)
        db.session.commit()
        flash(f"Bill #{bill.id} generated.", "success")
        return redirect(url_for("billing.bill_detail", bill_id=bill.id))
    return render_template("billing/generate.html", form=form, order=order)


# ---------- Bill detail / print view --------------------------------------


@bp.route("/bills/<int:bill_id>")
@login_required
def bill_detail(bill_id: int):
    bill = db.session.get(Bill, bill_id) or abort(404)
    pay_form = PayBillForm() if (not bill.is_paid and _can_pay(bill)) else None
    return render_template(
        "billing/detail.html",
        bill=bill,
        pay_form=pay_form,
        print_mode=request.args.get("print") == "1",
    )


# ---------- Mark bill paid -------------------------------------------------


@bp.route("/bills/<int:bill_id>/pay", methods=["POST"])
@login_required
def pay(bill_id: int):
    bill = db.session.get(Bill, bill_id) or abort(404)
    if bill.is_paid:
        flash("Bill is already paid.", "info")
        return redirect(url_for("billing.bill_detail", bill_id=bill.id))
    if not _can_pay(bill):
        abort(403)

    form = PayBillForm()
    if not form.validate_on_submit():
        flash("Invalid form submission.", "danger")
        return redirect(url_for("billing.bill_detail", bill_id=bill.id))

    bill.is_paid = True
    bill.payment_method = form.payment_method.data
    bill.paid_at = datetime.utcnow()
    # Cascade: the order is now fully settled
    bill.order.status = OrderStatus.PAID.value
    db.session.commit()
    flash(
        f"Bill #{bill.id} marked paid ({bill.payment_method.upper()}). "
        f"Order #{bill.order.id} is now closed.",
        "success",
    )
    return redirect(url_for("billing.bill_detail", bill_id=bill.id))


# ---------- Void an unpaid bill (admin/manager) ---------------------------


@bp.route("/bills/<int:bill_id>/void", methods=["POST"])
@login_required
def void(bill_id: int):
    if not current_user.is_manager:
        abort(403)
    bill = db.session.get(Bill, bill_id) or abort(404)
    if bill.is_paid:
        flash("Paid bills cannot be voided. Issue a refund instead.", "warning")
        return redirect(url_for("billing.bill_detail", bill_id=bill.id))
    order_id = bill.order_id
    db.session.delete(bill)
    db.session.commit()
    flash(f"Bill voided. Order #{order_id} is back to 'served'.", "info")
    return redirect(url_for("orders.order_detail", order_id=order_id))


# ---------- PDF receipt ----------------------------------------------------


@bp.route("/bills/<int:bill_id>/pdf")
@login_required
def pdf(bill_id: int):
    bill = db.session.get(Bill, bill_id) or abort(404)
    pdf_bytes = build_bill_pdf(bill)
    filename = f"receipt-{bill.id}.pdf"
    return send_file(
        __import__("io").BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
