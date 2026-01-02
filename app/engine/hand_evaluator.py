from typing import List, Tuple, Optional
from collections import Counter
from itertools import combinations
from ..models.cards import Card, Rank, Suit

class HandRank:
    """Hand ranking constants"""
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

    NAMES = {
        1: "High Card",
        2: "Pair",
        3: "Two Pair",
        4: "Three of a Kind",
        5: "Straight",
        6: "Flush",
        7: "Full House",
        8: "Four of a Kind",
        9: "Straight Flush",
        10: "Royal Flush"
    }

class HandEvaluator:
    """
    Evaluates poker hands and determines winners.
    Returns a tuple of (hand_rank, tiebreaker_values, hand_name)
    """

    @staticmethod
    def evaluate_hand(cards: List[Card]) -> Tuple[int, List[int], str]:
        """
        Evaluate a 5-card poker hand.
        Returns (rank, tiebreakers, hand_name)
        """
        if len(cards) != 5:
            raise ValueError("Hand must contain exactly 5 cards")

        ranks = sorted([c.rank.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]
        rank_counts = Counter(ranks)
        
        is_flush = len(set(suits)) == 1
        is_straight, straight_high = HandEvaluator._check_straight(ranks)

        # Check for each hand type from highest to lowest
        if is_straight and is_flush:
            if straight_high == 14:  # Ace high straight flush
                return (HandRank.ROYAL_FLUSH, [14], HandRank.NAMES[HandRank.ROYAL_FLUSH])
            return (HandRank.STRAIGHT_FLUSH, [straight_high], HandRank.NAMES[HandRank.STRAIGHT_FLUSH])

        if 4 in rank_counts.values():
            quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
            kicker = [r for r, c in rank_counts.items() if c == 1][0]
            return (HandRank.FOUR_OF_A_KIND, [quad_rank, kicker], HandRank.NAMES[HandRank.FOUR_OF_A_KIND])

        if 3 in rank_counts.values() and 2 in rank_counts.values():
            trips_rank = [r for r, c in rank_counts.items() if c == 3][0]
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            return (HandRank.FULL_HOUSE, [trips_rank, pair_rank], HandRank.NAMES[HandRank.FULL_HOUSE])

        if is_flush:
            return (HandRank.FLUSH, ranks, HandRank.NAMES[HandRank.FLUSH])

        if is_straight:
            return (HandRank.STRAIGHT, [straight_high], HandRank.NAMES[HandRank.STRAIGHT])

        if 3 in rank_counts.values():
            trips_rank = [r for r, c in rank_counts.items() if c == 3][0]
            kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
            return (HandRank.THREE_OF_A_KIND, [trips_rank] + kickers, HandRank.NAMES[HandRank.THREE_OF_A_KIND])

        if list(rank_counts.values()).count(2) == 2:
            pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
            kicker = [r for r, c in rank_counts.items() if c == 1][0]
            return (HandRank.TWO_PAIR, pairs + [kicker], HandRank.NAMES[HandRank.TWO_PAIR])

        if 2 in rank_counts.values():
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
            return (HandRank.PAIR, [pair_rank] + kickers, HandRank.NAMES[HandRank.PAIR])

        return (HandRank.HIGH_CARD, ranks, HandRank.NAMES[HandRank.HIGH_CARD])

    @staticmethod
    def _check_straight(ranks: List[int]) -> Tuple[bool, int]:
        """Check if ranks form a straight, return (is_straight, high_card)"""
        unique_ranks = sorted(set(ranks), reverse=True)
        
        if len(unique_ranks) != 5:
            return False, 0

        # Check for regular straight
        if unique_ranks[0] - unique_ranks[4] == 4:
            return True, unique_ranks[0]

        # Check for wheel (A-2-3-4-5)
        if unique_ranks == [14, 5, 4, 3, 2]:
            return True, 5  # 5-high straight

        return False, 0

    @staticmethod
    def get_best_hand(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[List[Card], int, List[int], str]:
        """
        Find the best 5-card hand from 7 cards.
        Returns (best_5_cards, rank, tiebreakers, hand_name)
        """
        all_cards = hole_cards + community_cards
        if len(all_cards) < 5:
            raise ValueError("Need at least 5 cards to evaluate")

        best_hand = None
        best_rank = (0, [], "")

        for combo in combinations(all_cards, 5):
            hand_cards = list(combo)
            rank, tiebreakers, name = HandEvaluator.evaluate_hand(hand_cards)
            
            if (rank, tiebreakers) > (best_rank[0], best_rank[1]):
                best_rank = (rank, tiebreakers, name)
                best_hand = hand_cards

        return best_hand, best_rank[0], best_rank[1], best_rank[2]

    @staticmethod
    def compare_hands(
        hands: List[Tuple[str, List[Card], List[Card]]]  # [(player_id, hole_cards, community_cards), ...]
    ) -> List[Tuple[str, int, List[int], str, List[Card]]]:
        """
        Compare multiple hands and return sorted results (best first).
        Returns [(player_id, rank, tiebreakers, hand_name, best_cards), ...]
        """
        results = []
        for player_id, hole_cards, community_cards in hands:
            best_cards, rank, tiebreakers, name = HandEvaluator.get_best_hand(hole_cards, community_cards)
            results.append((player_id, rank, tiebreakers, name, best_cards))

        # Sort by rank (desc), then tiebreakers (desc)
        results.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return results

    @staticmethod
    def determine_winners(
        hands: List[Tuple[str, List[Card], List[Card]]]
    ) -> List[Tuple[str, int, str, List[Card]]]:
        """
        Determine winner(s), handling ties.
        Returns list of winners [(player_id, rank, hand_name, best_cards), ...]
        """
        if not hands:
            return []

        sorted_hands = HandEvaluator.compare_hands(hands)
        
        if not sorted_hands:
            return []

        # Find all players tied for best hand
        best_rank = sorted_hands[0][1]
        best_tiebreakers = sorted_hands[0][2]

        winners = [
            (pid, rank, name, cards)
            for pid, rank, tiebreakers, name, cards in sorted_hands
            if rank == best_rank and tiebreakers == best_tiebreakers
        ]

        return winners