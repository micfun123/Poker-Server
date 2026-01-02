from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from .game import ActionType

class RegisterBotRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    team_name: Optional[str] = None

class RegisterBotResponse(BaseModel):
    success: bool
    player_id: Optional[str] = None
    api_key: Optional[str] = None
    message: str
    websocket_url: Optional[str] = None

class BotActionRequest(BaseModel):
    action_type: ActionType
    amount: Optional[int] = None

class BotActionResponse(BaseModel):
    success: bool
    message: str
    action_accepted: Optional[Dict] = None
    game_state: Optional[Dict] = None

class TournamentStatusResponse(BaseModel):
    tournament_id: str
    name: str
    status: str
    registered_players: int
    active_tables: int
    config: Dict[str, Any]

class AdminLoginRequest(BaseModel):
    password: str

class AdminCommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None

class WebSocketMessage(BaseModel):
    type: str
    data: Any
    timestamp: Optional[float] = None