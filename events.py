"""Integration Patterns: Event Bus + Undo stack (Command pattern)."""
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self.history: list[dict] = []

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict, undo: Callable = None) -> dict:
        event = {
            "id": len(self.history) + 1,
            "type": event_type,
            "payload": payload,
            "at": datetime.now().isoformat(timespec="seconds"),
            "undoable": undo is not None,
            "undone": False,
        }
        event["_undo"] = undo          # keep closure, not serialized out
        self.history.append(event)
        for h in self._subscribers.get(event_type, []):
            h(event)
        for h in self._subscribers.get("*", []):
            h(event)
        return event

    def undo(self, event_id: int) -> bool:
        for e in self.history:
            if e["id"] == event_id and e["undoable"] and not e["undone"]:
                if e["_undo"]:
                    e["_undo"]()
                e["undone"] = True
                self.publish("action.undone", {"original": e["type"], "id": event_id})
                return True
        return False

    def recent(self, n: int = 30) -> list[dict]:
        out = []
        for e in self.history[-n:][::-1]:
            out.append({k: v for k, v in e.items() if k != "_undo"})
        return out


bus = EventBus()
audit_log: list[dict] = []


def audit_subscriber(event: dict):
    audit_log.append({k: v for k, v in event.items() if k != "_undo"})


bus.subscribe("*", audit_subscriber)