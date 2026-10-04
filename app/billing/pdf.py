"""PDF receipt generator using ReportLab.

Renders a clean, single-page A4 receipt suitable for printing.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_bill_pdf(bill) -> bytes:
    """Render a `Bill` (with eager-loaded `order.items` + `created_by` + `table`)
    to a PDF byte string.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Receipt #{bill.id}",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=2)
    bold_right = ParagraphStyle("boldright", parent=styles["Normal"], alignment=2, fontName="Helvetica-Bold")

    story = []
    order = bill.order
    restaurant_name = "RestoAuto"
    story.append(Paragraph(restaurant_name, h1))
    story.append(Paragraph("Receipt", small))
    story.append(Spacer(1, 6 * mm))

    # Header table: bill meta (left) + table/server (right)
    meta_left = [
        Paragraph(f"<b>Bill #</b> {bill.id}", styles["Normal"]),
        Paragraph(f"<b>Issued</b> {bill.issued_at.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
    ]
    if bill.is_paid:
        meta_left.append(Paragraph(f"<b>Paid</b> {bill.paid_at.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        meta_left.append(Paragraph(f"<b>Method</b> {bill.payment_method.upper()}", styles["Normal"]))
    meta_right = [
        Paragraph(f"<b>Table</b> {order.table.number}", right),
        Paragraph(f"<b>Server</b> {order.created_by.username}", right),
        Paragraph(f"<b>Order</b> #{order.id}", right),
    ]
    header = Table(
        [[meta_left, meta_right]],
        colWidths=[(A4[0] - 36 * mm) / 2] * 2,
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    # Line items
    data = [["#", "Item", "Qty", "Unit (Rs.)", "Total (Rs.)"]]
    for i, it in enumerate(order.items, start=1):
        data.append([
            str(i),
            it.menu_item.name + (f"  ({it.notes})" if it.notes else ""),
            str(it.quantity),
            f"{it.unit_price:.2f}",
            f"{it.line_total:.2f}",
        ])
    tbl = Table(
        data,
        colWidths=[10 * mm, 80 * mm, 15 * mm, 25 * mm, 30 * mm],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    # Totals
    totals_data = [
        ["Subtotal", f"Rs. {bill.subtotal:.2f}"],
        [f"Tax ({bill.tax_percent:.2f}%)", f"Rs. {bill.tax_amount:.2f}"],
        ["Discount", f"- Rs. {bill.discount:.2f}"],
        ["Total", f"Rs. {bill.total:.2f}"],
    ]
    totals = Table(totals_data, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.7, colors.black),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(totals)
    story.append(Spacer(1, 10 * mm))

    # Status badge
    if bill.is_paid:
        story.append(Paragraph("<b>PAID</b>", ParagraphStyle(
            "paid", parent=styles["Heading2"], textColor=colors.darkgreen, alignment=1,
        )))
    else:
        story.append(Paragraph("<b>UNPAID</b>", ParagraphStyle(
            "unpaid", parent=styles["Heading2"], textColor=colors.darkred, alignment=1,
        )))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · RestoAuto",
        small,
    ))

    doc.build(story)
    return buf.getvalue()
