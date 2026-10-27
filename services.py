"""Application Services — orchestrate domain + events + undo."""
from datetime import datetime

from domain import Feedback, Policy, Role, Task, TaskStatus, User
from events import bus

# ---------- In-memory stores ----------
users: dict[str, User] = {}
tasks: dict[str, Task] = {}
feedback_list: list[Feedback] = []

# ---------- Constitution ----------
CONSTITUTION = [
    Policy("Fairness", "Tasks distributed across active members", 0.30),
    Policy("Urgency", "Critical tasks handled first", 0.40),
    Policy("Growth", "Members rotate across skill areas", 0.20),
    Policy("Wellbeing", "No member overloaded (>8 SP active)", 0.10),
]


def seed_users():
    """Create default users on startup."""
    if users:
        return
    for u in [
        User("admin", "admin123", "Hamza Admin", Role.ADMIN, "admin@fh.dev"),
        User("ayesha", "pass123", "Ayesha Khan", Role.MEMBER, "ayesha@fh.dev"),
        User("bilal", "pass123", "Bilal Ahmed", Role.MEMBER, "bilal@fh.dev"),
        User("sara", "pass123", "Sara Iqbal", Role.MEMBER, "sara@fh.dev"),
    ]:
        users[u.id] = u


def authenticate(username: str, password: str) -> User | None:
    for u in users.values():
        if u.username == username and u.password == password and u.is_active:
            return u
    return None


# ---------- Priority Scoring ----------
def compute_priority_score(task: Task) -> float:
    base = task.priority.value * 10
    age_days = (datetime.now() - task.created_at).days
    aging_bonus = min(age_days * 2, 10)
    return round(base + aging_bonus + task.story_points, 2)


# ---------- AI ----------
def ai_suggest(task: Task) -> dict:
    keywords = {
        "bug": "Reproduce first, write a failing test, then fix.",
        "ui": "Pair with a designer; validate with 3 real users.",
        "api": "Contract-first: update OpenAPI spec before coding.",
        "test": "Cover happy path + 2 edge cases.",
        "doc": "Short README with run instructions.",
    }
    suggestion = "Break into smaller deliverable chunks."
    for k, v in keywords.items():
        if k in (task.title + " " + task.description).lower():
            suggestion = v
            break
    active = [u for u in users.values() if u.is_active]
    pair = active[len(tasks) % len(active)].full_name if active else "—"
    return {"suggestion": suggestion, "pair_with": pair}


# ---------- Boy Scout ----------
def boy_scout_report() -> dict:
    return {
        "before": {"duplication": 18, "complexity": 22, "coverage": 40},
        "after":  {"duplication":  6, "complexity": 11, "coverage": 82},
    }


# ================= USERS =================
def create_user(username, password, full_name, role, email) -> tuple[User | None, str]:
    if any(u.username == username for u in users.values()):
        return None, "Username already exists"
    if len(password) < 6:
        return None, "Password must be at least 6 characters"
    u = User(username=username, password=password, full_name=full_name, role=role, email=email)
    users[u.id] = u

    def undo():
        users.pop(u.id, None)
    bus.publish("user.created", {"id": u.id, "username": u.username, "role": u.role.value}, undo=undo)
    return u, ""


def update_user(user_id, **fields) -> bool:
    u = users.get(user_id)
    if not u:
        return False
    old = {k: getattr(u, k) for k in fields}
    for k, v in fields.items():
        setattr(u, k, v)

    def undo():
        for k, v in old.items():
            setattr(u, k, v)
    bus.publish("user.updated", {"id": user_id, "fields": list(fields.keys())}, undo=undo)
    return True


def delete_user(user_id) -> bool:
    u = users.pop(user_id, None)
    if not u:
        return False
    # unassign tasks
    affected = []
    for t in tasks.values():
        if t.assigned_to == user_id:
            affected.append((t, t.assigned_to))
            t.assigned_to = None

    def undo():
        users[u.id] = u
        for t, aid in affected:
            t.assigned_to = aid
    bus.publish("user.deleted", {"id": u.id, "name": u.full_name}, undo=undo)
    return True


