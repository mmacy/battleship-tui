from blacksheep import Application, FromJSON, Response, WebSocket

from battleship.server.auth import AuthManager, FirebaseAuthManager
from battleship.server.config import Config, get_config
from battleship.server.connections import ConnectionManager
from battleship.server.players import Players
from battleship.server.schemas import GuestUser, SessionCreate
from battleship.server.sessions import Sessions
from battleship.shared.sessions import Session

app = Application()

app.services.add_singleton_by_factory(get_config, Config)
app.services.add_singleton(AuthManager, FirebaseAuthManager)
app.services.add_singleton(Sessions)
app.services.add_singleton(Players)
app.services.add_singleton(ConnectionManager)


@app.router.ws("/ws")
async def ws(websocket: WebSocket, connection_handler: ConnectionManager) -> None:
    await websocket.accept()
    await connection_handler(websocket)


@app.router.get("/sessions")
async def list_sessions(session_repository: Sessions) -> list[Session]:
    return session_repository.list()


@app.router.post("/sessions")
async def create_session(
    session: FromJSON[SessionCreate],
    session_repository: Sessions,
) -> Session:
    return session_repository.add(session.value)


@app.router.delete("/sessions/{session_id}")
async def remove_session(
    session_id: str,
    session_repository: Sessions,
) -> Response:
    session_repository.remove(session_id)
    return Response(status=204)


@app.router.post("/login/guest")
async def login_guest_user(auth_manager: AuthManager) -> GuestUser:
    return await auth_manager.login_guest()
