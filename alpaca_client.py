#!/usr/bin/env python3
"""
Alpaca Markets API Client for Portfolio Trading
Handles market data and order execution
"""

import alpaca_trade_api as tradeapi
import os
from typing import Dict, List, Optional
from datetime import datetime

class AlpacaClient:
    def __init__(self):
        """Initialize Alpaca API client"""
        self.api_key_id = os.environ.get('ALPACA_API_KEY_ID')
        self.secret_key = os.environ.get('ALPACA_SECRET_KEY')
        self.base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not self.api_key_id or not self.secret_key:
            raise ValueError("Alpaca API credentials not found in environment variables")
        
        self.api = tradeapi.REST(
            key_id=self.api_key_id,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        
        print(f"Alpaca client initialized for: {self.base_url}")

    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            account = self.api.get_account()
            print(f"Connected to Alpaca - Account Status: {account.status}")
            print(f"Buying Power: ${float(account.buying_power):,.2f}")
            return True
        except Exception as e:
            print(f"Alpaca connection failed: {e}")
            return False

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current stock price"""
        try:
            # Get latest quote
            quote = self.api.get_latest_quote(symbol)
            
            # Return mid price (average of bid and ask)
            if quote and quote.bid_price and quote.ask_price:
                mid_price = (float(quote.bid_price) + float(quote.ask_price)) / 2
                return mid_price
            
            # Fallback to latest trade if quote not available
            trade = self.api.get_latest_trade(symbol)
            if trade and trade.price:
                return float(trade.price)
                
            return None
            
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
            return None

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get comprehensive market data for a symbol"""
        try:
            # Get latest quote and trade
            quote = self.api.get_latest_quote(symbol)
            trade = self.api.get_latest_trade(symbol)
            
            if not trade or not trade.price:
                return None
            
            current_price = float(trade.price)
            
            # Get previous close for change calculation
            bars = self.api.get_bars(
                symbol, 
                tradeapi.TimeFrame.Day, 
                limit=2,
                adjustment='raw'
            ).df
            
            previous_close = current_price
            change = 0
            change_percent = 0
            
            if len(bars) >= 2:
                previous_close = float(bars.iloc[-2]['close'])
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100 if previous_close > 0 else 0
            
            return {
                'symbol': symbol,
                'price': current_price,
                'change': change,
                'change_percent': f"{change_percent:.2f}%",
                'volume': int(trade.size) if trade.size else 0,
                'previous_close': previous_close,
                'open': current_price,  # Simplified - would need daily bar for actual open
                'high': current_price,  # Simplified - would need daily bar for actual high/low
                'low': current_price,
                'bid': float(quote.bid_price) if quote and quote.bid_price else current_price,
                'ask': float(quote.ask_price) if quote and quote.ask_price else current_price,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error getting market data for {symbol}: {e}")
            return None

    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        try:
            account = self.api.get_account()
            return {
                'account_id': account.id,
                'status': account.status,
                'buying_power': float(account.buying_power),
                'cash': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'equity': float(account.equity),
                'last_equity': float(account.last_equity),
                'currency': account.currency,
                'trading_blocked': account.trading_blocked,
                'account_blocked': account.account_blocked
            }
        except Exception as e:
            print(f"Error getting account info: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """Get all current positions"""
        try:
            positions = self.api.list_positions()
            position_list = []
            
            for pos in positions:
                position_list.append({
                    'symbol': pos.symbol,
                    'qty': float(pos.qty),
                    'market_value': float(pos.market_value),
                    'cost_basis': float(pos.cost_basis),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc),
                    'avg_entry_price': float(pos.avg_entry_price),
                    'current_price': float(pos.current_price) if pos.current_price else 0,
                    'side': pos.side
                })
            
            return position_list
            
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def place_market_order(self, symbol: str, qty: float, side: str = 'buy') -> Optional[str]:
        """Place a market order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type='market',
                time_in_force='day'
            )
            
            print(f"Market order placed: {side.upper()} {qty} shares of {symbol}")
            return order.id
            
        except Exception as e:
            print(f"Error placing market order for {symbol}: {e}")
            return None

    def place_stop_order(self, symbol: str, qty: float, stop_price: float) -> Optional[str]:
        """Place a stop-loss order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='stop',
                stop_price=stop_price,
                time_in_force='day'
            )
            
            print(f"Stop order placed: SELL {qty} shares of {symbol} at stop ${stop_price:.2f}")
            return order.id
            
        except Exception as e:
            print(f"Error placing stop order for {symbol}: {e}")
            return None

    def get_orders(self, status: str = 'all') -> List[Dict]:
        """Get order history"""
        try:
            orders = self.api.list_orders(status=status, limit=100)
            order_list = []
            
            for order in orders:
                order_list.append({
                    'id': order.id,
                    'symbol': order.symbol,
                    'qty': float(order.qty),
                    'side': order.side,
                    'type': order.type,
                    'status': order.status,
                    'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                    'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else 0,
                    'created_at': order.created_at,
                    'updated_at': order.updated_at
                })
            
            return order_list
            
        except Exception as e:
            print(f"Error getting orders: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.api.cancel_order(order_id)
            print(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            print(f"Error cancelling order {order_id}: {e}")
            return False

def test_alpaca_connection():
    """Test function to verify Alpaca connection"""
    try:
        client = AlpacaClient()
        
        # Test connection
        if not client.test_connection():
            return False
        
        # Test account info
        account = client.get_account_info()
        if account:
            print(f"Account Status: {account['status']}")
            print(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
        
        # Test market data
        test_symbols = ['AAPL', 'MSFT']
        for symbol in test_symbols:
            data = client.get_market_data(symbol)
            if data:
                print(f"{symbol}: ${data['price']:.2f} ({data['change_percent']})")
        
        # Test positions
        positions = client.get_positions()
        print(f"Current positions: {len(positions)}")
        
        return True
        
    except Exception as e:
        print(f"Alpaca test failed: {e}")
        return False

if __name__ == "__main__":
    test_alpaca_connection()
