#!/usr/bin/env python3
"""
Mid-Cap Portfolio Tracker with Advanced Trailing Stop-Loss
Professional portfolio management system
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
        self.base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
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
                    logger.info("Using Alpaca Markets for data")
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
        """Update trailing stop levels using TrailingStopManager"""
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

    def run_daily_update(self) -> Dict:
        """Run complete daily update process"""
        data_source = "Alpaca" if self.use_alpaca else "Alpha Vantage"
        print(f"Starting daily portfolio update using {data_source}...")
        
        try:
            # 1. Update stock prices
            self.update_stock_prices()
            
            # 2. Update trailing stop levels
            self.update_stop_levels()
            
            # 3. Update portfolio value
            portfolio_value = self.update_portfolio_value()
            
            # 4. Save daily snapshot
            daily_record = self.save_daily_snapshot()
            
            # 5. Save portfolio state
            self.save_portfolio_state()
            
            # 6. Generate summary
            summary = self.generate_daily_summary()
            
            # 7. Save summary to docs for dashboard
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
    
    if summary['positions']:
        print(f"\n=== Current Positions ===")
        for symbol, pos in summary['positions'].items():
            print(f"{symbol}: {pos['shares']} shares @ ${pos['current_price']:.2f}")
            print(f"  P&L: ${pos['unrealized_pnl']:.2f} ({pos['unrealized_pnl_pct']:.2%})")
            print(f"  Stop: ${pos['stop_level']:.2f} ({pos['stop_type']})")

if __name__ == "__main__":
    main()
