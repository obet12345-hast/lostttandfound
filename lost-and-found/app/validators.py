"""
validators.py - checks form input and returns friendly error messages.

Each function returns (cleaned_data, errors). If `errors` is an empty list
the data is safe to save.
"""

import re
from datetime import date, datetime

import storage
from models import MIN_PASSWORD_LENGTH, ROLE_CLASSES, Item

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _clean(value):
    return (value or "").strip()


def validate_item_form(form):
    """Validate the add/edit item form."""
    data = {key: _clean(form.get(key)) for key in
            ("name", "category", "description", "location", "date_reported")}
    errors = []

    if not 3 <= len(data["name"]) <= 80:
        errors.append("Item name must be 3 to 80 characters.")
    if data["category"] not in Item.CATEGORIES:
        errors.append("Choose a category from the list.")
    if not 10 <= len(data["description"]) <= 500:
        errors.append("Description must be 10 to 500 characters.")
    if not 3 <= len(data["location"]) <= 100:
        errors.append("Location must be 3 to 100 characters.")

    try:
        parsed = datetime.strptime(data["date_reported"], "%Y-%m-%d").date()
        if parsed > date.today():
            errors.append("The date cannot be in the future.")
        data["date_reported"] = parsed
    except ValueError:
        errors.append("Enter a valid date.")

    return data, errors


def validate_user_form(form, user_id=None, password_required=True):
    """Validate the admin add/edit user form."""
    data = {key: _clean(form.get(key)) for key in ("full_name", "username", "role")}
    data["password"] = form.get("password") or ""
    errors = []

    if not 2 <= len(data["full_name"]) <= 50:
        errors.append("Full name must be 2 to 50 characters.")
    errors.extend(_username_errors(data["username"], user_id))
    if data["role"] not in ROLE_CLASSES:
        errors.append("Choose a valid role.")

    if data["password"] or password_required:
        if len(data["password"]) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    return data, errors


def validate_registration(form):
    """Validate the public sign-up form (always creates a student)."""
    data, errors = validate_user_form(
        {**form.to_dict(), "role": "student"}, password_required=True)
    if (form.get("password") or "") != (form.get("confirm_password") or ""):
        errors.append("Passwords do not match.")
    return data, errors


def validate_claim_proof(form):
    proof = _clean(form.get("proof"))
    errors = []
    if not 10 <= len(proof) <= 500:
        errors.append("Describe your proof of ownership in 10 to 500 characters.")
    return proof, errors


def _username_errors(username, user_id):
    if not USERNAME_PATTERN.match(username):
        return ["Username must be 3 to 20 letters, numbers or underscores."]
    existing = storage.find_user_by_username(username)
    if existing and existing.id != user_id:
        return ["That username is already taken."]
    return []
