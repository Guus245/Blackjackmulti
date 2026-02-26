from flask import Flask, request, jsonify, session, send_from_directory
import random
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Voor sessions – verander dit in productie

# ----------------- BLACKJACK LOGICA -----------------

deck = []
players = {}           # {session_id: {'name': str, 'balance': int, 'hand': [], 'bet': 0, 'state': 'playing/bust/stand'}}
dealer_hand = []
admin_code = "admin123"
redeem_codes = {"bonus100": 100, "startbonus": 500}

def create_deck():
    global deck
    suits = ['♥', '♦', '♣', '♠']
    ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    deck = [(r, s) for s in suits for r in ranks]
    random.shuffle(deck)

def card_value(card):
    r = card[0]
    if r in ['J','Q','K']: return 10
    if r == 'A': return 11
    return int(r)

def hand_value(hand):
    val = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0]=='A')
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

def deal_card(hand):
    global deck
    if not deck:
        create_deck()
    hand.append(deck.pop())

# ----------------- ROUTES -----------------

@app.route('/')
def serve_index():
    return send_from_directory('../public', 'index.html')

@app.route('/api/init', methods=['POST'])
def init_game():
    data = request.json
    player_name = data.get('name', 'Speler')

    session_id = session.get('id')
    if not session_id:
        session_id = str(random.randint(100000, 999999))
        session['id'] = session_id

    if session_id not in players:
        players[session_id] = {
            'name': player_name,
            'balance': 1000,
            'hand': [],
            'bet': 0,
            'state': 'waiting'
        }

    return jsonify({
        'name': players[session_id]['name'],
        'balance': players[session_id]['balance'],
        'message': 'Welkom!'
    })

@app.route('/api/redeem', methods=['POST'])
def redeem():
    session_id = session.get('id')
    if not session_id or session_id not in players:
        return jsonify({'error': 'Start eerst het spel'}), 400

    data = request.json
    code = data.get('code', '').strip()

    if code == admin_code:
        return jsonify({'admin': True, 'message': 'Admin mode – nog niet volledig geïmplementeerd'})

    if code in redeem_codes:
        value = redeem_codes.pop(code)
        players[session_id]['balance'] += value
        return jsonify({
            'success': True,
            'balance': players[session_id]['balance'],
            'message': f'+{value} toegevoegd!'
        })

    return jsonify({'error': 'Ongeldige code'}), 400

@app.route('/api/new_round', methods=['POST'])
def new_round():
    session_id = session.get('id')
    if not session_id or session_id not in players:
        return jsonify({'error': 'Geen speler'}), 400

    p = players[session_id]
    data = request.json
    bet = int(data.get('bet', 0))

    if bet < 1 or bet > p['balance']:
        return jsonify({'error': 'Ongeldige inzet'}), 400

    p['bet'] = bet
    p['balance'] -= bet
    p['hand'] = []
    p['state'] = 'playing'

    global dealer_hand
    dealer_hand = []

    create_deck()  # vers deck per ronde (simpel)

    # Deal
    deal_card(p['hand'])
    deal_card(dealer_hand)
    deal_card(p['hand'])
    deal_card(dealer_hand)

    return jsonify({
        'player_hand': p['hand'],
        'dealer_visible': [dealer_hand[0]],
        'player_value': hand_value(p['hand']),
        'balance': p['balance'],
        'bet': p['bet']
    })

@app.route('/api/hit', methods=['POST'])
def hit():
    session_id = session.get('id')
    if session_id not in players:
        return jsonify({'error': 'Geen spel'}), 400

    p = players[session_id]
    if p['state'] != 'playing':
        return jsonify({'error': 'Kan niet hitten'}), 400

    deal_card(p['hand'])
    val = hand_value(p['hand'])

    if val > 21:
        p['state'] = 'bust'
        return jsonify({
            'player_hand': p['hand'],
            'player_value': val,
            'message': 'Busted!',
            'done': True
        })

    return jsonify({
        'player_hand': p['hand'],
        'player_value': val,
        'done': False
    })

@app.route('/api/stand', methods=['POST'])
def stand():
    session_id = session.get('id')
    if session_id not in players:
        return jsonify({'error': 'Geen spel'}), 400

    p = players[session_id]
    p['state'] = 'stand'

    # Dealer speelt
    global dealer_hand
    while hand_value(dealer_hand) < 17:
        deal_card(dealer_hand)

    dealer_val = hand_value(dealer_hand)
    player_val = hand_value(p['hand'])

    result = ''
    winnings = 0

    if player_val > 21:
        result = 'Verloren (bust)'
    elif dealer_val > 21:
        result = 'Gewonnen! Dealer bust'
        winnings = p['bet'] * 2
    elif player_val > dealer_val:
        result = 'Gewonnen!'
        winnings = p['bet'] * 2
    elif player_val == dealer_val:
        result = 'Push (gelijkspel)'
        winnings = p['bet']
    else:
        result = 'Verloren'

    if winnings > 0:
        p['balance'] += winnings

    p['state'] = 'finished'

    return jsonify({
        'player_hand': p['hand'],
        'dealer_hand': dealer_hand,
        'player_value': player_val,
        'dealer_value': dealer_val,
        'result': result,
        'balance': p['balance'],
        'winnings': winnings - p['bet']  # netto
    })

if __name__ == '__main__':
    app.run(debug=True)
