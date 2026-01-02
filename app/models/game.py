# app/models/game.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum
from .cards import Card
from .player import Player, PlayerStatus

class BettingRound(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"

class GamePhase(str, Enum):
    WAITING = "waiting"
    DEALING = "dealing"
    BETTING = "betting"
    SHOWDOWN = "showdown"
    HAND_COMPLETE = "hand_complete"

class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"

class PlayerAction(BaseModel):
    """Action submitted by a player"""
    action_type: ActionType
    amount: Optional[int] = None

class ValidatedAction(BaseModel):
    """Server-validated action result"""
    player_id: str
    action_type: ActionType
    amount: int = 0
    is_valid: bool
    error_message: Optional[str] = None

class PotInfo(BaseModel):
    """Information about a pot (main or side)"""
    amount: int = 0
    eligible_players: List[str] = Field(default_factory=list)

class GameState(BaseModel):
    """Complete game state"""
    game_id: str
    table_id: str
    hand_number: int = 0
    phase: GamePhase = GamePhase.WAITING
    betting_round: BettingRound = BettingRound.PREFLOP
    
    players: Dict[str, Player] = Field(default_factory=dict)
    player_order: List[str] = Field(default_factory=list)  # Seat order
    
    community_cards: List[Card] = Field(default_factory=list)
    pots: List[PotInfo] = Field(default_factory=list)
    
    current_player_id: Optional[str] = None
    dealer_position: int = 0
    
    small_blind: int = 10
    big_blind: int = 20
    current_bet: int = 0      # Current bet to match
    min_raise: int = 0        # Minimum raise amount
    last_raiser_id: Optional[str] = None
    
    action_history: List[Dict] = Field(default_factory=list)
    hand_winners: List[Dict] = Field(default_factory=list)

    def get_active_players(self) -> List[Player]:
        """Get players still in the hand"""
        return [
            self.players[pid] for pid in self.player_order
            if self.players[pid].status in [PlayerStatus.ACTIVE, PlayerStatus.ALL_IN]
        ]

    def get_players_to_act(self) -> List[Player]:
        """Get players who can still act (not folded, not all-in)"""
        return [
            self.players[pid] for pid in self.player_order
            if self.players[pid].status == PlayerStatus.ACTIVE
        ]

    def get_total_pot(self) -> int:
        """Get total chips in all pots"""
        return sum(pot.amount for pot in self.pots)

    def to_public_dict(self) -> dict:
        """Return game state with hidden hole cards"""
        return {
            "game_id": self.game_id,
            "table_id": self.table_id,
            "hand_number": self.hand_number,
            "phase": self.phase.value,
            "betting_round": self.betting_round.value,
            "players": {pid: p.to_public_dict() for pid, p in self.players.items()},
            "player_order": self.player_order,
            "community_cards": [c.to_dict() for c in self.community_cards],
            "pots": [{"amount": p.amount, "eligible_players": p.eligible_players} for p in self.pots],
            "current_player_id": self.current_player_id,
            "dealer_position": self.dealer_position,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "current_bet": self.current_bet,
            "min_raise": self.min_raise,
            "total_pot": self.get_total_pot(),
            "action_history": self.action_history[-10:],  # Last 10 actions
            "hand_winners": self.hand_winners
        }

    def to_player_dict(self, player_id: str) -> dict:
        """Return game state for a specific player (shows their cards)"""
        data = self.to_public_dict()
        if player_id in self.players:
            data["players"][player_id] = self.players[player_id].to_private_dict()
            data["your_hole_cards"] = [c.to_dict() for c in self.players[player_id].hole_cards]
        return data