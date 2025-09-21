#!/usr/bin/env python3
import json
import requests
from datetime import datetime
from alpaca_client import get_alpaca_client, execute_stop_loss

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

def calculate_dynamic_stop_loss(symbol, current_price, config):
    """Calculate dynamic stop loss including trailing stops"""
    stock_config = config["stocks"][symbol]
    portfolio_config = config["portfolio"]
    
    entry_price = stock_config["entry_target"]
    base_stop = stock_config["stop_loss"]
    
    # Calculate gain percentage
    gain_pct = (current_price - entry_price) / entry_price
    
    # If gain exceeds trigger threshold, activate trailing stop
    if gain_pct > portfolio_config["trailing_stop_trigger"]:
        # 8% trailing stop
        trailing_stop = current_price * 0.92
        dynamic_stop = max(base_stop, trailing_stop)
        stop_type = "trailing"
    else:
        dynamic_stop = base_stop
        stop_type = "fixed"
    
    return {
        "stop_price": dynamic_stop,
        "stop_type": stop_type,
        "gain_pct": gain_pct,
        "entry_price": entry_price,
        "base_stop": base_stop
    }

def check_all_stop_losses():
    """Check all positions for stop loss triggers"""
    config = load_config()
    client = get_alpaca_client()
    
    print("=== Checking Stop Losses ===")
    
    # Get current Alpaca positions
    try:
        alpaca_positions = client.get_all_positions()
        current_positions = {pos.symbol: pos for pos in alpaca_positions if pos.symbol in config["stocks"]}
    except Exception as e:
        print(f"Error getting Alpaca positions: {e}")
        return {"status": "error", "error": str(e)}
    
    stop_loss_alerts = []
    
    for symbol in config["stocks"].keys():
        # Check if position still exists
        if symbol not in current_positions:
            print(f"Position {symbol} not found in Alpaca - already stopped out")
            continue
        
        # Get current price
        current_price = get_current_price(symbol)
        if not current_price:
            print(f"Could not get current price for {symbol}")
            continue
        
        # Calculate dynamic stop loss
        stop_data = calculate_dynamic_stop_loss(symbol, current_price, config)
        
        print(f"{symbol}: ${current_price:.2f} | Stop: ${stop_data['stop_price']:.2f} ({stop_data['stop_type']}) | Gain: {stop_data['gain_pct']:.2%}")
        
        # Check if stop loss should trigger
        if current_price <= stop_data["stop_price"]:
            print(f"STOP LOSS TRIGGERED for {symbol}")
            
            stop_loss_alerts.append({
                "symbol": symbol,
                "current_price": current_price,
                "stop_price": stop_data["stop_price"],
                "stop_type": stop_data["stop_type"],
                "trigger_reason": f"Price ${current_price:.2f} <= Stop ${stop_data['stop_price']:.2f}",
                "shares": float(current_positions[symbol].qty),
                "estimated_proceeds": float(current_positions[symbol].qty) * current_price,
                "timestamp": datetime.now().isoformat()
            })
    
    return {
        "status": "check_complete",
        "stop_loss_alerts": stop_loss_alerts,
        "positions_checked": len(current_positions),
        "timestamp": datetime.now().isoformat()
    }

def execute_triggered_stops():
    """Execute any stop losses that have been triggered"""
    print("=== Executing Triggered Stop Losses ===")
    
    # Check for triggers
    check_result = check_all_stop_losses()
    
    if check_result["status"] != "check_complete":
        print(f"Stop loss check failed: {check_result}")
        return check_result
    
    if not check_result["stop_loss_alerts"]:
        print("No stop losses triggered")
        return {"status": "no_triggers", "message": "No stop losses need execution"}
    
    # Execute stop losses
    execution_results = []
    
    for alert in check_result["stop_loss_alerts"]:
        symbol = alert["symbol"]
        reason = f"Stop loss triggered: {alert['trigger_reason']}"
        
        print(f"Executing stop loss for {symbol}: {reason}")
        
        execution_result = execute_stop_loss(symbol, reason)
        execution_results.append(execution_result)
        
        # Add alert data to execution result
        execution_result["alert_data"] = alert
    
    return {
        "status": "execution_complete",
        "triggers_found": len(check_result["stop_loss_alerts"]),
        "executions": execution_results,
        "timestamp": datetime.now().isoformat()
    }

