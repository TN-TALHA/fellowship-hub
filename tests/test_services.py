"""Unit tests for the application services layer.

The two classes marked "Scenario" map directly onto
features/fellowship.feature.txt — those are the acceptance criteria.
"""
from datetime import datetime, timedelta

import pytest

import services
from domain import Priority, Role, Task, TaskStatus
from events import bus


# ---------------------------------------------------------------- scenarios
class TestScenarioCriticalOutranksLow:
    """Scenario: Critical outranks Low."""

    def test_critical_scores_higher_than_low(self):
        critical = Task("Prod is down", "", Priority.CRITICAL)
        low = Task("Rename a label", "", Priority.LOW)
        assert services.compute_priority_score(critical) > services.compute_priority_score(low)

    def test_score_rises_with_priority_across_all_four_levels(self):
        scores = [
            services.compute_priority_score(Task("t", "", p))
            for p in (Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL)
        ]
        assert scores == sorted(scores)


class TestScenarioAnonymousFeedback:
    """Scenario: Anonymous feedback is stored."""

    def test_feedback_is_stored(self):
        fb = services.submit_feedback("Standups run long", "concerned")
        assert fb in services.feedback_list
        assert fb.mood == "concerned"

    def test_feedback_is_stored_without_an_identity(self):
        fb = services.submit_feedback("Standups run long", "concerned")
        stored = vars(fb)
        assert "author" not in stored
        assert "user_id" not in stored
        assert "username" not in stored

    def test_published_event_leaks_only_the_mood(self):
        services.submit_feedback("Secret complaint text", "concerned")
        event = bus.history[-1]
        assert event["type"] == "feedback.submitted"
        assert event["payload"] == {"mood": "concerned"}
        assert "Secret complaint text" not in str(event["payload"])


# ------------------------------------------------------------------ scoring
class TestPriorityScore:
    def test_story_points_add_to_the_score(self):
        small = Task("t", "", Priority.HIGH, story_points=1)
        large = Task("t", "", Priority.HIGH, story_points=8)
        diff = services.compute_priority_score(large) - services.compute_priority_score(small)
        assert diff == pytest.approx(7)

    def test_aging_bonus_grows_then_caps_at_10(self):
        fresh = Task("t", "", Priority.MEDIUM)
        three_days = Task("t", "", Priority.MEDIUM)
        three_days.created_at = datetime.now() - timedelta(days=3)
        ancient = Task("t", "", Priority.MEDIUM)
        ancient.created_at = datetime.now() - timedelta(days=365)

        base = services.compute_priority_score(fresh)
        assert services.compute_priority_score(three_days) == base + 6
        assert services.compute_priority_score(ancient) == base + 10


# ------------------------------------------------------------------- auth
class TestAuthenticate:
    def test_correct_credentials_return_the_user(self):
        u = services.authenticate("admin", "admin123")
        assert u is not None
        assert u.role is Role.ADMIN

    @pytest.mark.parametrize(
        "username,password",
        [
            ("admin", "wrong"),
            ("nobody", "admin123"),
            ("", ""),
            ("admin", ""),
        ],
    )
    def test_bad_credentials_return_none(self, username, password):
        assert services.authenticate(username, password) is None

    def test_deactivated_user_cannot_authenticate(self):
        u = services.authenticate("ayesha", "pass123")
        u.is_active = False
        assert services.authenticate("ayesha", "pass123") is None


# ------------------------------------------------------------------- users
class TestCreateUser:
    def test_creates_and_stores_the_user(self):
        u, err = services.create_user("new", "secret123", "New Person", Role.MEMBER, "n@fh.dev")
        assert err == ""
        assert services.users[u.id] is u

    def test_rejects_duplicate_username(self):
        u, err = services.create_user("admin", "secret123", "Clone", Role.MEMBER, "")
        assert u is None
        assert err == "Username already exists"

    def test_rejects_short_password(self):
        u, err = services.create_user("new", "123", "New", Role.MEMBER, "")
        assert u is None
        assert "6 characters" in err


class TestDeleteUser:
    def test_deleting_a_user_unassigns_their_tasks(self, user_ids):
        ayesha = user_ids["ayesha"]
        t = services.create_task("Task", "", Priority.HIGH, 2, user_ids["admin"])
        services.assign_task(t.id, ayesha)

        assert services.delete_user(ayesha) is True
        assert ayesha not in services.users
        assert t.assigned_to is None

    def test_deleting_an_unknown_user_returns_false(self):
        assert services.delete_user("does-not-exist") is False


