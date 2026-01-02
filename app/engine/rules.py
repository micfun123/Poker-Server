from typing import Optional, Tuple, List
from ..models.game import GameState, ActionType, GamePhase, PlayerAction
from ..models.player import Player, PlayerStatus

class RulesEngine:
    """
    Enforces poker rules and validates player actions.
    """

    @staticmethod
    def validate_action(
        game_state: GameState,
        player_id: str,
        action: PlayerAction
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Validate a player's action.
        Returns (is_valid, error_message, actual_amount)
        """
        # Check if it's this player's turn
        if game_state.current_player_id != player_id:
            return False, f"Not your turn. Current player: {game_state.current_player_id}", None

        # Check if game is in betting phase
        if game_state.phase != GamePhase.BETTING:
            return False, f"Cannot act during {game_state.phase.value} phase", None

        # Get player
        player = game_state.players.get(player_id)
        if not player:
            return False, "Player not found", None

        # Check player status
        if player.status not in [PlayerStatus.ACTIVE]:
            return False, f"Player cannot act with status: {player.status.value}", None

        # Validate specific action
        action_type = action.action_type
        amount = action.amount or 0

        if action_type == ActionType.FOLD:
            return True, "", 0

        elif action_type == ActionType.CHECK:
            return RulesEngine._validate_check(game_state, player)

        elif action_type == ActionType.CALL:
            return RulesEngine._validate_call(game_state, player)

        elif action_type == ActionType.BET:
            return RulesEngine._validate_bet(game_state, player, amount)

        elif action_type == ActionType.RAISE:
            return RulesEngine._validate_raise(game_state, player, amount)

        elif action_type == ActionType.ALL_IN:
            return True, "", player.chips

        return False, f"Unknown action type: {action_type}", None

    @staticmethod
    def _validate_check(game_state: GameState, player: Player) -> Tuple[bool, str, Optional[int]]:
        """Validate a check action"""
        # Can only check if no bet to call
        amount_to_call = game_state.current_bet - player.current_bet
        if amount_to_call > 0:
            return False, f"Cannot check. Must call {amount_to_call} or fold", None
        return True, "", 0

    @staticmethod
    def _validate_call(game_state: GameState, player: Player) -> Tuple[bool, str, Optional[int]]:
        """Validate a call action"""
        amount_to_call = game_state.current_bet - player.current_bet
        
        if amount_to_call <= 0:
            return False, "Nothing to call. Use check instead", None
        
        # If player doesn't have enough, they go all-in
        actual_amount = min(amount_to_call, player.chips)
        return True, "", actual_amount

    @staticmethod
    def _validate_bet(game_state: GameState, player: Player, amount: int) -> Tuple[bool, str, Optional[int]]:
        """Validate a bet action (first bet in a round)"""
        # Can only bet if no one has bet yet
        if game_state.current_bet > 0:
            return False, "Cannot bet when there's an existing bet. Use raise instead", None

        # Minimum bet is the big blind
        min_bet = game_state.big_blind
        
        if amount < min_bet:
            return False, f"Minimum bet is {min_bet}", None

        if amount > player.chips:
            return False, f"Cannot bet {amount}. You only have {player.chips} chips", None

        return True, "", amount

    @staticmethod
    def _validate_raise(game_state: GameState, player: Player, amount: int) -> Tuple[bool, str, Optional[int]]:
        """
        Validate a raise action.
        'amount' is the TOTAL bet the player wants to make (not the raise increment)
        """
        if game_state.current_bet == 0:
            return False, "Cannot raise when there's no bet. Use bet instead", None

        amount_to_call = game_state.current_bet - player.current_bet
        
        # The raise amount (increment above current bet)
        raise_increment = amount - game_state.current_bet
        
        # Minimum raise is the larger of: big blind or the last raise amount
        min_raise_increment = game_state.min_raise
        
        if raise_increment < min_raise_increment:
            min_total = game_state.current_bet + min_raise_increment
            # Allow all-in for less if player doesn't have enough
            if amount >= player.chips:
                return True, "", player.chips  # All-in
            return False, f"Minimum raise to {min_total} (raise by at least {min_raise_increment})", None

        total_needed = amount - player.current_bet  # Amount player needs to add
        
        if total_needed > player.chips:
            return False, f"Cannot raise to {amount}. You only have {player.chips} chips", None

        return True, "", total_needed

    @staticmethod
    def get_valid_actions(game_state: GameState, player_id: str) -> List[dict]:
        """
        Get list of valid actions for a player.
        Returns list of {action_type, min_amount, max_amount}
        """
        player = game_state.players.get(player_id)
        if not player or player.status != PlayerStatus.ACTIVE:
            return []

        if game_state.current_player_id != player_id:
            return []

        valid_actions = []
        amount_to_call = game_state.current_bet - player.current_bet

        # Fold is always valid
        valid_actions.append({
            "action_type": ActionType.FOLD.value,
            "min_amount": 0,
            "max_amount": 0
        })

        if amount_to_call == 0:
            # Can check
            valid_actions.append({
                "action_type": ActionType.CHECK.value,
                "min_amount": 0,
                "max_amount": 0
            })
            
            # Can bet (if has chips)
            if player.chips > 0:
                min_bet = min(game_state.big_blind, player.chips)
                valid_actions.append({
                    "action_type": ActionType.BET.value,
                    "min_amount": min_bet,
                    "max_amount": player.chips
                })
        else:
            # Can call
            call_amount = min(amount_to_call, player.chips)
            valid_actions.append({
                "action_type": ActionType.CALL.value,
                "min_amount": call_amount,
                "max_amount": call_amount
            })

            # Can raise (if has chips beyond call amount)
            if player.chips > amount_to_call:
                min_raise_to = game_state.current_bet + game_state.min_raise
                min_raise_amount = min_raise_to - player.current_bet
                max_raise_amount = player.chips
                
                if max_raise_amount >= min_raise_amount:
                    valid_actions.append({
                        "action_type": ActionType.RAISE.value,
                        "min_amount": min(min_raise_to, player.chips + player.current_bet),
                        "max_amount": player.chips + player.current_bet
                    })

        # All-in is always valid if player has chips
        if player.chips > 0:
            valid_actions.append({
                "action_type": ActionType.ALL_IN.value,
                "min_amount": player.chips,
                "max_amount": player.chips
            })

        return valid_actions

    @staticmethod
    def is_betting_round_complete(game_state: GameState) -> bool:
        """Check if the current betting round is complete"""
        active_players = game_state.get_players_to_act()
        
        # If only one player left (others folded/all-in), round is complete
        if len(active_players) <= 1:
            return True

        # Check if all active players have acted and matched the current bet
        for player in active_players:
            # Player hasn't acted yet
            if not player.has_acted:
                return False
            
            # Player hasn't matched current bet (and isn't all-in)
            if player.current_bet < game_state.current_bet and player.status == PlayerStatus.ACTIVE:
                return False

        # If there was a raise, check if it came back to the raiser
        if game_state.last_raiser_id:
            # Everyone has acted since the last raise
            raiser = game_state.players.get(game_state.last_raiser_id)
            if raiser and raiser.has_acted:
                return True

        return True

    @staticmethod
    def is_hand_complete(game_state: GameState) -> bool:
        """Check if the hand is complete (showdown or everyone folded)"""
        active_players = [
            p for p in game_state.players.values()
            if p.status in [PlayerStatus.ACTIVE, PlayerStatus.ALL_IN]
        ]
        
        # Only one player left
        if len(active_players) <= 1:
            return True

        # River betting is complete
        if game_state.betting_round == game_state.betting_round.RIVER:
            if RulesEngine.is_betting_round_complete(game_state):
                return True

        return False