"""WTForms for the billing blueprint."""
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField
from wtforms.validators import DataRequired, InputRequired, NumberRange

from ..models import PaymentMethod


class GenerateBillForm(FlaskForm):
    """Form to create a Bill from a served order.

    We use `InputRequired` (not `DataRequired`) on numeric fields so that
    0% tax or Rs. 0 discount are accepted — `DataRequired` treats 0 as falsy
    and rejects it.
    """
    tax_percent = DecimalField(
        "Tax (%)",
        places=2,
        default=13.0,
        validators=[InputRequired(), NumberRange(min=0, max=100)],
    )
    discount = DecimalField(
        "Discount (Rs.)",
        places=2,
        default=0,
        validators=[InputRequired(), NumberRange(min=0)],
    )


class PayBillForm(FlaskForm):
    """Form to mark a bill as paid and choose the payment method."""
    payment_method = SelectField(
        "Payment method",
        choices=[(m.value, m.value.upper()) for m in PaymentMethod],
        validators=[DataRequired()],
    )
