"""Reports blueprint: sales reports, CSV export."""
from flask import Blueprint

bp = Blueprint("reports", __name__, template_folder="../templates/reports", url_prefix="/reports")

from . import routes  # noqa: E402,F401
