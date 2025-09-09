#!/usr/bin/env python3
"""
Mid-Cap Trading Experiment - Main Portfolio Tracker
Enhanced version with trailing stop-loss capabilities
"""

import json
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import requests
from typing import Dict, List, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MidCapPortfolioTracker:
    def __init__(self, config_file='config.json'):
        """Initialize the portfolio tracker with configuration"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.api_key = os.environ.get('ALPHAVANTAGE_API_KEY')
        self.portfolio_state_file = 'state/portfolio_state.json'
        self.portfolio_history_file = 'data/portfolio_history.csv'
        self.stop_loss_history_file = 'data/stop_loss_history.csv'
        
        # Create directories
        os.makedirs('state', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('docs', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        # Load current portfolio state
        self.portfolio_state = self.load_portfolio_state()
        
    def load_portfolio_state(self) -> Dict:
        """Load current portfolio state from file"""
        if os.path.exists(self.portfolio_state_file):
            with open(self.portfolio_state_file, 'r') as f:
                return json.load(f)
        else:
            return {
                "positions": {},
                "cash": self.config['portfolio']['initial_capital'],
                "portfolio_value": self.config['portfolio']['initial_capital'],
                "last_update": None
            }
    
    def save_portfolio_state(self):
        """Save current portfolio state to file"""
        with open(self.portfolio_state_file, 'w') as f:
            json.dump(self.portfolio_state, f, indent=2, default=str)
    
    def get_stock_price(self, symbol: str) -> Dict:
        """Get current stock price using Alpha Vantage API"""
        if not self.api_key:
            logger.error("Alpha Vantage API key not found")
            return None
            
        url = f'https://www.alphavantage.co/query'
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'Global Quote' in data:
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
    
    def calculate_trailing_stop(self, symbol: str, current_price: float) -> Tuple[float, str]:
        """Calculate trailing stop loss level"""
        if symbol not in self.portfolio_state['positions']:
            return None, "No position"
        
        position = self.portfolio_state['positions'][symbol]
        entry_price = position['entry_price']
        highest_price = position.get('highest_price', entry_price)
        
        # Update highest price if current price is higher
        if current_price > highest_price:
            highest_price = current_price
            self.portfolio_state['positions'][symbol]['highest_price'] = highest_price
        
        # Calculate gain from entry
        gain_from_entry = (current_price - entry_price) / entry_price
        
        # Determine stop type and level
        if gain_from_entry < self.config['risk_management']['stop_loss']['activation_gain_pct']:
            # Use initial stop loss
            stop_level = entry_price * (1 - self.config['risk_management']['stop_loss']['initial_stop_pct'])
            stop_type = "initial"
        else:
            # Use trailing stop loss
            stop_level = highest_price * (1 - self.config['risk_management']['stop_loss']['trailing_stop_pct'])
            stop_type = "trailing"
        
        return stop_level, stop_type
    
    def check_stop_loss_triggers(self) -> List[Dict]:
        """Check if any positions have triggered stop losses"""
        triggered_stops = []
        
        for symbol in self.portfolio_state['positions']:
            position = self.portfolio_state['positions'][symbol]
            price_data = self.get_stock_price(symbol)
            
            if price_data:
                current_price = price_data['price']
                stop_level, stop_type = self.calculate_trailing_stop(symbol, current_price)
                
                # Update position with current data
                position['current_price'] = current_price
                position['stop_level'] = stop_level
                position['stop_type'] = stop_type
                
                # Check if stop is triggered
                if current_price <= stop_level:
                    triggered_stops.append({
                        'symbol': symbol,
                        'current_price': current_price,
                        'stop_level': stop_level,
                        'stop_type': stop_type,
                        'position': position
                    })
        
        return triggered_stops
    
    def execute_stop_loss(self, symbol: str, price: float, stop_type: str):
        """Execute stop loss for a position"""
        if symbol not in self.portfolio_state['positions']:
            return False
        
        position = self.portfolio_state['positions'][symbol]
        shares = position['shares']
        entry_price = position['entry_price']
        
        # Calculate P&L
        proceeds = shares * price
        cost_basis = shares * entry_price
        pnl = proceeds - cost_basis
        pnl_pct = (price - entry_price) / entry_price
        
        # Add to cash
        self.portfolio_state['cash'] += proceeds
        
        # Log the trade
        trade_record = {
            'date': datetime.now().isoformat(),
            'symbol': symbol,
            'action': 'SELL_STOP',
            'shares': shares,
            'price': price,
            'proceeds': proceeds,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'stop_type': stop_type,
            'entry_price': entry_price,
            'days_held': (datetime.now().date() - datetime.fromisoformat(position['entry_date']).date()).days
        }
        
        # Remove position
        del self.portfolio_state['positions'][symbol]
        
        # Save stop loss to history
        self.save_stop_loss_history(trade_record)
        
        logger.info(f"STOP LOSS EXECUTED: {symbol} at ${price:.2f} ({stop_type}), P&L: ${pnl:.2f} ({pnl_pct:.2%})")
        
        return True
    
    def save_stop_loss_history(self, trade_record: Dict):
        """Save stop loss execution to history file"""
        df_new = pd.DataFrame([trade_record])
        
        if os.path.exists(self.stop_loss_history_file):
            df_existing = pd.read_csv(self.stop_loss_history_file)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new
        
        df_combined.to_csv(self.stop_loss_history_file, index=False)
    
    def update_portfolio_value(self):
        """Update current portfolio value and metrics"""
        total_position_value = 0
        
        for symbol in self.portfolio_state['positions']:
            position = self.portfolio_state['positions'][symbol]
            price_data = self.get_stock_price(symbol)
            
            if price_data:
                current_price = price_data['price']
                shares = position['shares']
                market_value = shares * current_price
                
                # Update position data
                position['current_price'] = current_price
                position['market_value'] = market_value
                position['unrealized_pnl'] = market_value - (shares * position['entry_price'])
                position['unrealized_pnl_pct'] = (current_price - position['entry_price']) / position['entry_price']
                
                # Update stop levels
                stop_level, stop_type = self.calculate_trailing_stop(symbol, current_price)
                position['stop_level'] = stop_level
                position['stop_type'] = stop_type
                
                total_position_value += market_value
        
        # Update portfolio totals
        self.portfolio_state['portfolio_value'] = self.portfolio_state['cash'] + total_position_value
        self.portfolio_state['last_update'] = datetime.now().isoformat()
        
        return self.portfolio_state['portfolio_value']
    
    def get_benchmark_prices(self) -> Dict:
        """Get benchmark ETF prices"""
        benchmarks = {}
        symbols = [self.config['benchmarks']['primary']] + self.config['benchmarks']['secondary']
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d')
                if not hist.empty:
                    benchmarks[symbol] = hist['Close'].iloc[-1]
            except Exception as e:
                logger.error(f"Error getting benchmark price for {symbol}: {e}")
        
        return benchmarks
    
    def save_daily_snapshot(self):
        """Save daily portfolio snapshot to history"""
        portfolio_value = self.portfolio_state['portfolio_value']
        cash = self.portfolio_state['cash']
        
        # Calculate total invested
        total_cost_basis = sum(
            pos['shares'] * pos['entry_price'] 
            for pos in self.portfolio_state['positions'].values()
        )
        
        # Get benchmark prices
        benchmarks = self.get_benchmark_prices()
        
        # Create daily record
        daily_record = {
            'date': datetime.now().date(),
            'portfolio_value': portfolio_value,
            'cash': cash,
            'positions_value': portfolio_value - cash,
            'total_invested': total_cost_basis + cash,
            'total_return': portfolio_value - self.config['portfolio']['initial_capital'],
            'total_return_pct': (portfolio_value - self.config['portfolio']['initial_capital']) / self.config['portfolio']['initial_capital'],
            'positions_count': len(self.portfolio_state['positions']),
            **{f'{symbol}_price': price for symbol, price in benchmarks.items()}
        }
        
        # Save to CSV
        df_new = pd.DataFrame([daily_record])
        
        if os.path.exists(self.portfolio_history_file):
            df_existing = pd.read_csv(self.portfolio_history_file)
            # Check if today's record already exists
            df_existing['date'] = pd.to_datetime(df_existing['date']).dt.date
            today = datetime.now().date()
            
            if today in df_existing['date'].values:
                # Remove existing today's record and append new one
                df_existing = df_existing[df_existing['date'] != today]
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                logger.info("Updated existing daily record")
            else:
                # Append new record
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                logger.info("Added new daily record")
        else:
            df_combined = df_new
            logger.info("Created new portfolio history file")
        
        # Sort by date to ensure chronological order
        df_combined = df_combined.sort_values('date').reset_index(drop=True)
        
        df_combined.to_csv(self.portfolio_history_file, index=False)
        
        return daily_record
    
    def generate_daily_summary(self) -> Dict:
        """Generate daily portfolio summary"""
        portfolio_value = self.portfolio_state['portfolio_value']
        initial_capital = self.config['portfolio']['initial_capital']
        
        summary = {
            'date': datetime.now().date().isoformat(),
            'portfolio_value': portfolio_value,
            'cash': self.portfolio_state['cash'],
            'total_return': portfolio_value - initial_capital,
            'total_return_pct': (portfolio_value - initial_capital) / initial_capital,
            'positions_count': len(self.portfolio_state['positions']),
            'positions': {}
        }
        
        # Add position details
        for symbol, position in self.portfolio_state['positions'].items():
            summary['positions'][symbol] = {
                'shares': position['shares'],
                'entry_price': position['entry_price'],
                'current_price': position.get('current_price', 0),
                'market_value': position.get('market_value', 0),
                'unrealized_pnl': position.get('unrealized_pnl', 0),
                'unrealized_pnl_pct': position.get('unrealized_pnl_pct', 0),
                'stop_level': position.get('stop_level', 0),
                'stop_type': position.get('stop_type', 'initial'),
                'days_held': (datetime.now().date() - datetime.fromisoformat(position['entry_date']).date()).days
            }
        
        return summary
    
    def run_daily_update(self):
        """Run complete daily portfolio update"""
        logger.info("Starting daily portfolio update...")
        
        # 1. Check for stop loss triggers
        triggered_stops = self.check_stop_loss_triggers()
        
        # 2. Execute stop losses if any
        for stop in triggered_stops:
            self.execute_stop_loss(
                stop['symbol'], 
                stop['current_price'], 
                stop['stop_type']
            )
        
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
        
        logger.info(f"Daily update complete. Portfolio value: ${portfolio_value:.2f}")
        
        return summary

def main():
    """Main execution function"""
    tracker = MidCapPortfolioTracker()
    summary = tracker.run_daily_update()
    
    print(f"\n=== Mid-Cap Portfolio Update ===")
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