# ------------------------------------------------------------------- tasks
class TestTaskLifecycle:
    def test_create_move_and_delete(self, user_ids):
        t = services.create_task("Write tests", "cover auth", Priority.MEDIUM, 2, user_ids["admin"])
        assert services.tasks[t.id] is t

        assert services.move_task(t.id, TaskStatus.IN_PROGRESS) is True
        assert t.status is TaskStatus.IN_PROGRESS

        assert services.delete_task(t.id) is True
        assert t.id not in services.tasks

    def test_operations_on_a_missing_task_return_false(self):
        assert services.move_task("nope", TaskStatus.DONE) is False
        assert services.delete_task("nope") is False
        assert services.assign_task("nope", "nope") is False
        assert services.add_comment("nope", "me", "hi") is False

    def test_add_comment_records_author_and_text(self, user_ids):
        t = services.create_task("T", "", Priority.LOW, 1, user_ids["admin"])
        assert services.add_comment(t.id, "Ayesha Khan", "On it") is True
        assert t.comments[0]["author"] == "Ayesha Khan"
        assert t.comments[0]["text"] == "On it"


# -------------------------------------------------------------- sprint board
class TestSprintBoard:
    def test_board_has_a_column_per_status(self):
        board = services.sprint_board()
        assert set(board) == {s.value for s in TaskStatus}

    def test_tasks_are_sorted_highest_score_first(self, user_ids):
        admin = user_ids["admin"]
        services.create_task("Low one", "", Priority.LOW, 1, admin)
        services.create_task("Critical one", "", Priority.CRITICAL, 1, admin)
        backlog = services.sprint_board()["Backlog"]
        assert [t["title"] for t in backlog] == ["Critical one", "Low one"]

    def test_archived_tasks_are_hidden(self, user_ids):
        t = services.create_task("Hidden", "", Priority.HIGH, 1, user_ids["admin"])
        t.archived = True
        assert services.sprint_board()["Backlog"] == []

    def test_search_filters_by_title_and_description(self, user_ids):
        admin = user_ids["admin"]
        services.create_task("Fix login", "mobile broken", Priority.HIGH, 1, admin)
        services.create_task("Design UI", "landing page", Priority.HIGH, 1, admin)

        assert len(services.sprint_board(search="login")["Backlog"]) == 1
        assert len(services.sprint_board(search="MOBILE")["Backlog"]) == 1
        assert len(services.sprint_board(search="zzz")["Backlog"]) == 0

    def test_priority_filter(self, user_ids):
        admin = user_ids["admin"]
        services.create_task("A", "", Priority.CRITICAL, 1, admin)
        services.create_task("B", "", Priority.LOW, 1, admin)
        board = services.sprint_board(filter_priority="CRITICAL")
        assert [t["title"] for t in board["Backlog"]] == ["A"]

    def test_unassigned_tasks_are_labelled(self, user_ids):
        services.create_task("Orphan", "", Priority.LOW, 1, user_ids["admin"])
        assert services.sprint_board()["Backlog"][0]["assignee"] == "Unassigned"


# --------------------------------------------------------------- undo / bus
class TestUndo:
    def test_undo_restores_a_deleted_task(self, user_ids):
        t = services.create_task("Oops", "", Priority.HIGH, 1, user_ids["admin"])
        services.delete_task(t.id)
        assert t.id not in services.tasks

        delete_event = bus.history[-1]
        assert bus.undo(delete_event["id"]) is True
        assert services.tasks[t.id] is t

    def test_undo_reverts_a_status_move(self, user_ids):
        t = services.create_task("T", "", Priority.HIGH, 1, user_ids["admin"])
        services.move_task(t.id, TaskStatus.DONE)
        move_event = bus.history[-1]

        assert bus.undo(move_event["id"]) is True
        assert t.status is TaskStatus.BACKLOG

    def test_an_event_cannot_be_undone_twice(self, user_ids):
        t = services.create_task("T", "", Priority.HIGH, 1, user_ids["admin"])
        services.delete_task(t.id)
        eid = bus.history[-1]["id"]

        assert bus.undo(eid) is True
        assert bus.undo(eid) is False

    def test_undoing_an_unknown_event_returns_false(self):
        assert bus.undo(9999) is False


class TestGovernance:
    def test_summary_counts_audited_events(self, user_ids):
        before = services.governance_summary()["total_events"]
        services.create_task("T", "", Priority.LOW, 1, user_ids["admin"])
        after = services.governance_summary()["total_events"]
        assert after > before


class TestAiSuggest:
    @pytest.mark.parametrize(
        "title,expected_fragment",
        [
            ("Fix bug in parser", "failing test"),
            ("Polish ui spacing", "designer"),
            ("Add api endpoint", "OpenAPI"),
            ("Something unrelated", "smaller deliverable chunks"),
        ],
    )
    def test_keyword_routing(self, title, expected_fragment, user_ids):
        t = services.create_task(title, "", Priority.LOW, 1, user_ids["admin"])
        assert expected_fragment in services.ai_suggest(t)["suggestion"]

    def test_suggests_a_real_pairing_partner(self, user_ids):
        t = services.create_task("T", "", Priority.LOW, 1, user_ids["admin"])
        names = {u.full_name for u in services.users.values()}
        assert services.ai_suggest(t)["pair_with"] in names


class TestConstitution:
    def test_policy_weights_sum_to_one(self):
        total = sum(p.weight for p in services.CONSTITUTION)
        assert total == pytest.approx(1.0)
