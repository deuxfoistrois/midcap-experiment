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

# Alpaca integration
try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-trade-api not installed. Using Alpha Vantage fallback.")

class AlpacaClient:
    def __init__(self):
        """Initialize Alpaca API client"""
        self.api_key_id = os.environ.get('ALPACA_API_KEY_ID')
        self.secret_key = os.environ.get('ALPACA_SECRET_KEY')
        self.base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not self.api_key_id or not self.secret_key:
            logger.error("Alpaca API credentials not found in environment variables")
            return
        
        try:
            self.api = tradeapi.REST(
                key_id=self.api_key_id,
                secret_key=self.secret_key,
                base_url=self.base_url,
                api_version='v2'
            )
            logger.info(f"Alpaca client initialized for: {self.base_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca client: {e}")
            self.api = None

    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            if not self.api:
                return False
            account = self.api.get_account()
            logger.info(f"Connected to Alpaca - Account Status: {account.status}")
            logger.info(f"Buying Power: ${float(account.buying_power):,.2f}")
            return True
        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")
            return False

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current stock price"""
        try:
            if not self.api:
                return None
            
            # Get latest quote
            quote = self.api.get_latest_quote(symbol)
            
            # Return mid price (average of bid and ask)
            if quote and hasattr(quote, 'bid_price') and hasattr(quote, 'ask_price'):
                if quote.bid_price and quote.ask_price:
                    mid_price = (float(quote.bid_price) + float(quote.ask_price)) / 2
                    return mid_price
            
            # Fallback to latest trade if quote not available
            trade = self.api.get_latest_trade(symbol)
            if trade and hasattr(trade, 'price') and trade.price:
                return float(trade.price)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def sync_portfolio_positions(self) -> Dict:
        """Get current positions from Alpaca"""
        try:
            if not self.api:
                return {}
            
            positions = self.api.list_positions()
            position_data = {}
            
            for pos in positions:
                position_data[pos.symbol] = {
                    'symbol': pos.symbol,
                    'shares': float(pos.qty),
                    'current_price': float(pos.market_value) / float(pos.qty) if float(pos.qty) > 0 else 0,
                    'market_value': float(pos.market_value),
                    'unrealized_pnl': float(pos.unrealized_pl),
                    'unrealized_pnl_pct': float(pos.unrealized_plpc),
                    'cost_basis': float(pos.cost_basis) if hasattr(pos, 'cost_basis') and pos.cost_basis else 0
                }
            
            return position_data
            
        except Exception as e:
            logger.error(f"Error syncing portfolio positions: {e}")
            return {}

class MidCapPortfolioTracker:
    def __init__(self, config_file='config.json'):
        """Initialize the portfolio tracker"""
        # Load configuration
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {config_file} not found")
            self.config = {}
        
        # File paths
        self.portfolio_state_file = 'state/portfolio_state.json'
        self.portfolio_history_file = 'data/portfolio_history.csv'
        
        # API setup
        self.api_key = os.environ.get('ALPHAVANTAGE_API_KEY')
        
        # Data source preference
        self.data_source = 'alpaca' if ALPACA_AVAILABLE else 'alpha_vantage'
        
        # Initialize Alpaca client if available
        self.alpaca_client = None
        self.use_alpaca = False
        
        if ALPACA_AVAILABLE:
            try:
                self.alpaca_client = AlpacaClient()
                if self.alpaca_client.test_connection():
                    self.use_alpaca = True
                    logger.info("Using Alpaca Markets for data and trading")
                else:
                    logger.warning("Alpaca connection failed, falling back to Alpha Vantage")
                    self.data_source = 'alpha_vantage'
            except Exception as e:
                logger.error(f"Error initializing Alpaca: {e}")
                self.data_source = 'alpha_vantage'
        
        if not self.use_alpaca:
            if not self.api_key:
                logger.error("No ALPHAVANTAGE_API_KEY found in environment variables")
            else:
                logger.info("Using Alpha Vantage for data")
        
        # Initialize portfolio state
        self.portfolio_state = self.load_portfolio_state()
        
        # Ensure directories exist
        os.makedirs('state', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('docs', exist_ok=True)
        os.makedirs('logs', exist_ok=True)

    def load_portfolio_state(self) -> Dict:
        """Load current portfolio state"""
        try:
            with open(self.portfolio_state_file, 'r') as f:
                state = json.load(f)
            logger.info("Portfolio state loaded successfully")
            return state
        except FileNotFoundError:
            logger.info("No existing portfolio state found, creating new state")
            return {
                "positions": {},
                "cash": 24.52,
                "portfolio_value": 1000.0,
                "last_update": datetime.now().isoformat(),
                "experiment_start": "2025-09-08T00:00:00"
            }

    def sync_with_alpaca_positions(self):
        """Sync portfolio with current Alpaca positions, respecting stop loss executions"""
        try:
            if not self.alpaca_client or not self.use_alpaca:
                logger.info("No Alpaca connection available")
                return

            logger.info("Syncing with Alpaca positions...")
            alpaca_positions = self.alpaca_client.sync_portfolio_positions()
            
            if not alpaca_positions:
                logger.info("No positions found in Alpaca account")
                return
            
            # Get current experiment symbols that should exist
            experiment_symbols = set(['CRNX', 'STRL', 'OTEX', 'ZION'])
            alpaca_symbols = set(alpaca_positions.keys())
            
            # Find positions that were sold (exist in experiment but not in Alpaca)
            sold_positions = experiment_symbols - alpaca_symbols
            
            if sold_positions:
                logger.info(f"Positions sold via stop loss: {sold_positions}")
                
                # Remove sold positions from portfolio state
                for symbol in sold_positions:
                    if symbol in self.portfolio_state['positions']:
                        logger.info(f"Removing {symbol} from portfolio (stop loss executed)")
                        del self.portfolio_state['positions'][symbol]
            
            # Update existing positions with current Alpaca data
            for symbol, alpaca_pos in alpaca_positions.items():
                if symbol in experiment_symbols:
                    if symbol not in self.portfolio_state['positions']:
                        # Add new position (shouldn't happen normally)
                        self.portfolio_state['positions'][symbol] = {
                            'symbol': symbol,
                            'shares': alpaca_pos['shares'],
                            'entry_price': alpaca_pos['current_price'],
                            'catalyst': 'N/A'
                        }
                    
                    # Update with current market data
                    self.portfolio_state['positions'][symbol].update({
                        'current_price': alpaca_pos['current_price'],
                        'market_value': alpaca_pos['market_value'],
                        'unrealized_pnl': alpaca_pos['unrealized_pnl'],
                        'unrealized_pnl_pct': alpaca_pos['unrealized_pnl_pct'],
                        'last_update': datetime.now().isoformat()
                    })
                    logger.info(f"Updated {symbol} with current Alpaca data")
            
            # Update portfolio totals
            self.update_portfolio_totals()
            
        except Exception as e:
            logger.error(f"Error during Alpaca sync: {e}")
            
    def update_portfolio_totals(self):
        """Recalculate portfolio totals after position changes"""
        try:
            total_value = 0
            for position in self.portfolio_state['positions'].values():
                total_value += position.get('market_value', 0)
            
            total_value += self.portfolio_state.get('cash', 0)
            
            self.portfolio_state['portfolio_value'] = total_value
            self.portfolio_state['positions_count'] = len(self.portfolio_state['positions'])
            self.portfolio_state['last_update'] = datetime.now().isoformat()
            
            logger.info(f"Portfolio totals updated - Value: ${total_value:.2f}, Positions: {len(self.portfolio_state['positions'])}")
            
        except Exception as e:
            logger.error(f"Error updating portfolio totals: {e}")

    def get_alpha_vantage_price(self, symbol: str) -> Optional[float]:
        """Fallback price fetching from Alpha Vantage"""
        if not self.api_key:
            return None
            
        try:
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'Global Quote' in data:
                price_str = data['Global Quote']['05. price']
                return float(price_str)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage price for {symbol}: {e}")
            return None

    def update_stock_prices(self):
        """Update prices only for positions that still exist in portfolio"""
        try:
            if not self.portfolio_state.get('positions'):
                logger.info("No positions to update")
                return
                
            for symbol in list(self.portfolio_state['positions'].keys()):
                try:
                    # Skip if position was removed by stop loss sync
                    if symbol not in self.portfolio_state['positions']:
                        continue
                        
                    if self.use_alpaca and self.alpaca_client:
                        price = self.alpaca_client.get_current_price(symbol)
                    else:
                        price = self.get_alpha_vantage_price(symbol)
                    
                    if price:
                        position = self.portfolio_state['positions'][symbol]
                        old_price = position.get('current_price', 0)
                        position['current_price'] = price
                        position['market_value'] = position['shares'] * price
                        
                        # Calculate P&L
                        cost_basis = position.get('cost_basis', position['shares'] * position.get('entry_price', price))
                        position['unrealized_pnl'] = position['market_value'] - cost_basis
                        position['unrealized_pnl_pct'] = position['unrealized_pnl'] / cost_basis if cost_basis > 0 else 0
                        position['last_update'] = datetime.now().isoformat()
                        
                        logger.info(f"Updated {symbol}: ${old_price:.2f} -> ${price:.2f}")
                    else:
                        logger.warning(f"Could not get price for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error updating {symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in update_stock_prices: {e}")

    def save_portfolio_state(self):
        """Save current portfolio state to file"""
        try:
            with open(self.portfolio_state_file, 'w') as f:
                json.dump(self.portfolio_state, f, indent=2, default=str)
            logger.info("Portfolio state saved successfully")
        except Exception as e:
            logger.error(f"Error saving portfolio state: {e}")

    def save_daily_snapshot(self):
        """Save daily portfolio snapshot to CSV"""
        try:
            # Calculate current totals
            positions_value = sum([pos.get('market_value', 0) for pos in self.portfolio_state['positions'].values()])
            cash = self.portfolio_state.get('cash', 0)
            total_value = positions_value + cash
            
            # Create record
            record = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'portfolio_value': total_value,
                'cash': cash,
                'positions_value': positions_value,
                'total_invested': 1000.0,
                'total_return': total_value - 1000.0,
                'total_return_pct': (total_value - 1000.0) / 1000.0,
                'positions_count': len(self.portfolio_state['positions'])
            }
            
            # Add individual position data
            for symbol in ['CRNX', 'STRL', 'OTEX', 'ZION']:
                if symbol in self.portfolio_state['positions']:
                    pos = self.portfolio_state['positions'][symbol]
                    record[f'{symbol}_price'] = pos.get('current_price', 0)
                    record[f'{symbol}_pnl'] = pos.get('unrealized_pnl', 0)
                    record[f'{symbol}_pnl_pct'] = pos.get('unrealized_pnl_pct', 0)
                else:
                    record[f'{symbol}_price'] = None
                    record[f'{symbol}_pnl'] = None
                    record[f'{symbol}_pnl_pct'] = None
            
            # Save to CSV
            df_new = pd.DataFrame([record])
            
            if os.path.exists(self.portfolio_history_file):
                df_existing = pd.read_csv(self.portfolio_history_file)
                # Remove today's entry if it exists
                today = datetime.now().strftime('%Y-%m-%d')
                df_existing = df_existing[df_existing['date'] != today]
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(self.portfolio_history_file, index=False)
            logger.info("Daily snapshot saved to CSV")
            
            return record
            
        except Exception as e:
            logger.error(f"Error saving daily snapshot: {e}")
            return {}

    def generate_daily_summary(self) -> Dict:
        """Generate summary for dashboard"""
        try:
            positions_value = sum([pos.get('market_value', 0) for pos in self.portfolio_state['positions'].values()])
            cash = self.portfolio_state.get('cash', 0)
            total_value = positions_value + cash
            total_return = total_value - 1000.0
            total_return_pct = total_return / 1000.0
            
            summary = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'data_source': self.data_source,
                'portfolio_value': total_value,
                'cash': cash,
                'positions_value': positions_value,
                'total_invested': 1000.0,
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'positions_count': len(self.portfolio_state['positions']),
                'positions': self.portfolio_state['positions'],
                'last_update': datetime.now().isoformat(),
                'experiment_start': "2025-09-08T00:00:00"
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return {}

    def run_daily_update(self):
        """Run complete daily portfolio update"""
        try:
            logger.info("Starting daily portfolio update")
            
            # 1. Sync with Alpaca positions first (handles stop losses)
            if self.use_alpaca:
                self.sync_with_alpaca_positions()
            
            # 2. Update stock prices for remaining positions
            self.update_stock_prices()
            
            # 3. Update portfolio totals
            self.update_portfolio_totals()
            
            # 4. Save portfolio state
            self.save_portfolio_state()
            
            # 5. Save daily snapshot
            daily_record = self.save_daily_snapshot()
            
            # 6. Generate summary for dashboard
            summary = self.generate_daily_summary()
            
            # 7. Save summary to docs for dashboard
            with open('docs/latest.json', 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            portfolio_value = summary.get('portfolio_value', 0)
            logger.info(f"Daily update complete. Portfolio value: ${portfolio_value:.2f}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error during daily update: {e}")
            raise

def main():
    """Main execution function"""
    try:
        tracker = MidCapPortfolioTracker()
        summary = tracker.run_daily_update()
        
        print(f"\n=== Mid-Cap Portfolio Update ===")
        print(f"Data Source: {summary.get('data_source', 'unknown')}")
        print(f"Date: {summary.get('date', 'unknown')}")
        print(f"Portfolio Value: ${summary.get('portfolio_value', 0):.2f}")
        print(f"Total Return: ${summary.get('total_return', 0):.2f} ({summary.get('total_return_pct', 0):.2%})")
        print(f"Cash: ${summary.get('cash', 0):.2f}")
        print(f"Positions: {summary.get('positions_count', 0)}")
        
        if summary.get('positions'):
            print(f"\n=== Current Positions ===")
            for symbol, pos in summary['positions'].items():
                print(f"{symbol}: {pos.get('shares', 0)} shares @ ${pos.get('current_price', 0):.2f}")
                print(f"  P&L: ${pos.get('unrealized_pnl', 0):.2f} ({pos.get('unrealized_pnl_pct', 0):.2%})")
                
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise

if __name__ == "__main__":
    main()
