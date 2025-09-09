#!/usr/bin/env python3
"""
Migration Script: Adapt Micro-Cap Repository for Mid-Cap Experiment
This script helps migrate your existing micro-cap repo structure to mid-cap with trailing stops
"""

import os
import json
import shutil
import pandas as pd
from datetime import datetime
import argparse

def create_directory_structure():
    """Create the required directory structure for mid-cap experiment"""
    directories = [
        'data',
        'docs', 
        'reports',
        'state',
        '.github/workflows',
        'reporting'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created directory: {directory}")

def migrate_config_file():
    """Create new config.json for mid-cap experiment"""
    midcap_config = {
        "portfolio": {
            "experiment_name": "Mid-Cap Catalyst Experiment",
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "duration_days": 30,
            "initial_capital": 1000.00,
            "strategy": "catalyst-driven-midcap",
            "description": "30-Day Mid-Cap Trading Experiment with Trailing Stop-Loss"
        },
        "positions": {
            "max_positions": 4,
            "position_sizing": "equal_weight",
            "min_position_size": 200,
            "max_position_size": 300,
            "market_cap_range": {
                "min": 2000000000,
                "max": 10000000000
            }
        },
        "risk_management": {
            "stop_loss": {
                "type": "trailing",
                "initial_stop_pct": 0.13,
                "trailing_stop_pct": 0.12,
                "activation_gain_pct": 0.05,
                "grace_period_days": 1
            }
        },
        "symbols": [],
        "api": {
            "alphavantage_key": "ALPHAVANTAGE_API_KEY",
            "update_schedule": "20:20"
        },
        "benchmarks": {
            "primary": "MDY",
            "secondary": ["SPY", "IWM", "QQQ"]
        }
    }
    
    with open('config.json', 'w') as f:
        json.dump(midcap_config, f, indent=2)
    
    print("✓ Created mid-cap config.json")

def migrate_portfolio_history(source_file=None):
    """Migrate existing portfolio history or create new structure"""
    if source_file and os.path.exists(source_file):
        # Copy existing history
        try:
            df = pd.read_csv(source_file)
            # Rename columns if needed for mid-cap structure
            column_mapping = {
                'Date': 'date',
                'Portfolio_Value': 'portfolio_value',
                'Cash': 'cash',
                'Total_Return': 'total_return',
                'Total_Return_Pct': 'total_return_pct'
            }
            
            df.rename(columns=column_mapping, inplace=True)
            df.to_csv('data/portfolio_history.csv', index=False)
            print(f"✓ Migrated portfolio history from {source_file}")
            
        except Exception as e:
            print(f"⚠ Error migrating portfolio history: {e}")
            create_empty_history()
    else:
        create_empty_history()

def create_empty_history():
    """Create empty portfolio history file with proper structure"""
    columns = [
        'date', 'portfolio_value', 'cash', 'positions_value', 
        'total_invested', 'total_return', 'total_return_pct', 
        'positions_count', 'MDY_price', 'SPY_price', 'IWM_price'
    ]
    
    df = pd.DataFrame(columns=columns)
    df.to_csv('data/portfolio_history.csv', index=False)
    print("✓ Created empty portfolio history file")

def create_stop_loss_files():
    """Create stop loss tracking files"""
    # Stop loss history
    stop_columns = [
        'date', 'symbol', 'action', 'shares', 'price', 'proceeds',
        'pnl', 'pnl_pct', 'stop_type', 'entry_price', 'days_held'
    ]
    
    df_stops = pd.DataFrame(columns=stop_columns)
    df_stops.to_csv('data/stop_loss_history.csv', index=False)
    
    # Benchmark data placeholder
    benchmark_columns = ['date', 'MDY', 'SPY', 'IWM', 'QQQ']
    df_benchmarks = pd.DataFrame(columns=benchmark_columns)
    df_benchmarks.to_csv('data/benchmark_data.csv', index=False)
    
    print("✓ Created stop loss tracking files")

def create_initial_portfolio_state():
    """Create initial portfolio state file"""
    initial_state = {
        "positions": {},
        "cash": 1000.00,
        "portfolio_value": 1000.00,
        "last_update": None,
        "experiment_start": datetime.now().isoformat(),
        "stop_loss_config": {
            "initial_stop_pct": 0.13,
            "trailing_stop_pct": 0.12,
            "activation_gain_pct": 0.05
        }
    }
    
    with open('state/portfolio_state.json', 'w') as f:
        json.dump(initial_state, f, indent=2)
    
    print("✓ Created initial portfolio state")

def copy_github_workflows():
    """Create GitHub Actions workflows for automation"""
    workflow_content = """name: Mid-Cap Portfolio Daily Update

on:
  schedule:
    - cron: '20 20 * * 1-5'  # 8:20 PM UTC, Mon-Fri
  workflow_dispatch:

jobs:
  update-portfolio:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - run: |
        pip install -r requirements.txt
        python main.py
      env:
        ALPHAVANTAGE_API_KEY: ${{ secrets.ALPHAVANTAGE_API_KEY }}
    - run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add .
        git diff --staged --quiet || git commit -m "📈 Daily update $(date +'%Y-%m-%d')"
        git push
"""
    
    with open('.github/workflows/midcap_schedule.yml', 'w') as f:
        f.write(workflow_content)
    
    print("✓ Created GitHub Actions workflow")

def create_dashboard_template():
    """Create basic dashboard template in docs/"""
    dashboard_json = {
        "date": datetime.now().isoformat(),
        "portfolio_value": 1000.00,
        "cash": 1000.00,
        "total_return": 0.00,
        "total_return_pct": 0.00,
        "positions_count": 0,
        "positions": {}
    }
    
    with open('docs/latest.json', 'w') as f:
        json.dump(dashboard_json, f, indent=2)
    
    print("✓ Created dashboard data template")

def backup_existing_files():
    """Backup existing files before migration"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    files_to_backup = [
        'config.json',
        'main.py', 
        'data/portfolio_history.csv',
        'state/portfolio_state.json'
    ]
    
    backed_up = []
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            os.makedirs(f"{backup_dir}/{os.path.dirname(file_path)}", exist_ok=True)
            shutil.copy2(file_path, f"{backup_dir}/{file_path}")
            backed_up.append(file_path)
    
    if backed_up:
        print(f"✓ Backed up {len(backed_up)} files to {backup_dir}/")
        return backup_dir
    else:
        print("ℹ No existing files to backup")
        return None

def update_requirements():
    """Update requirements.txt for mid-cap experiment"""
    requirements = [
        "pandas>=1.5.0",
        "yfinance>=0.2.0", 
        "requests>=2.28.0",
        "numpy>=1.24.0",
        "matplotlib>=3.6.0",
        "seaborn>=0.12.0",
        "openpyxl>=3.1.0",
        "python-dateutil>=2.8.0",
        "plotly>=5.15.0",
        "jinja2>=3.1.0"
    ]
    
    with open('requirements.txt', 'w') as f:
        f.write('\n'.join(requirements))
    
    print("✓ Updated requirements.txt")

def create_migration_summary():
    """Create summary of migration changes"""
    summary = f"""
# Mid-Cap Migration Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Files Created/Modified:
- config.json (updated for mid-cap strategy)
- main.py (new with trailing stop-loss)
- trailing_stops.py (new stop-loss manager)
- requirements.txt (updated dependencies)
- .github/workflows/midcap_schedule.yml (new automation)
- docs/index.html (new dashboard)
- data/portfolio_history.csv (migrated/created)
- data/stop_loss_history.csv (new)
- state/portfolio_state.json (updated structure)

## Key Changes:
1. Trailing stop-loss system (vs static stops)
2. Mid-cap focus ($2B-$10B market cap)
3. Advanced risk management
4. Real-time dashboard with stop monitoring
5. Automated GitHub Actions workflows
6. Professional analytics and reporting

## Next Steps:
1. Set ALPHAVANTAGE_API_KEY in GitHub secrets
2. Review config.json settings
3. Add initial positions using add_position.py
4. Monitor daily automation via GitHub Actions
5. View live dashboard at: https://yourusername.github.io/repo-name

## Configuration:
- Initial Stop: 13% below entry
- Trailing Stop: 12% below highest price
- Activation: 5% gain triggers trailing
- Max Positions: 4
- Target Market Cap: $2B-$10B
"""
    
    with open('MIGRATION_SUMMARY.md', 'w') as f:
        f.write(summary)
    
    print("✓ Created migration summary")

def main():
    """Main migration function"""
    parser = argparse.ArgumentParser(description="Migrate micro-cap repo to mid-cap experiment")
    parser.add_argument('--source-history', help='Path to existing portfolio_history.csv')
    parser.add_argument('--backup', action='store_true', help='Backup existing files')
    parser.add_argument('--force', action='store_true', help='Overwrite existing files')
    
    args = parser.parse_args()
    
    print("🔄 Starting Mid-Cap Migration...")
    print("=" * 50)
    
    # Backup if requested
    if args.backup:
        backup_dir = backup_existing_files()
    
    # Create directory structure
    create_directory_structure()
    
    # Create/update configuration files
    migrate_config_file()
    update_requirements()
    
    # Create data files
    migrate_portfolio_history(args.source_history)
    create_stop_loss_files()
    create_initial_portfolio_state()
    
    # Create automation
    copy_github_workflows()
    create_dashboard_template()
    
    # Create summary
    create_migration_summary()
    
    print("=" * 50)
    print("✅ Migration Complete!")
    print("\n📋 Next Steps:")
    print("1. Add ALPHAVANTAGE_API_KEY to GitHub secrets")
    print("2. Review config.json settings")
    print("3. Run: python main.py (test locally)")
    print("4. Commit and push to enable automation")
    print("5. View dashboard at GitHub Pages URL")
    print("\n📊 Key Features Added:")
    print("- Trailing stop-loss system")
    print("- Real-time risk monitoring") 
    print("- Advanced analytics dashboard")
    print("- Automated daily updates")
    print("\nSee MIGRATION_SUMMARY.md for complete details.")

if __name__ == "__main__":
    main()
