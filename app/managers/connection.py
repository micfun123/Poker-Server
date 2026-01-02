import asyncio
import json
from typing import Dict, List, Set, Optional
from fastapi import WebSocket
from datetime import datetime

class ConnectionManager:
    """
    Manages WebSocket connections for players and viewers.
    """

    def __init__(self):
        # Player connections: player_id -> WebSocket
        self.player_connections: Dict[str, WebSocket] = {}
        # Viewer connections: Set of WebSockets
        self.viewer_connections: Set[WebSocket] = set()
        # Admin connections
        self.admin_connections: Set[WebSocket] = set()
        # Message queues for players
        self.player_queues: Dict[str, asyncio.Queue] = {}

    async def connect_player(self, websocket: WebSocket, player_id: str) -> bool:
        """Connect a player WebSocket"""
        await websocket.accept()
        self.player_connections[player_id] = websocket
        self.player_queues[player_id] = asyncio.Queue()
        print(f"[ConnectionManager] Player {player_id} connected")
        return True

    async def disconnect_player(self, player_id: str):
        """Disconnect a player"""
        if player_id in self.player_connections:
            del self.player_connections[player_id]
        if player_id in self.player_queues:
            del self.player_queues[player_id]
        print(f"[ConnectionManager] Player {player_id} disconnected")

    async def connect_viewer(self, websocket: WebSocket) -> bool:
        """Connect a viewer WebSocket"""
        await websocket.accept()
        self.viewer_connections.add(websocket)
        print(f"[ConnectionManager] Viewer connected. Total viewers: {len(self.viewer_connections)}")
        return True

    async def disconnect_viewer(self, websocket: WebSocket):
        """Disconnect a viewer"""
        self.viewer_connections.discard(websocket)
        print(f"[ConnectionManager] Viewer disconnected. Total viewers: {len(self.viewer_connections)}")

    async def connect_admin(self, websocket: WebSocket) -> bool:
        """Connect an admin WebSocket"""
        await websocket.accept()
        self.admin_connections.add(websocket)
        print(f"[ConnectionManager] Admin connected")
        return True

    async def disconnect_admin(self, websocket: WebSocket):
        """Disconnect an admin"""
        self.admin_connections.discard(websocket)
        print(f"[ConnectionManager] Admin disconnected")

    async def send_to_player(self, player_id: str, message: dict):
        """Send a message to a specific player"""
        if player_id in self.player_connections:
            try:
                ws = self.player_connections[player_id]
                await ws.send_json(message)
            except Exception as e:
                print(f"[ConnectionManager] Error sending to player {player_id}: {e}")
                await self.disconnect_player(player_id)

    async def send_to_all_players(self, message: dict, player_ids: Optional[List[str]] = None):
        """Send a message to multiple players"""
        targets = player_ids if player_ids else list(self.player_connections.keys())
        for pid in targets:
            await self.send_to_player(pid, message)

    async def broadcast_to_viewers(self, message: dict):
        """Broadcast a message to all viewers"""
        disconnected = []
        for websocket in self.viewer_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"[ConnectionManager] Error broadcasting to viewer: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self.viewer_connections.discard(ws)

    async def broadcast_to_admins(self, message: dict):
        """Broadcast a message to all admins"""
        disconnected = []
        for websocket in self.admin_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"[ConnectionManager] Error broadcasting to admin: {e}")
                disconnected.append(websocket)
        
        for ws in disconnected:
            self.admin_connections.discard(ws)

    async def broadcast_game_state(self, game_engine, player_ids: List[str]):
        """Broadcast game state to all relevant parties"""
        # Send personalized state to each player
        for pid in player_ids:
            player_state = game_engine.get_state_for_player(pid)
            await self.send_to_player(pid, {
                "type": "game_state",
                "data": player_state,
                "timestamp": datetime.now().isoformat()
            })

        # Send public state to viewers
        public_state = game_engine.get_public_state()
        await self.broadcast_to_viewers({
            "type": "game_state",
            "data": public_state,
            "timestamp": datetime.now().isoformat()
        })

        # Send to admins as well
        await self.broadcast_to_admins({
            "type": "game_state",
            "data": public_state,
            "timestamp": datetime.now().isoformat()
        })

    def is_player_connected(self, player_id: str) -> bool:
        """Check if a player is connected"""
        return player_id in self.player_connections

    def get_connected_player_count(self) -> int:
        """Get number of connected players"""
        return len(self.player_connections)

    def get_viewer_count(self) -> int:
        """Get number of connected viewers"""
        return len(self.viewer_connections)


# Global connection manager instance
connection_manager = ConnectionManager()