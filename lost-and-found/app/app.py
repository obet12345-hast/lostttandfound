"""
app.py - Flask routes for the Lost and Found system.

Run locally:   python app.py
Production:    gunicorn --chdir app app:app --workers 1
"""

import os
from datetime import date
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)

import storage
import validators
from models import ROLE_CLASSES, Item

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CSS lives in public/static so Vercel can serve it from its CDN.
# Flask serves the same folder when you run locally.
app = Flask(__name__,
            template_folder=os.path.join(ROOT, "app", "templates"),
            static_folder=os.path.join(ROOT, "public", "static"),
            static_url_path="/static")
# Set SECRET_KEY as an environment variable when you deploy.
app.secret_key = os.environ.get("SECRET_KEY", "change-me-before-deploying")


# ======================================================================
#  Current user, decorators and template helpers
# ======================================================================
@app.before_request
def load_current_user():
    """Look up the logged-in user once per request and store it on `g`."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = storage.find_user_by_id(user_id)
        if g.user is None:          # account was deleted while logged in
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Allow only the listed roles. Others are redirected with a message."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user.role not in roles:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def can_edit_item(user, item):
    return user.role in ("admin", "staff") or item.reported_by == user.id


def can_delete_item(user, item):
    return user.role == "admin" or item.reported_by == user.id


def get_item_or_404(item_id):
    item = storage.find_item_by_id(item_id)
    if item is None:
        abort(404)
    return item


def get_claim_or_404(claim_id):
    claim = storage.find_claim_by_id(claim_id)
    if claim is None:
        abort(404)
    return claim


def allowed_kinds(user):
    """Which kinds of item may this user create?"""
    kinds = []
    if user.has_permission("report_lost"):
        kinds.append("lost")
    if user.has_permission("post_found"):
        kinds.append("found")
    return kinds


@app.context_processor
def inject_helpers():
    """Make these names available in every template."""
    return {
        "current_user": getattr(g, "user", None),
        "user_name": storage.user_name,
        "get_item": storage.find_item_by_id,
        "can_edit_item": can_edit_item,
        "can_delete_item": can_delete_item,
        "has_pending_claim": storage.has_pending_claim,
        "STATUSES": Item.STATUSES,
        "CATEGORIES": Item.CATEGORIES,
        "ROLES": ROLE_CLASSES,
        "today": date.today().isoformat(),
    }


# ======================================================================
#  Authentication
# ======================================================================
@app.route("/")
def home():
    return redirect(url_for("dashboard" if g.user else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Enter your username and password.", "error")
        else:
            user = storage.find_user_by_username(username)
            if user and user.check_password(password):
                session.clear()
                session["user_id"] = user.id
                flash(f"Welcome back, {user.full_name}.", "success")
                return redirect(url_for("dashboard"))
            flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = validators.validate_registration(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            storage.add_user("student", data["username"], data["full_name"],
                             data["password"])
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ======================================================================
#  Dashboards (one template per role, same route)
# ======================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    # Polymorphism: each role class builds its own dashboard data.
    data = g.user.get_dashboard_data(storage.items, storage.claims, storage.users)
    return render_template(f"{g.user.role}_dashboard.html", data=data)


# ======================================================================
#  Items: list, add, edit, delete, mark returned
# ======================================================================
@app.route("/items")
@login_required
def items_list():
    filters = {
        "q": request.args.get("q", ""),
        "category": request.args.get("category", ""),
        "status": request.args.get("status", ""),
        "kind": request.args.get("kind", ""),
    }
    results = storage.search_items(
        filters["q"], filters["category"], filters["status"], filters["kind"])
    return render_template("items.html", items=results, filters=filters)


@app.route("/items/add", methods=["GET", "POST"])
@login_required
def add_item():
    kinds = allowed_kinds(g.user)
    if not kinds:
        abort(403)
    kind = request.values.get("kind") or kinds[0]
    if kind not in kinds:
        abort(403)

    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = validators.validate_item_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            storage.add_item(kind, data["name"], data["category"],
                             data["description"], data["location"],
                             data["date_reported"], g.user.id)
            flash("Item saved.", "success")
            return redirect(url_for("items_list"))
    return render_template("item_form.html", form=form, item=None, kind=kind,
                           kinds=kinds)


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = get_item_or_404(item_id)
    if not can_edit_item(g.user, item):
        abort(403)

    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = validators.validate_item_form(request.form)
        status = None
        if g.user.has_permission("update_status"):
            status = request.form.get("status")
            if status not in Item.STATUSES:
                errors.append("Choose a valid status.")
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            storage.update_item(item.id, data["name"], data["category"],
                                data["description"], data["location"],
                                data["date_reported"], status)
            flash("Item updated.", "success")
            return redirect(url_for("items_list"))
    return render_template("item_form.html", form=form, item=item,
                           kind=item.kind, kinds=[item.kind])


@app.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = get_item_or_404(item_id)
    if not can_delete_item(g.user, item):
        abort(403)
    storage.delete_item(item.id)
    flash("Item deleted.", "success")
    return redirect(request.referrer or url_for("items_list"))


@app.route("/items/<int:item_id>/return", methods=["POST"])
@role_required("staff", "admin")
def mark_returned(item_id):
    item = get_item_or_404(item_id)
    if item.status != "Claimed":
        flash("Only claimed items can be marked as returned.", "error")
    else:
        item.status = "Returned"
        flash(f"'{item.name}' marked as returned.", "success")
    return redirect(request.referrer or url_for("dashboard"))


# ======================================================================
#  Claims
# ======================================================================
@app.route("/items/<int:item_id>/claim", methods=["GET", "POST"])
@role_required("student")
def claim_item(item_id):
    item = get_item_or_404(item_id)
    if item.kind != "found" or item.status != "Found":
        flash("This item is not available to claim.", "error")
        return redirect(url_for("items_list"))
    if storage.has_pending_claim(item.id, g.user.id):
        flash("You already have a pending claim on this item.", "error")
        return redirect(url_for("my_claims"))

    form = {}
    if request.method == "POST":
        form = request.form
        proof, errors = validators.validate_claim_proof(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            storage.add_claim(item.id, g.user.id, proof)
            flash("Claim submitted. Staff will review it.", "success")
            return redirect(url_for("my_claims"))
    return render_template("claim_form.html", item=item, form=form)


@app.route("/my-claims")
@role_required("student")
def my_claims():
    return render_template("my_claims.html",
                           claims=storage.claims_for_user(g.user.id))


@app.route("/claims/<int:claim_id>/withdraw", methods=["POST"])
@role_required("student")
def withdraw_claim(claim_id):
    claim = get_claim_or_404(claim_id)
    if claim.claimant_id != g.user.id:
        abort(403)
    if claim.status != "Pending":
        flash("Only pending claims can be withdrawn.", "error")
    else:
        storage.delete_claim(claim.id)
        flash("Claim withdrawn.", "success")
    return redirect(url_for("my_claims"))


@app.route("/claims")
@role_required("staff", "admin")
def manage_claims():
    status = request.args.get("status", "")
    shown = [c for c in storage.claims if not status or c.status == status]
    shown.sort(key=lambda c: c.id, reverse=True)
    return render_template("claims.html", claims=shown, status=status)


@app.route("/claims/<int:claim_id>/<action>", methods=["POST"])
@role_required("staff", "admin")
def review_claim(claim_id, action):
    claim = get_claim_or_404(claim_id)
    if action not in ("approve", "reject"):
        abort(404)
    item = storage.find_item_by_id(claim.item_id)
    if claim.status != "Pending":
        flash("That claim has already been reviewed.", "error")
    elif action == "approve":
        if item is None or item.status != "Found":
            flash("The item is no longer available.", "error")
        else:
            storage.approve_claim(claim, g.user.id)
            flash("Claim approved. Other pending claims for this item were rejected.",
                  "success")
    else:
        claim.reject(g.user.id)
        flash("Claim rejected.", "success")
    return redirect(request.referrer or url_for("manage_claims"))


@app.route("/claims/<int:claim_id>/delete", methods=["POST"])
@role_required("admin")
def delete_claim(claim_id):
    claim = get_claim_or_404(claim_id)
    storage.delete_claim(claim.id)
    flash("Claim deleted.", "success")
    return redirect(url_for("manage_claims"))


# ======================================================================
#  Users (admin only)
# ======================================================================
@app.route("/users")
@role_required("admin")
def users_list():
    return render_template("users.html", users=storage.users)


@app.route("/users/add", methods=["GET", "POST"])
@role_required("admin")
def add_user():
    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = validators.validate_user_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            storage.add_user(data["role"], data["username"], data["full_name"],
                             data["password"])
            flash("User created.", "success")
            return redirect(url_for("users_list"))
    return render_template("user_form.html", form=form, user=None)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_user(user_id):
    user = storage.find_user_by_id(user_id)
    if user is None:
        abort(404)

    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = validators.validate_user_form(
            request.form, user_id=user.id, password_required=False)
        if user.id == g.user.id and data["role"] != user.role:
            errors.append("You cannot change your own role.")
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            try:
                storage.update_user(user.id, data["full_name"], data["username"],
                                    data["role"], data["password"])
            except ValueError as problem:
                flash(str(problem), "error")
            else:
                flash("User updated.", "success")
                return redirect(url_for("users_list"))
    return render_template("user_form.html", form=form, user=user)


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    user = storage.find_user_by_id(user_id)
    if user is None:
        abort(404)
    if user.id == g.user.id:
        flash("You cannot delete your own account.", "error")
    else:
        storage.delete_user(user.id)
        flash("User deleted.", "success")
    return redirect(url_for("users_list"))


# ======================================================================
#  Error pages
# ======================================================================
def error_page(code, title, message):
    return render_template("error.html", code=code, title=title,
                           message=message), code


@app.errorhandler(403)
def forbidden(error):
    return error_page(403, "Access denied",
                      "You do not have permission to do that.")


@app.errorhandler(404)
def not_found(error):
    return error_page(404, "Page not found",
                      "We could not find what you were looking for.")


@app.errorhandler(405)
def method_not_allowed(error):
    return error_page(405, "Action not allowed",
                      "That action is not available from this page.")


@app.errorhandler(500)
def server_error(error):
    return error_page(500, "Something went wrong",
                      "The server hit a problem. Try again in a moment.")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
