from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.register(websocket)

    def register(self, websocket: WebSocket):
        # Add an already-accepted socket to the broadcast pool (used after auth).
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except:
            pass

    async def close(self):
        for websocket in self.active_connections:
            await websocket.close()
        self.active_connections = []

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        # Iterate a copy and remove dead sockets afterwards — disconnecting during
        # iteration over the live list skips the socket after each dead one.
        dead = []
        for websocket in list(self.active_connections):
            try:
                await websocket.send_text(message)
            except:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)
