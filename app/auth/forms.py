"""WTForms for the auth blueprint."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
    ValidationError,
)

from ..models import Role, User


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=64),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Letters, digits, and . _ - only.",
            ),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Role",
        choices=[(r.value, r.value.title()) for r in Role],
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, message="At least 6 characters.")],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with that email already exists.")
