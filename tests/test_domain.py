"""Unit tests for the domain layer — pure business concepts, no Flask."""
from datetime import datetime

from domain import Feedback, Policy, Priority, Role, Task, TaskStatus, User


class TestEnums:
    def test_priority_is_ordered_low_to_critical(self):
        assert Priority.LOW.value < Priority.MEDIUM.value
        assert Priority.MEDIUM.value < Priority.HIGH.value
        assert Priority.HIGH.value < Priority.CRITICAL.value

    def test_roles(self):
        assert Role.ADMIN.value == "Admin"
        assert Role.MEMBER.value == "Member"

    def test_task_statuses_cover_the_board(self):
        values = [s.value for s in TaskStatus]
        assert values == ["Backlog", "In Progress", "Review", "Done"]


class TestUser:
    def test_new_user_gets_an_id_and_is_active(self):
        u = User("ali", "secret123", "Ali Raza", Role.MEMBER)
        assert len(u.id) == 8
        assert u.is_active is True
        assert isinstance(u.joined_at, datetime)

    def test_ids_are_unique(self):
        a = User("a", "secret123", "A", Role.MEMBER)
        b = User("b", "secret123", "B", Role.MEMBER)
        assert a.id != b.id


class TestTask:
    def test_task_starts_in_backlog_unassigned(self):
        t = Task("Fix bug", "desc", Priority.HIGH)
        assert t.status is TaskStatus.BACKLOG
        assert t.assigned_to is None
        assert t.archived is False
        assert t.comments == []

    def test_comments_list_is_not_shared_between_tasks(self):
        a = Task("A", "", Priority.LOW)
        b = Task("B", "", Priority.LOW)
        a.comments.append({"author": "x", "text": "hi", "at": "now"})
        assert b.comments == []


class TestFeedback:
    def test_feedback_carries_no_author_field(self):
        fb = Feedback("Too many meetings", "concerned")
        assert not hasattr(fb, "author")
        assert not hasattr(fb, "user_id")


class TestPolicy:
    def test_policy_is_a_weighted_rule(self):
        p = Policy("Urgency", "Critical tasks handled first", 0.40)
        assert p.weight == 0.40
