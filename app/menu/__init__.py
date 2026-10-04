"""Menu blueprint: categories and items."""
from flask import Blueprint

bp = Blueprint("menu", __name__, template_folder="../templates/menu", url_prefix="/menu")

from . import routes  # noqa: E402,F401