# ================= TASKS =================
def create_task(title, description, priority, sp, created_by) -> Task:
    t = Task(title=title, description=description, priority=priority,
             story_points=sp, created_by=created_by)
    tasks[t.id] = t

    def undo():
        tasks.pop(t.id, None)
    bus.publish("task.created", {"id": t.id, "title": t.title, "priority": t.priority.name}, undo=undo)
    return t


def update_task(task_id, **fields) -> bool:
    t = tasks.get(task_id)
    if not t:
        return False
    old = {k: getattr(t, k) for k in fields}
    for k, v in fields.items():
        setattr(t, k, v)

    def undo():
        for k, v in old.items():
            setattr(t, k, v)
    bus.publish("task.updated", {"id": task_id, "fields": list(fields.keys())}, undo=undo)
    return True


def delete_task(task_id) -> bool:
    t = tasks.pop(task_id, None)
    if not t:
        return False

    def undo():
        tasks[t.id] = t
    bus.publish("task.deleted", {"id": t.id, "title": t.title}, undo=undo)
    return True


def assign_task(task_id, user_id) -> bool:
    t = tasks.get(task_id)
    if not t:
        return False
    old = t.assigned_to
    t.assigned_to = user_id
    who = users[user_id].full_name if user_id in users else "Unassigned"

    def undo():
        t.assigned_to = old
    bus.publish("task.assigned", {"task": t.id, "assignee": who}, undo=undo)
    return True


def move_task(task_id, new_status: TaskStatus) -> bool:
    t = tasks.get(task_id)
    if not t:
        return False
    old = t.status
    t.status = new_status

    def undo():
        t.status = old
    bus.publish("task.moved", {"task": t.id, "from": old.value, "to": new_status.value}, undo=undo)
    return True


def add_comment(task_id, author, text) -> bool:
    t = tasks.get(task_id)
    if not t:
        return False
    c = {"author": author, "text": text, "at": datetime.now().isoformat(timespec="seconds")}
    t.comments.append(c)

    def undo():
        if c in t.comments:
            t.comments.remove(c)
    bus.publish("comment.added", {"task": t.id, "author": author}, undo=undo)
    return True


# ================= FEEDBACK =================
def submit_feedback(message, mood) -> Feedback:
    fb = Feedback(message=message, mood=mood)
    feedback_list.append(fb)

    def undo():
        if fb in feedback_list:
            feedback_list.remove(fb)
    bus.publish("feedback.submitted", {"mood": mood}, undo=undo)
    return fb


def delete_feedback(fb_id) -> bool:
    for fb in feedback_list:
        if fb.id == fb_id:
            feedback_list.remove(fb)

            def undo(fb=fb):          # bind the loop variable, not the name
                feedback_list.append(fb)
            bus.publish("feedback.deleted", {"id": fb_id}, undo=undo)
            return True
    return False


# ================= BOARD / REPORTS =================
def sprint_board(filter_priority=None, filter_status=None, search=None) -> dict:
    board = {s.value: [] for s in TaskStatus}
    for t in tasks.values():
        if t.archived:
            continue
        if filter_priority and t.priority.name != filter_priority:
            continue
        if filter_status and t.status.value != filter_status:
            continue
        if search and search.lower() not in (t.title + " " + t.description).lower():
            continue
        board[t.status.value].append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority.name,
            "sp": t.story_points,
            "score": compute_priority_score(t),
            "assignee": users[t.assigned_to].full_name if t.assigned_to in users else "Unassigned",
            "assignee_id": t.assigned_to,
            "comments": len(t.comments),
        })
    for col in board.values():
        col.sort(key=lambda x: -x["score"])
    return board


def governance_summary() -> dict:
    from events import audit_log
    return {"total_events": len(audit_log), "recent": audit_log[-15:][::-1]}