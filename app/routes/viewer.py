
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from ..managers.tournament import tournament_manager
from ..managers.connection import connection_manager

router = APIRouter(prefix="/viewer", tags=["Viewer API"])


@router.get("/status")
async def get_public_status():
    """Get public tournament status (no auth required)"""
    status = tournament_manager.get_tournament_status()
    # Remove sensitive info
    return {
        "tournament_id": status["tournament_id"],
        "name": status["name"],
        "status": status["status"],
        "registered_players": status["registered_players"],
        "remaining_players": status["remaining_players"],
        "active_tables": status["active_tables"],
        "hands_played": status["hands_played"],
        "current_blinds": status["current_blinds"]
    }


@router.get("/tables")
async def get_public_tables():
    """Get public table states (hole cards hidden)"""
    return {
        "tables": tournament_manager.get_table_states()
    }


@router.get("/leaderboard")
async def get_leaderboard():
    """Get current chip leaderboard"""
    players = tournament_manager.get_player_list()
    
    # Sort by chips (descending)
    leaderboard = sorted(
        [p for p in players if p.get("chips", 0) > 0],
        key=lambda x: x.get("chips", 0),
        reverse=True
    )

    return {
        "leaderboard": [
            {
                "position": i + 1,
                "username": p["username"],
                "chips": p.get("chips", 0),
                "table_id": p.get("table_id")
            }
            for i, p in enumerate(leaderboard)
        ],
        "eliminations": tournament_manager.eliminations[-20:]
    }


@router.websocket("/ws")
async def viewer_websocket(websocket: WebSocket):
    """WebSocket for real-time game viewing"""
    await connection_manager.connect_viewer(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "data": {
                "tournament_status": tournament_manager.get_tournament_status(),
                "tables": tournament_manager.get_table_states()
            }
        })

        while True:
            # Keep connection alive, viewers don't send data typically
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect_viewer(websocket)