def monitor_risk_levels():
    """Monitor portfolio risk levels and alert if approaching limits"""
    config = load_config()
    client = get_alpaca_client()
    
    try:
        account = client.get_account()
        portfolio_value = float(account.equity)
        baseline_investment = config["portfolio"]["baseline_investment"]
        max_risk = config["portfolio"]["max_portfolio_risk"]
        
        current_loss = baseline_investment - portfolio_value
        current_loss_pct = current_loss / baseline_investment
        
        risk_alerts = []
        
        # Check if approaching maximum risk
        if current_loss_pct > max_risk * 0.8:  # 80% of max risk
            risk_alerts.append({
                "type": "risk_warning",
                "message": f"Portfolio loss approaching maximum risk limit",
                "current_loss": current_loss,
                "current_loss_pct": current_loss_pct,
                "max_risk_pct": max_risk,
                "threshold_reached": "80% of maximum risk"
            })
        
        # Check if maximum risk exceeded
        if current_loss_pct > max_risk:
            risk_alerts.append({
                "type": "risk_exceeded",
                "message": f"Portfolio loss EXCEEDS maximum risk limit",
                "current_loss": current_loss,
                "current_loss_pct": current_loss_pct,
                "max_risk_pct": max_risk,
                "action_required": "IMMEDIATE RISK MANAGEMENT REQUIRED"
            })
        
        return {
            "status": "risk_monitoring_complete",
            "portfolio_value": portfolio_value,
            "baseline_investment": baseline_investment,
            "current_loss": current_loss,
            "current_loss_pct": current_loss_pct,
            "max_risk_pct": max_risk,
            "risk_alerts": risk_alerts,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def generate_stop_loss_report():
    """Generate comprehensive stop loss monitoring report"""
    print("=== Generating Stop Loss Report ===")
    
    # Check stop losses
    stop_check = check_all_stop_losses()
    
    # Monitor risk levels
    risk_monitoring = monitor_risk_levels()
    
    # Combine results
    report = {
        "report_timestamp": datetime.now().isoformat(),
        "stop_loss_check": stop_check,
        "risk_monitoring": risk_monitoring,
        "summary": {
            "stop_losses_triggered": len(stop_check.get("stop_loss_alerts", [])),
            "risk_alerts": len(risk_monitoring.get("risk_alerts", [])),
            "action_required": False
        }
    }
    
    # Determine if action is required
    if stop_check.get("stop_loss_alerts") or risk_monitoring.get("risk_alerts"):
        report["summary"]["action_required"] = True
    
    return report

if __name__ == "__main__":
    # Generate and display report
    report = generate_stop_loss_report()
    
    print("\n=== STOP LOSS MONITORING REPORT ===")
    print(f"Report Time: {report['report_timestamp']}")
    print(f"Stop Losses Triggered: {report['summary']['stop_losses_triggered']}")
    print(f"Risk Alerts: {report['summary']['risk_alerts']}")
    print(f"Action Required: {report['summary']['action_required']}")
    
    if report["summary"]["action_required"]:
        print("\n🚨 ALERTS:")
        
        # Show stop loss alerts
        for alert in report["stop_loss_check"].get("stop_loss_alerts", []):
            print(f"  STOP LOSS: {alert['symbol']} - {alert['trigger_reason']}")
        
        # Show risk alerts
        for alert in report["risk_monitoring"].get("risk_alerts", []):
            print(f"  RISK: {alert['message']}")
    else:
        print("\n✅ All systems normal - no action required")
    
    # Save report to file
    with open('data/stop_loss_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to data/stop_loss_report.json")
