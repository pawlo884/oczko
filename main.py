#!/usr/bin/env python3
"""
Blackjack Probability Calculator
Calculates advice on whether to hit or stand based on probabilities.
"""

import sys
from collections import Counter
from functools import lru_cache

try:
    from flask import Flask, request, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Card ranks and their values
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
VALUES = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}

# Number of decks
NUM_DECKS = 6

# Global state for card counting
history = []
remaining_global = Counter()
for rank in RANKS:
    remaining_global[rank] = 4 * NUM_DECKS

def calculate_hand_value(cards):
    """
    Calculate the best possible hand value for blackjack.
    Aces can be 1 or 11.
    """
    value = 0
    aces = 0
    for card in cards:
        if card == 'A':
            aces += 1
            value += 11
        else:
            value += VALUES[card]

    # Adjust for aces
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1

    return value

def get_remaining_cards(dealer_card, player_cards, remaining_global):
    """
    Calculate remaining cards after removing dealer's visible card and player's cards from global remaining.
    Returns a Counter of remaining ranks.
    """
    remaining = remaining_global.copy()

    # Remove dealer's card
    remaining[dealer_card] -= 1

    # Remove player's cards
    for card in player_cards:
        remaining[card] -= 1

    return remaining

def calculate_bust_probability(current_value, remaining_cards):
    """
    Calculate probability of busting when hitting from current hand value.
    """
    total_remaining = sum(remaining_cards.values())
    if total_remaining == 0:
        return 0.0

    bust_count = 0
    for rank, count in remaining_cards.items():
        new_value = current_value + VALUES[rank]
        if new_value > 21:
            bust_count += count

    return bust_count / total_remaining

@lru_cache(maxsize=None)
def _dealer_probs_recursive(hand_tuple, rem_tuple):
    """
    Recursive helper for dealer probabilities.
    hand_tuple: tuple of cards
    rem_tuple: tuple of (rank, count) sorted
    """
    hand = list(hand_tuple)
    rem_cards = Counter(dict(rem_tuple))
    value = calculate_hand_value(hand)
    if value > 21:
        return (('bust', 1.0),)
    if value >= 17:
        return ((value, 1.0),)
    
    total = sum(rem_cards.values())
    if total == 0:
        return ((value, 1.0),)
    
    probs = Counter()
    for rank, count in rem_cards.items():
        if count == 0:
            continue
        new_hand = hand + [rank]
        new_rem = rem_cards.copy()
        new_rem[rank] -= 1
        new_rem_tuple = tuple(sorted(new_rem.items()))
        sub_probs = _dealer_probs_recursive(tuple(new_hand), new_rem_tuple)
        for k, p in sub_probs:
            probs[k] += p * (count / total)
    return tuple(probs.items())

def calculate_dealer_probabilities(dealer_card, remaining_cards):
    """
    Calculate probability distribution of dealer's final hand value.
    Returns dict {value: prob} where value is 17-21 or 'bust'
    """
    rem_tuple = tuple(sorted(remaining_cards.items()))
    probs_tuple = _dealer_probs_recursive((dealer_card,), rem_tuple)
    return dict(probs_tuple)

def calculate_ev_stand(player_value, dealer_probs):
    """
    Calculate expected value if player stands.
    """
    ev = 0
    for d_val, prob in dealer_probs.items():
        if d_val == 'bust':
            ev += prob * 1  # win
        elif isinstance(d_val, int):
            if d_val > player_value:
                ev += prob * (-1)  # lose
            elif d_val < player_value:
                ev += prob * 1  # win
            else:
                ev += prob * 0  # push
    return ev

def calculate_ev_hit(player_cards, remaining, dealer_probs):
    """
    Calculate expected value if player hits.
    """
    total = sum(remaining.values())
    if total == 0:
        return -1  # assume bust
    
    ev = 0
    for rank, count in remaining.items():
        if count == 0:
            continue
        new_cards = player_cards + [rank]
        new_value = calculate_hand_value(new_cards)
        if new_value > 21:
            outcome = -1
        else:
            outcome = calculate_ev_stand(new_value, dealer_probs)
        ev += outcome * (count / total)
    return ev

def get_advice(dealer_card, player_cards, remaining_global):
    """
    Get advice on whether to hit or stand.
    """
    player_value = calculate_hand_value(player_cards)
    if player_value > 21:
        return "Already busted!"

    remaining = get_remaining_cards(dealer_card, player_cards, remaining_global)
    dealer_probs = calculate_dealer_probabilities(dealer_card, remaining)

    ev_stand = calculate_ev_stand(player_value, dealer_probs)
    ev_hit = calculate_ev_hit(player_cards, remaining, dealer_probs)

    bust_prob = calculate_bust_probability(player_value, remaining)

    if ev_hit > ev_stand:
        advice = "Hit"
    else:
        advice = "Stand"

    dealer_bust_prob = dealer_probs.get('bust', 0)

    return (f"Player hand value: {player_value}\n"
            f"Bust probability if hit: {bust_prob:.2%}\n"
            f"Dealer bust probability: {dealer_bust_prob:.2%}\n"
            f"EV Stand: {ev_stand:.3f}\n"
            f"EV Hit: {ev_hit:.3f}\n"
            f"Advice: {advice}")

