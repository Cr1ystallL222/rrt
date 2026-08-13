import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from aiohttp import web

@dataclass
class ClientSession:
    client_id: str
    hostname: str
    username: str
    os_info: str
    ip_address: str
    ws: web.WebSocketResponse
    is_admin: bool = False
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    pending_requests: Dict[str, asyncio.Future] = field(default_factory=dict)

class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, ClientSession] = {}
        self._lock = asyncio.Lock()

    async def register(self, client_id: str, data: dict, ws: web.WebSocketResponse, ip: str) -> ClientSession:
        async with self._lock:
            session = ClientSession(
                client_id=client_id,
                hostname=data.get("hostname", "Unknown"),
                username=data.get("username", "Unknown"),
                os_info=data.get("os_info", "Unknown"),
                ip_address=ip,
                ws=ws,
                is_admin=data.get("is_admin", False)
            )
            self._sessions[client_id] = session
            return session

    async def unregister(self, client_id: str):
        async with self._lock:
            if client_id in self._sessions:
                session = self._sessions.pop(client_id)
                # Отменяем все зависшие запросы
                for req_id, future in session.pending_requests.items():
                    if not future.done():
                        future.cancel()

    def get_session(self, client_id: str) -> Optional[ClientSession]:
        return self._sessions.get(client_id)

    def get_all_sessions(self) -> Dict[str, ClientSession]:
        return dict(self._sessions)

    async def send_command(self, client_id: str, action: str, params: dict = None, timeout: float = 15.0) -> dict:
        """Отправляет команду клиенту и ожидает ответа с correlation request_id"""
        session = self.get_session(client_id)
        if not session or session.ws.closed:
            raise ConnectionError("Клиент оффлайн или сессия не найдена")

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        session.pending_requests[request_id] = future

        message = {
            "type": "command",
            "request_id": request_id,
            "action": action,
            "params": params or {}
        }

        try:
            await session.ws.send_str(json.dumps(message))
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        finally:
            session.pending_requests.pop(request_id, None)

    def handle_client_response(self, client_id: str, payload: dict):
        """Обрабатывает ответ от клиента по request_id"""
        session = self.get_session(client_id)
        if not session:
            return

        req_id = payload.get("request_id")
        if req_id and req_id in session.pending_requests:
            future = session.pending_requests[req_id]
            if not future.done():
                future.set_result(payload)

    def update_heartbeat(self, client_id: str, status_data: dict):
        session = self.get_session(client_id)
        if session:
            session.last_heartbeat = datetime.now()


session_manager = SessionManager()
