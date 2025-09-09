#!/usr/bin/env python3
"""
Benchmark Data Updater for Mid-Cap Experiment
Updates benchmark prices (MDY, SPY, IWM, QQQ) and saves to CSV
"""

import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_benchmark_data():
    """Fetch current benchmark prices"""
    benchmarks = {
        'MDY': 'SPDR S&P MidCap 400 ETF',
        'SPY': 'SPDR S&P 500 ETF',
        'IWM': 'iShares Russell 2000 ETF', 
        'QQQ': 'Invesco QQQ ETF'
    }
    
    benchmark_data = {}
    
    for symbol, name in benchmarks.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d')
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                benchmark_data[symbol] = {
                    'price': round(current_price, 2),
                    'name': name,
                    'timestamp': datetime.now().isoformat()
                }
                logger.info(f"Retrieved {symbol}: ${current_price:.2f}")
            else:
                logger.warning(f"No data retrieved for {symbol}")
                
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
    
    return benchmark_data

def save_benchmark_history(benchmark_data):
    """Save benchmark data to CSV history"""
    if not benchmark_data:
        logger.error("No benchmark data to save")
        return
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Prepare row for CSV
    today = datetime.now().date()
    row_data = {'date': today}
    
    for symbol, data in benchmark_data.items():
        row_data[f'{symbol}_price'] = data['price']
    
    # Create DataFrame
    df_new = pd.DataFrame([row_data])
    
    # File path
    csv_file = 'data/benchmark_history.csv'
    
    try:
        if os.path.exists(csv_file):
            # Read existing data
            df_existing = pd.read_csv(csv_file)
            df_existing['date'] = pd.to_datetime(df_existing['date']).dt.date
            
            # Check if today's data already exists
            if today in df_existing['date'].values:
                # Update today's row
                df_existing.loc[df_existing['date'] == today] = row_data
                df_combined = df_existing
                logger.info("Updated existing benchmark data for today")
            else:
                # Append new row
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                logger.info("Added new benchmark data row")
        else:
            # Create new file
            df_combined = df_new
            logger.info("Created new benchmark history file")
        
        # Save to CSV
        df_combined.to_csv(csv_file, index=False)
        logger.info(f"Saved benchmark data to {csv_file}")
        
    except Exception as e:
        logger.error(f"Error saving benchmark data: {e}")

def update_latest_benchmarks(benchmark_data):
    """Update latest benchmark data for dashboard"""
    if not benchmark_data:
        return
    
    try:
        # Create docs directory if it doesn't exist
        os.makedirs('docs', exist_ok=True)
        
        # Save latest benchmark data
        latest_file = 'docs/latest_benchmarks.json'
        
        import json
        with open(latest_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'benchmarks': benchmark_data
            }, f, indent=2)
        
        logger.info(f"Updated latest benchmarks in {latest_file}")
        
    except Exception as e:
        logger.error(f"Error updating latest benchmarks: {e}")

def calculate_benchmark_returns():
    """Calculate benchmark returns for comparison"""
    csv_file = 'data/benchmark_history.csv'
    
    if not os.path.exists(csv_file):
        logger.warning("No benchmark history file found")
        return
    
    try:
        df = pd.read_csv(csv_file)
        
        if len(df) < 2:
            logger.info("Not enough data for return calculations")
            return
        
        # Calculate returns for each benchmark
        returns_data = {}
        
        for col in df.columns:
            if col.endswith('_price'):
                symbol = col.replace('_price', '')
                prices = df[col].dropna()
                
                if len(prices) >= 2:
                    current_price = prices.iloc[-1]
                    start_price = prices.iloc[0]
                    total_return = (current_price - start_price) / start_price
                    
                    returns_data[symbol] = {
                        'start_price': round(start_price, 2),
                        'current_price': round(current_price, 2),
                        'total_return': round(total_return * 100, 2),
                        'days': len(prices)
                    }
        
        # Save returns data
        if returns_data:
            import json
            with open('docs/benchmark_returns.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'returns': returns_data
                }, f, indent=2)
            
            logger.info("Calculated and saved benchmark returns")
            
            # Log returns summary
            for symbol, data in returns_data.items():
                logger.info(f"{symbol}: {data['total_return']:+.2f}% over {data['days']} days")
        
    except Exception as e:
        logger.error(f"Error calculating benchmark returns: {e}")

def main():
    """Main execution function"""
    logger.info("Starting benchmark data update...")
    
    # Fetch benchmark data
    benchmark_data = get_benchmark_data()
    
    if benchmark_data:
        # Save to history
        save_benchmark_history(benchmark_data)
        
        # Update latest data
        update_latest_benchmarks(benchmark_data)
        
        # Calculate returns
        calculate_benchmark_returns()
        
        logger.info("Benchmark update completed successfully")
        
        # Print summary
        print("\n📊 BENCHMARK UPDATE SUMMARY")
        print("=" * 40)
        for symbol, data in benchmark_data.items():
            print(f"{symbol}: ${data['price']:.2f}")
        
    else:
        logger.error("Failed to fetch benchmark data")

if __name__ == "__main__":
    main()
