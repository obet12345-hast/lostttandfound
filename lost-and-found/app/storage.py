"""
storage.py - temporary storage using plain Python lists (NO DATABASE).

All data lives in memory. It is created when the server starts and is lost
when the server restarts. Every function here works on those three lists.
"""

from datetime import date, timedelta

from models import ITEM_CLASSES, Claim, create_user

# ----------------------------------------------------------------------
#  The "database": three plain lists
# ----------------------------------------------------------------------
users = []
items = []
claims = []


def _next_id(collection):
    """Return the next free id for a list of objects."""
    return max((obj.id for obj in collection), default=0) + 1


# ----------------------------------------------------------------------
#  Users
# ----------------------------------------------------------------------
def find_user_by_id(user_id):
    return next((u for u in users if u.id == user_id), None)


def find_user_by_username(username):
    wanted = (username or "").strip().lower()
    return next((u for u in users if u.username.lower() == wanted), None)


def add_user(role, username, full_name, password):
    user = create_user(role, _next_id(users), username, full_name, password)
    users.append(user)
    return user


def update_user(user_id, full_name, username, role, password=None):
    """Update a user. Changing the role swaps the object for the new subclass."""
    user = find_user_by_id(user_id)
    if user is None:
        return None
    if role != user.role:
        if not password:
            raise ValueError("Enter a new password when changing a user's role.")
        replacement = create_user(role, user.id, username, full_name, password)
        users[users.index(user)] = replacement
        return replacement
    user.username = username
    user.full_name = full_name
    if password:
        user.set_password(password)
    return user


def delete_user(user_id):
    user = find_user_by_id(user_id)
    if user is not None:
        users.remove(user)
        return True
    return False


def user_name(user_id):
    user = find_user_by_id(user_id)
    return user.full_name if user else "Deleted user"


# ----------------------------------------------------------------------
#  Items
# ----------------------------------------------------------------------
def find_item_by_id(item_id):
    return next((i for i in items if i.id == item_id), None)


def add_item(kind, name, category, description, location,
             date_reported, reported_by, status=None):
    item_class = ITEM_CLASSES[kind]
    item = item_class(_next_id(items), name, category, description,
                      location, date_reported, reported_by, status)
    items.append(item)
    return item


def update_item(item_id, name, category, description, location,
                date_reported, status=None):
    item = find_item_by_id(item_id)
    if item is None:
        return None
    item.name = name
    item.category = category
    item.description = description
    item.location = location
    item.date_reported = date_reported
    if status:
        item.status = status
    return item


def delete_item(item_id):
    """Delete an item and every claim that points at it."""
    item = find_item_by_id(item_id)
    if item is None:
        return False
    items.remove(item)
    claims[:] = [c for c in claims if c.item_id != item_id]
    return True


def search_items(keyword="", category="", status="", kind=""):
    """Filter the items list. Empty filters are ignored."""
    keyword = (keyword or "").strip().lower()
    results = []
    for item in items:
        if keyword and keyword not in (
            f"{item.name} {item.description} {item.location}".lower()
        ):
            continue
        if category and item.category != category:
            continue
        if status and item.status != status:
            continue
        if kind and item.kind != kind:
            continue
        results.append(item)
    return sorted(results, key=lambda i: i.id, reverse=True)


# ----------------------------------------------------------------------
#  Claims
# ----------------------------------------------------------------------
def find_claim_by_id(claim_id):
    return next((c for c in claims if c.id == claim_id), None)


def add_claim(item_id, claimant_id, proof):
    claim = Claim(_next_id(claims), item_id, claimant_id, proof)
    claims.append(claim)
    return claim


def delete_claim(claim_id):
    claim = find_claim_by_id(claim_id)
    if claim is not None:
        claims.remove(claim)
        return True
    return False


def has_pending_claim(item_id, claimant_id):
    return any(
        c.item_id == item_id and c.claimant_id == claimant_id
        and c.status == "Pending"
        for c in claims
    )


def claims_for_user(user_id):
    return sorted(
        [c for c in claims if c.claimant_id == user_id],
        key=lambda c: c.id, reverse=True,
    )


def approve_claim(claim, reviewer_id):
    """Approve one claim, reject competing ones, mark the item as Claimed."""
    item = find_item_by_id(claim.item_id)
    claim.approve(reviewer_id)
    item.status = "Claimed"
    for other in claims:
        if (other is not claim and other.item_id == claim.item_id
                and other.status == "Pending"):
            other.reject(reviewer_id)


# ----------------------------------------------------------------------
#  Demo data (so the system can be shown right away)
# ----------------------------------------------------------------------
def seed_data():
    users.clear()
    items.clear()
    claims.clear()

    add_user("admin", "admin", "Alex Rivera", "admin123")
    staff = add_user("staff", "staff", "Sam Dela Cruz", "staff123")
    student = add_user("student", "student", "Jamie Santos", "student123")

    today = date.today()
    add_item(
        "found", "Black folding umbrella", "Accessories",
        "Automatic umbrella with a wooden handle, left on a bench.",
        "Main Library, ground floor", today - timedelta(days=6), staff.id)
    add_item(
        "lost", "Casio scientific calculator", "Electronics",
        "Grey Casio fx-991 with my initials J.S. written on the back cover.",
        "Engineering Building, Room 204", today - timedelta(days=4), student.id)
    add_item(
        "found", "Keys with red keychain", "Keys",
        "Three keys and a red rubber keychain shaped like a star.",
        "Cafeteria entrance", today - timedelta(days=3), staff.id)
    wallet = add_item(
        "found", "Brown leather wallet", "Wallet & Cards",
        "Bi-fold wallet with a school ID and two cards inside.",
        "Gym lobby", today - timedelta(days=2), staff.id)
    backpack = add_item(
        "found", "Blue backpack", "Bags",
        "Navy backpack with a laptop sleeve and a keychain on the zipper.",
        "Bus stop near Gate 2", today - timedelta(days=9), staff.id,
        status="Returned")

    # One pending claim to review, one approved claim for the returned bag.
    add_claim(wallet.id, student.id,
              "The wallet has my school ID and a green library card inside.")
    returned_claim = add_claim(
        backpack.id, student.id,
        "Navy bag with a white laptop sleeve and a panda keychain.")
    returned_claim.approve(staff.id)


seed_data()
