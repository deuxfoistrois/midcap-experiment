#!/usr/bin/env python3
import os
import json
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def get_alpaca_client():
    """Initialize Alpaca client"""
    api_key = os.environ.get('ALPACA_API_KEY')
    secret_key = os.environ.get('ALPACA_SECRET_KEY')
    base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    if not api_key or not secret_key:
        raise ValueError("Alpaca API credentials not found in environment variables")
    
    return TradingClient(api_key, secret_key, paper=True)

def sync_with_alpaca_positions():
    """Sync portfolio with current Alpaca positions"""
    config = load_config()
    client = get_alpaca_client()
    
    print("=== Syncing with Alpaca Positions ===")
    
    try:
        # Get account info
        account = client.get_account()
        print(f"Account Status: {account.status}")
        print(f"Cash: ${float(account.cash):,.2f}")
        
        # Get current positions
        positions = client.get_all_positions()
        alpaca_symbols = [pos.symbol for pos in positions if pos.symbol in config["stocks"]]
        
        print(f"Current Alpaca positions: {alpaca_symbols}")
        print(f"Expected positions: {list(config['stocks'].keys())}")
        
        # Check for missing positions (potential stop losses)
        expected_symbols = set(config["stocks"].keys())
        current_symbols = set(alpaca_symbols)
        missing_positions = expected_symbols - current_symbols
        
        if missing_positions:
            print(f"Missing positions (potential stop losses): {missing_positions}")
            
            # Log stop loss events
            stop_loss_data = []
            for symbol in missing_positions:
                stop_loss_data.append({
                    "symbol": symbol,
                    "detected_at": datetime.now().isoformat(),
                    "reason": "Position missing from Alpaca account"
                })
            
            return {
                "status": "stop_losses_detected",
                "missing_positions": list(missing_positions),
                "stop_loss_data": stop_loss_data,
                "current_positions": alpaca_symbols,
                "cash": float(account.cash)
            }
        
        # All positions present
        position_data = {}
        for pos in positions:
            if pos.symbol in config["stocks"]:
                position_data[pos.symbol] = {
                    "shares": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pnl": float(pos.unrealized_pl),
                    "unrealized_pnl_pct": float(pos.unrealized_plpc)
                }
        
        return {
            "status": "positions_synced",
            "positions": position_data,
            "cash": float(account.cash),
            "total_equity": float(account.equity)
        }
        
    except Exception as e:
        print(f"Error syncing with Alpaca: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def execute_stop_loss(symbol, reason="Manual trigger"):
    """Execute stop loss for a specific symbol"""
    config = load_config()
    client = get_alpaca_client()
    
    print(f"=== Executing Stop Loss for {symbol} ===")
    print(f"Reason: {reason}")
    
    try:
        # Get current position
        positions = client.get_all_positions()
        position = next((pos for pos in positions if pos.symbol == symbol), None)
        
        if not position:
            print(f"No position found for {symbol}")
            return {"status": "no_position", "symbol": symbol}
        
        shares = float(position.qty)
        current_price = float(position.market_value) / shares
        
        print(f"Current position: {shares} shares @ ${current_price:.2f}")
        
        # Submit market sell order
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        
        order = client.submit_order(order_request)
        
        print(f"Stop loss order submitted: {order.id}")
        
        return {
            "status": "order_submitted",
            "symbol": symbol,
            "shares": shares,
            "estimated_price": current_price,
            "estimated_proceeds": shares * current_price,
            "order_id": order.id,
            "timestamp": datetime.now().isoformat(),
            "reason": reason
        }
        
    except Exception as e:
        print(f"Error executing stop loss for {symbol}: {e}")
        return {
            "status": "error",
            "symbol": symbol,
            "error": str(e)
        }

def execute_profit_target(symbol, percentage=0.5):
    """Execute partial profit taking at target level"""
    config = load_config()
    client = get_alpaca_client()
    
    print(f"=== Executing Profit Target for {symbol} ===")
    print(f"Selling {percentage*100}% of position")
    
    try:
        # Get current position
        positions = client.get_all_positions()
        position = next((pos for pos in positions if pos.symbol == symbol), None)
        
        if not position:
            print(f"No position found for {symbol}")
            return {"status": "no_position", "symbol": symbol}
        
        total_shares = float(position.qty)
        sell_shares = total_shares * percentage
        current_price = float(position.market_value) / total_shares
        
        print(f"Selling {sell_shares:.3f} of {total_shares} shares @ ~${current_price:.2f}")
        
        # Submit market sell order
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=sell_shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        
        order = client.submit_order(order_request)
        
        print(f"Profit target order submitted: {order.id}")
        
        return {
            "status": "order_submitted",
            "symbol": symbol,
            "shares_sold": sell_shares,
            "shares_remaining": total_shares - sell_shares,
            "estimated_price": current_price,
            "estimated_proceeds": sell_shares * current_price,
            "order_id": order.id,
            "timestamp": datetime.now().isoformat(),
            "percentage": percentage
        }
        
    except Exception as e:
        print(f"Error executing profit target for {symbol}: {e}")
        return {
            "status": "error",
            "symbol": symbol,
            "error": str(e)
        }

def get_account_summary():
    """Get comprehensive account summary"""
    client = get_alpaca_client()
    
    try:
        account = client.get_account()
        positions = client.get_all_positions()
        
        # Filter positions to only our stocks
        config = load_config()
        our_positions = [pos for pos in positions if pos.symbol in config["stocks"]]
        
        summary = {
            "account_status": account.status,
            "cash": float(account.cash),
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "positions_count": len(our_positions),
            "positions": {}
        }
        
        for pos in our_positions:
            summary["positions"][pos.symbol] = {
                "shares": float(pos.qty),
                "avg_entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.market_value) / float(pos.qty),
                "market_value": float(pos.market_value),
                "cost_basis": float(pos.cost_basis),
                "unrealized_pnl": float(pos.unrealized_pl),
                "unrealized_pnl_pct": float(pos.unrealized_plpc)
            }
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}

