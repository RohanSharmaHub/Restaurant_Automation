"""WTForms for the menu blueprint."""
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, URL, ValidationError

from ..models import Category, MenuItem


class CategoryForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(min=2, max=80)]
    )
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    display_order = IntegerField(
        "Display order",
        default=0,
        validators=[NumberRange(min=0, max=999)],
    )

    def __init__(self, original_name: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_name = (original_name or "").strip().lower()

    def validate_name(self, field):
        cleaned = field.data.strip()
        existing = Category.query.filter(
            Category.name.ilike(cleaned)
        ).first()
        if existing and existing.name.lower() != self._original_name:
            raise ValidationError("A category with that name already exists.")


class MenuItemForm(FlaskForm):
    name = StringField(
        "Name", validators=[DataRequired(), Length(min=2, max=120)]
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    price = DecimalField(
        "Price",
        places=2,
        validators=[DataRequired(), NumberRange(min=0, max=99999)],
    )
    image_url = StringField("Image URL", validators=[Optional(), URL(message="Must be a valid URL"), Length(max=500)])
    is_vegetarian = BooleanField("Vegetarian")
    prep_time_minutes = IntegerField(
        "Prep time (minutes)",
        default=10,
        validators=[NumberRange(min=1, max=240)],
    )
    is_available = BooleanField("Available", default=True)
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate category choices fresh on every form build so newly added
        # categories appear without restarting the server.
        self.category_id.choices = [
            (c.id, c.name) for c in Category.query.order_by(Category.display_order, Category.name).all()
        ]

    def validate_category_id(self, field):
        if not Category.query.get(field.data):
            raise ValidationError("Please pick a valid category.")
