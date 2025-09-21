#!/usr/bin/env python3
"""
Mid-Cap Portfolio Management System
Updated for $100K baseline with new stock selections
"""

import os
import json
import pandas as pd
import requests
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from config import (
    BASELINE_INVESTMENT, PORTFOLIO_STOCKS, ALPACA_API_KEY, ALPACA_SECRET_KEY,
    ALPACA_BASE_URL, ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_BASE_URL,
    PORTFOLIO_HISTORY_FILE, LATEST_JSON_FILE, TRAILING_STOP_TRIGGER,
    PARTIAL_PROFIT_TARGET, MAX_PORTFOLIO_RISK, EXPERIMENT_START_DATE
)

class PortfolioManager:
    def __init__(self):
        self.alpaca_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
        self.portfolio_data = {}
        self.positions = {}
        
    def get_current_price(self, symbol):
        """Get current stock price from Alpha Vantage with Alpaca fallback"""
        try:
            # Try Alpha Vantage first
            url = f"{ALPHA_VANTAGE_BASE_URL}?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if "Global Quote" in data:
                return float(data["Global Quote"]["05. price"])
        except Exception as e:
            print(f"Alpha Vantage failed for {symbol}: {e}")
        
        try:
            # Fallback to Alpaca
            positions = self.alpaca_client.get_all_positions()
            for pos in positions:
                if pos.symbol == symbol:
                    return float(pos.market_value) / float(pos.qty)
        except Exception as e:
            print(f"Alpaca fallback failed for {symbol}: {e}")
        
        return None

    def get_benchmark_prices(self):
        """Get benchmark ETF prices"""
        benchmarks = ["SPY", "MDY", "IWM", "QQQ"]
        benchmark_data = {}
        
        for symbol in benchmarks:
            price = self.get_current_price(symbol)
            if price:
                benchmark_data[f"{symbol}_price"] = price
        
        return benchmark_data

    def calculate_position_metrics(self, symbol, current_price):
        """Calculate position metrics for a stock"""
        stock_config = PORTFOLIO_STOCKS[symbol]
        
        # Get position from Alpaca
        alpaca_positions = self.alpaca_client.get_all_positions()
        alpaca_pos = next((pos for pos in alpaca_positions if pos.symbol == symbol), None)
        
        if alpaca_pos:
            shares = float(alpaca_pos.qty)
            entry_price = float(alpaca_pos.avg_entry_price)
            cost_basis = float(alpaca_pos.cost_basis)
            market_value = shares * current_price
        else:
            # Calculate based on allocation if not yet purchased
            shares = stock_config["allocation"] / stock_config["entry_target"]
            entry_price = stock_config["entry_target"]
            cost_basis = stock_config["allocation"]
            market_value = shares * current_price
        
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = unrealized_pnl / cost_basis if cost_basis > 0 else 0
        
        # Calculate stop loss levels
        current_stop = max(stock_config["stop_loss"], current_price * 0.92)  # 8% trailing stop
        
        # Check if trailing stop should be activated
        gain_pct = (current_price - entry_price) / entry_price
        if gain_pct > TRAILING_STOP_TRIGGER:
            trailing_stop = current_price * 0.92  # 8% trailing
            current_stop = max(current_stop, trailing_stop)
        
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
            "last_update": datetime.now().isoformat()
        }

    def check_stop_losses(self):
        """Check and execute stop losses if triggered"""
        stop_loss_triggered = []
        
        alpaca_positions = self.alpaca_client.get_all_positions()
        
        for symbol in PORTFOLIO_STOCKS.keys():
            current_price = self.get_current_price(symbol)
            if not current_price:
                continue
                
            alpaca_pos = next((pos for pos in alpaca_positions if pos.symbol == symbol), None)
            if not alpaca_pos:
                continue
                
            position_data = self.calculate_position_metrics(symbol, current_price)
            
            # Check if stop loss should trigger
            if current_price <= position_data["stop_loss"]:
                print(f"STOP LOSS TRIGGERED for {symbol}: {current_price} <= {position_data['stop_loss']}")
                
                try:
                    # Execute stop loss order
                    order_request = MarketOrderRequest(
                        symbol=symbol,
                        qty=float(alpaca_pos.qty),
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    
                    order = self.alpaca_client.submit_order(order_request)
                    print(f"Stop loss order submitted for {symbol}: {order.id}")
                    
                    stop_loss_triggered.append({
                        "symbol": symbol,
                        "trigger_price": current_price,
                        "stop_level": position_data["stop_loss"],
                        "shares": float(alpaca_pos.qty),
                        "proceeds": float(alpaca_pos.qty) * current_price,
                        "order_id": order.id
                    })
                    
                except Exception as e:
                    print(f"Failed to execute stop loss for {symbol}: {e}")
        
        return stop_loss_triggered

    def check_profit_targets(self):
        """Check if any positions hit profit targets"""
        profit_targets_hit = []
        
        alpaca_positions = self.alpaca_client.get_all_positions()
        
        for symbol in PORTFOLIO_STOCKS.keys():
            current_price = self.get_current_price(symbol)
            if not current_price:
                continue
                
            alpaca_pos = next((pos for pos in alpaca_positions if pos.symbol == symbol), None)
            if not alpaca_pos:
                continue
                
            position_data = self.calculate_position_metrics(symbol, current_price)
            
            # Check target 1
            if current_price >= position_data["target_1"]:
                # Sell 50% at target 1
                sell_qty = float(alpaca_pos.qty) * PARTIAL_PROFIT_TARGET
                
                try:
                    order_request = MarketOrderRequest(
                        symbol=symbol,
                        qty=sell_qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    
                    order = self.alpaca_client.submit_order(order_request)
                    print(f"Profit target 1 hit for {symbol}: Sold {sell_qty} shares at {current_price}")
                    
                    profit_targets_hit.append({
                        "symbol": symbol,
                        "target": "Target 1",
                        "price": current_price,
                        "target_price": position_data["target_1"],
                        "shares_sold": sell_qty,
                        "proceeds": sell_qty * current_price,
                        "order_id": order.id
                    })
                    
                except Exception as e:
                    print(f"Failed to execute profit target sale for {symbol}: {e}")
        
        return profit_targets_hit

    def update_portfolio_data(self):
        """Update portfolio data with current positions and metrics"""
        print("Updating portfolio data...")
        
        # Get current account balance
        account = self.alpaca_client.get_account()
        cash = float(account.cash)
        
        # Calculate positions
        positions = {}
        total_positions_value = 0
        
        for symbol in PORTFOLIO_STOCKS.keys():
            current_price = self.get_current_price(symbol)
            if current_price:
                position_data = self.calculate_position_metrics(symbol, current_price)
                positions[symbol] = position_data
                total_positions_value += position_data["market_value"]
        
        # Calculate portfolio totals
        portfolio_value = total_positions_value + cash
        total_return = portfolio_value - BASELINE_INVESTMENT
        total_return_pct = total_return / BASELINE_INVESTMENT
        
        # Get benchmark prices
        benchmark_data = self.get_benchmark_prices()
        
        # Update portfolio data
        self.portfolio_data = {
            "positions": positions,
            "cash": cash,
            "portfolio_value": portfolio_value,
            "total_invested": BASELINE_INVESTMENT,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "positions_count": len([pos for pos in positions.values() if pos["shares"] > 0]),
            "last_update": datetime.now().isoformat(),
            "experiment_start": EXPERIMENT_START_DATE,
            "max_portfolio_risk": MAX_PORTFOLIO_RISK,
            **benchmark_data
        }
        
        print(f"Portfolio Value: ${portfolio_value:,.2f}")
        print(f"Total Return: ${total_return:,.2f} ({total_return_pct:.2%})")
        print(f"Cash: ${cash:,.2f}")
        print(f"Positions: {len(positions)}")
        
        return self.portfolio_data

    def save_to_json(self):
        """Save current portfolio data to JSON file"""
        os.makedirs(os.path.dirname(LATEST_JSON_FILE), exist_ok=True)
        
        with open(LATEST_JSON_FILE, 'w') as f:
            json.dump(self.portfolio_data, f, indent=2)
        
        print(f"Portfolio data saved to {LATEST_JSON_FILE}")

    def save_to_csv(self):
        """Save portfolio data to CSV history"""
        os.makedirs(os.path.dirname(PORTFOLIO_HISTORY_FILE), exist_ok=True)
        
        # Create CSV record
        csv_record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "portfolio_value": self.portfolio_data["portfolio_value"],
            "cash": self.portfolio_data["cash"],
            "positions_value": sum([pos["market_value"] for pos in self.portfolio_data["positions"].values()]),
            "total_invested": self.portfolio_data["total_invested"],
            "total_return": self.portfolio_data["total_return"],
            "total_return_pct": self.portfolio_data["total_return_pct"],
            "positions_count": self.portfolio_data["positions_count"],
        }
        
        # Add benchmark prices
        for key, value in self.portfolio_data.items():
            if key.endswith("_price"):
                csv_record[key] = value
        
        # Add individual stock prices and PnL
        for symbol, position in self.portfolio_data["positions"].items():
            csv_record[f"{symbol}_price"] = position["current_price"]
            csv_record[f"{symbol}_pnl"] = position["unrealized_pnl"]
            csv_record[f"{symbol}_pnl_pct"] = position["unrealized_pnl_pct"]
        
        # Read existing CSV or create new
        if os.path.exists(PORTFOLIO_HISTORY_FILE):
            df = pd.read_csv(PORTFOLIO_HISTORY_FILE)
            
            # Update today's record or append new
            today = datetime.now().strftime("%Y-%m-%d")
            if today in df['date'].values:
                df.loc[df['date'] == today] = pd.Series(csv_record)
            else:
                df = pd.concat([df, pd.DataFrame([csv_record])], ignore_index=True)
        else:
            # Create header
            df = pd.DataFrame([csv_record])
        
        df.to_csv(PORTFOLIO_HISTORY_FILE, index=False)
        print(f"Portfolio history saved to {PORTFOLIO_HISTORY_FILE}")

    def run_daily_update(self):
        """Run complete daily portfolio update"""
        print("=== Daily Portfolio Update Starting ===")
        print(f"Baseline Investment: ${BASELINE_INVESTMENT:,.2f}")
        print(f"Portfolio Stocks: {list(PORTFOLIO_STOCKS.keys())}")
        
        try:
            # Check stop losses first
            stop_losses = self.check_stop_losses()
            if stop_losses:
                print(f"Stop losses triggered: {len(stop_losses)}")
                for sl in stop_losses:
                    print(f"  {sl['symbol']}: {sl['shares']} shares at ${sl['trigger_price']:.2f}")
            
            # Check profit targets
            profit_targets = self.check_profit_targets()
            if profit_targets:
                print(f"Profit targets hit: {len(profit_targets)}")
                for pt in profit_targets:
                    print(f"  {pt['symbol']}: {pt['shares_sold']} shares at ${pt['price']:.2f}")
            
            # Update portfolio data
            self.update_portfolio_data()
            
            # Save to files
            self.save_to_json()
            self.save_to_csv()
            
            print("=== Daily Portfolio Update Completed ===")
            
        except Exception as e:
            print(f"Error during portfolio update: {e}")
            raise

if __name__ == "__main__":
    manager = PortfolioManager()
    manager.run_daily_update()