def monitor_positions():
    """Monitor positions for stop loss and profit target triggers"""
    config = load_config()
    
    print("=== Monitoring Positions ===")
    
    # Sync with Alpaca
    sync_result = sync_with_alpaca_positions()
    
    if sync_result["status"] == "stop_losses_detected":
        print(f"Stop losses detected: {sync_result['missing_positions']}")
        return sync_result
    
    if sync_result["status"] == "error":
        print(f"Sync error: {sync_result['error']}")
        return sync_result
    
    # Check for profit targets and stop losses
    alerts = []
    
    for symbol, position in sync_result["positions"].items():
        stock_config = config["stocks"][symbol]
        current_price = position["market_value"] / position["shares"]
        
        # Check stop loss
        gain_pct = (current_price - stock_config["entry_target"]) / stock_config["entry_target"]
        
        # Dynamic stop loss calculation
        if gain_pct > config["portfolio"]["trailing_stop_trigger"]:
            trailing_stop = current_price * 0.92  # 8% trailing
            dynamic_stop = max(stock_config["stop_loss"], trailing_stop)
        else:
            dynamic_stop = stock_config["stop_loss"]
        
        if current_price <= dynamic_stop:
            alerts.append({
                "type": "stop_loss_trigger",
                "symbol": symbol,
                "current_price": current_price,
                "stop_level": dynamic_stop,
                "action_required": True
            })
        
        # Check profit targets
        if current_price >= stock_config["target_1"]:
            alerts.append({
                "type": "profit_target_1",
                "symbol": symbol,
                "current_price": current_price,
                "target_price": stock_config["target_1"],
                "action_required": True
            })
        
        if current_price >= stock_config["target_2"]:
            alerts.append({
                "type": "profit_target_2",
                "symbol": symbol,
                "current_price": current_price,
                "target_price": stock_config["target_2"],
                "action_required": True
            })
    
    return {
        "status": "monitoring_complete",
        "alerts": alerts,
        "positions": sync_result["positions"],
        "cash": sync_result["cash"]
    }

if __name__ == "__main__":
    # Run position monitoring
    result = monitor_positions()
    print(json.dumps(result, indent=2))
