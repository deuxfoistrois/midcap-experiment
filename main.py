#!/usr/bin/env python3
import os
import json
import pandas as pd
import requests
from datetime import datetime
from alpaca.trading.client import TradingClient

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

def get_alpaca_client():
    """Initialize Alpaca client"""
    api_key = os.environ.get('ALPACA_API_KEY')
    secret_key = os.environ.get('ALPACA_SECRET_KEY')
    base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    return TradingClient(api_key, secret_key, paper=True)

def get_current_price(symbol):
    """Get current stock price from Alpha Vantage with fallbacks"""
    alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
    
    # Try Alpha Vantage first
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

def get_benchmark_prices(config):
    """Get benchmark ETF prices"""
    benchmark_data = {}
    
    for symbol in config["benchmarks"]:
        price = get_current_price(symbol)
        if price:
            benchmark_data[f"{symbol}_price"] = price
    
    return benchmark_data

def calculate_position_metrics(symbol, current_price, config, alpaca_client):
    """Calculate position metrics for a stock"""
    stock_config = config["stocks"][symbol]
    portfolio_config = config["portfolio"]
    
    # Get position from Alpaca
    try:
        alpaca_positions = alpaca_client.get_all_positions()
        alpaca_pos = next((pos for pos in alpaca_positions if pos.symbol == symbol), None)
    except:
        alpaca_pos = None
    
    if alpaca_pos:
        shares = float(alpaca_pos.qty)
        entry_price = float(alpaca_pos.avg_entry_price)
        cost_basis = float(alpaca_pos.cost_basis)
        market_value = shares * current_price
    else:
        # Use config values if not yet purchased
        shares = stock_config["shares"]
        entry_price = stock_config["entry_target"]
        cost_basis = stock_config["allocation"]
        market_value = shares * current_price
    
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_pct = unrealized_pnl / cost_basis if cost_basis > 0 else 0
    
    # Calculate dynamic stop loss (trailing stop logic)
    gain_pct = (current_price - entry_price) / entry_price
    if gain_pct > portfolio_config["trailing_stop_trigger"]:
        # Activate 8% trailing stop
        trailing_stop = current_price * 0.92
        current_stop = max(stock_config["stop_loss"], trailing_stop)
    else:
        current_stop = stock_config["stop_loss"]
    
    return {
        "symbol": symbol,
        "shares": shares,
        "entry_price": entry_price,
        "current_price": current_price,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_pct": unrealized_pnl_pct,
        "stop_loss": current_stop,
        "target_1": stock_config["target_1"],
        "target_2": stock_config["target_2"],
        "catalyst": stock_config["catalyst"],
        "risk_level": stock_config["risk_level"],
        "sector": stock_config["sector"],
        "last_update": datetime.now().isoformat()
    }

def check_stop_losses(config, alpaca_client):
    """Check if any stop losses should trigger"""
    stop_losses_triggered = []
    
    try:
        alpaca_positions = alpaca_client.get_all_positions()
    except:
        alpaca_positions = []
    
    for symbol in config["stocks"].keys():
        current_price = get_current_price(symbol)
        if not current_price:
            continue
            
        alpaca_pos = next((pos for pos in alpaca_positions if pos.symbol == symbol), None)
        if not alpaca_pos:
            continue
            
        position_data = calculate_position_metrics(symbol, current_price, config, alpaca_client)
        
        # Check if stop loss should trigger
        if current_price <= position_data["stop_loss"]:
            print(f"STOP LOSS TRIGGERED for {symbol}: ${current_price:.2f} <= ${position_data['stop_loss']:.2f}")
            
            stop_losses_triggered.append({
                "symbol": symbol,
                "trigger_price": current_price,
                "stop_level": position_data["stop_loss"],
                "shares": float(alpaca_pos.qty),
                "estimated_proceeds": float(alpaca_pos.qty) * current_price,
                "timestamp": datetime.now().isoformat()
            })
    
    return stop_losses_triggered

