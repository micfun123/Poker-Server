# app/config.py
from pydantic import BaseModel
from typing import Optional
import os

class TournamentSettings(BaseModel):
    """Tournament configuration settings"""
    name: str = "University Poker Championship"
    starting_chips: int = 1000
    small_blind: int = 10
    big_blind: int = 20
    min_players: int = 2
    max_players_per_table: int = 6
    action_timeout_seconds: int = 30
    blind_increase_interval_hands: int = 20
    blind_increase_multiplier: float = 1.5

class ServerSettings(BaseModel):
    """Server configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")

# Global settings instances
tournament_settings = TournamentSettings()
server_settings = ServerSettings()