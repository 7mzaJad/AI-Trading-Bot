import time
import logging
from data_fetcher import DataFetcher
from ai_engine import AIEngine
from execution import ExecutionManager
from config import Config, setup_logging

def run_trading_cycle(data_fetcher, ai_engine, execution_manager, logger):
    try:
        account_status = execution_manager.get_account_status()
        logger.info(f"Current Equity: ${account_status['equity']:.2f} | Buying Power: ${account_status['buying_power']:.2f}")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        return

    # 1. Ask AI to scan the entire market
    scan_result = ai_engine.scan_market_for_best_stock()
    ticker = scan_result.get("ticker", "NONE").upper()
    confidence = scan_result.get("confidence", 0)
    
    if ticker == "NONE" or not ticker or confidence < 90:
        logger.info(f"AI did not find a guaranteed solid trade today (Confidence: {confidence}). Skipping.")
        return
        
    logger.info(f"--- AI Recommended: {ticker} ---")
    
    # 2. Fetch Technicals for the AI's chosen ticker
    technicals = data_fetcher.get_technical_indicators(ticker)
    if not technicals:
        logger.warning(f"Could not fetch technical data for {ticker}. Skipping.")
        return
        
    current_price = technicals.get("current_price")
    logger.info(f"{ticker} Current Price: ${current_price:.2f}")
    
    # 3. Calculate SL and TP based on volatility
    atr = technicals.get("daily_volatility_percent", 2.0)
    if atr is None: atr = 2.0
    sl_price = current_price * (1 - (atr/100))
    tp_price = current_price * (1 + ((atr*2)/100))
    
    evaluation = {
        "decision": "BUY",
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price
    }
    
    # 4. Execute Trade
    execution_manager.execute_trade(ticker, evaluation, current_price)
    logger.info("Trading cycle complete. Waiting for next cycle...")

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting AI Trading Bot V2 (24/7 Mode)...")
    
    try:
        data_fetcher = DataFetcher()
        ai_engine = AIEngine()
        execution_manager = ExecutionManager()
    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        return

    logger.info("Monitoring the entire US Stock Market via AI Search...")

    
    while True:
        try:
            if execution_manager.is_market_open():
                logger.info("Market is OPEN. Starting trading cycle.")
                run_trading_cycle(data_fetcher, ai_engine, execution_manager, logger)
                
                # Sleep for 1 hour before analyzing again
                logger.info("Sleeping for 60 minutes...")
                time.sleep(60 * 60)
            else:
                seconds_to_open = execution_manager.time_until_open()
                hours = int(seconds_to_open // 3600)
                minutes = int((seconds_to_open % 3600) // 60)
                logger.info(f"Market is CLOSED. Sleeping for {hours}h {minutes}m until exactly the next open...")
                time.sleep(seconds_to_open + 5) # add 5s buffer to ensure it's fully open
        except Exception as e:
            logger.error(f"CRITICAL ERROR in main loop (likely internet dropout): {e}")
            logger.info("Sleeping for 60 seconds before retrying...")
            time.sleep(60)

if __name__ == "__main__":
    main()
