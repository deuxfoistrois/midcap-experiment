#!/usr/bin/env python3
"""
Trailing Stop Loss Manager for Mid-Cap Experiment
Advanced stop-loss management with multiple algorithms
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class TrailingStopManager:
    def __init__(self, config_file='config.json'):
        """Initialize trailing stop manager"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.stop_config = self.config['risk_management']['stop_loss']
        self.stop_history_file = 'data/stop_loss_history.csv'
        self.alerts_file = 'data/stop_alerts.json'
        
    def calculate_initial_stop(self, entry_price: float) -> float:
        """Calculate initial stop loss level"""
        return entry_price * (1 - self.stop_config['initial_stop_pct'])
    
    def calculate_trailing_stop(self, highest_price: float) -> float:
        """Calculate trailing stop loss level"""
        return highest_price * (1 - self.stop_config['trailing_stop_pct'])
    
    def should_activate_trailing(self, entry_price: float, current_price: float) -> bool:
        """Check if trailing stop should be activated"""
        gain_pct = (current_price - entry_price) / entry_price
        return gain_pct >= self.stop_config['activation_gain_pct']
    
    def update_stop_levels(self, positions: Dict) -> Dict:
        """Update stop levels for all positions"""
        updated_positions = {}
        
        for symbol, position in positions.items():
            updated_position = position.copy()
            
            entry_price = position['entry_price']
            current_price = position.get('current_price', entry_price)
            highest_price = position.get('highest_price', entry_price)
            
            # Update highest price if current is higher
            if current_price > highest_price:
                highest_price = current_price
                updated_position['highest_price'] = highest_price
            
            # Determine stop type and level
            if self.should_activate_trailing(entry_price, current_price):
                # Use trailing stop
                stop_level = self.calculate_trailing_stop(highest_price)
                stop_type = "trailing"
                
                # Ensure trailing stop never goes below initial stop
                initial_stop = self.calculate_initial_stop(entry_price)
                stop_level = max(stop_level, initial_stop)
            else:
                # Use initial stop
                stop_level = self.calculate_initial_stop(entry_price)
                stop_type = "initial"
            
            # Update position with stop data
            updated_position.update({
                'stop_level': stop_level,
                'stop_type': stop_type,
                'highest_price': highest_price,
                'stop_distance': (current_price - stop_level) / current_price,
                'stop_distance_dollars': current_price - stop_level
            })
            
            updated_positions[symbol] = updated_position
        
        return updated_positions
    
    def check_stop_violations(self, positions: Dict) -> List[Dict]:
        """Check for stop loss violations"""
        violations = []
        
        for symbol, position in positions.items():
            current_price = position.get('current_price')
            stop_level = position.get('stop_level')
            
            if current_price and stop_level and current_price <= stop_level:
                violation = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'stop_level': stop_level,
                    'stop_type': position.get('stop_type', 'unknown'),
                    'violation_amount': stop_level - current_price,
                    'violation_pct': (stop_level - current_price) / stop_level,
                    'entry_price': position['entry_price'],
                    'shares': position['shares'],
                    'position_value': position.get('market_value', 0),
                    'timestamp': datetime.now().isoformat()
                }
                violations.append(violation)
        
        return violations
    
    def calculate_risk_metrics(self, positions: Dict) -> Dict:
        """Calculate portfolio risk metrics related to stops"""
        total_portfolio_value = sum(pos.get('market_value', 0) for pos in positions.values())
        
        if total_portfolio_value == 0:
            return {}
        
        # Calculate weighted average stop distance
        weighted_stop_distance = 0
        total_at_risk = 0
        
        for symbol, position in positions.items():
            market_value = position.get('market_value', 0)
            stop_distance = position.get('stop_distance', 0)
            
            if market_value > 0:
                weight = market_value / total_portfolio_value
                weighted_stop_distance += weight * stop_distance
                
                # Calculate amount at risk (from current price to stop)
                current_price = position.get('current_price', 0)
                stop_level = position.get('stop_level', 0)
                shares = position.get('shares', 0)
                
                if current_price > 0 and stop_level > 0:
                    at_risk = shares * (current_price - stop_level)
                    total_at_risk += max(0, at_risk)
        
        return {
            'weighted_avg_stop_distance': weighted_stop_distance,
            'total_amount_at_risk': total_at_risk,
            'portfolio_risk_pct': total_at_risk / total_portfolio_value if total_portfolio_value > 0 else 0,
            'positions_with_stops': len([p for p in positions.values() if p.get('stop_level', 0) > 0])
        }
    
    def generate_stop_alerts(self, positions: Dict) -> List[Dict]:
        """Generate alerts for positions approaching stop levels"""
        alerts = []
        warning_thresholds = [0.02, 0.05, 0.10]  # 2%, 5%, 10% away from stop
        
        for symbol, position in positions.items():
            current_price = position.get('current_price', 0)
            stop_level = position.get('stop_level', 0)
            
            if current_price > 0 and stop_level > 0:
                distance_to_stop = (current_price - stop_level) / current_price
                
                for threshold in warning_thresholds:
                    if distance_to_stop <= threshold:
                        alert = {
                            'symbol': symbol,
                            'alert_type': f'STOP_WARNING_{int(threshold*100)}PCT',
                            'current_price': current_price,
                            'stop_level': stop_level,
                            'distance_to_stop': distance_to_stop,
                            'stop_type': position.get('stop_type', 'unknown'),
                            'severity': 'HIGH' if threshold <= 0.02 else 'MEDIUM' if threshold <= 0.05 else 'LOW',
                            'timestamp': datetime.now().isoformat(),
                            'message': f"{symbol} is {distance_to_stop:.2%} away from {position.get('stop_type', 'stop')} stop at ${stop_level:.2f}"
                        }
                        alerts.append(alert)
                        break  # Only add one alert per position (highest severity)
        
        return alerts
    
    def save_stop_execution(self, trade_record: Dict):
        """Save stop loss execution to history"""
        # Add additional stop-specific fields
        trade_record.update({
            'stop_execution_time': datetime.now().isoformat(),
            'execution_type': 'AUTOMATIC_STOP',
            'slippage': 0,  # Would be calculated if using real execution
        })
        
        # Save to CSV
        df_new = pd.DataFrame([trade_record])
        
        try:
            if pd.io.common.file_exists(self.stop_history_file):
                df_existing = pd.read_csv(self.stop_history_file)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(self.stop_history_file, index=False)
            logger.info(f"Stop execution saved: {trade_record['symbol']} at ${trade_record['price']:.2f}")
            
        except Exception as e:
            logger.error(f"Error saving stop execution: {e}")
    
    def save_alerts(self, alerts: List[Dict]):
        """Save stop alerts to file"""
        if alerts:
            with open(self.alerts_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'alerts': alerts
                }, f, indent=2)
    
    def get_stop_performance_stats(self) -> Dict:
        """Get performance statistics for stop losses"""
        try:
            if not pd.io.common.file_exists(self.stop_history_file):
                return {}
            
            df = pd.read_csv(self.stop_history_file)
            
            if df.empty:
                return {}
            
            stats = {
                'total_stops_executed': len(df),
                'profitable_stops': len(df[df['pnl'] > 0]),
                'losing_stops': len(df[df['pnl'] <= 0]),
                'avg_pnl': df['pnl'].mean(),
                'avg_pnl_pct': df['pnl_pct'].mean(),
                'avg_days_held': df['days_held'].mean(),
                'best_stop': df['pnl'].max(),
                'worst_stop': df['pnl'].min(),
                'stop_success_rate': len(df[df['pnl'] > 0]) / len(df) if len(df) > 0 else 0
            }
            
            # Break down by stop type
            for stop_type in df['stop_type'].unique():
                type_df = df[df['stop_type'] == stop_type]
                stats[f'{stop_type}_stops'] = {
                    'count': len(type_df),
                    'avg_pnl_pct': type_df['pnl_pct'].mean(),
                    'success_rate': len(type_df[type_df['pnl'] > 0]) / len(type_df) if len(type_df) > 0 else 0
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating stop performance stats: {e}")
            return {}
