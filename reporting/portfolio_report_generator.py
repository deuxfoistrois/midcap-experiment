#!/usr/bin/env python3
"""
Portfolio Report Generator for Mid-Cap Experiment
Generates daily markdown and HTML reports with performance analysis
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta
import logging

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PortfolioReportGenerator:
    def __init__(self):
        # File paths (relative to parent directory)
        self.portfolio_state_file = '../state/portfolio_state.json'
        self.portfolio_history_file = '../data/portfolio_history.csv'
        self.benchmark_history_file = '../data/benchmark_history.csv'
        self.stop_history_file = '../data/stop_loss_history.csv'
        self.reports_dir = '../reports'
        
        # Create reports directory
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def load_portfolio_data(self):
        """Load all portfolio data"""
        data = {}
        
        # Portfolio state
        if os.path.exists(self.portfolio_state_file):
            with open(self.portfolio_state_file, 'r') as f:
                data['state'] = json.load(f)
        else:
            data['state'] = {}
        
        # Portfolio history
        if os.path.exists(self.portfolio_history_file):
            data['history'] = pd.read_csv(self.portfolio_history_file)
        else:
            data['history'] = pd.DataFrame()
        
        # Benchmark history
        if os.path.exists(self.benchmark_history_file):
            data['benchmarks'] = pd.read_csv(self.benchmark_history_file)
        else:
            data['benchmarks'] = pd.DataFrame()
        
        # Stop loss history
        if os.path.exists(self.stop_history_file):
            data['stops'] = pd.read_csv(self.stop_history_file)
        else:
            data['stops'] = pd.DataFrame()
        
        return data
    
    def calculate_performance_metrics(self, data):
        """Calculate key performance metrics"""
        state = data['state']
        history = data['history']
        
        metrics = {
            'current_value': state.get('portfolio_value', 1000),
            'cash': state.get('cash', 0),
            'total_return': 0,
            'total_return_pct': 0,
            'daily_change': 0,
            'daily_change_pct': 0,
            'positions_count': len(state.get('positions', {})),
            'days_active': 0,
            'best_day': 0,
            'worst_day': 0,
            'volatility': 0
        }
        
        initial_value = 1000
        current_value = metrics['current_value']
        
        # Total return
        metrics['total_return'] = current_value - initial_value
        metrics['total_return_pct'] = (current_value - initial_value) / initial_value * 100
        
        # Historical analysis
        if not history.empty and len(history) > 1:
            # Daily change
            if len(history) >= 2:
                yesterday_value = history['portfolio_value'].iloc[-2]
                metrics['daily_change'] = current_value - yesterday_value
                metrics['daily_change_pct'] = (current_value - yesterday_value) / yesterday_value * 100
            
            # Days active
            metrics['days_active'] = len(history)
            
            # Calculate daily returns for volatility and best/worst days
            history['daily_return'] = history['portfolio_value'].pct_change()
            
            if len(history) > 1:
                daily_returns = history['daily_return'].dropna()
                if not daily_returns.empty:
                    metrics['best_day'] = daily_returns.max() * 100
                    metrics['worst_day'] = daily_returns.min() * 100
                    metrics['volatility'] = daily_returns.std() * 100
        
        return metrics
    
    def calculate_benchmark_comparison(self, data):
        """Calculate performance vs benchmarks"""
        history = data['history']
        benchmarks = data['benchmarks']
        
        comparison = {}
        
        if not history.empty and not benchmarks.empty and len(history) > 1:
            # Get date ranges
            start_date = history['date'].iloc[0]
            end_date = history['date'].iloc[-1]
            
            # Portfolio return
            portfolio_start = history['portfolio_value'].iloc[0]
            portfolio_end = history['portfolio_value'].iloc[-1]
            portfolio_return = (portfolio_end - portfolio_start) / portfolio_start * 100
            
            # Benchmark returns
            benchmark_cols = [col for col in benchmarks.columns if col.endswith('_price')]
            
            for col in benchmark_cols:
                symbol = col.replace('_price', '')
                
                # Find matching date range in benchmarks
                benchmark_subset = benchmarks[benchmarks['date'].between(start_date, end_date)]
                
                if not benchmark_subset.empty and len(benchmark_subset) > 1:
                    benchmark_start = benchmark_subset[col].iloc[0]
                    benchmark_end = benchmark_subset[col].iloc[-1]
                    
                    if benchmark_start > 0:
                        benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
                        outperformance = portfolio_return - benchmark_return
                        
                        comparison[symbol] = {
                            'return': benchmark_return,
                            'outperformance': outperformance,
                            'start_price': benchmark_start,
                            'end_price': benchmark_end
                        }
        
        return comparison
    
    def analyze_positions(self, data):
        """Analyze individual positions"""
        positions = data['state'].get('positions', {})
        analysis = {}
        
        for symbol, position in positions.items():
            entry_price = position.get('entry_price', 0)
            current_price = position.get('current_price', 0)
            shares = position.get('shares', 0)
            stop_level = position.get('stop_level', 0)
            
            if entry_price > 0 and current_price > 0:
                pnl = shares * (current_price - entry_price)
                pnl_pct = (current_price - entry_price) / entry_price * 100
                
                analysis[symbol] = {
                    'shares': shares,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'market_value': shares * current_price,
                    'cost_basis': shares * entry_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'stop_level': stop_level,
                    'stop_distance_pct': (current_price - stop_level) / current_price * 100 if stop_level > 0 else 0,
                    'catalyst': position.get('catalyst', ''),
                    'sector': position.get('sector', ''),
                    'days_held': (datetime.now() - datetime.fromisoformat(position.get('entry_date', datetime.now().isoformat()))).days
                }
        
        return analysis
    
    def generate_markdown_report(self, data, metrics, comparison, positions):
        """Generate markdown report"""
        timestamp = datetime.now().strftime('%Y-%m-%d')
        report_file = f'{self.reports_dir}/portfolio_report_{timestamp}.md'
        
        try:
            with open(report_file, 'w') as f:
                # Header
                f.write(f"# Mid-Cap Portfolio Report - {timestamp}\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
                
                # Executive Summary
                f.write("## 📊 Executive Summary\n\n")
                f.write(f"- **Portfolio Value:** ${metrics['current_value']:,.2f}\n")
                f.write(f"- **Total Return:** ${metrics['total_return']:+,.2f} ({metrics['total_return_pct']:+.2f}%)\n")
                f.write(f"- **Daily Change:** ${metrics['daily_change']:+,.2f} ({metrics['daily_change_pct']:+.2f}%)\n")
                f.write(f"- **Cash Position:** ${metrics['cash']:,.2f}\n")
                f.write(f"- **Active Positions:** {metrics['positions_count']}\n")
                f.write(f"- **Days Active:** {metrics['days_active']}\n\n")
                
                # Performance Statistics
                f.write("## 📈 Performance Statistics\n\n")
                f.write(f"- **Best Day:** {metrics['best_day']:+.2f}%\n")
                f.write(f"- **Worst Day:** {metrics['worst_day']:+.2f}%\n")
                f.write(f"- **Volatility (1-day):** {metrics['volatility']:.2f}%\n\n")
                
                # Benchmark Comparison
                if comparison:
                    f.write("## 🏆 Benchmark Comparison\n\n")
                    f.write("| Benchmark | Return | Outperformance |\n")
                    f.write("|-----------|--------|----------------|\n")
                    for symbol, comp in comparison.items():
                        f.write(f"| {symbol} | {comp['return']:+.2f}% | {comp['outperformance']:+.2f}% |\n")
                    f.write("\n")
                
                # Position Analysis
                if positions:
                    f.write("## 💼 Position Analysis\n\n")
                    for symbol, pos in positions.items():
                        f.write(f"### {symbol} ({pos['sector']})\n")
                        f.write(f"- **Shares:** {pos['shares']}\n")
                        f.write(f"- **Entry Price:** ${pos['entry_price']:.2f}\n")
                        f.write(f"- **Current Price:** ${pos['current_price']:.2f}\n")
                        f.write(f"- **Market Value:** ${pos['market_value']:,.2f}\n")
                        f.write(f"- **P&L:** ${pos['pnl']:+,.2f} ({pos['pnl_pct']:+.2f}%)\n")
                        f.write(f"- **Stop Level:** ${pos['stop_level']:.2f} ({pos['stop_distance_pct']:.1f}% away)\n")
                        f.write(f"- **Catalyst:** {pos['catalyst']}\n")
                        f.write(f"- **Days Held:** {pos['days_held']}\n\n")
                
                # Risk Analysis
                f.write("## ⚠️ Risk Analysis\n\n")
                total_at_risk = sum(max(0, pos['shares'] * (pos['current_price'] - pos['stop_level'])) for pos in positions.values())
                f.write(f"- **Total Amount at Risk:** ${total_at_risk:.2f}\n")
                f.write(f"- **Portfolio Risk:** {total_at_risk / metrics['current_value'] * 100:.2f}%\n")
                
                # High-risk positions (within 5% of stop)
                high_risk = {symbol: pos for symbol, pos in positions.items() if pos['stop_distance_pct'] < 5}
                if high_risk:
                    f.write(f"- **High-Risk Positions:** {len(high_risk)} positions within 5% of stops\n")
                    for symbol in high_risk:
                        f.write(f"  - {symbol}: {high_risk[symbol]['stop_distance_pct']:.1f}% from stop\n")
                f.write("\n")
                
                # Footer
                f.write("---\n")
                f.write(f"*Report generated by Mid-Cap Experiment automated system*\n")
            
            logger.info(f"Generated markdown report: {report_file}")
            return report_file
            
        except Exception as e:
            logger.error(f"Error generating markdown report: {e}")
            return None
    
    def update_latest_report(self, data, metrics, comparison, positions):
        """Update latest report data for dashboard"""
        try:
            latest_data = {
                'timestamp': datetime.now().isoformat(),
                'performance': metrics,
                'benchmark_comparison': comparison,
                'positions': positions,
                'summary': {
                    'experiment_day': metrics['days_active'],
                    'total_return_pct': metrics['total_return_pct'],
                    'daily_change_pct': metrics['daily_change_pct'],
                    'positions_count': metrics['positions_count'],
                    'cash_pct': metrics['cash'] / metrics['current_value'] * 100
                }
            }
            
            # Save to docs for dashboard
            with open('../docs/latest_report.json', 'w') as f:
                json.dump(latest_data, f, indent=2, default=str)
            
            logger.info("Updated latest report data")
            
        except Exception as e:
            logger.error(f"Error updating latest report: {e}")
    
    def generate_report(self):
        """Generate complete portfolio report"""
        logger.info("Generating portfolio report...")
        
        # Load data
        data = self.load_portfolio_data()
        
        # Calculate metrics
        metrics = self.calculate_performance_metrics(data)
        comparison = self.calculate_benchmark_comparison(data)
        positions = self.analyze_positions(data)
        
        # Generate reports
        markdown_file = self.generate_markdown_report(data, metrics, comparison, positions)
        self.update_latest_report(data, metrics, comparison, positions)
        
        # Print summary
        self.print_summary(metrics, comparison, positions)
        
        return {
            'markdown_file': markdown_file,
            'metrics': metrics,
            'comparison': comparison,
            'positions': positions
        }
    
    def print_summary(self, metrics, comparison, positions):
        """Print report summary to console"""
        print("\n📊 PORTFOLIO REPORT SUMMARY")
        print("=" * 50)
        print(f"💰 Portfolio Value: ${metrics['current_value']:,.2f}")
        print(f"📈 Total Return: {metrics['total_return_pct']:+.2f}%")
        print(f"📅 Daily Change: {metrics['daily_change_pct']:+.2f}%")
        print(f"💼 Positions: {metrics['positions_count']}")
        print(f"⏱️ Days Active: {metrics['days_active']}")
        
        if comparison:
            print(f"\n🏆 Benchmark Outperformance:")
            for symbol, comp in comparison.items():
                print(f"   vs {symbol}: {comp['outperformance']:+.2f}%")
        
        if positions:
            print(f"\n💼 Top Performers:")
            sorted_positions = sorted(positions.items(), key=lambda x: x[1]['pnl_pct'], reverse=True)
            for symbol, pos in sorted_positions[:3]:
                print(f"   {symbol}: {pos['pnl_pct']:+.2f}%")

def main():
    """Main execution function"""
    generator = PortfolioReportGenerator()
    generator.generate_report()

if __name__ == "__main__":
    main()
