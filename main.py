#!/usr/bin/env python3
"""
Mid-Cap Portfolio Tracker with Advanced Trailing Stop-Loss
Professional portfolio management system with Alpaca trading integration
"""

import json
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from trailing_stops import TrailingStopManager

# Alpaca integration
try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("Warning: alpaca-trade-api not installed. Using Alpha Vantage fallback.")

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/portfolio.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlpacaClient:
    def __init__(self):
        """Initialize Alpaca API client"""
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-trade-api package not available")
            
        self.api_key_id = os.environ.get('ALPACA_API_KEY_ID')
        self.secret_key = os.environ.get('ALPACA_SECRET_KEY')
        self.base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets/v2')
        
        if not self.api_key_id or not self.secret_key:
            raise ValueError("Alpaca API credentials not found in environment variables")
        
        self.api = tradeapi.REST(
            key_id=self.api_key_id,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        
        logger.info(f"Alpaca client initialized for: {self.base_url}")

    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            account = self.api.get_account()
            logger.info(f"Connected to Alpaca - Account Status: {account.status}")
            logger.info(f"Buying Power: ${float(account.buying_power):,.2f}")
            return True
        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")
            return False

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
                'low': current_price
            }
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
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
            logger.error(f"Error getting positions: {e}")
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
            
            logger.info(f"Market order placed: {side.upper()} {qty} shares of {symbol}")
            return order.id
            
        except Exception as e:
            logger.error(f"Error placing market order for {symbol}: {e}")
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
            
            logger.info(f"Stop order placed: SELL {qty} shares of {symbol} at stop ${stop_price:.2f}")
            return order.id
            
        except Exception as e:
            logger.error(f"Error placing stop order for {symbol}: {e}")
            return None

    def place_initial_portfolio_positions(self) -> Dict[str, str]:
        """Place the initial midcap portfolio positions"""
        initial_positions = {
            "CRNX": {"shares": 8.0, "target_value": 260.0},
            "STRL": {"shares": 0.874, "target_value": 250.0}, 
            "OTEX": {"shares": 8.0, "target_value": 243.92},
            "ZION": {"shares": 4.0, "target_value": 221.56}
        }
        
        placed_orders = {}
        
        logger.info("Placing initial portfolio positions...")
        
        for symbol, data in initial_positions.items():
            try:
                # Place market order
                order_id = self.place_market_order(symbol, data["shares"], 'buy')
                
                if order_id:
                    placed_orders[symbol] = order_id
                    logger.info(f"✓ {symbol}: Ordered {data['shares']} shares (target: ${data['target_value']:.2f})")
                else:
                    logger.error(f"✗ {symbol}: Order failed")
                    
            except Exception as e:
                logger.error(f"Error placing initial order for {symbol}: {e}")
        
        logger.info(f"Initial positions placed: {len(placed_orders)}/{len(initial_positions)} successful")
        return placed_orders

    def sync_portfolio_positions(self) -> Dict[str, Dict]:
        """Get current positions and sync with portfolio state"""
        _positions = self.get_positions()
        
        portfolio_positions = {}
        
        for pos in alpaca_positions:
            symbol = pos['symbol']
            
            # Only track our midcap positions
            if symbol in ['CRNX', 'STRL', 'OTEX', 'ZION']:
                portfolio_positions[symbol] = {
                    'symbol': symbol,
                    'shares': pos['qty'],
                    'current_price': pos['current_price'],
                    'market_value': pos['market_value'],
                    'cost_basis': pos['cost_basis'],
                    'avg_entry_price': pos['avg_entry_price'],
                    'unrealized_pnl': pos['unrealized_pl'],
                    'unrealized_pnl_pct': pos['unrealized_plpc'],
                    'side': pos['side']
                }
                
                logger.info(f"Synced {symbol}: {pos['qty']} shares @ ${pos['current_price']:.2f} (P&L: ${pos['unrealized_pl']:.2f})")
        
        return portfolio_positions

    def update_stop_orders(self, positions_with_stops: Dict[str, Dict]) -> Dict[str, str]:
        """Update stop-loss orders for positions"""
        stop_orders_placed = {}
        
        # Cancel existing stop orders first
        existing_orders = self.get_orders(status='open')
        stop_orders = [order for order in existing_orders if order['type'] == 'stop']
        
        for order in stop_orders:
            if order['symbol'] in positions_with_stops:
                logger.info(f"Cancelling existing stop order for {order['symbol']}")
                self.cancel_order(order['id'])
        
        # Place new stop orders
        for symbol, position in positions_with_stops.items():
            if position.get('stop_level') and position['shares'] > 0:
                try:
                    order_id = self.place_stop_order(
                        symbol=symbol, 
                        qty=position['shares'], 
                        stop_price=position['stop_level']
                    )
                    
                    if order_id:
                        stop_orders_placed[symbol] = order_id
                        logger.info(f"✓ {symbol}: Stop order at ${position['stop_level']:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error placing stop order for {symbol}: {e}")
        
        return stop_orders_placed

    def liquidate_position(self, symbol: str) -> Optional[str]:
        """Liquidate entire position for a symbol"""
        try:
            positions = self.get_positions()
            position = next((pos for pos in positions if pos['symbol'] == symbol), None)
            
            if not position:
                logger.warning(f"No position found for {symbol}")
                return None
            
            if position['qty'] <= 0:
                logger.warning(f"No shares to sell for {symbol}")
                return None
            
            # Place market sell order for entire position
            order_id = self.place_market_order(symbol, position['qty'], 'sell')
            
            if order_id:
                logger.info(f"✓ Liquidated {symbol}: Sold {position['qty']} shares")
            
            return order_id
            
        except Exception as e:
            logger.error(f"Error liquidating {symbol}: {e}")
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
            logger.error(f"Error getting orders: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.api.cancel_order(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

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
            logger.error(f"Error getting account info: {e}")
            return None

class MidCapPortfolioTracker:
    def __init__(self, config_file='config.json'):
        """Initialize the portfolio tracker"""
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Initialize trailing stop manager
        self.stop_manager = TrailingStopManager(config_file)
        
        # Initialize data source (Alpaca or Alpha Vantage)
        self.use_alpaca = False
        self.alpaca_client = None
        
        # Try to initialize Alpaca client
        if ALPACA_AVAILABLE:
            try:
                self.alpaca_client = AlpacaClient()
                if self.alpaca_client.test_connection():
                    self.use_alpaca = True
                    logger.info("Using Alpaca Markets for data and trading")
                else:
                    logger.warning("Alpaca connection failed, falling back to Alpha Vantage")
            except Exception as e:
                logger.warning(f"Could not initialize Alpaca client: {e}")
        
        # Fallback to Alpha Vantage if Alpaca not available
        if not self.use_alpaca:
            self.api_key = os.environ.get('ALPHAVANTAGE_API_KEY')
            if not self.api_key:
                raise ValueError("No data source available - need either Alpaca credentials or ALPHAVANTAGE_API_KEY")
            logger.info("Using Alpha Vantage for data")
        
        # File paths
        self.portfolio_state_file = 'state/portfolio_state.json'
        self.portfolio_history_file = 'data/portfolio_history.csv'
        self.benchmark_file = 'data/benchmark_history.csv'
        
        # Initialize portfolio state
        self.portfolio_state = self.load_portfolio_state()
        
        # Ensure directories exist
        os.makedirs('state', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('docs', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        os.makedirs('reports', exist_ok=True)

    def load_portfolio_state(self) -> Dict:
        """Load current portfolio state"""
        try:
            with open(self.portfolio_state_file, 'r') as f:
                state = json.load(f)
            logger.info("Portfolio state loaded successfully")
            return state
        except FileNotFoundError:
            logger.info("No existing portfolio state found, initializing new portfolio")
            return self.initialize_portfolio()

    def initialize_portfolio(self) -> Dict:
        """Initialize new portfolio with default positions"""
        initial_state = {
            "positions": {
                "CRNX": {
                    "symbol": "CRNX",
                    "shares": 8.0,
                    "entry_price": 32.50,
                    "entry_date": "2025-09-08T00:00:00",
                    "cost_basis": 260.0,
                    "catalyst": "FDA PDUFA September 25",
                    "sector": "Healthcare",
                    "current_price": 32.50,
                    "market_value": 260.0,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "highest_price": 32.50,
                    "stop_level": 28.275,
                    "stop_type": "initial"
                },
                "STRL": {
                    "symbol": "STRL", 
                    "shares": 0.874,
                    "entry_price": 286.0,
                    "entry_date": "2025-09-08T00:00:00",
                    "cost_basis": 250.0,
                    "catalyst": "Q3 Earnings October",
                    "sector": "Industrial",
                    "current_price": 286.0,
                    "market_value": 250.0,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "highest_price": 286.0,
                    "stop_level": 248.82,
                    "stop_type": "initial"
                },
                "OTEX": {
                    "symbol": "OTEX",
                    "shares": 8.0,
                    "entry_price": 30.49,
                    "entry_date": "2025-09-08T00:00:00",
                    "cost_basis": 243.92,
                    "catalyst": "Q1 FY2025 Earnings Oct 31",
                    "sector": "Technology",
                    "current_price": 30.49,
                    "market_value": 243.92,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "highest_price": 30.49,
                    "stop_level": 26.53,
                    "stop_type": "initial"
                },
                "ZION": {
                    "symbol": "ZION",
                    "shares": 4.0,
                    "entry_price": 55.39,
                    "entry_date": "2025-09-08T00:00:00",
                    "cost_basis": 221.56,
                    "catalyst": "Q3 Earnings + Fed Cuts",
                    "sector": "Financial",
                    "current_price": 55.39,
                    "market_value": 221.56,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "highest_price": 55.39,
                    "stop_level": 48.19,
                    "stop_type": "initial"
                }
            },
            "cash": 24.52,
            "portfolio_value": 1000.00,
            "last_update": datetime.now().isoformat(),
            "experiment_start": "2025-09-08T00:00:00"
        }
        
        self.save_portfolio_state(initial_state)
        return initial_state

    def sync_with_alpaca_positions(self):
        """Sync portfolio state with actual Alpaca positions and place initial orders if needed"""
        if not self.use_alpaca or not self.alpaca_client:
            return
            
        logger.info("Syncing with Alpaca positions...")
        
        try:
            alpaca_positions = self.alpaca_client.sync_portfolio_positions()
            
            # Check if we need to place initial orders
            target_symbols = set(['CRNX', 'STRL', 'OTEX', 'ZION'])
            current_symbols = set(alpaca_positions.keys())
            missing_symbols = target_symbols - current_symbols
            
            if missing_symbols:
                logger.info(f"Missing positions in Alpaca: {missing_symbols}")
                logger.info("Placing initial portfolio positions...")
                orders = self.alpaca_client.place_initial_portfolio_positions()
                logger.info(f"Placed {len(orders)} initial orders")
                
                # Refresh positions after placing orders
                alpaca_positions = self.alpaca_client.sync_portfolio_positions()
            
            # Update our portfolio state with actual Alpaca data
            for symbol in self.portfolio_state['positions']:
                if symbol in alpaca_positions:
                    alpaca_pos = alpaca_positions[symbol]
                    our_pos = self.portfolio_state['positions'][symbol]
                    
                    # Update with actual Alpaca data
                    our_pos['shares'] = alpaca_pos['shares']
                    our_pos['current_price'] = alpaca_pos['current_price']
                    our_pos['market_value'] = alpaca_pos['market_value']
                    our_pos['unrealized_pnl'] = alpaca_pos['unrealized_pnl']
                    our_pos['unrealized_pnl_pct'] = alpaca_pos['unrealized_pnl_pct']
                    
                    # Update highest price tracking
                    if alpaca_pos['current_price'] > our_pos.get('highest_price', our_pos['entry_price']):
                        our_pos['highest_price'] = alpaca_pos['current_price']
                    
                    logger.info(f"Synced {symbol}: {alpaca_pos['shares']} shares @ ${alpaca_pos['current_price']:.2f}")
                else:
                    logger.warning(f"{symbol} not found in Alpaca positions")
        
        except Exception as e:
            logger.error(f"Error syncing with Alpaca positions: {e}")

    def get_stock_price_alpaca(self, symbol: str) -> Optional[Dict]:
        """Get current stock price from Alpaca"""
        if self.alpaca_client:
            return self.alpaca_client.get_market_data(symbol)
        return None

    def get_stock_price_alpha_vantage(self, symbol: str) -> Optional[Dict]:
        """Get current stock price from Alpha Vantage"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                return {
                    'symbol': symbol,
                    'price': float(quote['05. price']),
                    'change': float(quote['09. change']),
                    'change_percent': quote['10. change percent'].rstrip('%'),
                    'volume': int(quote['06. volume']),
                    'previous_close': float(quote['08. previous close']),
                    'open': float(quote['02. open']),
                    'high': float(quote['03. high']),
                    'low': float(quote['04. low'])
                }
            else:
                logger.error(f"Error getting price for {symbol}: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def get_stock_price(self, symbol: str) -> Optional[Dict]:
        """Get current stock price from preferred data source"""
        if self.use_alpaca:
            return self.get_stock_price_alpaca(symbol)
        else:
            return self.get_stock_price_alpha_vantage(symbol)

    def update_stock_prices(self):
        """Update all stock prices"""
        data_source = "Alpaca" if self.use_alpaca else "Alpha Vantage"
        logger.info(f"Updating stock prices from {data_source}...")
        
        for symbol in self.portfolio_state['positions']:
            price_data = self.get_stock_price(symbol)
            
            if price_data:
                position = self.portfolio_state['positions'][symbol]
                position['current_price'] = price_data['price']
                
                # Update highest price if current is higher
                if price_data['price'] > position.get('highest_price', position['entry_price']):
                    position['highest_price'] = price_data['price']
                
                # Calculate unrealized P&L
                shares = position['shares']
                entry_price = position['entry_price']
                current_price = price_data['price']
                
                position['market_value'] = shares * current_price
                position['unrealized_pnl'] = (current_price - entry_price) * shares
                position['unrealized_pnl_pct'] = (current_price - entry_price) / entry_price
                
                logger.info(f"Updated {symbol}: ${current_price:.2f} (P&L: {position['unrealized_pnl_pct']:.2%})")
            else:
                logger.warning(f"Could not update price for {symbol}")

    def update_stop_levels(self):
        """Update trailing stop levels and execute actual stop orders in Alpaca"""
        logger.info("Updating stop levels...")
        
        # Use the TrailingStopManager to update stop levels
        updated_positions = self.stop_manager.update_stop_levels(self.portfolio_state['positions'])
        self.portfolio_state['positions'] = updated_positions
        
        # Check for stop violations
        violations = self.stop_manager.check_stop_violations(self.portfolio_state['positions'])
        
        if violations:
            logger.warning(f"Found {len(violations)} stop violations!")
            for violation in violations:
                logger.warning(f"STOP TRIGGERED: {violation['symbol']} at ${violation['current_price']:.2f}, stop at ${violation['stop_level']:.2f}")
                
                # Execute actual sell order in Alpaca if using Alpaca
                if self.use_alpaca and self.alpaca_client:
                    logger.info(f"Executing stop-loss sell for {violation['symbol']}")
                    order_id = self.alpaca_client.liquidate_position(violation['symbol'])
                    if order_id:
                        logger.info(f"Stop-loss executed: Order ID {order_id}")
                    else:
                        logger.error(f"Failed to execute stop-loss for {violation['symbol']}")
        
        # Update stop orders in Alpaca for all positions
        if self.use_alpaca and self.alpaca_client:
            positions_with_stops = {
                symbol: pos for symbol, pos in self.portfolio_state['positions'].items() 
                if pos.get('stop_level', 0) > 0
            }
            stop_orders = self.alpaca_client.update_stop_orders(positions_with_stops)
            logger.info(f"Updated {len(stop_orders)} stop orders in Alpaca")
        
        # Generate and save stop report
        stop_report = self.stop_manager.generate_stop_report(self.portfolio_state['positions'])
        
        with open('docs/trailing_stops_report.json', 'w') as f:
            json.dump(stop_report, f, indent=2, default=str)

    def update_portfolio_value(self) -> float:
        """Calculate and update total portfolio value"""
        total_positions_value = sum(pos['market_value'] for pos in self.portfolio_state['positions'].values())
        cash = self.portfolio_state['cash']
        portfolio_value = total_positions_value + cash
        
        self.portfolio_state['portfolio_value'] = portfolio_value
        logger.info(f"Portfolio value updated: ${portfolio_value:.2f}")
        
        return portfolio_value

    def save_daily_snapshot(self) -> Dict:
        """Save daily portfolio snapshot to history"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate portfolio metrics
        portfolio_value = self.portfolio_state['portfolio_value']
        initial_capital = self.config['portfolio']['initial_capital']
        total_return = portfolio_value - initial_capital
        total_return_pct = total_return / initial_capital
        
        daily_record = {
            'date': today,
            'portfolio_value': portfolio_value,
            'cash': self.portfolio_state['cash'],
            'positions_value': sum(pos['market_value'] for pos in self.portfolio_state['positions'].values()),
            'positions_count': len(self.portfolio_state['positions']),
            'total_return': total_return,
            'total_return_pct': total_return_pct
        }
        
        # Add individual position data
        for symbol, position in self.portfolio_state['positions'].items():
            daily_record[f'{symbol}_price'] = position['current_price']
            daily_record[f'{symbol}_pnl'] = position['unrealized_pnl']
            daily_record[f'{symbol}_pnl_pct'] = position['unrealized_pnl_pct']
        
        # Save to CSV
        df_new = pd.DataFrame([daily_record])
        
        try:
            # Load existing data
            if os.path.exists(self.portfolio_history_file):
                df_existing = pd.read_csv(self.portfolio_history_file)
                
                # Check if today's record already exists
                if today in df_existing['date'].values:
                    # Update existing record
                    mask = df_existing['date'] == today
                    for col in daily_record.keys():
                        df_existing.loc[mask, col] = daily_record[col]
                    df_combined = df_existing
                else:
                    # Append new record
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(self.portfolio_history_file, index=False)
            logger.info(f"Daily snapshot saved for {today}")
            
        except Exception as e:
            logger.error(f"Error saving daily snapshot: {e}")
        
        return daily_record

    def save_portfolio_state(self, state=None):
        """Save current portfolio state"""
        if state is None:
            state = self.portfolio_state
        
        state['last_update'] = datetime.now().isoformat()
        
        with open(self.portfolio_state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info("Portfolio state saved")

    def generate_daily_summary(self) -> Dict:
        """Generate daily summary for dashboard"""
        portfolio_value = self.portfolio_state['portfolio_value']
        initial_capital = self.config['portfolio']['initial_capital']
        
        summary = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'portfolio_value': portfolio_value,
            'cash': self.portfolio_state['cash'],
            'total_return': portfolio_value - initial_capital,
            'total_return_pct': (portfolio_value - initial_capital) / initial_capital,
            'positions_count': len(self.portfolio_state['positions']),
            'data_source': 'Alpaca' if self.use_alpaca else 'Alpha Vantage',
            'positions': {}
        }
        
        # Add position details
        for symbol, position in self.portfolio_state['positions'].items():
            summary['positions'][symbol] = {
                'shares': position['shares'],
                'entry_price': position['entry_price'],
                'current_price': position['current_price'],
                'market_value': position['market_value'],
                'unrealized_pnl': position['unrealized_pnl'],
                'unrealized_pnl_pct': position['unrealized_pnl_pct'],
                'stop_level': position.get('stop_level', 0),
                'stop_type': position.get('stop_type', 'none'),
                'catalyst': position['catalyst']
            }
        
        return summary

    def get_alpaca_account_summary(self) -> Dict:
        """Get Alpaca account information for validation"""
        if not self.use_alpaca or not self.alpaca_client:
            return {}
            
        account_info = self.alpaca_client.get_account_info()
        if account_info:
            return {
                'alpaca_portfolio_value': account_info['portfolio_value'],
                'alpaca_cash': account_info['cash'],
                'alpaca_buying_power': account_info['buying_power'],
                'account_status': account_info['status']
            }
        return {}

    def run_daily_update(self) -> Dict:
        """Run complete daily update process"""
        data_source = "Alpaca" if self.use_alpaca else "Alpha Vantage"
        print(f"Starting daily portfolio update using {data_source}...")
        
        try:
            # 1. Sync with Alpaca positions first (places initial orders if needed)
            if self.use_alpaca:
                self.sync_with_alpaca_positions()
            
            # 2. Update stock prices
            self.update_stock_prices()
            
            # 3. Update trailing stop levels (executes actual stops in Alpaca)
            self.update_stop_levels()
            
            # 4. Update portfolio value
            portfolio_value = self.update_portfolio_value()
            
            # 5. Save daily snapshot
            daily_record = self.save_daily_snapshot()
            
            # 6. Save portfolio state
            self.save_portfolio_state()
            
            # 7. Generate summary
            summary = self.generate_daily_summary()
            
            # 8. Add Alpaca account info to summary
            if self.use_alpaca:
                alpaca_summary = self.get_alpaca_account_summary()
                summary.update(alpaca_summary)
            
            # 9. Save summary to docs for dashboard
            with open('docs/latest.json', 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            print(f"Daily update complete. Portfolio value: ${portfolio_value:.2f}")
            
            return summary
            
        except Exception as e:
            print(f"Error during daily update: {e}")
            raise

def main():
    """Main execution function"""
    tracker = MidCapPortfolioTracker()
    summary = tracker.run_daily_update()
    
    print(f"\n=== Mid-Cap Portfolio Update ===")
    print(f"Data Source: {summary['data_source']}")
    print(f"Date: {summary['date']}")
    print(f"Portfolio Value: ${summary['portfolio_value']:.2f}")
    print(f"Total Return: ${summary['total_return']:.2f} ({summary['total_return_pct']:.2%})")
    print(f"Cash: ${summary['cash']:.2f}")
    print(f"Positions: {summary['positions_count']}")
    
    if 'alpaca_portfolio_value' in summary:
        print(f"Alpaca Account Value: ${summary['alpaca_portfolio_value']:.2f}")
        print(f"Alpaca Status: {summary['account_status']}")
    
    if summary['positions']:
        print(f"\n=== Current Positions ===")
        for symbol, pos in summary['positions'].items():
            print(f"{symbol}: {pos['shares']} shares @ ${pos['current_price']:.2f}")
            print(f"  P&L: ${pos['unrealized_pnl']:.2f} ({pos['unrealized_pnl_pct']:.2%})")
            print(f"  Stop: ${pos['stop_level']:.2f} ({pos['stop_type']})")

if __name__ == "__main__":
    main()
