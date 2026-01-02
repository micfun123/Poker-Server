from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from typing import Optional
import json

from ..models.api import RegisterBotRequest, RegisterBotResponse, BotActionRequest, BotActionResponse
from ..models.game import ActionType
from ..managers.tournament import tournament_manager
from ..managers.connection import connection_manager

router = APIRouter(prefix="/bot", tags=["Bot API"])


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Verify API key and return player_id"""
    player_id = tournament_manager.authenticate_player(x_api_key)
    if not player_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return player_id


@router.post("/register", response_model=RegisterBotResponse)
async def register_bot(request: RegisterBotRequest):
    """
    Register a new bot for the tournament.
    Returns player_id and api_key for authentication.
    """
    result = tournament_manager.register_player(
        username=request.username,
        team_name=request.team_name
    )

    if not result["success"]:
        return RegisterBotResponse(
            success=False,
            message=result["message"]
        )

    return RegisterBotResponse(
        success=True,
        player_id=result["player_id"],
        api_key=result["api_key"],
        message=result["message"],
        websocket_url=f"/ws/player/{result['player_id']}"
    )


@router.post("/action", response_model=BotActionResponse)
async def submit_action(
    request: BotActionRequest,
    player_id: str = Depends(verify_api_key)
):
    """
    Submit a poker action (fold, check, call, bet, raise, all_in).
    Requires X-API-Key header for authentication.
    """
    result = await tournament_manager.process_player_action(
        player_id=player_id,
        action_type=request.action_type,
        amount=request.amount
    )

    game_state = tournament_manager.get_player_game_state(player_id)

    return BotActionResponse(
        success=result["success"],
        message=result["message"],
        action_accepted=result.get("action"),
        game_state=game_state
    )


@router.get("/state")
async def get_game_state(player_id: str = Depends(verify_api_key)):
    """
    Get current game state for your bot.
    Includes your hole cards and valid actions.
    """
    game_state = tournament_manager.get_player_game_state(player_id)
    
    if not game_state:
        return {
            "status": "waiting",
            "message": "Not currently at a table",
            "tournament_status": tournament_manager.status.value
        }

    return {
        "status": "active",
        "game_state": game_state
    }


@router.get("/valid-actions")
async def get_valid_actions(player_id: str = Depends(verify_api_key)):
    """Get list of valid actions for current game state"""
    table_id = tournament_manager.player_table_map.get(player_id)
    
    if not table_id or table_id not in tournament_manager.tables:
        return {"valid_actions": [], "message": "Not at an active table"}

    game_engine = tournament_manager.tables[table_id]
    valid_actions = game_engine.get_valid_actions(player_id)

    return {
        "player_id": player_id,
        "is_your_turn": game_engine.game_state.current_player_id == player_id,
        "valid_actions": valid_actions
    }


@router.websocket("/ws/{player_id}")
async def bot_websocket(websocket: WebSocket, player_id: str):
    """
    WebSocket connection for real-time game updates.
    Bot should send actions as JSON: {"action_type": "call", "amount": null}
    """
    # Verify player exists
    if player_id not in tournament_manager.registered_players:
        await websocket.close(code=4001, reason="Player not registered")
        return

    await connection_manager.connect_player(websocket, player_id)

    try:
        # Send initial state
        game_state = tournament_manager.get_player_game_state(player_id)
        await websocket.send_json({
            "type": "connected",
            "data": {
                "player_id": player_id,
                "tournament_status": tournament_manager.status.value,
                "game_state": game_state
            }
        })

        while True:
            # Receive action from bot
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "action":
                    action_data = message.get("data", {})
                    action_type = ActionType(action_data.get("action_type"))
                    amount = action_data.get("amount")

                    result = await tournament_manager.process_player_action(
                        player_id=player_id,
                        action_type=action_type,
                        amount=amount
                    )

                    await websocket.send_json({
                        "type": "action_result",
                        "data": result
                    })

                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Invalid JSON"}
                })
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": str(e)}
                })

    except WebSocketDisconnect:
        print(f"[Bot WS] Player {player_id} disconnected")
    except Exception as e:
        print(f"[Bot WS] Error for player {player_id}: {e}")
    finally:
        await connection_manager.disconnect_player(player_id)