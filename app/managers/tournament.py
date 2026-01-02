import asyncio
import uuid
import secrets
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from ..config import tournament_settings, TournamentSettings
from ..models.player import Player, PlayerStatus
from ..models.game import ActionType, PlayerAction, GamePhase
from ..engine.game_engine import PokerGameEngine
from .connection import connection_manager

class TournamentStatus(str, Enum):
    REGISTRATION = "registration"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"

class TournamentManager:
    """
    Manages the overall tournament, including player registration,
    table management, and game coordination.
    """

    def __init__(self, config: TournamentSettings = tournament_settings):
        self.tournament_id = str(uuid.uuid4())
        self.config = config
        self.status = TournamentStatus.REGISTRATION
        
        # Player management
        self.registered_players: Dict[str, dict] = {}  # player_id -> {username, api_key, ...}
        self.api_keys: Dict[str, str] = {}  # api_key -> player_id
        
        # Table/Game management
        self.tables: Dict[str, PokerGameEngine] = {}  # table_id -> game engine
        self.player_table_map: Dict[str, str] = {}  # player_id -> table_id
        
        # Tournament stats
        self.start_time: Optional[datetime] = None
        self.hands_played: int = 0
        self.eliminations: List[dict] = []
        
        # Blind level tracking
        self.current_blind_level: int = 1
        self.small_blind: int = config.small_blind
        self.big_blind: int = config.big_blind

        # Action timeout task
        self._timeout_tasks: Dict[str, asyncio.Task] = {}

        print(f"[TournamentManager] Tournament '{config.name}' created with ID: {self.tournament_id}")

    def register_player(self, username: str, team_name: Optional[str] = None) -> dict:
        """Register a new player/bot for the tournament"""
        if self.status != TournamentStatus.REGISTRATION:
            return {
                "success": False,
                "message": f"Registration closed. Tournament status: {self.status.value}"
            }

        # Check for duplicate username
        for player_info in self.registered_players.values():
            if player_info["username"].lower() == username.lower():
                return {
                    "success": False,
                    "message": f"Username '{username}' is already taken"
                }

        player_id = f"player_{len(self.registered_players) + 1}_{secrets.token_hex(4)}"
        api_key = secrets.token_urlsafe(32)

        self.registered_players[player_id] = {
            "username": username,
            "team_name": team_name,
            "api_key": api_key,
            "registered_at": datetime.now().isoformat(),
            "status": "registered"
        }
        self.api_keys[api_key] = player_id

        print(f"[TournamentManager] Player '{username}' registered with ID: {player_id}")

        return {
            "success": True,
            "player_id": player_id,
            "api_key": api_key,
            "message": f"Successfully registered as '{username}'"
        }

    def authenticate_player(self, api_key: str) -> Optional[str]:
        """Authenticate a player by API key, return player_id if valid"""
        return self.api_keys.get(api_key)

    def get_player_by_id(self, player_id: str) -> Optional[dict]:
        """Get player info by player_id"""
        return self.registered_players.get(player_id)

    def get_player_username(self, player_id: str) -> str:
        """Get username for a player_id"""
        player_info = self.registered_players.get(player_id)
        return player_info["username"] if player_info else "Unknown"

    async def start_tournament(self) -> dict:
        """Start the tournament"""
        if self.status != TournamentStatus.REGISTRATION:
            return {
                "success": False,
                "message": f"Cannot start tournament. Current status: {self.status.value}"
            }

        num_players = len(self.registered_players)
        if num_players < self.config.min_players:
            return {
                "success": False,
                "message": f"Not enough players. Need at least {self.config.min_players}, have {num_players}"
            }

        self.status = TournamentStatus.RUNNING
        self.start_time = datetime.now()

        # Create tables and assign players
        await self._create_tables()

        # Start games on all tables
        for table_id, game_engine in self.tables.items():
            if game_engine.start_hand():
                await self._broadcast_table_state(table_id)
                # Start action timeout for current player
                self._start_action_timeout(table_id)

        print(f"[TournamentManager] Tournament started with {num_players} players across {len(self.tables)} tables")

        return {
            "success": True,
            "message": f"Tournament started with {num_players} players",
            "tables": len(self.tables)
        }

    async def _create_tables(self):
        """Create tables and distribute players"""
        player_ids = list(self.registered_players.keys())
        
        # Shuffle players for random seating
        import random
        random.shuffle(player_ids)

        # Calculate number of tables needed
        max_per_table = self.config.max_players_per_table
        num_tables = (len(player_ids) + max_per_table - 1) // max_per_table

        # Distribute players evenly across tables
        table_assignments: List[List[str]] = [[] for _ in range(num_tables)]
        for i, player_id in enumerate(player_ids):
            table_idx = i % num_tables
            table_assignments[table_idx].append(player_id)

        # Create game engines for each table
        for table_idx, table_players in enumerate(table_assignments):
            if len(table_players) < 2:
                continue  # Skip tables with less than 2 players

            table_id = f"table_{table_idx + 1}"
            game_engine = PokerGameEngine(
                table_id=table_id,
                small_blind=self.small_blind,
                big_blind=self.big_blind
            )

            # Add players to the table
            for seat, player_id in enumerate(table_players):
                player_info = self.registered_players[player_id]
                game_engine.add_player(
                    player_id=player_id,
                    username=player_info["username"],
                    chips=self.config.starting_chips,
                    seat=seat
                )
                self.player_table_map[player_id] = table_id

            self.tables[table_id] = game_engine
            print(f"[TournamentManager] Created {table_id} with players: {[self.get_player_username(p) for p in table_players]}")

    async def process_player_action(
        self,
        player_id: str,
        action_type: ActionType,
        amount: Optional[int] = None
    ) -> dict:
        """Process an action from a player"""
        # Check tournament is running
        if self.status != TournamentStatus.RUNNING:
            return {
                "success": False,
                "message": f"Tournament is not running. Status: {self.status.value}"
            }

        # Find player's table
        table_id = self.player_table_map.get(player_id)
        if not table_id:
            return {
                "success": False,
                "message": "Player not assigned to any table"
            }

        game_engine = self.tables.get(table_id)
        if not game_engine:
            return {
                "success": False,
                "message": "Table not found"
            }

        # Cancel existing timeout
        self._cancel_action_timeout(table_id)

        # Create and process the action
        action = PlayerAction(action_type=action_type, amount=amount)
        result = game_engine.process_action(player_id, action)

        if not result.is_valid:
            # Restart timeout since action was invalid
            self._start_action_timeout(table_id)
            return {
                "success": False,
                "message": result.error_message,
                "valid_actions": game_engine.get_valid_actions(player_id)
            }

        # Broadcast updated state
        await self._broadcast_table_state(table_id)

        # Check if hand is complete
        if game_engine.game_state.phase == GamePhase.HAND_COMPLETE:
            self.hands_played += 1
            await self._handle_hand_complete(table_id)
        else:
            # Start timeout for next player
            self._start_action_timeout(table_id)

        return {
            "success": True,
            "message": f"Action accepted: {action_type.value}",
            "action": {
                "type": result.action_type.value,
                "amount": result.amount
            }
        }

    async def _handle_hand_complete(self, table_id: str):
        """Handle end of hand - check eliminations, start new hand"""
        game_engine = self.tables.get(table_id)
        if not game_engine:
            return

        # Check for eliminated players
        eliminated = []
        for player_id, player in game_engine.game_state.players.items():
            if player.chips <= 0:
                eliminated.append(player_id)
                self.eliminations.append({
                    "player_id": player_id,
                    "username": player.username,
                    "position": len(self.registered_players) - len(self.eliminations),
                    "eliminated_at": datetime.now().isoformat(),
                    "table_id": table_id
                })
                print(f"[TournamentManager] Player {player.username} eliminated!")

        # Remove eliminated players from table map
        for player_id in eliminated:
            self.player_table_map.pop(player_id, None)

        # Broadcast elimination notifications
        if eliminated:
            await connection_manager.broadcast_to_viewers({
                "type": "elimination",
                "data": {
                    "eliminated": [self.get_player_username(p) for p in eliminated],
                    "remaining_players": self._get_remaining_player_count()
                }
            })

        # Check for tournament winner
        remaining = self._get_remaining_player_count()
        if remaining <= 1:
            await self._end_tournament()
            return

        # Check if table needs to be closed/merged
        active_at_table = len([
            p for p in game_engine.game_state.players.values()
            if p.chips > 0
        ])

        if active_at_table < 2:
            await self._handle_table_closure(table_id)
            return

        # Check for blind increase
        self._check_blind_increase()

        # Small delay before next hand
        await asyncio.sleep(3)

        # Start next hand
        if game_engine.start_hand():
            await self._broadcast_table_state(table_id)
            self._start_action_timeout(table_id)

    async def _handle_table_closure(self, table_id: str):
        """Handle closing a table and redistributing players"""
        game_engine = self.tables.get(table_id)
        if not game_engine:
            return

        # Get remaining players from this table
        remaining_players = [
            (pid, player.chips)
            for pid, player in game_engine.game_state.players.items()
            if player.chips > 0
        ]

        # Remove the table
        del self.tables[table_id]
        print(f"[TournamentManager] Closed {table_id}")

        # If no other tables, tournament is over
        if not self.tables:
            await self._end_tournament()
            return

        # Redistribute players to other tables
        for player_id, chips in remaining_players:
            # Find table with fewest players
            target_table_id = min(
                self.tables.keys(),
                key=lambda tid: len(self.tables[tid].game_state.players)
            )
            target_engine = self.tables[target_table_id]

            # Add player to new table
            player_info = self.registered_players[player_id]
            target_engine.add_player(
                player_id=player_id,
                username=player_info["username"],
                chips=chips
            )
            self.player_table_map[player_id] = target_table_id
            print(f"[TournamentManager] Moved {player_info['username']} to {target_table_id}")

            # Notify player
            await connection_manager.send_to_player(player_id, {
                "type": "table_change",
                "data": {
                    "new_table_id": target_table_id,
                    "message": "You have been moved to a new table"
                }
            })

    def _check_blind_increase(self):
        """Check if blinds should increase"""
        hands_per_level = self.config.blind_increase_interval_hands
        if hands_per_level <= 0:
            return

        expected_level = (self.hands_played // hands_per_level) + 1
        
        if expected_level > self.current_blind_level:
            self.current_blind_level = expected_level
            multiplier = self.config.blind_increase_multiplier ** (self.current_blind_level - 1)
            
            self.small_blind = int(self.config.small_blind * multiplier)
            self.big_blind = int(self.config.big_blind * multiplier)

            # Update all tables
            for game_engine in self.tables.values():
                game_engine.game_state.small_blind = self.small_blind
                game_engine.game_state.big_blind = self.big_blind

            print(f"[TournamentManager] Blinds increased to {self.small_blind}/{self.big_blind}")

    async def _end_tournament(self):
        """End the tournament and determine final standings"""
        self.status = TournamentStatus.FINISHED

        # Determine winner
        winner = None
        for table_id, game_engine in self.tables.items():
            for pid, player in game_engine.game_state.players.items():
                if player.chips > 0:
                    winner = {
                        "player_id": pid,
                        "username": player.username,
                        "chips": player.chips
                    }
                    break

        # Build final standings
        standings = []
        if winner:
            standings.append({
                "position": 1,
                "player_id": winner["player_id"],
                "username": winner["username"],
                "chips": winner["chips"]
            })

        # Add eliminated players in reverse order
        for i, elim in enumerate(reversed(self.eliminations)):
            standings.append({
                "position": i + 2,
                "player_id": elim["player_id"],
                "username": elim["username"],
                "chips": 0
            })

        result = {
            "type": "tournament_complete",
            "data": {
                "winner": winner,
                "standings": standings,
                "total_hands": self.hands_played,
                "duration_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            }
        }

        # Broadcast to everyone
        await connection_manager.broadcast_to_viewers(result)
        await connection_manager.broadcast_to_admins(result)
        for player_id in self.registered_players:
            await connection_manager.send_to_player(player_id, result)

        print(f"[TournamentManager] Tournament complete! Winner: {winner['username'] if winner else 'None'}")

    async def _broadcast_table_state(self, table_id: str):
        """Broadcast game state to all relevant parties"""
        game_engine = self.tables.get(table_id)
        if not game_engine:
            return

        player_ids = list(game_engine.game_state.players.keys())
        await connection_manager.broadcast_game_state(game_engine, player_ids)

    def _start_action_timeout(self, table_id: str):
        """Start a timeout task for the current player's action"""
        game_engine = self.tables.get(table_id)
        if not game_engine:
            return

        current_player_id = game_engine.game_state.current_player_id
        if not current_player_id:
            return

        # Cancel any existing timeout
        self._cancel_action_timeout(table_id)

        # Create new timeout task
        async def timeout_handler():
            try:
                await asyncio.sleep(self.config.action_timeout_seconds)
                # Auto-fold on timeout
                print(f"[TournamentManager] Player {current_player_id} timed out, auto-folding")
                await self.process_player_action(current_player_id, ActionType.FOLD)
            except asyncio.CancelledError:
                pass

        self._timeout_tasks[table_id] = asyncio.create_task(timeout_handler())

    def _cancel_action_timeout(self, table_id: str):
        """Cancel the action timeout for a table"""
        if table_id in self._timeout_tasks:
            self._timeout_tasks[table_id].cancel()
            del self._timeout_tasks[table_id]

    def _get_remaining_player_count(self) -> int:
        """Get count of players still in tournament"""
        remaining = 0
        for game_engine in self.tables.values():
            for player in game_engine.game_state.players.values():
                if player.chips > 0:
                    remaining += 1
        return remaining

    def pause_tournament(self) -> dict:
        """Pause the tournament"""
        if self.status != TournamentStatus.RUNNING:
            return {"success": False, "message": "Tournament is not running"}

        self.status = TournamentStatus.PAUSED
        
        # Cancel all timeouts
        for table_id in list(self._timeout_tasks.keys()):
            self._cancel_action_timeout(table_id)

        return {"success": True, "message": "Tournament paused"}

    async def resume_tournament(self) -> dict:
        """Resume a paused tournament"""
        if self.status != TournamentStatus.PAUSED:
            return {"success": False, "message": "Tournament is not paused"}

        self.status = TournamentStatus.RUNNING

        # Restart timeouts for current players
        for table_id in self.tables:
            self._start_action_timeout(table_id)

        return {"success": True, "message": "Tournament resumed"}

    def get_tournament_status(self) -> dict:
        """Get current tournament status"""
        return {
            "tournament_id": self.tournament_id,
            "name": self.config.name,
            "status": self.status.value,
            "registered_players": len(self.registered_players),
            "remaining_players": self._get_remaining_player_count() if self.status == TournamentStatus.RUNNING else len(self.registered_players),
            "active_tables": len(self.tables),
            "hands_played": self.hands_played,
            "current_blinds": {
                "small": self.small_blind,
                "big": self.big_blind,
                "level": self.current_blind_level
            },
            "config": {
                "starting_chips": self.config.starting_chips,
                "min_players": self.config.min_players,
                "max_players_per_table": self.config.max_players_per_table,
                "action_timeout_seconds": self.config.action_timeout_seconds
            },
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "eliminations": self.eliminations[-10:]  # Last 10 eliminations
        }

    def get_player_list(self) -> List[dict]:
        """Get list of all registered players"""
        players = []
        for player_id, info in self.registered_players.items():
            player_data = {
                "player_id": player_id,
                "username": info["username"],
                "team_name": info.get("team_name"),
                "registered_at": info["registered_at"],
                "connected": connection_manager.is_player_connected(player_id)
            }

            # Add chip count if tournament is running
            if self.status == TournamentStatus.RUNNING:
                table_id = self.player_table_map.get(player_id)
                if table_id and table_id in self.tables:
                    game_engine = self.tables[table_id]
                    player = game_engine.game_state.players.get(player_id)
                    if player:
                        player_data["chips"] = player.chips
                        player_data["table_id"] = table_id
                        player_data["status"] = player.status.value

            players.append(player_data)

        return players

    def get_table_states(self) -> List[dict]:
        """Get states of all active tables"""
        table_states = []
        for table_id, game_engine in self.tables.items():
            state = game_engine.get_public_state()
            state["table_id"] = table_id
            table_states.append(state)
        return table_states

    def get_player_game_state(self, player_id: str) -> Optional[dict]:
        """Get game state for a specific player"""
        table_id = self.player_table_map.get(player_id)
        if not table_id:
            return None

        game_engine = self.tables.get(table_id)
        if not game_engine:
            return None

        return game_engine.get_state_for_player(player_id)

    async def kick_player(self, player_id: str, reason: str = "Kicked by admin") -> dict:
        """Kick a player from the tournament"""
        if player_id not in self.registered_players:
            return {"success": False, "message": "Player not found"}

        username = self.get_player_username(player_id)

        # Notify the player
        await connection_manager.send_to_player(player_id, {
            "type": "kicked",
            "data": {"reason": reason}
        })

        # Remove from table if in game
        table_id = self.player_table_map.get(player_id)
        if table_id and table_id in self.tables:
            game_engine = self.tables[table_id]
            if player_id in game_engine.game_state.players:
                player = game_engine.game_state.players[player_id]
                player.status = PlayerStatus.FOLDED
                player.chips = 0

        # Remove from player maps
        self.player_table_map.pop(player_id, None)
        
        # Add to eliminations
        self.eliminations.append({
            "player_id": player_id,
            "username": username,
            "position": len(self.registered_players) - len(self.eliminations),
            "eliminated_at": datetime.now().isoformat(),
            "reason": "kicked"
        })

        return {"success": True, "message": f"Player {username} kicked"}

    def reset_tournament(self) -> dict:
        """Reset the tournament for a new run"""
        # Cancel all timeout tasks
        for table_id in list(self._timeout_tasks.keys()):
            self._cancel_action_timeout(table_id)

        # Clear all state
        self.status = TournamentStatus.REGISTRATION
        self.tables.clear()
        self.player_table_map.clear()
        self.eliminations.clear()
        self.hands_played = 0
        self.start_time = None
        self.current_blind_level = 1
        self.small_blind = self.config.small_blind
        self.big_blind = self.config.big_blind

        # Keep registered players but reset their status
        for player_info in self.registered_players.values():
            player_info["status"] = "registered"

        print(f"[TournamentManager] Tournament reset")
        return {"success": True, "message": "Tournament reset"}


# Global tournament manager instance
tournament_manager = TournamentManager()