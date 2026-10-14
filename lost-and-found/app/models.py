"""
models.py - every class used by the Lost and Found system.

OOP concepts shown in this file
-------------------------------
Encapsulation : private attributes (__password_hash, __status, ...) exposed
                only through @property getters/setters and methods.
Inheritance   : Admin, Staff, Student extend User.
                LostItem, FoundItem extend Item.
Polymorphism  : get_permissions(), get_dashboard_data() are overridden in each
                role class; describe() and location_label are overridden in
                each item class. The rest of the app calls the same method
                name and gets role/type specific behaviour.
"""

from collections import Counter
from datetime import date

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 6


# ======================================================================
#  USERS
# ======================================================================
class User:
    """Base class for every account in the system."""

    role = "user"          # overridden by subclasses
    role_label = "User"

    def __init__(self, user_id, username, full_name, password):
        self.id = user_id
        # Private attributes: only reachable through the properties below.
        self.__username = username
        self.__full_name = full_name
        self.__password_hash = None
        self.set_password(password)

    # ----- encapsulated attributes -----------------------------------
    @property
    def username(self):
        return self.__username

    @username.setter
    def username(self, value):
        value = (value or "").strip()
        if not value:
            raise ValueError("Username cannot be empty.")
        self.__username = value

    @property
    def full_name(self):
        return self.__full_name

    @full_name.setter
    def full_name(self, value):
        value = (value or "").strip()
        if not value:
            raise ValueError("Full name cannot be empty.")
        self.__full_name = value

    def set_password(self, raw_password):
        """Store only a hash, never the plain password."""
        if len(raw_password or "") < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        self.__password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.__password_hash, raw_password or "")

    # ----- behaviour that subclasses override (polymorphism) ---------
    def get_permissions(self):
        """Return the set of actions this kind of user may perform."""
        return set()

    def has_permission(self, permission):
        return permission in self.get_permissions()

    def get_dashboard_data(self, items, claims, users):
        """Return the numbers/lists shown on this user's dashboard."""
        return {}

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.username}>"


class Admin(User):
    """Manages users, items, claims and sees system-wide statistics."""

    role = "admin"
    role_label = "Administrator"

    def get_permissions(self):
        return {
            "view_stats", "manage_users", "delete_claims",
            "post_found", "report_lost", "update_status", "review_claims",
        }

    def get_dashboard_data(self, items, claims, users):
        status_counts = Counter(item.status for item in items)
        return {
            "total_users": len(users),
            "users_by_role": Counter(u.role for u in users),
            "total_items": len(items),
            "status_counts": {s: status_counts.get(s, 0) for s in Item.STATUSES},
            "pending_claims": sum(1 for c in claims if c.status == "Pending"),
            "total_claims": len(claims),
            "recent_items": sorted(items, key=lambda i: i.id, reverse=True)[:5],
        }


class Staff(User):
    """Security / office personnel who handle found items and claims."""

    role = "staff"
    role_label = "Staff"

    def get_permissions(self):
        return {"post_found", "update_status", "review_claims"}

    def get_dashboard_data(self, items, claims, users):
        return {
            "pending_claims": [c for c in claims if c.status == "Pending"],
            "awaiting_return": [i for i in items if i.status == "Claimed"],
            "found_count": sum(1 for i in items if i.status == "Found"),
            "lost_count": sum(1 for i in items if i.status == "Lost"),
            "recent_found": sorted(
                [i for i in items if i.kind == "found"],
                key=lambda i: i.id, reverse=True,
            )[:5],
        }


class Student(User):
    """Regular user who reports lost items and claims found ones."""

    role = "student"
    role_label = "Student"

    def get_permissions(self):
        return {"report_lost", "submit_claim"}

    def get_dashboard_data(self, items, claims, users):
        my_items = [i for i in items if i.reported_by == self.id]
        my_claims = [c for c in claims if c.claimant_id == self.id]
        return {
            "my_items": sorted(my_items, key=lambda i: i.id, reverse=True),
            "my_claims": sorted(my_claims, key=lambda c: c.id, reverse=True),
            "pending_claims": sum(1 for c in my_claims if c.status == "Pending"),
            "approved_claims": sum(1 for c in my_claims if c.status == "Approved"),
            "available_found": sum(
                1 for i in items if i.kind == "found" and i.status == "Found"
            ),
        }


# Maps the role string stored in forms/sessions to the class that handles it.
ROLE_CLASSES = {"admin": Admin, "staff": Staff, "student": Student}


def create_user(role, user_id, username, full_name, password):
    """Factory: build the right User subclass for a role name."""
    return ROLE_CLASSES[role](user_id, username, full_name, password)


# ======================================================================
#  ITEMS
# ======================================================================
class Item:
    """Base class for anything reported to the system."""

    STATUSES = ["Lost", "Found", "Claimed", "Returned"]
    CATEGORIES = [
        "Electronics", "Wallet & Cards", "Keys", "Bags",
        "Clothing", "Books & Documents", "Accessories", "Other",
    ]

    kind = "item"            # overridden by subclasses
    kind_label = "Item"
    default_status = "Lost"

    def __init__(self, item_id, name, category, description, location,
                 date_reported, reported_by, status=None):
        self.id = item_id
        self.name = name
        self.category = category
        self.description = description
        self.location = location
        self.date_reported = date_reported      # datetime.date
        self.reported_by = reported_by          # user id
        self.__status = None
        self.status = status or self.default_status

    # ----- encapsulated status ---------------------------------------
    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, value):
        if value not in Item.STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(Item.STATUSES)}.")
        self.__status = value

    # ----- behaviour that subclasses override (polymorphism) ---------
    @property
    def location_label(self):
        return "Location"

    def describe(self):
        return f"{self.name} at {self.location}"

    def __repr__(self):
        return f"<{self.__class__.__name__} #{self.id} {self.name}>"


class LostItem(Item):
    """An item somebody has lost and is looking for."""

    kind = "lost"
    kind_label = "Lost"
    default_status = "Lost"

    @property
    def location_label(self):
        return "Last seen at"

    def describe(self):
        return f"Lost near {self.location} on {self.date_reported:%b %d, %Y}"


class FoundItem(Item):
    """An item that was handed in or found and is waiting for its owner."""

    kind = "found"
    kind_label = "Found"
    default_status = "Found"

    @property
    def location_label(self):
        return "Found at"

    def describe(self):
        return f"Found at {self.location} on {self.date_reported:%b %d, %Y}"


ITEM_CLASSES = {"lost": LostItem, "found": FoundItem}


# ======================================================================
#  CLAIMS
# ======================================================================
class Claim:
    """A student's request to receive a found item."""

    STATUSES = ["Pending", "Approved", "Rejected"]

    def __init__(self, claim_id, item_id, claimant_id, proof):
        self.id = claim_id
        self.item_id = item_id
        self.claimant_id = claimant_id
        self.proof = proof
        self.date_submitted = date.today()
        self.reviewed_by = None
        self.__status = "Pending"

    @property
    def status(self):
        return self.__status

    def approve(self, reviewer_id):
        self.__status = "Approved"
        self.reviewed_by = reviewer_id

    def reject(self, reviewer_id):
        self.__status = "Rejected"
        self.reviewed_by = reviewer_id

    def __repr__(self):
        return f"<Claim #{self.id} item={self.item_id} {self.status}>"
