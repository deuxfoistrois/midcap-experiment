#!/usr/bin/env python3
"""
Add Position Script for Mid-Cap Experiment
Usage: python add_position.py --symbol TICKER --shares 100 --price 25.50 --catalyst "Earnings beat"
"""

import json
import argparse
from datetime import datetime
import os

def load_portfolio_state():
    """Load current portfolio state"""
    if os.path.exists('state/portfolio_state.json'):
        with open('state/portfolio_state.json', 'r') as f:
            return json.load(f)
    else:
        return {
            "positions": {},
            "cash": 1000.00,
            "portfolio_value": 1000.00,
            "last_update": None
        }

def save_portfolio_state(state):
    """Save portfolio state"""
    os.makedirs('state', exist_ok=True)
    with open('state/portfolio_state.json', 'w') as f:
        json.dump(state, f, indent=2, default=str)

def add_position(symbol, shares, price, catalyst="", sector=""):
    """Add a new position to the portfolio"""
    state = load_portfolio_state()
    
    # Calculate cost
    cost = shares * price
    
    # Check if enough cash
    if cost > state['cash']:
        print(f"❌ Insufficient cash. Need: ${cost:.2f}, Available: ${state['cash']:.2f}")
        return False
    
    # Check if position already exists
    if symbol in state['positions']:
        print(f"❌ Position {symbol} already exists")
        return False
    
    # Calculate initial stop loss (13% below entry)
    initial_stop = price * 0.87
    
    # Add position
    state['positions'][symbol] = {
        'symbol': symbol,
        'shares': shares,
        'entry_price': price,
        'entry_date': datetime.now().isoformat(),
        'cost_basis': cost,
        'catalyst': catalyst,
        'sector': sector,
        'current_price': price,
        'market_value': cost,
        'unrealized_pnl': 0,
        'unrealized_pnl_pct': 0,
        'highest_price': price,
        'stop_level': initial_stop,
        'stop_type': 'initial'
    }
    
    # Update cash and portfolio value
    state['cash'] -= cost
    state['portfolio_value'] = state['cash'] + sum(pos['market_value'] for pos in state['positions'].values())
    state['last_update'] = datetime.now().isoformat()
    
    # Save state
    save_portfolio_state(state)
    
    print(f"✅ Added position: {symbol}")
    print(f"   Shares: {shares}")
    print(f"   Entry Price: ${price:.2f}")
    print(f"   Cost: ${cost:.2f}")
    print(f"   Initial Stop: ${initial_stop:.2f}")
    print(f"   Catalyst: {catalyst}")
    print(f"   Remaining Cash: ${state['cash']:.2f}")
    print(f"   Portfolio Value: ${state['portfolio_value']:.2f}")
    
    return True

def show_portfolio():
    """Display current portfolio"""
    state = load_portfolio_state()
    
    print(f"\n📊 CURRENT PORTFOLIO")
    print(f"Cash: ${state['cash']:.2f}")
    print(f"Portfolio Value: ${state['portfolio_value']:.2f}")
    print(f"Positions: {len(state['positions'])}")
    
    if state['positions']:
        print(f"\n📈 POSITIONS:")
        for symbol, pos in state['positions'].items():
            print(f"  {symbol}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
            print(f"    Stop: ${pos['stop_level']:.2f} | Catalyst: {pos['catalyst']}")

def main():
    parser = argparse.ArgumentParser(description='Add position to mid-cap portfolio')
    parser.add_argument('--symbol', required=True, help='Stock symbol (e.g., CRNX)')
    parser.add_argument('--shares', type=int, required=True, help='Number of shares')
    parser.add_argument('--price', type=float, required=True, help='Entry price per share')
    parser.add_argument('--catalyst', default='', help='Investment catalyst')
    parser.add_argument('--sector', default='', help='Sector classification')
    parser.add_argument('--show', action='store_true', help='Show current portfolio')
    
    args = parser.parse_args()
    
    # Show portfolio if requested
    if args.show:
        show_portfolio()
        return
    
    # Validate inputs
    if args.shares <= 0:
        print("❌ Shares must be positive")
        return
        
    if args.price <= 0:
        print("❌ Price must be positive")
        return
    
    # Add position
    success = add_position(
        args.symbol.upper(),
        args.shares,
        args.price,
        args.catalyst,
        args.sector
    )
    
    if success:
        print(f"\n🎯 Next steps:")
        print(f"1. Run: python main.py (update portfolio)")
        print(f"2. Commit changes to GitHub")
        print(f"3. Monitor position on dashboard")

if __name__ == "__main__":
    main()
