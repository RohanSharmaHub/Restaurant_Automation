import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'restaurant.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Billing config
    DEFAULT_TAX_PERCENT = float(os.environ.get("DEFAULT_TAX_PERCENT", 13.0))

    # Pagination
    ITEMS_PER_PAGE = 20
