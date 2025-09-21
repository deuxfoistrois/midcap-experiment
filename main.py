def sync_with_alpaca_positions(self):
        """Sync portfolio with current Alpaca positions, respecting stop loss executions"""
        try:
            if not self.alpaca_client:
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
                if symbol in self.portfolio_state['positions']:
                    # Update with current market data
                    self.portfolio_state['positions'][symbol].update({
                        'current_price': alpaca_pos['current_price'],
                        'market_value': alpaca_pos['market_value'],
                        'unrealized_pnl': alpaca_pos['unrealized_pnl'],
                        'unrealized_pnl_pct': alpaca_pos['unrealized_pnl_pct'],
                        'last_update': datetime.now().isoformat()
                    })
                    logger.info(f"Updated {symbol} with current Alpaca data")
            
            # Only place initial orders if account is completely empty
            if not alpaca_symbols and not self.portfolio_state['positions']:
                logger.info("Account empty - placing initial portfolio positions")
                orders = self.alpaca_client.place_initial_portfolio_positions()
                if orders:
                    logger.info(f"Placed {len(orders)} initial orders")
            
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
                        
                    if self.data_source == 'alpaca' and self.alpaca_client:
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
