#!/usr/bin/env python3
import json
import requests
from datetime import datetime
from alpaca_client import get_alpaca_client

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def get_current_price(symbol):
    """Get current stock price"""
    import os
    alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
    
    if alpha_vantage_key:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={alpha_vantage_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if "Global Quote" in data:
                return float(data["Global Quote"]["05. price"])
        except Exception as e:
            print(f"Alpha Vantage failed for {symbol}: {e}")
    
    # Fallback to Yahoo Finance
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        print(f"YFinance failed for {symbol}: {e}")
    
    return None

def calculate_trailing_stop(symbol, current_price, config):
    """Calculate trailing stop level for a position"""
    stock_config = config["stocks"][symbol]
    portfolio_config = config["portfolio"]
    
    entry_price = stock_config["entry_target"]
    base_stop = stock_config["stop_loss"]
    trailing_trigger = portfolio_config["trailing_stop_trigger"]
    
    # Calculate gain percentage from entry
    gain_pct = (current_price - entry_price) / entry_price
    
    trailing_data = {
        "symbol": symbol,
        "current_price": current_price,
        "entry_price": entry_price,
        "base_stop": base_stop,
        "gain_pct": gain_pct,
        "trailing_active": False,
        "trailing_stop": base_stop,
        "stop_distance_pct": 0.08  # 8% trailing distance
    }
    
    # Check if trailing stop should be activated
    if gain_pct > trailing_trigger:
        trailing_data["trailing_active"] = True
        
        # Calculate 8% trailing stop from current price
        trailing_stop_price = current_price * (1 - trailing_data["stop_distance_pct"])
        
        # Use the higher of base stop or trailing stop
        trailing_data["trailing_stop"] = max(base_stop, trailing_stop_price)
        
        trailing_data["activation_reason"] = f"Gain of {gain_pct:.2%} exceeded {trailing_trigger:.2%} trigger"
    else:
        trailing_data["activation_reason"] = f"Gain of {gain_pct:.2%} below {trailing_trigger:.2%} trigger"
    
    return trailing_data

def update_all_trailing_stops():
    """Update trailing stops for all positions"""
    config = load_config()
    client = get_alpaca_client()
    
    print("=== Updating Trailing Stops ===")
    
    # Get current positions
    try:
        alpaca_positions = client.get_all_positions()
        current_positions = {pos.symbol: pos for pos in alpaca_positions if pos.symbol in config["stocks"]}
    except Exception as e:
        print(f"Error getting positions: {e}")
        return {"status": "error", "error": str(e)}
    
    trailing_stops = {}
    
    for symbol in config["stocks"].keys():
        if symbol not in current_positions:
            print(f"Position {symbol} not found - skipping")
            continue
        
        # Get current price
        current_price = get_current_price(symbol)
        if not current_price:
            print(f"Could not get price for {symbol} - skipping")
            continue
        
        # Calculate trailing stop
        trailing_data = calculate_trailing_stop(symbol, current_price, config)
        trailing_stops[symbol] = trailing_data
        
        # Display results
        if trailing_data["trailing_active"]:
            print(f"{symbol}: ${current_price:.2f} | Trailing Stop: ${trailing_data['trailing_stop']:.2f} | Gain: {trailing_data['gain_pct']:.2%} ✅")
        else:
            print(f"{symbol}: ${current_price:.2f} | Base Stop: ${trailing_data['base_stop']:.2f} | Gain: {trailing_data['gain_pct']:.2%}")
    
    return {
        "status": "update_complete",
        "trailing_stops": trailing_stops,
        "positions_updated": len(trailing_stops),
        "timestamp": datetime.now().isoformat()
    }

def check_trailing_stop_triggers():
    """Check if any trailing stops should trigger"""
    update_result = update_all_trailing_stops()
    
    if update_result["status"] != "update_complete":
        return update_result
    
    print("\n=== Checking Trailing Stop Triggers ===")
    
    triggers = []
    
    for symbol, trailing_data in update_result["trailing_stops"].items():
        current_price = trailing_data["current_price"]
        trailing_stop = trailing_data["trailing_stop"]
        
        # Check if price has fallen below trailing stop
        if current_price <= trailing_stop:
            trigger_info = {
                "symbol": symbol,
                "trigger_type": "trailing_stop" if trailing_data["trailing_active"] else "base_stop",
                "current_price": current_price,
                "stop_level": trailing_stop,
                "trigger_reason": f"Price ${current_price:.2f} <= Stop ${trailing_stop:.2f}",
                "gain_preserved": trailing_data["gain_pct"],
                "timestamp": datetime.now().isoformat()
            }
            
            triggers.append(trigger_info)
            print(f"TRIGGER: {symbol} - {trigger_info['trigger_reason']}")
    
    return {
        "status": "check_complete",
        "trailing_stops": update_result["trailing_stops"],
        "triggers": triggers,
        "triggers_count": len(triggers),
        "timestamp": datetime.now().isoformat()
    }

def optimize_trailing_stops():
    """Optimize trailing stop levels based on volatility and momentum"""
    config = load_config()
    
    print("=== Optimizing Trailing Stops ===")
    
    optimizations = {}
    
    for symbol in config["stocks"].keys():
        # Get historical volatility data
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="20d")  # 20-day history
            
            if len(hist) >= 10:
                # Calculate volatility metrics
                returns = hist['Close'].pct_change().dropna()
                volatility = returns.std() * (252 ** 0.5)  # Annualized volatility
                
                # Calculate optimal trailing distance based on volatility
                base_distance = 0.08  # 8% base trailing distance
                
                if volatility > 0.4:  # High volatility
                    optimal_distance = min(0.12, base_distance * 1.5)
                    volatility_level = "high"
                elif volatility < 0.2:  # Low volatility
                    optimal_distance = max(0.05, base_distance * 0.75)
                    volatility_level = "low"
                else:  # Normal volatility
                    optimal_distance = base_distance
                    volatility_level = "normal"
                
                optimizations[symbol] = {
                    "current_distance": base_distance,
                    "optimal_distance": optimal_distance,
                    "volatility": volatility,
                    "volatility_level": volatility_level,
                    "recommendation": "adjust" if abs(optimal_distance - base_distance) > 0.01 else "maintain"
                }
                
                print(f"{symbol}: Volatility {volatility:.1%} ({volatility_level}) | Optimal distance: {optimal_distance:.1%}")
            
        except Exception as e:
            print(f"Could not optimize {symbol}: {e}")
            optimizations[symbol] = {"error": str(e)}
    
    return {
        "status": "optimization_complete",
        "optimizations": optimizations,
        "timestamp": datetime.now().isoformat()
    }

