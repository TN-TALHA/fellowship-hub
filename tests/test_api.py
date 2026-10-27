"""HTTP-level tests for the Flask API, driven through the test client."""
import pytest

import services


# -------------------------------------------------------------------- auth
class TestLogin:
    def test_login_page_renders(self, client):
        assert client.get("/login").status_code == 200

    def test_valid_login_returns_the_user(self, client):
        res = client.post("/login", json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200
        assert res.get_json()["user"]["role"] == "Admin"

    def test_invalid_login_is_401(self, client):
        res = client.post("/login", json={"username": "admin", "password": "nope"})
        assert res.status_code == 401
        assert "error" in res.get_json()

    def test_login_never_returns_the_password(self, client):
        res = client.post("/login", json={"username": "admin", "password": "admin123"})
        assert "password" not in res.get_json()["user"]

    def test_root_redirects_anonymous_visitors_to_login(self, client):
        res = client.get("/")
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_root_renders_for_logged_in_users(self, admin_client):
        assert admin_client.get("/").status_code == 200

    def test_logout_clears_the_session(self, admin_client):
        assert admin_client.post("/api/logout").status_code == 200
        assert admin_client.get("/api/me").status_code == 401


class TestProtectedRoutes:
    @pytest.mark.parametrize(
        "path",
        ["/api/me", "/api/users", "/api/tasks", "/api/feedback",
         "/api/events", "/api/governance", "/api/constitution", "/api/boy-scout"],
    )
    def test_anonymous_requests_are_rejected(self, client, path):
        assert client.get(path).status_code == 401


# ------------------------------------------------------------------- RBAC
class TestAdminOnlyRoutes:
    def test_member_cannot_create_users(self, member_client):
        res = member_client.post("/api/users", json={
            "username": "x", "password": "secret123",
            "full_name": "X", "role": "Member",
        })
        assert res.status_code == 403

    def test_admin_can_create_users(self, admin_client):
        res = admin_client.post("/api/users", json={
            "username": "newbie", "password": "secret123",
            "full_name": "New Bie", "role": "Member", "email": "n@fh.dev",
        })
        assert res.status_code == 201
        assert res.get_json()["username"] == "newbie"

    def test_creating_a_user_with_a_bad_role_is_400(self, admin_client):
        res = admin_client.post("/api/users", json={
            "username": "x", "password": "secret123",
            "full_name": "X", "role": "Wizard",
        })
        assert res.status_code == 400

    def test_duplicate_username_is_400(self, admin_client):
        res = admin_client.post("/api/users", json={
            "username": "admin", "password": "secret123",
            "full_name": "Clone", "role": "Member",
        })
        assert res.status_code == 400

    def test_admin_cannot_delete_themselves(self, admin_client, user_ids):
        res = admin_client.delete(f"/api/users/{user_ids['admin']}")
        assert res.status_code == 400
        assert user_ids["admin"] in services.users

    def test_member_cannot_delete_feedback(self, member_client):
        fb = services.submit_feedback("msg", "ok")
        assert member_client.delete(f"/api/feedback/{fb.id}").status_code == 403


# ------------------------------------------------------------------ tasks
class TestTasksApi:
    def test_board_starts_empty(self, member_client):
        board = member_client.get("/api/tasks").get_json()
        assert board["Backlog"] == []

    def test_create_task_returns_201(self, member_client):
        res = member_client.post("/api/tasks", json={
            "title": "Write CI pipeline", "description": "GitHub Actions",
            "priority": "HIGH", "story_points": 3,
        })
        assert res.status_code == 201
        assert res.get_json()["title"] == "Write CI pipeline"

    def test_created_task_appears_on_the_board(self, member_client):
        member_client.post("/api/tasks", json={"title": "On the board", "priority": "LOW"})
        board = member_client.get("/api/tasks").get_json()
        assert [t["title"] for t in board["Backlog"]] == ["On the board"]

    def test_task_detail_round_trip(self, member_client):
        tid = member_client.post(
            "/api/tasks", json={"title": "Detail me", "priority": "CRITICAL", "story_points": 5}
        ).get_json()["id"]

        detail = member_client.get(f"/api/tasks/{tid}").get_json()
        assert detail["priority"] == "CRITICAL"
        assert detail["sp"] == 5
        assert detail["assignee"] == "Unassigned"

    def test_unknown_task_detail_is_404(self, member_client):
        assert member_client.get("/api/tasks/nope").status_code == 404

    def test_move_task_between_columns(self, member_client):
        tid = member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"}).get_json()["id"]
        assert member_client.post(f"/api/tasks/{tid}/move", json={"status": "Done"}).status_code == 200
        assert member_client.get("/api/tasks").get_json()["Done"][0]["id"] == tid

    def test_assign_task_to_a_member(self, member_client, user_ids):
        tid = member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"}).get_json()["id"]
        res = member_client.post(f"/api/tasks/{tid}/assign", json={"user_id": user_ids["bilal"]})
        assert res.status_code == 200
        assert member_client.get(f"/api/tasks/{tid}").get_json()["assignee"] == "Bilal Ahmed"

    def test_comment_is_attributed_to_the_logged_in_user(self, member_client):
        tid = member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"}).get_json()["id"]
        assert member_client.post(f"/api/tasks/{tid}/comment", json={"text": "Looking"}).status_code == 200

        comments = member_client.get(f"/api/tasks/{tid}").get_json()["comments"]
        assert comments[0]["author"] == "Ayesha Khan"
        assert comments[0]["text"] == "Looking"

    def test_delete_task(self, member_client):
        tid = member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"}).get_json()["id"]
        assert member_client.delete(f"/api/tasks/{tid}").status_code == 200
        assert member_client.get("/api/tasks").get_json()["Backlog"] == []

    def test_board_search_query_param(self, member_client):
        member_client.post("/api/tasks", json={"title": "Fix login", "priority": "HIGH"})
        member_client.post("/api/tasks", json={"title": "Design UI", "priority": "HIGH"})
        board = member_client.get("/api/tasks?q=login").get_json()
        assert len(board["Backlog"]) == 1

    def test_ai_endpoint_returns_a_suggestion(self, member_client):
        tid = member_client.post(
            "/api/tasks", json={"title": "Fix bug", "priority": "HIGH"}
        ).get_json()["id"]
        body = member_client.get(f"/api/tasks/{tid}/ai").get_json()
        assert body["suggestion"]
        assert body["pair_with"]

    def test_ai_endpoint_404s_for_unknown_task(self, member_client):
        assert member_client.get("/api/tasks/nope/ai").status_code == 404


# --------------------------------------------------------------- feedback
class TestFeedbackApi:
    def test_submitted_feedback_is_listed_without_an_author(self, member_client):
        assert member_client.post(
            "/api/feedback", json={"message": "Too many meetings", "mood": "concerned"}
        ).status_code == 201

        items = member_client.get("/api/feedback").get_json()
        assert len(items) == 1
        assert items[0]["message"] == "Too many meetings"
        assert "author" not in items[0]
        assert "user_id" not in items[0]

    def test_admin_can_delete_feedback(self, admin_client):
        fid = admin_client.post(
            "/api/feedback", json={"message": "msg", "mood": "ok"}
        ).get_json()["id"]
        assert admin_client.delete(f"/api/feedback/{fid}").status_code == 200
        assert admin_client.get("/api/feedback").get_json() == []


# ------------------------------------------------------- governance / undo
class TestGovernanceApi:
    def test_constitution_exposes_four_weighted_policies(self, member_client):
        policies = member_client.get("/api/constitution").get_json()
        assert len(policies) == 4
        assert {"name", "description", "weight"} <= set(policies[0])

    def test_events_feed_records_actions(self, member_client):
        member_client.post("/api/tasks", json={"title": "Tracked", "priority": "HIGH"})
        types = [e["type"] for e in member_client.get("/api/events").get_json()]
        assert "task.created" in types

    def test_events_feed_never_leaks_undo_closures(self, member_client):
        member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"})
        for event in member_client.get("/api/events").get_json():
            assert "_undo" not in event

    def test_undo_endpoint_restores_a_deleted_task(self, member_client):
        tid = member_client.post("/api/tasks", json={"title": "T", "priority": "HIGH"}).get_json()["id"]
        member_client.delete(f"/api/tasks/{tid}")

        delete_event = next(
            e for e in member_client.get("/api/events").get_json() if e["type"] == "task.deleted"
        )
        res = member_client.post(f"/api/undo/{delete_event['id']}")
        assert res.get_json()["ok"] is True
        assert member_client.get(f"/api/tasks/{tid}").status_code == 200

    def test_undo_of_an_unknown_event_reports_failure(self, member_client):
        assert member_client.post("/api/undo/9999").get_json()["ok"] is False

    def test_boy_scout_report_shows_improvement(self, member_client):
        report = member_client.get("/api/boy-scout").get_json()
        assert report["after"]["coverage"] > report["before"]["coverage"]
        assert report["after"]["duplication"] < report["before"]["duplication"]
