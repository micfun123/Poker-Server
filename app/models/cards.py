# app/models/cards.py
from enum import IntEnum, Enum
from pydantic import BaseModel
from typing import List
import random

class Suit(str, Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"

class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @classmethod
    def from_char(cls, char: str) -> 'Rank':
        mapping = {
            '2': cls.TWO, '3': cls.THREE, '4': cls.FOUR, '5': cls.FIVE,
            '6': cls.SIX, '7': cls.SEVEN, '8': cls.EIGHT, '9': cls.NINE,
            'T': cls.TEN, 'J': cls.JACK, 'Q': cls.QUEEN, 'K': cls.KING, 'A': cls.ACE
        }
        return mapping[char.upper()]

    def to_char(self) -> str:
        if self.value <= 9:
            return str(self.value)
        return {10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}[self.value]

class Card(BaseModel):
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.to_char()}{self.suit.value}"

    def __hash__(self):
        return hash((self.rank, self.suit))

    def __eq__(self, other):
        if isinstance(other, Card):
            return self.rank == other.rank and self.suit == other.suit
        return False

    def to_dict(self) -> dict:
        return {"rank": self.rank.to_char(), "suit": self.suit.value}

    @classmethod
    def from_string(cls, s: str) -> 'Card':
        return cls(rank=Rank.from_char(s[0]), suit=Suit(s[1].lower()))

class Deck:
    """Standard 52-card deck"""
    
    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck"""
        self.cards = [
            Card(rank=rank, suit=suit)
            for suit in Suit
            for rank in Rank
        ]
        self.shuffle()

    def shuffle(self):
        """Shuffle the deck"""
        random.shuffle(self.cards)

    def deal(self, count: int = 1) -> List[Card]:
        """Deal cards from the deck"""
        if len(self.cards) < count:
            raise ValueError("Not enough cards in deck")
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def deal_one(self) -> Card:
        """Deal a single card"""
        return self.deal(1)[0]

    @property
    def remaining(self) -> int:
        return len(self.cards)