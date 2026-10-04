"""Auth routes."""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from urllib.parse import urlparse

from ..extensions import db
from ..models import Role, User
from . import bp
from .forms import LoginForm, RegisterForm


def _is_safe_url(target: str) -> bool:
    """Prevent open-redirect on the 'next' param."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    """Only admins can create new users."""
    if not current_user.is_admin:
        flash("Only admins can create users.", "danger")
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"User {user.username} created.", "success")
        return redirect(url_for("auth.list_users"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data) and user.is_active_user:
            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, {user.username}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url if _is_safe_url(next_url) else url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/users")
@login_required
def list_users():
    if not current_user.is_admin:
        flash("Admin only.", "danger")
        return redirect(url_for("main.dashboard"))
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("auth/users.html", users=users, roles=list(Role))
