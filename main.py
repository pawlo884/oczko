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
SUITS = ['♥', '♣', '♠', '♦']
NUMBERS = ['2', '3', '4', '5', '6', '7', '8', '9', '10']
FIGURES = ['J', 'Q', 'K']
ACES = ['A']
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

def calculate_ev_double(player_cards, remaining, dealer_probs):
    """
    Calculate expected value if player doubles down (hits once, doubles bet).
    """
    total = sum(remaining.values())
    if total == 0:
        return -2  # bust with double bet
    
    ev = 0
    for rank, count in remaining.items():
        if count == 0:
            continue
        new_cards = player_cards + [rank]
        new_value = calculate_hand_value(new_cards)
        if new_value > 21:
            outcome = -2  # double bet lose
        else:
            outcome = 2 * calculate_ev_stand(new_value, dealer_probs)  # double bet
        ev += outcome * (count / total)
    return ev

def get_advice(dealer_card, player_cards, remaining_global, can_double=False):
    """
    Get advice on whether to hit, stand, or double.
    """
    player_value = calculate_hand_value(player_cards)
    if player_value > 21:
        return "Już przekroczyłeś!"

    remaining = get_remaining_cards(dealer_card, player_cards, remaining_global)
    dealer_probs = calculate_dealer_probabilities(dealer_card, remaining)

    ev_stand = calculate_ev_stand(player_value, dealer_probs)
    ev_hit = calculate_ev_hit(player_cards, remaining, dealer_probs)

    options = [('Stój', ev_stand), ('Dobierz', ev_hit)]
    if can_double:
        ev_double = calculate_ev_double(player_cards, remaining, dealer_probs)
        options.append(('Podwój', ev_double))

    best = max(options, key=lambda x: x[1])
    advice = best[0]

    bust_prob = calculate_bust_probability(player_value, remaining)
    dealer_bust_prob = dealer_probs.get('bust', 0)

    result = (f"Wartość ręki gracza: {player_value}\n"
              f"Prawdopodobieństwo przekroczenia przy doborze: {bust_prob:.2%}\n"
              f"Prawdopodobieństwo przekroczenia krupiera: {dealer_bust_prob:.2%}\n"
              f"Oczekiwana wartość stania: {ev_stand:.3f}\n"
              f"Oczekiwana wartość doboru: {ev_hit:.3f}\n")
    if can_double:
        result += f"Oczekiwana wartość podwojenia: {ev_double:.3f}\n"
    result += f"Porada: {advice}"
    return result

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
        dealer_selected = []
        player_selected = []
        can_double_checked = False
        if request.method == 'POST':
            dealer_selected = request.form.getlist('dealer_card')
            player_selected = request.form.getlist('player_cards')
            can_double_checked = 'can_double' in request.form
            if 'get_advice' in request.form and (dealer_selected or player_selected):
                if len(dealer_selected) == 1 and dealer_selected[0] in RANKS and all(c in RANKS for c in player_selected):
                    dealer_card = dealer_selected[0]
                    advice = get_advice(dealer_card, player_selected, remaining_global, can_double_checked).replace('\n', '<br>')
                    # Clear selections after advice
                    dealer_selected = []
                    player_selected = []
                    can_double_checked = False
                else:
                    advice = "Nieprawidłowe dane. Wybierz dokładnie jedną kartę krupiera i zaznacz karty gracza."
            if 'add_history' in request.form:
                played_str = request.form.get('played_cards', '').strip().upper()
                played = []
                for c in played_str.split():
                    if len(c) >= 2 and c[0] in RANKS and c[1] in SUITS:
                        played.append(c[0])
                    elif c in RANKS:
                        played.append(c)
                if played:
                    history.extend(played)
                    for c in played:
                        remaining_global[c] -= 1
                else:
                    advice = "Nieprawidłowe karty dla historii."
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kalkulator Prawdopodobieństwa w Blackjacku</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f4; }
                h1 { color: #333; }
                form { margin-bottom: 20px; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                label { display: inline-block; margin: 2px; font-weight: bold; font-size: 14px; }
                input[type="checkbox"] { margin-right: 3px; }
                .card-group { margin-bottom: 15px; }
                .suit-group { display: inline-block; vertical-align: top; margin-right: 20px; }
                .suit-group strong { display: block; margin-bottom: 5px; font-size: 16px; }
                button { padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-right: 10px; }
                button:hover { background-color: #45a049; }
                .advice { margin-top: 20px; padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                .advice h2 { color: #333; }
                .history { margin-top: 20px; padding: 20px; background-color: #e8f5e8; border-radius: 8px; }
                hr { border: none; height: 1px; background-color: #ccc; margin: 30px 0; }
            </style>
        </head>
        <body>
            <h1>Kalkulator Prawdopodobieństwa w Blackjacku</h1>
            <form method="post" id="advice-form">
                <div class="card-group">
                    <label>Widoczna karta krupiera:</label><br>
                    {% for suit in suits %}
                    <div class="suit-group">
                        <strong>{{ suit }}</strong>
                        {% for rank in ranks %}
                        <label><input type="checkbox" name="dealer_card" value="{{ rank }}" {% if rank in dealer_selected %}checked{% endif %}> {{ rank }}</label>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
                <div class="card-group">
                    <label>Karty gracza (zaznacz wszystkie):</label><br>
                    {% for suit in suits %}
                    <div class="suit-group">
                        <strong>{{ suit }}</strong>
                        {% for rank in ranks %}
                        <label><input type="checkbox" name="player_cards" value="{{ rank }}" {% if rank in player_selected %}checked{% endif %}> {{ rank }}</label>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
                <label><input type="checkbox" name="can_double" {% if can_double_checked %}checked{% endif %}> Czy możesz podwoić stawkę?</label><br>
                <button type="submit" name="get_advice">Uzyskaj poradę</button>
                <button type="button" id="clear-btn">Wyczyść zaznaczenia</button>
            </form>
            {% if advice %}
            <div class="advice">
                <h2>Porada:</h2>
                {{ advice | safe }}
            </div>
            {% endif %}
            <hr>
            <div class="history">
                <h2>Historia gry (liczenie kart)</h2>
                <form method="post">
                    <label>Karty zagrane (oddzielone spacją):</label>
                    <input type="text" name="played_cards" placeholder="np. 10 J 5"><br>
                    <button type="submit" name="add_history">Dodaj do historii</button>
                </form>
                {% if history %}
                <p><strong>Zagrane karty:</strong> {{ history | join(' ') }}</p>
                <p><strong>Pozostałe karty:</strong> {% for rank, count in remaining_global.items() %}{{ rank }}:{{ count }} {% endfor %}</p>
                {% endif %}
            </div>
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // Make dealer checkboxes exclusive
                    const dealerCheckboxes = document.querySelectorAll('input[name="dealer_card"]');
                    dealerCheckboxes.forEach(cb => {
                        cb.addEventListener('change', function() {
                            if (this.checked) {
                                dealerCheckboxes.forEach(other => {
                                    if (other !== this) other.checked = false;
                                });
                            }
                        });
                    });
                    // Clear button
                    document.getElementById('clear-btn').addEventListener('click', function() {
                        const allCheckboxes = document.querySelectorAll('#advice-form input[type="checkbox"]');
                        allCheckboxes.forEach(cb => cb.checked = false);
                    });
                });
            </script>
        </body>
        </html>
        """
        return render_template_string(html, suits=SUITS, ranks=RANKS, advice=advice, history=history, remaining_global=remaining_global, dealer_selected=dealer_selected, player_selected=player_selected, can_double_checked=can_double_checked)

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