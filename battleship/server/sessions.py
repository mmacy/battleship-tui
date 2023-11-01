import asyncio
import weakref
from asyncio import Task
from typing import Callable, Coroutine, TypeAlias

from battleship.shared.models import (
    Action,
    Session,
    SessionCreate,
    SessionID,
    make_session_id,
)

Listener: TypeAlias = Callable[[SessionID, Action], Coroutine]


class Sessions:
    def __init__(self) -> None:
        self._sessions: dict[SessionID, Session] = {}
        self._listeners: weakref.WeakSet[Listener] = weakref.WeakSet()
        self._notify_task: Task[None] | None = None

    def add(self, data: SessionCreate) -> Session:
        session = Session(id=make_session_id(), **data.to_dict())
        self._sessions[session.id] = session
        self._notify_listeners(session.id, Action.ADD)
        return session

    def get(self, session_id: str) -> Session:
        return self._sessions[session_id]

    def list(self) -> list[Session]:
        return list(self._sessions.values())

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._notify_listeners(session_id, Action.REMOVE)

    def subscribe(self, callback: Listener) -> None:
        self._listeners.add(callback)

    def unsubscribe(self, callback: Listener) -> None:
        self._listeners.discard(callback)

    def _notify_listeners(self, session_id: str, action: Action) -> None:
        async def notify_task() -> None:
            for subscriber in self._listeners:
                await subscriber(session_id, action)

        self._notify_task = asyncio.create_task(notify_task())
