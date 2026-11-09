import asyncio
import json
import queue
import threading
from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self, queue_size: int = 32):
        self._queue_size = queue_size
        self._clients: Dict[int, Dict[WebSocket, queue.Queue]] = {}
        self._lock = threading.RLock()

    def connect(self, session_id: int, websocket: WebSocket) -> queue.Queue:
        client_queue = queue.Queue(maxsize=self._queue_size)
        with self._lock:
            self._clients.setdefault(session_id, {})[websocket] = client_queue
        return client_queue

    def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        with self._lock:
            clients = self._clients.get(session_id)
            if clients is None:
                return
            clients.pop(websocket, None)
            if not clients:
                self._clients.pop(session_id, None)

    def publish(self, session_id: int, message: dict) -> None:
        encoded = json.dumps(message, default=str)
        with self._lock:
            clients = list(self._clients.get(session_id, {}).values())
        for client_queue in clients:
            try:
                client_queue.put_nowait(encoded)
            except queue.Full:
                try:
                    client_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    client_queue.put_nowait(encoded)
                except queue.Full:
                    pass

    async def receive(self, client_queue: queue.Queue, timeout: float = 1.0) -> str:
        try:
            return await asyncio.to_thread(client_queue.get, True, timeout)
        except queue.Empty:
            return ""
