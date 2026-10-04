"""Menu routes — list, create, edit, delete categories & items."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Category, MenuItem
from . import bp
from .forms import CategoryForm, MenuItemForm


# ---------- Permission helpers ---------------------------------------------


def _can_manage():
    return current_user.is_authenticated and current_user.is_manager


def _require_manager():
    if not _can_manage():
        abort(403)


# ---------- Public-ish: list & detail --------------------------------------


@bp.route("/")
@login_required
def list_items():
    """Show the menu, grouped by category, with an availability filter."""
    only_available = request.args.get("available") == "1"
    show_veg_only = request.args.get("veg") == "1"

    q = MenuItem.query
    if only_available:
        q = q.filter(MenuItem.is_available.is_(True))
    if show_veg_only:
        q = q.filter(MenuItem.is_vegetarian.is_(True))

    items = q.order_by(MenuItem.name).all()
    categories = Category.query.order_by(Category.display_order, Category.name).all()

    # Group items by category id, preserving category order
    by_cat: dict[int, list[MenuItem]] = {c.id: [] for c in categories}
    for it in items:
        by_cat.setdefault(it.category_id, []).append(it)
    uncategorised = by_cat.pop(None, [])  # defensive

    return render_template(
        "menu/list.html",
        categories=categories,
        by_cat=by_cat,
        uncategorised=uncategorised,
        only_available=only_available,
        show_veg_only=show_veg_only,
        can_manage=_can_manage(),
    )


@bp.route("/items/<int:item_id>")
@login_required
def item_detail(item_id: int):
    item = db.session.get(MenuItem, item_id) or abort(404)
    return render_template("menu/item_detail.html", item=item, can_manage=_can_manage())


# ---------- Categories -----------------------------------------------------


@bp.route("/categories/new", methods=["GET", "POST"])
@login_required
def category_new():
    _require_manager()
    form = CategoryForm()
    if form.validate_on_submit():
        cat = Category(
            name=form.name.data.strip(),
            description=form.description.data,
            display_order=form.display_order.data or 0,
        )
        db.session.add(cat)
        db.session.commit()
        flash(f"Category '{cat.name}' created.", "success")
        return redirect(url_for("menu.list_items"))
    return render_template("menu/category_form.html", form=form, title="New category")


@bp.route("/categories/<int:cat_id>/edit", methods=["GET", "POST"])
@login_required
def category_edit(cat_id: int):
    _require_manager()
    cat = db.session.get(Category, cat_id) or abort(404)
    form = CategoryForm(original_name=cat.name, obj=cat)
    if form.validate_on_submit():
        cat.name = form.name.data.strip()
        cat.description = form.description.data
        cat.display_order = form.display_order.data or 0
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("menu.list_items"))
    return render_template("menu/category_form.html", form=form, title=f"Edit {cat.name}")


@bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def category_delete(cat_id: int):
    if not current_user.is_admin:
        abort(403)
    cat = db.session.get(Category, cat_id) or abort(404)
    if cat.items:
        flash(
            f"Cannot delete '{cat.name}' — it has {len(cat.items)} item(s). "
            "Move or delete them first.",
            "danger",
        )
        return redirect(url_for("menu.list_items"))
    db.session.delete(cat)
    db.session.commit()
    flash(f"Category '{cat.name}' deleted.", "info")
    return redirect(url_for("menu.list_items"))


# ---------- Items ----------------------------------------------------------


@bp.route("/items/new", methods=["GET", "POST"])
@login_required
def item_new():
    _require_manager()
    form = MenuItemForm()
    if form.validate_on_submit():
        item = MenuItem(
            name=form.name.data.strip(),
            description=form.description.data,
            price=form.price.data,
            image_url=form.image_url.data,
            is_vegetarian=form.is_vegetarian.data,
            prep_time_minutes=form.prep_time_minutes.data or 10,
            is_available=form.is_available.data,
            category_id=form.category_id.data,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Item '{item.name}' added.", "success")
        return redirect(url_for("menu.list_items"))
    return render_template("menu/item_form.html", form=form, title="New item")


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def item_edit(item_id: int):
    _require_manager()
    item = db.session.get(MenuItem, item_id) or abort(404)
    form = MenuItemForm(obj=item)
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.description = form.description.data
        item.price = form.price.data
        item.image_url = form.image_url.data
        item.is_vegetarian = form.is_vegetarian.data
        item.prep_time_minutes = form.prep_time_minutes.data or 10
        item.is_available = form.is_available.data
        item.category_id = form.category_id.data
        db.session.commit()
        flash("Item updated.", "success")
        return redirect(url_for("menu.item_detail", item_id=item.id))
    return render_template("menu/item_form.html", form=form, title=f"Edit {item.name}")


@bp.route("/items/<int:item_id>/toggle-availability", methods=["POST"])
@login_required
def item_toggle_availability(item_id: int):
    _require_manager()
    item = db.session.get(MenuItem, item_id) or abort(404)
    item.is_available = not item.is_available
    db.session.commit()
    state = "available" if item.is_available else "86'd"
    flash(f"'{item.name}' is now {state}.", "info")
    # Bounce back to wherever the user came from, default to list
    return redirect(request.referrer or url_for("menu.list_items"))


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def item_delete(item_id: int):
    if not current_user.is_admin:
        abort(403)
    item = db.session.get(MenuItem, item_id) or abort(404)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Item '{name}' deleted.", "info")
    return redirect(url_for("menu.list_items"))