def generate_trailing_stops_report():
    """Generate comprehensive trailing stops report"""
    print("=== Generating Trailing Stops Report ===")
    
    # Check current trailing stops
    trailing_check = check_trailing_stop_triggers()
    
    # Optimize trailing stops
    optimization = optimize_trailing_stops()
    
    # Combine results
    report = {
        "report_timestamp": datetime.now().isoformat(),
        "trailing_stops_check": trailing_check,
        "optimization": optimization,
        "summary": {
            "positions_monitored": len(trailing_check.get("trailing_stops", {})),
            "trailing_stops_active": len([ts for ts in trailing_check.get("trailing_stops", {}).values() if ts.get("trailing_active")]),
            "triggers_detected": len(trailing_check.get("triggers", [])),
            "optimizations_suggested": len([opt for opt in optimization.get("optimizations", {}).values() if opt.get("recommendation") == "adjust"])
        }
    }
    
    return report

def save_trailing_stops_state(trailing_stops_data):
    """Save current trailing stops state to file"""
    state = {
        "timestamp": datetime.now().isoformat(),
        "trailing_stops": trailing_stops_data,
        "last_update": datetime.now().isoformat()
    }
    
    with open('data/trailing_stops_state.json', 'w') as f:
        json.dump(state, f, indent=2)
    
    print("Trailing stops state saved to data/trailing_stops_state.json")

def load_trailing_stops_state():
    """Load previous trailing stops state"""
    try:
        with open('data/trailing_stops_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error loading trailing stops state: {e}")
        return None

if __name__ == "__main__":
    # Generate and display report
    report = generate_trailing_stops_report()
    
    print("\n=== TRAILING STOPS REPORT ===")
    print(f"Report Time: {report['report_timestamp']}")
    print(f"Positions Monitored: {report['summary']['positions_monitored']}")
    print(f"Trailing Stops Active: {report['summary']['trailing_stops_active']}")
    print(f"Triggers Detected: {report['summary']['triggers_detected']}")
    print(f"Optimizations Suggested: {report['summary']['optimizations_suggested']}")
    
    if report["summary"]["triggers_detected"] > 0:
        print("\n🔥 TRAILING STOP TRIGGERS:")
        for trigger in report["trailing_stops_check"]["triggers"]:
            print(f"  {trigger['symbol']}: {trigger['trigger_reason']} (Gain preserved: {trigger['gain_preserved']:.2%})")
    
    if report["summary"]["optimizations_suggested"] > 0:
        print("\n💡 OPTIMIZATION SUGGESTIONS:")
        for symbol, opt in report["optimization"]["optimizations"].items():
            if opt.get("recommendation") == "adjust":
                print(f"  {symbol}: Adjust trailing distance from {opt['current_distance']:.1%} to {opt['optimal_distance']:.1%} (Volatility: {opt['volatility_level']})")
    
    if report["summary"]["triggers_detected"] == 0 and report["summary"]["optimizations_suggested"] == 0:
        print("\n✅ All trailing stops optimal - no action required")
    
    # Save current state
    if "trailing_stops" in report["trailing_stops_check"]:
        save_trailing_stops_state(report["trailing_stops_check"]["trailing_stops"])
    
    # Save report
    with open('data/trailing_stops_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to data/trailing_stops_report.json")
