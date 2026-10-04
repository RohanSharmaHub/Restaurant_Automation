"""Orders blueprint: tables, order lifecycle, kitchen view."""
from flask import Blueprint

bp = Blueprint("orders", __name__, template_folder="../templates/orders", url_prefix="/orders")

from . import routes  # noqa: E402,F401
