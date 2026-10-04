"""Application factory for the restaurant automation system."""
from datetime import datetime

from flask import Flask, render_template

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register user loader
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):  # noqa: D401
        return db.session.get(User, int(user_id))

    # Register blueprints
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .menu import bp as menu_bp
    from .orders import bp as orders_bp
    from .billing import bp as billing_bp
    from .reports import bp as reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(reports_bp)

    # Shell context (so `flask shell` works)
    @app.shell_context_processor
    def shell_context():  # noqa: D401
        return {"db": db, "User": User}

    # Template context — available in every template
    @app.context_processor
    def template_globals():
        return {
            "now_year": datetime.utcnow().year,
            "now_iso": lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        }

    # Error handlers
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        # Roll back any pending DB transaction so the error page itself
        # can render without hitting a PendingRollbackError when templates
        # try to read related objects.
        try:
            db.session.rollback()
        except Exception:
            pass
        return render_template("errors/500.html"), 500

    return app