def main():
    print("Blackjack Probability Calculator")
    print("Enter dealer's visible card (2-10, J, Q, K, A):")
    dealer_card = input().strip().upper()
    if dealer_card not in RANKS:
        print("Invalid card.")
        sys.exit(1)

    print("Enter player's cards separated by space (e.g., A 7):")
    player_input = input().strip().upper().split()
    player_cards = []
    for card in player_input:
        if card not in RANKS:
            print(f"Invalid card: {card}")
            sys.exit(1)
        player_cards.append(card)

    advice = get_advice(dealer_card, player_cards)
    print(advice)

def test():
    """Test function with sample scenarios."""
    full_remaining = Counter({rank: 4 * NUM_DECKS for rank in RANKS})
    print("Testing scenarios:")

    # Test 1: Dealer 10, Player A 6 (soft 17)
    print("\nTest 1: Dealer 10, Player A 6")
    print(get_advice('10', ['A', '6'], full_remaining))

    # Test 2: Dealer 5, Player 10 7 (17)
    print("\nTest 2: Dealer 5, Player 10 7")
    print(get_advice('5', ['10', '7'], full_remaining))

    # Test 3: Dealer A, Player 8 8 (16)
    print("\nTest 3: Dealer A, Player 8 8")
    print(get_advice('A', ['8', '8'], full_remaining))

if FLASK_AVAILABLE:
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        advice = ""
        if request.method == 'POST':
            if 'get_advice' in request.form:
                dealer_card = request.form.get('dealer_card', '').strip().upper()
                player_cards = request.form.getlist('player_cards')
                if dealer_card in RANKS and all(c in RANKS for c in player_cards):
                    advice = get_advice(dealer_card, player_cards, remaining_global).replace('\n', '<br>')
                else:
                    advice = "Invalid input. Please select valid cards."
            elif 'add_history' in request.form:
                played_str = request.form.get('played_cards', '').strip().upper()
                played = played_str.split()
                if all(c in RANKS for c in played):
                    history.extend(played)
                    for c in played:
                        remaining_global[c] -= 1
                else:
                    advice = "Invalid cards for history."
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Blackjack Probability Calculator</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f4; }
                h1 { color: #333; }
                form { margin-bottom: 20px; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                select, input { margin-bottom: 10px; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
                input[type="checkbox"] { margin-right: 5px; }
                .checkbox-group { display: flex; flex-wrap: wrap; gap: 10px; }
                button { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-right: 10px; }
                button:hover { background-color: #45a049; }
                .advice { margin-top: 20px; padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                .advice h2 { color: #333; }
                .history { margin-top: 20px; padding: 20px; background-color: #e8f5e8; border-radius: 8px; }
                hr { border: none; height: 1px; background-color: #ccc; margin: 30px 0; }
            </style>
        </head>
        <body>
            <h1>Blackjack Probability Calculator</h1>
            <form method="post">
                <label>Dealer's visible card:</label>
                <select name="dealer_card" required>
                    <option value="">Select card</option>
                    {% for rank in ranks %}
                    <option value="{{ rank }}">{{ rank }}</option>
                    {% endfor %}
                </select><br>
                <label>Player's cards (check all that apply):</label>
                <div class="checkbox-group">
                    {% for rank in ranks %}
                    <label><input type="checkbox" name="player_cards" value="{{ rank }}"> {{ rank }}</label>
                    {% endfor %}
                </div><br>
                <button type="submit" name="get_advice">Get Advice</button>
            </form>
            {% if advice %}
            <div class="advice">
                <h2>Advice:</h2>
                {{ advice | safe }}
            </div>
            {% endif %}
            <hr>
            <div class="history">
                <h2>Game History (Card Counting)</h2>
                <form method="post">
                    <label>Cards played (space separated):</label>
                    <input type="text" name="played_cards" placeholder="e.g., 10 J 5"><br>
                    <button type="submit" name="add_history">Add to History</button>
                </form>
                {% if history %}
                <p><strong>Played cards:</strong> {{ history | join(' ') }}</p>
                <p><strong>Remaining cards:</strong> {% for rank, count in remaining_global.items() %}{{ rank }}:{{ count }} {% endfor %}</p>
                {% endif %}
            </div>
        </body>
        </html>
        """
        return render_template_string(html, ranks=RANKS, advice=advice, history=history, remaining_global=remaining_global)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        if FLASK_AVAILABLE:
            print("Starting web server... Open http://127.0.0.1:5000 in your browser")
            app.run(debug=True)
        else:
            print("Flask not installed. Install with: pip install flask")
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    else:
        main()