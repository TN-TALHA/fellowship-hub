import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import services
from domain import Priority, Role, TaskStatus
from events import bus

app = Flask(__name__)
app.secret_key = "fellowship-hub-demo-secret-2024"


# ---------- Auth decorator ----------
def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if "user_id" not in session:
            return jsonify({"error": "unauthorized"}), 401
        return f(*a, **kw)
    return wrap


def current_user():
    return services.users.get(session.get("user_id"))


def admin_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        u = current_user()
        if not u or u.role != Role.ADMIN:
            return jsonify({"error": "forbidden"}), 403
        return f(*a, **kw)
    return wrap


# ---------- Auth routes ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    d = request.json or {}
    u = services.authenticate(d.get("username", ""), d.get("password", ""))
    if not u:
        return jsonify({"error": "Invalid username or password"}), 401
    session["user_id"] = u.id
    bus.publish("auth.login", {"username": u.username})
    return jsonify({"ok": True, "user": _user_json(u)})


@app.post("/api/logout")
def logout():
    u = current_user()
    if u:
        bus.publish("auth.logout", {"username": u.username})
    session.clear()
    return jsonify({"ok": True})


def _user_json(u):
    return {"id": u.id, "username": u.username, "full_name": u.full_name,
            "role": u.role.value, "email": u.email}


@app.get("/api/me")
def me():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_user_json(u))


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")


# ---------- Users API ----------
@app.get("/api/users")
@login_required
def api_users():
    return jsonify([_user_json(u) for u in services.users.values()])


@app.post("/api/users")
@login_required
@admin_required
def api_create_user():
    d = request.json
    try:
        role = Role(d.get("role", "Member"))
    except ValueError:
        return jsonify({"error": "Invalid role"}), 400
    u, err = services.create_user(
        d["username"], d["password"], d["full_name"], role, d.get("email", ""))
    if err:
        return jsonify({"error": err}), 400
    return jsonify(_user_json(u)), 201


@app.patch("/api/users/<uid>")
@login_required
@admin_required
def api_update_user(uid):
    services.update_user(uid, **request.json)
    return jsonify({"ok": True})


@app.delete("/api/users/<uid>")
@login_required
@admin_required
def api_delete_user(uid):
    if uid == session.get("user_id"):
        return jsonify({"error": "You can't delete yourself"}), 400
    services.delete_user(uid)
    return jsonify({"ok": True})


# ---------- Tasks API ----------
@app.get("/api/tasks")
@login_required
def api_tasks():
    return jsonify(services.sprint_board(
        filter_priority=request.args.get("priority"),
        filter_status=request.args.get("status"),
        search=request.args.get("q"),
    ))


@app.post("/api/tasks")
@login_required
def api_add_task():
    d = request.json
    t = services.create_task(
        d["title"], d.get("description", ""),
        Priority[d.get("priority", "MEDIUM").upper()],
        int(d.get("story_points", 1)),
        session["user_id"],
    )
    return jsonify({"id": t.id, "title": t.title}), 201


@app.patch("/api/tasks/<tid>")
@login_required
def api_update_task(tid):
    services.update_task(tid, **request.json)
    return jsonify({"ok": True})


@app.delete("/api/tasks/<tid>")
@login_required
def api_delete_task(tid):
    services.delete_task(tid)
    return jsonify({"ok": True})


@app.post("/api/tasks/<tid>/assign")
@login_required
def api_assign(tid):
    services.assign_task(tid, request.json["user_id"])
    return jsonify({"ok": True})


@app.post("/api/tasks/<tid>/move")
@login_required
def api_move(tid):
    services.move_task(tid, TaskStatus(request.json["status"]))
    return jsonify({"ok": True})


@app.post("/api/tasks/<tid>/comment")
@login_required
def api_comment(tid):
    u = current_user()
    services.add_comment(tid, u.full_name, request.json["text"])
    return jsonify({"ok": True})


@app.get("/api/tasks/<tid>")
@login_required
def api_task_detail(tid):
    t = services.tasks.get(tid)
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": t.id, "title": t.title, "description": t.description,
        "priority": t.priority.name, "status": t.status.value,
        "sp": t.story_points,
        "assignee": services.users[t.assigned_to].full_name
                    if t.assigned_to in services.users else "Unassigned",
        "assignee_id": t.assigned_to,
        "comments": t.comments,
    })


@app.get("/api/tasks/<tid>/ai")
@login_required
def api_ai(tid):
    t = services.tasks.get(tid)
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify(services.ai_suggest(t))


# ---------- Feedback ----------
@app.get("/api/feedback")
@login_required
def api_feedback():
    return jsonify([{"id": f.id, "message": f.message, "mood": f.mood,
                     "at": f.created_at.isoformat()} for f in services.feedback_list])


@app.post("/api/feedback")
@login_required
def api_add_feedback():
    d = request.json
    fb = services.submit_feedback(d["message"], d.get("mood", "ok"))
    return jsonify({"id": fb.id}), 201


@app.delete("/api/feedback/<fid>")
@login_required
@admin_required
def api_del_feedback(fid):
    services.delete_feedback(fid)
    return jsonify({"ok": True})


# ---------- Governance / Undo / Events ----------
@app.get("/api/governance")
@login_required
def api_governance():
    return jsonify(services.governance_summary())


@app.get("/api/events")
@login_required
def api_events():
    return jsonify(bus.recent(40))


@app.post("/api/undo/<int:eid>")
@login_required
def api_undo(eid):
    ok = bus.undo(eid)
    return jsonify({"ok": ok})


@app.get("/api/boy-scout")
@login_required
def api_boy_scout():
    return jsonify(services.boy_scout_report())


@app.get("/api/constitution")
@login_required
def api_constitution():
    return jsonify([{"name": p.name, "description": p.description, "weight": p.weight}
                    for p in services.CONSTITUTION])


if __name__ == "__main__":
    services.seed_users()
    # seed tasks
    admin = list(services.users.values())[0]
    ids = [u.id for u in services.users.values()]
    t1 = services.create_task("Fix login bug", "Users can't login on mobile", Priority.CRITICAL, 3, admin.id)
    t2 = services.create_task("Design dashboard UI", "New landing dashboard", Priority.HIGH, 5, admin.id)
    t3 = services.create_task("Write API tests", "Cover auth endpoints", Priority.MEDIUM, 2, admin.id)
    services.assign_task(t1.id, ids[1])
    services.assign_task(t2.id, ids[2])
    services.move_task(t1.id, TaskStatus.IN_PROGRESS)
    services.move_task(t2.id, TaskStatus.REVIEW)
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )