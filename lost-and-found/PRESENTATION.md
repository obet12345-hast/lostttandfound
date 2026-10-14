# Presentation outline (7 slides)

**1. Title and problem**
Lost & Found Desk. Lost items on campus are hard to track and hard to return. The system gives students, staff and admins one place to report, find and claim items.

**2. Users and roles**
- Admin: manages users and all records, sees statistics.
- Staff: posts found items, reviews claims, marks items returned.
- Student: reports lost items, claims found items, tracks claims.
Show the three different dashboards.

**3. How it works (the flow)**
Staff posts a found item, a student claims it with proof, staff approves, the item becomes Claimed, then staff marks it Returned. Show this live with the demo accounts.

**4. Python OOP: where each concept is used**

| Concept | Where to find it | What to say |
|---------|------------------|-------------|
| Classes | `models.py` | `User`, `Item`, `Claim` model the real-world things |
| Encapsulation | `User.__password_hash`, `Item.__status`, `Claim.__status` in `models.py` | Private attributes. The password is stored as a hash and checked with `check_password()`. Status can only be set to valid values through a property setter. |
| Inheritance | `Admin`, `Staff`, `Student` extend `User`; `LostItem`, `FoundItem` extend `Item` | Shared fields live in the base class. Subclasses add only what is different. |
| Polymorphism | `get_permissions()` and `get_dashboard_data()` in each role class; `describe()` and `location_label` in each item class | The route calls `g.user.get_dashboard_data(...)` without knowing the role. Each class answers differently. |
| Functions | `storage.py`: `add_item()`, `update_item()`, `delete_item()`, `find_item_by_id()`, `search_items()` | Logic is split into small, reusable functions. |

**5. Flask and storage**
- Routes in `app.py`, templates in `templates/`, styling in `static/style.css`.
- Role-based access: the `@role_required(...)` decorator redirects with a message; item ownership checks return a 403 page.
- Temporary storage: three Python lists in `storage.py`. No database. Data resets on restart.

**6. Validation and error handling**
Show: empty login, duplicate username, short password, future date, short proof of ownership, student trying to open the admin page, and the custom 404 page.

**7. Deployment and what I learned**
Live URL, GitHub repository, and one thing that was hard (for example, keeping a single process because data lives in memory). Mention a next step: replace the lists with a database.

## Live demo order (about 3 minutes)
1. Log in as **staff**, post a found item.
2. Log out, log in as **student**, find the item, submit a claim.
3. Log in as **staff**, approve the claim, mark as returned.
4. Log in as **admin**, show statistics and user management.
5. Try a restricted page as a student to show access control.
