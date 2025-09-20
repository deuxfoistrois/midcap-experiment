def sync_with_alpaca_positions(self):
    """Sync portfolio state with actual Alpaca positions - respect what Alpaca has"""
    if not self.use_alpaca or not self.alpaca_client:
        return
        
    logger.info("Syncing with Alpaca positions...")
    
    try:
        alpaca_positions = self.alpaca_client.sync_portfolio_positions()
        
        # Get current symbols from Alpaca (this is the source of truth)
        current_symbols = set(alpaca_positions.keys())
        logger.info(f"Current positions in Alpaca: {current_symbols}")
        
        # Remove positions from our portfolio state that are no longer in Alpaca
        # (e.g., due to stop losses being executed)
        portfolio_symbols = set(self.portfolio_state['positions'].keys())
        sold_symbols = portfolio_symbols - current_symbols
        
        if sold_symbols:
            logger.info(f"Positions sold/missing from Alpaca (removing): {sold_symbols}")
            for symbol in sold_symbols:
                if symbol in self.portfolio_state['positions']:
                    logger.info(f"Removing {symbol} from portfolio state - no longer in Alpaca")
                    del self.portfolio_state['positions'][symbol]
        
        # Only place initial orders if we have NO positions at all (completely empty account)
        if len(alpaca_positions) == 0 and len(self.portfolio_state['positions']) > 0:
            logger.info("No positions found in Alpaca - placing initial orders")
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
