from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
import secrets

from ..config import server_settings
from ..managers.tournament import tournament_manager
from ..managers.connection import connection_manager
from ..models.api import AdminLoginRequest, AdminCommandRequest

router = APIRouter(prefix="/admin", tags=["Admin API"])
security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials"""
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        server_settings.admin_password.encode("utf-8")
    )
    if not correct_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"}
        )
    return True


@router.get("/status")
async def get_tournament_status(_: bool = Depends(verify_admin)):
    """Get current tournament status"""
    return tournament_manager.get_tournament_status()


@router.get("/players")
async def get_players(_: bool = Depends(verify_admin)):
    """Get list of all registered players"""
    return {
        "players": tournament_manager.get_player_list(),
        "total": len(tournament_manager.registered_players)
    }


@router.get("/tables")
async def get_tables(_: bool = Depends(verify_admin)):
    """Get state of all active tables"""
    return {
        "tables": tournament_manager.get_table_states(),
        "total": len(tournament_manager.tables)
    }


@router.post("/start")
async def start_tournament(_: bool = Depends(verify_admin)):
    """Start the tournament"""
    result = await tournament_manager.start_tournament()
    return result


@router.post("/pause")
async def pause_tournament(_: bool = Depends(verify_admin)):
    """Pause the tournament"""
    return tournament_manager.pause_tournament()


@router.post("/resume")
async def resume_tournament(_: bool = Depends(verify_admin)):
    """Resume a paused tournament"""
    return await tournament_manager.resume_tournament()


@router.post("/reset")
async def reset_tournament(_: bool = Depends(verify_admin)):
    """Reset the tournament (clears game state, keeps registrations)"""
    return tournament_manager.reset_tournament()


@router.post("/kick/{player_id}")
async def kick_player(player_id: str, reason: str = "Admin decision", _: bool = Depends(verify_admin)):
    """Kick a player from the tournament"""
    return await tournament_manager.kick_player(player_id, reason)


@router.delete("/player/{player_id}")
async def remove_player(player_id: str, _: bool = Depends(verify_admin)):
    """Remove a player from registration"""
    if player_id not in tournament_manager.registered_players:
        raise HTTPException(status_code=404, detail="Player not found")

    # Remove from all maps
    player_info = tournament_manager.registered_players.pop(player_id)
    api_key = player_info.get("api_key")
    if api_key:
        tournament_manager.api_keys.pop(api_key, None)
    tournament_manager.player_table_map.pop(player_id, None)

    return {"success": True, "message": f"Player {player_info['username']} removed"}


@router.post("/broadcast")
async def broadcast_message(message: str, _: bool = Depends(verify_admin)):
    """Broadcast a message to all connected clients"""
    broadcast_data = {
        "type": "admin_message",
        "data": {"message": message}
    }

    await connection_manager.broadcast_to_viewers(broadcast_data)
    await connection_manager.send_to_all_players(broadcast_data)

    return {"success": True, "message": "Broadcast sent"}


@router.websocket("/ws")
async def admin_websocket(websocket: WebSocket):
    """WebSocket for real-time admin updates"""
    await connection_manager.connect_admin(websocket)

    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "data": tournament_manager.get_tournament_status()
        })

        while True:
            data = await websocket.receive_text()
            # Admin can send commands via WebSocket
            # For now, just keep connection alive

    except WebSocketDisconnect:
        print("[Admin WS] Admin disconnected")
    finally:
        await connection_manager.disconnect_admin(websocket)