def update_portfolio_data():
    """Main portfolio update function"""
    print("=== Portfolio Update Starting ===")
    
    # Load configuration
    config = load_config()
    baseline_investment = config["portfolio"]["baseline_investment"]
    
    print(f"Baseline Investment: ${baseline_investment:,.2f}")
    print(f"Portfolio Stocks: {list(config['stocks'].keys())}")
    
    # Initialize Alpaca client
    alpaca_client = get_alpaca_client()
    
    try:
        account = alpaca_client.get_account()
        cash = float(account.cash)
        print(f"Connected to Alpaca. Cash: ${cash:,.2f}")
    except Exception as e:
        print(f"Alpaca connection failed: {e}")
        cash = 0.0
    
    # Check for stop losses
    stop_losses = check_stop_losses(config, alpaca_client)
    if stop_losses:
        print(f"Stop losses detected: {len(stop_losses)}")
        for sl in stop_losses:
            print(f"  {sl['symbol']}: {sl['shares']:.3f} shares @ ${sl['trigger_price']:.2f}")
    
    # Calculate positions
    positions = {}
    total_positions_value = 0
    
    for symbol in config["stocks"].keys():
        current_price = get_current_price(symbol)
        if current_price:
            position_data = calculate_position_metrics(symbol, current_price, config, alpaca_client)
            positions[symbol] = position_data
            total_positions_value += position_data["market_value"]
            
            print(f"{symbol}: ${current_price:.2f} | P&L: ${position_data['unrealized_pnl']:.2f} ({position_data['unrealized_pnl_pct']:.2%})")
        else:
            print(f"Warning: Could not get price for {symbol}")
    
    # Calculate portfolio totals
    portfolio_value = total_positions_value + cash
    total_return = portfolio_value - baseline_investment
    total_return_pct = total_return / baseline_investment
    
    # Get benchmark prices
    benchmark_data = get_benchmark_prices(config)
    
    # Create portfolio data
    portfolio_data = {
        "positions": positions,
        "cash": cash,
        "portfolio_value": portfolio_value,
        "total_invested": baseline_investment,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "positions_count": len([pos for pos in positions.values() if pos["shares"] > 0]),
        "last_update": datetime.now().isoformat(),
        "experiment_start": config["portfolio"]["experiment_start_date"],
        "stop_losses_triggered": stop_losses,
        **benchmark_data
    }
    
    print(f"\nPortfolio Summary:")
    print(f"Portfolio Value: ${portfolio_value:,.2f}")
    print(f"Total Return: ${total_return:,.2f} ({total_return_pct:.2%})")
    print(f"Cash: ${cash:,.2f}")
    print(f"Positions: {len(positions)}")
    
    # Save to JSON file
    os.makedirs("docs", exist_ok=True)
    with open(config["files"]["latest_json"], 'w') as f:
        json.dump(portfolio_data, f, indent=2)
    print(f"Portfolio data saved to {config['files']['latest_json']}")
    
    # Save to CSV
    save_to_csv(portfolio_data, config)
    
    print("=== Portfolio Update Completed ===")
    return portfolio_data

def save_to_csv(portfolio_data, config):
    """Save portfolio data to CSV history"""
    os.makedirs("data", exist_ok=True)
    
    # Create CSV record
    csv_record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "portfolio_value": portfolio_data["portfolio_value"],
        "cash": portfolio_data["cash"],
        "positions_value": sum([pos["market_value"] for pos in portfolio_data["positions"].values()]),
        "total_invested": portfolio_data["total_invested"],
        "total_return": portfolio_data["total_return"],
        "total_return_pct": portfolio_data["total_return_pct"],
        "positions_count": portfolio_data["positions_count"],
    }
    
    # Add benchmark prices
    for benchmark in config["benchmarks"]:
        key = f"{benchmark}_price"
        csv_record[key] = portfolio_data.get(key, 0.0)
    
    # Add individual stock prices and PnL
    for symbol, position in portfolio_data["positions"].items():
        csv_record[f"{symbol}_price"] = position["current_price"]
        csv_record[f"{symbol}_pnl"] = position["unrealized_pnl"]
        csv_record[f"{symbol}_pnl_pct"] = position["unrealized_pnl_pct"]
    
    # Read existing CSV or create new
    csv_file = config["files"]["portfolio_history"]
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        
        # Update today's record or append new
        today = datetime.now().strftime("%Y-%m-%d")
        if today in df['date'].values:
            for key, value in csv_record.items():
                df.loc[df['date'] == today, key] = value
        else:
            df = pd.concat([df, pd.DataFrame([csv_record])], ignore_index=True)
    else:
        # Create new CSV
        df = pd.DataFrame([csv_record])
    
    df.to_csv(csv_file, index=False)
    print(f"Portfolio history saved to {csv_file}")

if __name__ == "__main__":
    update_portfolio_data()
