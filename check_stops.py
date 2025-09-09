#!/usr/bin/env python3
"""Check for stop loss violations and generate alerts"""

import json
import os
from datetime import datetime

def main():
    """Check for stop loss alerts"""
    # Load portfolio state
    if os.path.exists('state/portfolio_state.json'):
        with open('state/portfolio_state.json', 'r') as f:
            state = json.load(f)
        
        alerts = []
        for symbol, position in state.get('positions', {}).items():
            current_price = position.get('current_price', 0)
            stop_level = position.get('stop_level', 0)
            
            if current_price > 0 and stop_level > 0:
                distance = (current_price - stop_level) / current_price
                if distance < 0.05:  # Within 5% of stop
                    alerts.append({
                        'symbol': symbol,
                        'current_price': current_price,
                        'stop_level': stop_level,
                        'distance_pct': distance * 100
                    })
        
        if alerts:
            with open('data/stop_alerts.json', 'w') as f:
                json.dump(alerts, f, indent=2)
            print(f"⚠️ Generated {len(alerts)} stop loss alerts")
        else:
            print("✅ No stop loss alerts")
    
    else:
        print("No portfolio state found")

if __name__ == "__main__":
    main()
