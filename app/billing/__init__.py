"""Billing blueprint: bills, payment, PDF receipts."""
from flask import Blueprint

bp = Blueprint("billing", __name__, template_folder="../templates/billing", url_prefix="/billing")

from . import routes  # noqa: E402,F401
