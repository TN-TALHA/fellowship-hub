"""Shared pytest fixtures.

The app keeps its data in module-level dicts (in-memory stores), so every test
must start from a clean slate. `reset_state` runs automatically before each
test and wipes users, tasks, feedback and the event history.
"""
import pytest

import app as app_module
import events
import services


@pytest.fixture(autouse=True)
def reset_state():
    """Wipe all in-memory stores, then re-seed the four demo users."""
    services.users.clear()
    services.tasks.clear()
    services.feedback_list.clear()
    events.bus.history.clear()
    events.audit_log.clear()
    services.seed_users()
    yield
    services.users.clear()
    services.tasks.clear()
    services.feedback_list.clear()
    events.bus.history.clear()
    events.audit_log.clear()


@pytest.fixture
def client():
    """Anonymous Flask test client — not logged in."""
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


def _login(c, username, password):
    res = c.post("/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"login failed for {username}: {res.get_json()}"
    return c


@pytest.fixture
def admin_client(client):
    """Logged in as the Admin user."""
    return _login(client, "admin", "admin123")


@pytest.fixture
def member_client(client):
    """Logged in as a plain Member (no admin rights)."""
    return _login(client, "ayesha", "pass123")


@pytest.fixture
def user_ids():
    """Map username -> id for the seeded users."""
    return {u.username: u.id for u in services.users.values()}
