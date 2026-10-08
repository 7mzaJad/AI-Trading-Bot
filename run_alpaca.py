import time
import logging
from data_fetcher import DataFetcher
from ai_engine import AIEngine
from execution import ExecutionManager
from config import Config, setup_logging

def run_trading_cycle(data_fetcher, ai_engine, execution_manager, logger, target_tickers):
    try:
        account_status = execution_manager.get_account_status()
        logger.info(f"Current Equity: ${account_status['equity']:.2f} | Buying Power: ${account_status['buying_power']:.2f}")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        return

    # Fetch Macro Market Context
    market_context = data_fetcher.get_market_context()
    logger.info(f"SPY Status: {market_context.get('status')}")

    for ticker in target_tickers:
        logger.info(f"--- Analyzing {ticker} ---")
        
        # 1. Fetch News
        news = data_fetcher.get_stock_news(ticker)
        
        # 2. Fetch Technicals
        technicals = data_fetcher.get_technical_indicators(ticker)
        if not technicals:
            logger.warning(f"Could not fetch sufficient technical data for {ticker}. Skipping.")
            continue
            
        current_price = technicals.get("current_price")
        logger.info(f"{ticker} Current Price: ${current_price:.2f}")
        
        # 3. AI Evaluation
        evaluation = ai_engine.evaluate_stock(ticker, news, technicals, market_context)
        
        # 4. Execute Trade
        execution_manager.execute_trade(ticker, evaluation, current_price)
        
        # Free Tier Rate Limit Handling
        logger.info("Sleeping for 5 seconds to respect Gemini API free tier limits...")
        time.sleep(5)

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

    target_tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GLD", "GOLD"]
    logger.info(f"Monitoring Tickers: {', '.join(target_tickers)}")
    
    while True:
        try:
            if execution_manager.is_market_open():
                logger.info("Market is OPEN. Starting trading cycle.")
                run_trading_cycle(data_fetcher, ai_engine, execution_manager, logger, target_tickers)
                
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
