"""WTForms for the reports blueprint."""
from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField
from wtforms.validators import DataRequired, Optional


PRESETS = [
    ("today", "Today"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("mtd", "Month-to-date"),
    ("custom", "Custom range"),
]


class SalesReportForm(FlaskForm):
    preset = SelectField("Range", choices=PRESETS, default="7d", validators=[DataRequired()])
    start = DateField("From", default=date.today, validators=[Optional()])
    end = DateField("To", default=date.today, validators=[Optional()])
