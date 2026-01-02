import uuid
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from ..models.cards import Deck, Card
from ..models.player import Player, PlayerStatus
from ..models.game import (
    GameState, GamePhase, BettingRound, ActionType,
    PlayerAction, ValidatedAction, PotInfo
)
from .rules import RulesEngine
from .hand_evaluator import HandEvaluator

class PokerGameEngine:
    """
    Core poker game engine for Texas Hold'em.
    Manages a single table/game.
    """

    def __init__(self, table_id: str, small_blind: int = 10, big_blind: int = 20):
        self.game_state = GameState(
            game_id=str(uuid.uuid4()),
            table_id=table_id,
            small_blind=small_blind,
            big_blind=big_blind,
            min_raise=big_blind
        )
        self.deck = Deck()
        self._action_callbacks: List[callable] = []

    def add_player(self, player_id: str, username: str, chips: int, seat: int = -1) -> bool:
        """Add a player to the table"""
        if player_id in self.game_state.players:
            return False

        if seat == -1:
            seat = len(self.game_state.players)

        player = Player(
            player_id=player_id,
            username=username,
            chips=chips,
            seat_position=seat,
            status=PlayerStatus.WAITING
        )
        
        self.game_state.players[player_id] = player
        self.game_state.player_order.append(player_id)
        self.game_state.player_order.sort(
            key=lambda pid: self.game_state.players[pid].seat_position
        )
        
        return True

    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the table"""
        if player_id not in self.game_state.players:
            return False
        
        del self.game_state.players[player_id]
        self.game_state.player_order.remove(player_id)
        return True

    def start_hand(self) -> bool:
        """Start a new hand"""
        # Need at least 2 players with chips
        eligible_players = [
            p for p in self.game_state.players.values()
            if p.chips > 0 and p.status != PlayerStatus.DISCONNECTED
        ]
        
        if len(eligible_players) < 2:
            return False

        # Reset game state for new hand
        self.game_state.hand_number += 1
        self.game_state.game_id = str(uuid.uuid4())
        self.game_state.phase = GamePhase.DEALING
        self.game_state.betting_round = BettingRound.PREFLOP
        self.game_state.community_cards = []
        self.game_state.pots = [PotInfo(amount=0, eligible_players=[])]
        self.game_state.current_bet = 0
        self.game_state.min_raise = self.game_state.big_blind
        self.game_state.last_raiser_id = None
        self.game_state.action_history = []
        self.game_state.hand_winners = []

        # Reset players
        for player in self.game_state.players.values():
            player.reset_for_hand()

        # Update player order (remove eliminated players)
        self.game_state.player_order = [
            pid for pid in self.game_state.player_order
            if self.game_state.players[pid].status != PlayerStatus.ELIMINATED
        ]

        # Rotate dealer
        self._rotate_dealer()

        # Reset and deal
        self.deck.reset()
        self._deal_hole_cards()
        self._post_blinds()

        # Set phase to betting
        self.game_state.phase = GamePhase.BETTING
        
        # Set first player to act (after big blind)
        self._set_next_player()

        return True

    def _rotate_dealer(self):
        """Move dealer button to next player"""
        active_players = [
            pid for pid in self.game_state.player_order
            if self.game_state.players[pid].status == PlayerStatus.ACTIVE
        ]
        
        if not active_players:
            return

        num_players = len(active_players)
        self.game_state.dealer_position = (self.game_state.dealer_position + 1) % num_players
        
        dealer_pid = active_players[self.game_state.dealer_position]
        self.game_state.players[dealer_pid].is_dealer = True

        # Set blinds
        if num_players == 2:
            # Heads up: dealer is small blind
            sb_idx = self.game_state.dealer_position
            bb_idx = (self.game_state.dealer_position + 1) % num_players
        else:
            sb_idx = (self.game_state.dealer_position + 1) % num_players
            bb_idx = (self.game_state.dealer_position + 2) % num_players

        self.game_state.players[active_players[sb_idx]].is_small_blind = True
        self.game_state.players[active_players[bb_idx]].is_big_blind = True

    def _deal_hole_cards(self):
        """Deal 2 hole cards to each active player"""
        active_pids = [
            pid for pid in self.game_state.player_order
            if self.game_state.players[pid].status == PlayerStatus.ACTIVE
        ]
        
        # Deal one card at a time, twice around
        for _ in range(2):
            for pid in active_pids:
                card = self.deck.deal_one()
                self.game_state.players[pid].hole_cards.append(card)

    def _post_blinds(self):
        """Post small and big blinds"""
        for player in self.game_state.players.values():
            if player.is_small_blind:
                blind_amount = min(self.game_state.small_blind, player.chips)
                player.chips -= blind_amount
                player.current_bet = blind_amount
                player.total_bet = blind_amount
                self.game_state.pots[0].amount += blind_amount
                self._add_action_history(player.player_id, "small_blind", blind_amount)
                
            elif player.is_big_blind:
                blind_amount = min(self.game_state.big_blind, player.chips)
                player.chips -= blind_amount
                player.current_bet = blind_amount
                player.total_bet = blind_amount
                self.game_state.pots[0].amount += blind_amount
                self.game_state.current_bet = blind_amount
                self._add_action_history(player.player_id, "big_blind", blind_amount)

    def _set_next_player(self):
        """Set the next player to act"""
        players_to_act = self.game_state.get_players_to_act()
        
        if not players_to_act:
            self.game_state.current_player_id = None
            return

        # Find current player index
        current_order = [p.player_id for p in players_to_act]
        
        if self.game_state.current_player_id in current_order:
            current_idx = current_order.index(self.game_state.current_player_id)
            next_idx = (current_idx + 1) % len(current_order)
        else:
            # Start from after the big blind position
            next_idx = 0
            for i, pid in enumerate(current_order):
                if self.game_state.players[pid].is_big_blind:
                    next_idx = (i + 1) % len(current_order)
                    break

        self.game_state.current_player_id = current_order[next_idx]

    def process_action(self, player_id: str, action: PlayerAction) -> ValidatedAction:
        """
        Process a player's action with full validation.
        Returns the validated action result.
        """
        # Validate the action
        is_valid, error_msg, actual_amount = RulesEngine.validate_action(
            self.game_state, player_id, action
        )

        if not is_valid:
            return ValidatedAction(
                player_id=player_id,
                action_type=action.action_type,
                amount=0,
                is_valid=False,
                error_message=error_msg
            )

        # Apply the action
        player = self.game_state.players[player_id]
        action_type = action.action_type

        if action_type == ActionType.FOLD:
            player.status = PlayerStatus.FOLDED
            player.last_action = "fold"

        elif action_type == ActionType.CHECK:
            player.last_action = "check"

        elif action_type == ActionType.CALL:
            player.chips -= actual_amount
            player.current_bet += actual_amount
            player.total_bet += actual_amount
            self.game_state.pots[0].amount += actual_amount
            player.last_action = f"call {actual_amount}"
            
            # Check if player is now all-in
            if player.chips == 0:
                player.status = PlayerStatus.ALL_IN

        elif action_type == ActionType.BET:
            player.chips -= actual_amount
            player.current_bet = actual_amount
            player.total_bet += actual_amount
            self.game_state.pots[0].amount += actual_amount
            self.game_state.current_bet = actual_amount
            self.game_state.min_raise = actual_amount
            self.game_state.last_raiser_id = player_id
            player.last_action = f"bet {actual_amount}"
            
            # Reset has_acted for other players
            for p in self.game_state.get_players_to_act():
                if p.player_id != player_id:
                    p.has_acted = False

            if player.chips == 0:
                player.status = PlayerStatus.ALL_IN

        elif action_type == ActionType.RAISE:
            # actual_amount is the amount to add (already validated)
            new_total_bet = player.current_bet + actual_amount
            raise_increment = new_total_bet - self.game_state.current_bet
            
            player.chips -= actual_amount
            player.current_bet = new_total_bet
            player.total_bet += actual_amount
            self.game_state.pots[0].amount += actual_amount
            self.game_state.min_raise = max(self.game_state.min_raise, raise_increment)
            self.game_state.current_bet = new_total_bet
            self.game_state.last_raiser_id = player_id
            player.last_action = f"raise to {new_total_bet}"

            # Reset has_acted for other players
            for p in self.game_state.get_players_to_act():
                if p.player_id != player_id:
                    p.has_acted = False

            if player.chips == 0:
                player.status = PlayerStatus.ALL_IN

        elif action_type == ActionType.ALL_IN:
            all_in_amount = player.chips
            new_total_bet = player.current_bet + all_in_amount
            
            player.chips = 0
            player.current_bet = new_total_bet
            player.total_bet += all_in_amount
            self.game_state.pots[0].amount += all_in_amount
            player.status = PlayerStatus.ALL_IN
            player.last_action = f"all-in {all_in_amount}"

            # If this is a raise, update current bet and reset has_acted
            if new_total_bet > self.game_state.current_bet:
                raise_increment = new_total_bet - self.game_state.current_bet
                self.game_state.min_raise = max(self.game_state.min_raise, raise_increment)
                self.game_state.current_bet = new_total_bet
                self.game_state.last_raiser_id = player_id
                
                for p in self.game_state.get_players_to_act():
                    if p.player_id != player_id:
                        p.has_acted = False

            actual_amount = all_in_amount

        # Mark player as having acted
        player.has_acted = True
        
        # Add to action history
        self._add_action_history(player_id, action_type.value, actual_amount)

        # Check if betting round is complete
        self._check_betting_round_complete()

        return ValidatedAction(
            player_id=player_id,
            action_type=action_type,
            amount=actual_amount,
            is_valid=True,
            error_message=None
        )

    def _add_action_history(self, player_id: str, action: str, amount: int):
        """Add action to history"""
        self.game_state.action_history.append({
            "player_id": player_id,
            "username": self.game_state.players[player_id].username,
            "action": action,
            "amount": amount,
            "round": self.game_state.betting_round.value,
            "timestamp": datetime.now().isoformat()
        })

    def _check_betting_round_complete(self):
        """Check if betting round is complete and advance if so"""
        if not RulesEngine.is_betting_round_complete(self.game_state):
            self._set_next_player()
            return

        # Check if hand should end early (everyone folded except one)
        active_players = self.game_state.get_active_players()
        if len(active_players) <= 1:
            self._end_hand()
            return

        # Advance to next round
        self._advance_betting_round()

    def _advance_betting_round(self):
        """Advance to the next betting round"""
        # Reset for new betting round
        for player in self.game_state.players.values():
            player.reset_for_betting_round()
        
        self.game_state.current_bet = 0
        self.game_state.min_raise = self.game_state.big_blind
        self.game_state.last_raiser_id = None

        current_round = self.game_state.betting_round

        if current_round == BettingRound.PREFLOP:
            self.game_state.betting_round = BettingRound.FLOP
            # Deal 3 community cards
            self.game_state.community_cards.extend(self.deck.deal(3))
            
        elif current_round == BettingRound.FLOP:
            self.game_state.betting_round = BettingRound.TURN
            # Deal 1 community card
            self.game_state.community_cards.extend(self.deck.deal(1))
            
        elif current_round == BettingRound.TURN:
            self.game_state.betting_round = BettingRound.RIVER
            # Deal 1 community card
            self.game_state.community_cards.extend(self.deck.deal(1))
            
        elif current_round == BettingRound.RIVER:
            # Go to showdown
            self._end_hand()
            return

        # Set first player to act (after dealer)
        self._set_first_to_act()

        # If only one player can act (others all-in), continue to next round
        players_to_act = self.game_state.get_players_to_act()
        if len(players_to_act) <= 1:
            self._advance_betting_round()

    def _set_first_to_act(self):
        """Set the first player to act after flop (left of dealer)"""
        active_players = self.game_state.get_players_to_act()
        if not active_players:
            self.game_state.current_player_id = None
            return

        # Find player left of dealer
        player_order = [p.player_id for p in active_players]
        dealer_pos = self.game_state.dealer_position % len(player_order)
        first_pos = (dealer_pos + 1) % len(player_order)
        
        self.game_state.current_player_id = player_order[first_pos]

    def _end_hand(self):
        """End the hand and determine winner(s)"""
        self.game_state.phase = GamePhase.SHOWDOWN
        self.game_state.betting_round = BettingRound.SHOWDOWN
        self.game_state.current_player_id = None

        active_players = self.game_state.get_active_players()

        if len(active_players) == 1:
            # Everyone else folded
            winner = active_players[0]
            winner.chips += self.game_state.get_total_pot()
            self.game_state.hand_winners = [{
                "player_id": winner.player_id,
                "username": winner.username,
                "amount": self.game_state.get_total_pot(),
                "hand": "Everyone else folded"
            }]
        else:
            # Showdown - evaluate hands
            self._evaluate_showdown(active_players)

        # Mark pots as empty
        for pot in self.game_state.pots:
            pot.amount = 0

        self.game_state.phase = GamePhase.HAND_COMPLETE

    def _evaluate_showdown(self, players: List[Player]):
        """Evaluate hands at showdown and distribute pot"""
        hands = [
            (p.player_id, p.hole_cards, self.game_state.community_cards)
            for p in players
        ]

        winners = HandEvaluator.determine_winners(hands)
        total_pot = self.game_state.get_total_pot()
        
        if not winners:
            return

        # Split pot among winners
        share = total_pot // len(winners)
        remainder = total_pot % len(winners)

        self.game_state.hand_winners = []
        
        for i, (pid, rank, hand_name, best_cards) in enumerate(winners):
            player = self.game_state.players[pid]
            amount = share + (1 if i < remainder else 0)
            player.chips += amount
            
            self.game_state.hand_winners.append({
                "player_id": pid,
                "username": player.username,
                "amount": amount,
                "hand": hand_name,
                "cards": [str(c) for c in best_cards]
            })

    def get_valid_actions(self, player_id: str) -> List[dict]:
        """Get valid actions for a player"""
        return RulesEngine.get_valid_actions(self.game_state, player_id)

    def get_state_for_player(self, player_id: str) -> dict:
        """Get game state with private info for specific player"""
        state = self.game_state.to_player_dict(player_id)
        state["valid_actions"] = self.get_valid_actions(player_id)
        return state

    def get_public_state(self) -> dict:
        """Get public game state (for viewers)"""
        return self.game_state.to_public_dict()