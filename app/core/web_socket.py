import json
from collections import defaultdict
from fastapi import WebSocket


class WebSocketManager:
    """
    Manages active WebSocket connections for multiple clients.
    Ensures state separation between browser sessions and reliable broadcasts.
    """
    def __init__(self) -> None:
        self._clients: dict[str, list[WebSocket]] = defaultdict(list)

    async def register_client(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        # Close any stale connections for this session before adding new one
        stale = list(self._clients.get(session_id, []))
        for old_ws in stale:
            try:
                await old_ws.close()
            except Exception:
                pass
        self._clients[session_id] = [ws]

    def unregister_client(self, session_id: str, ws: WebSocket) -> None:
        """Removes a socket connection from the manager."""
        conns = self._clients.get(session_id, [])
        if ws in conns:
            conns.remove(ws)

    async def transmit_event(self, session_id: str, event: str, data: dict) -> None:
        """Sends a named message event payload to all sockets tied to a session."""
        payload = json.dumps({"event": event, **data})
        dead = []
        for ws in list(self._clients.get(session_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister_client(session_id, ws)

    async def transmit_to_all(self, event: str, data: dict) -> None:
        """Globally pushes an event out to every single connected client."""
        payload = json.dumps({"event": event, **data})
        for sid in list(self._clients):
            for ws in list(self._clients[sid]):
                try:
                    await ws.send_text(payload)
                except Exception:
                    self.unregister_client(sid, ws)


ws_manager = WebSocketManager()