"""WTForms for the orders blueprint.

Forms are intentionally simple: we mostly use them as input validators +
CSRF tokens. The "add multiple items" pattern uses dynamic sub-forms.
"""
from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from ..models import MenuItem, Table


# ---------- New order ------------------------------------------------------


class NewOrderForm(FlaskForm):
    """Empty form used to take a CSRF token on the order-creation page."""
    table_id = HiddenField()


# ---------- Add an item to an existing order -------------------------------


class AddOrderItemForm(FlaskForm):
    menu_item_id = SelectField("Item", coerce=int, validators=[DataRequired()])
    quantity = IntegerField(
        "Qty", default=1, validators=[DataRequired(), NumberRange(min=1, max=99)]
    )
    notes = StringField("Notes", validators=[Optional(), Length(max=255)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show items that are still orderable
        self.menu_item_id.choices = [
            (m.id, f"{m.name} — Rs. {m.price:.2f}")
            for m in MenuItem.query.filter_by(is_available=True)
            .order_by(MenuItem.name)
            .all()
        ]


# ---------- Status transition ----------------------------------------------


class OrderStatusForm(FlaskForm):
    """Form backing the status-change buttons; hidden, only CSRF needed."""
    pass
