#!/usr/bin/env python3
"""
Trailing Stops Report Generator for Mid-Cap Experiment
Generates comprehensive stop-loss analysis and saves reports
"""

import json
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrailingStopsReporter:
    def __init__(self):
        self.portfolio_state_file = 'state/portfolio_state.json'
        self.stop_history_file = 'data/stop_loss_history.csv'
        self.reports_dir = 'reports'
        
        # Create reports directory
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs('docs', exist_ok=True)
    
    def load_portfolio_state(self):
        """Load current portfolio state"""
        if os.path.exists(self.portfolio_state_file):
            with open(self.portfolio_state_file, 'r') as f:
                return json.load(f)
        return {"positions": {}}
    
    def calculate_stop_metrics(self, positions):
        """Calculate stop-loss related metrics"""
        if not positions:
            return {}
        
        total_portfolio_value = sum(pos.get('market_value', 0) for pos in positions.values())
        metrics = {
            'total_positions': len(positions),
            'positions_with_stops': 0,
            'total_at_risk': 0,
            'weighted_avg_stop_distance': 0,
            'trailing_stops_active': 0,
            'initial_stops_active': 0,
            'closest_stop_distance': float('inf'),
            'furthest_stop_distance': 0
        }
        
        total_weight = 0
        
        for symbol, position in positions.items():
            current_price = position.get('current_price', 0)
            stop_level = position.get('stop_level', 0)
            stop_type = position.get('stop_type', 'initial')
            market_value = position.get('market_value', 0)
            shares = position.get('shares', 0)
            
            if current_price > 0 and stop_level > 0:
                metrics['positions_with_stops'] += 1
                
                # Calculate stop distance
                stop_distance = (current_price - stop_level) / current_price
                
                # Amount at risk
                at_risk = shares * (current_price - stop_level) if current_price > stop_level else 0
                metrics['total_at_risk'] += max(0, at_risk)
                
                # Weighted average calculation
                if total_portfolio_value > 0:
                    weight = market_value / total_portfolio_value
                    metrics['weighted_avg_stop_distance'] += weight * stop_distance
                    total_weight += weight
                
                # Stop type counts
                if stop_type == 'trailing':
                    metrics['trailing_stops_active'] += 1
                else:
                    metrics['initial_stops_active'] += 1
                
                # Min/max distances
                metrics['closest_stop_distance'] = min(metrics['closest_stop_distance'], stop_distance)
                metrics['furthest_stop_distance'] = max(metrics['furthest_stop_distance'], stop_distance)
        
        # Finalize calculations
        if metrics['closest_stop_distance'] == float('inf'):
            metrics['closest_stop_distance'] = 0
        
        metrics['portfolio_risk_pct'] = (metrics['total_at_risk'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
        
        return metrics
    
    def analyze_stop_performance(self):
        """Analyze historical stop-loss performance"""
        if not os.path.exists(self.stop_history_file):
            return {}
        
        try:
            df = pd.read_csv(self.stop_history_file)
            
            if df.empty:
                return {}
            
            performance = {
                'total_stops_executed': len(df),
                'profitable_stops': len(df[df['pnl'] > 0]),
                'losing_stops': len(df[df['pnl'] <= 0]),
                'avg_pnl': df['pnl'].mean(),
                'avg_pnl_pct': df['pnl_pct'].mean() * 100,
                'avg_days_held': df['days_held'].mean(),
                'best_stop_pnl': df['pnl'].max(),
                'worst_stop_pnl': df['pnl'].min(),
                'success_rate': len(df[df['pnl'] > 0]) / len(df) * 100 if len(df) > 0 else 0
            }
            
            # Performance by stop type
            for stop_type in df['stop_type'].unique():
                type_df = df[df['stop_type'] == stop_type]
                performance[f'{stop_type}_count'] = len(type_df)
                performance[f'{stop_type}_avg_pnl_pct'] = type_df['pnl_pct'].mean() * 100
                performance[f'{stop_type}_success_rate'] = len(type_df[type_df['pnl'] > 0]) / len(type_df) * 100 if len(type_df) > 0 else 0
            
            return performance
            
        except Exception as e:
            logger.error(f"Error analyzing stop performance: {e}")
            return {}
    
    def generate_position_analysis(self, positions):
        """Generate detailed analysis for each position"""
        analysis = {}
        
        for symbol, position in positions.items():
            current_price = position.get('current_price', 0)
            entry_price = position.get('entry_price', 0)
            stop_level = position.get('stop_level', 0)
            stop_type = position.get('stop_type', 'initial')
            highest_price = position.get('highest_price', entry_price)
            
            if current_price > 0 and entry_price > 0:
                analysis[symbol] = {
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'stop_level': stop_level,
                    'stop_type': stop_type,
                    'gain_from_entry_pct': (current_price - entry_price) / entry_price * 100,
                    'distance_to_stop_pct': (current_price - stop_level) / current_price * 100 if stop_level > 0 else 0,
                    'distance_to_stop_dollars': current_price - stop_level if stop_level > 0 else 0,
                    'highest_price': highest_price,
                    'max_gain_pct': (highest_price - entry_price) / entry_price * 100,
                    'trailing_activated': stop_type == 'trailing',
                    'stop_protection_pct': (stop_level - entry_price) / entry_price * 100 if stop_level > 0 else -13.0,
                    'risk_level': self._assess_risk_level(current_price, stop_level)
                }
        
        return analysis
    
    def _assess_risk_level(self, current_price, stop_level):
        """Assess risk level based on stop distance"""
        if not current_price or not stop_level:
            return 'UNKNOWN'
        
        distance_pct = (current_price - stop_level) / current_price * 100
        
        if distance_pct < 2:
            return 'HIGH'
        elif distance_pct < 5:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def generate_alerts(self, position_analysis):
        """Generate stop-loss alerts"""
        alerts = []
        
        for symbol, analysis in position_analysis.items():
            distance_pct = analysis['distance_to_stop_pct']
            
            if distance_pct < 2:
                alerts.append({
                    'symbol': symbol,
                    'severity': 'HIGH',
                    'message': f"{symbol} is {distance_pct:.1f}% away from stop at ${analysis['stop_level']:.2f}",
                    'current_price': analysis['current_price'],
                    'stop_level': analysis['stop_level']
                })
            elif distance_pct < 5:
                alerts.append({
                    'symbol': symbol,
                    'severity': 'MEDIUM',
                    'message': f"{symbol} is {distance_pct:.1f}% away from stop at ${analysis['stop_level']:.2f}",
                    'current_price': analysis['current_price'],
                    'stop_level': analysis['stop_level']
                })
        
        return alerts
    
    def save_report_json(self, report_data):
        """Save comprehensive report as JSON"""
        report_file = 'docs/trailing_stops_report.json'
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            logger.info(f"Saved trailing stops report to {report_file}")
            
        except Exception as e:
            logger.error(f"Error saving JSON report: {e}")
    
    def save_report_markdown(self, report_data):
        """Save report as Markdown"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        report_file = f'{self.reports_dir}/trailing_stops_report_{timestamp}.md'
        
        try:
            with open(report_file, 'w') as f:
                f.write("# Trailing Stop-Loss Report\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Portfolio metrics
                metrics = report_data.get('portfolio_metrics', {})
                f.write("## Portfolio Stop-Loss Metrics\n\n")
                f.write(f"- **Total Positions:** {metrics.get('total_positions', 0)}\n")
                f.write(f"- **Positions with Stops:** {metrics.get('positions_with_stops', 0)}\n")
                f.write(f"- **Trailing Stops Active:** {metrics.get('trailing_stops_active', 0)}\n")
                f.write(f"- **Total Amount at Risk:** ${metrics.get('total_at_risk', 0):.2f}\n")
                f.write(f"- **Portfolio Risk:** {metrics.get('portfolio_risk_pct', 0):.2f}%\n")
                f.write(f"- **Average Stop Distance:** {metrics.get('weighted_avg_stop_distance', 0) * 100:.2f}%\n\n")
                
                # Position analysis
                position_analysis = report_data.get('position_analysis', {})
                if position_analysis:
                    f.write("## Position Analysis\n\n")
                    for symbol, analysis in position_analysis.items():
                        f.write(f"### {symbol}\n")
                        f.write(f"- **Current Price:** ${analysis['current_price']:.2f}\n")
                        f.write(f"- **Stop Level:** ${analysis['stop_level']:.2f} ({analysis['stop_type']})\n")
                        f.write(f"- **Distance to Stop:** {analysis['distance_to_stop_pct']:.2f}%\n")
                        f.write(f"- **Gain from Entry:** {analysis['gain_from_entry_pct']:+.2f}%\n")
                        f.write(f"- **Risk Level:** {analysis['risk_level']}\n\n")
                
                # Alerts
                alerts = report_data.get('alerts', [])
                if alerts:
                    f.write("## Active Alerts\n\n")
                    for alert in alerts:
                        f.write(f"- **{alert['severity']}:** {alert['message']}\n")
                    f.write("\n")
                
                # Historical performance
                performance = report_data.get('historical_performance', {})
                if performance.get('total_stops_executed', 0) > 0:
                    f.write("## Historical Stop Performance\n\n")
                    f.write(f"- **Total Stops Executed:** {performance['total_stops_executed']}\n")
                    f.write(f"- **Success Rate:** {performance['success_rate']:.1f}%\n")
                    f.write(f"- **Average P&L:** {performance['avg_pnl_pct']:+.2f}%\n")
                    f.write(f"- **Average Days Held:** {performance['avg_days_held']:.1f}\n")
            
            logger.info(f"Saved markdown report to {report_file}")
            
        except Exception as e:
            logger.error(f"Error saving markdown report: {e}")
    
    def generate_report(self):
        """Generate comprehensive trailing stops report"""
        logger.info("Generating trailing stops report...")
        
        # Load data
        portfolio_state = self.load_portfolio_state()
        positions = portfolio_state.get('positions', {})
        
        if not positions:
            logger.info("No positions found, generating empty report")
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'portfolio_metrics': {},
                'position_analysis': {},
                'alerts': [],
                'historical_performance': {}
            }
        else:
            # Generate analysis
            portfolio_metrics = self.calculate_stop_metrics(positions)
            position_analysis = self.generate_position_analysis(positions)
            alerts = self.generate_alerts(position_analysis)
            historical_performance = self.analyze_stop_performance()
            
            # Compile report
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'portfolio_metrics': portfolio_metrics,
                'position_analysis': position_analysis,
                'alerts': alerts,
                'historical_performance': historical_performance
            }
        
        # Save reports
        self.save_report_json(report_data)
        self.save_report_markdown(report_data)
        
        # Print summary
        self.print_summary(report_data)
        
        return report_data
    
    def print_summary(self, report_data):
        """Print report summary to console"""
        print("\n🛡️ TRAILING STOPS REPORT SUMMARY")
        print("=" * 50)
        
        metrics = report_data.get('portfolio_metrics', {})
        print(f"📊 Positions: {metrics.get('total_positions', 0)} total, {metrics.get('positions_with_stops', 0)} with stops")
        print(f"🎯 Trailing Stops: {metrics.get('trailing_stops_active', 0)} active")
        print(f"💰 Amount at Risk: ${metrics.get('total_at_risk', 0):.2f}")
        print(f"📏 Avg Stop Distance: {metrics.get('weighted_avg_stop_distance', 0) * 100:.2f}%")
        
        alerts = report_data.get('alerts', [])
        if alerts:
            print(f"\n⚠️ ACTIVE ALERTS: {len(alerts)}")
            for alert in alerts:
                print(f"   {alert['severity']}: {alert['symbol']} - {alert['message']}")
        else:
            print(f"\n✅ No active alerts")
        
        performance = report_data.get('historical_performance', {})
        if performance.get('total_stops_executed', 0) > 0:
            print(f"\n📈 Historical Performance:")
            print(f"   Stops Executed: {performance['total_stops_executed']}")
            print(f"   Success Rate: {performance['success_rate']:.1f}%")
            print(f"   Avg P&L: {performance['avg_pnl_pct']:+.2f}%")

def main():
    """Main execution function"""
    reporter = TrailingStopsReporter()
    reporter.generate_report()

if __name__ == "__main__":
    main()
