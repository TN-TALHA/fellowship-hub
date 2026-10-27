"""DDD: Domain layer — pure business concepts, no framework code."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


def _uid() -> str:
    return uuid.uuid4().hex[:8]


class Role(Enum):
    ADMIN = "Admin"
    MEMBER = "Member"


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    BACKLOG = "Backlog"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"


@dataclass
class User:
    """Aggregate Root — a person with login."""
    username: str
    password: str        # demo only; real product uses hashing
    full_name: str
    role: Role
    email: str = ""
    id: str = field(default_factory=_uid)
    joined_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class Task:
    """Entity — a unit of work."""
    title: str
    description: str
    priority: Priority
    story_points: int = 1
    id: str = field(default_factory=_uid)
    status: TaskStatus = TaskStatus.BACKLOG
    assigned_to: str | None = None
    created_by: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    archived: bool = False
    comments: list = field(default_factory=list)   # [{author, text, at}]


@dataclass
class Feedback:
    """Entity — anonymous psychological-safety feedback."""
    message: str
    mood: str
    id: str = field(default_factory=_uid)
    created_at: datetime = field(default_factory=datetime.now)
    archived: bool = False


@dataclass
class Policy:
    """Value Object — a constitution rule."""
    name: str
    description: str
    weight: float