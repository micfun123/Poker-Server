from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from .cards import Card

class PlayerStatus(str, Enum):
    WAITING = "waiting"      # Registered but not in game
    ACTIVE = "active"        # Currently in hand
    FOLDED = "folded"        # Folded this hand
    ALL_IN = "all_in"        # All-in this hand
    ELIMINATED = "eliminated" # Out of tournament
    DISCONNECTED = "disconnected"

class Player(BaseModel):
    """Player state model"""
    player_id: str
    username: str
    chips: int = 0
    hole_cards: List[Card] = Field(default_factory=list)
    current_bet: int = 0      # Bet in current betting round
    total_bet: int = 0        # Total bet in current hand
    status: PlayerStatus = PlayerStatus.WAITING
    seat_position: int = -1
    is_dealer: bool = False
    is_small_blind: bool = False
    is_big_blind: bool = False
    has_acted: bool = False   # Has acted this betting round
    last_action: Optional[str] = None

    def reset_for_hand(self):
        """Reset player state for a new hand"""
        self.hole_cards = []
        self.current_bet = 0
        self.total_bet = 0
        self.has_acted = False
        self.last_action = None
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False
        if self.chips > 0 and self.status != PlayerStatus.DISCONNECTED:
            self.status = PlayerStatus.ACTIVE
        elif self.chips <= 0:
            self.status = PlayerStatus.ELIMINATED

    def reset_for_betting_round(self):
        """Reset player state for a new betting round"""
        self.current_bet = 0
        self.has_acted = False

    def to_public_dict(self) -> dict:
        """Return public information (hide hole cards)"""
        return {
            "player_id": self.player_id,
            "username": self.username,
            "chips": self.chips,
            "current_bet": self.current_bet,
            "total_bet": self.total_bet,
            "status": self.status.value,
            "seat_position": self.seat_position,
            "is_dealer": self.is_dealer,
            "is_small_blind": self.is_small_blind,
            "is_big_blind": self.is_big_blind,
            "last_action": self.last_action,
            "hole_cards": []  # Hidden
        }

    def to_private_dict(self) -> dict:
        """Return full information including hole cards"""
        data = self.to_public_dict()
        data["hole_cards"] = [card.to_dict() for card in self.hole_cards]
        return data