"""Auth blueprint: register, login, logout."""
from flask import Blueprint

bp = Blueprint("auth", __name__, template_folder="../templates/auth", url_prefix="/auth")

from . import routes  # noqa: E402,F401
