import time
import logging
from config import Config
from mt5_data_fetcher import MT5DataFetcher
from mt5_execution import MT5ExecutionManager
from ai_engine import AIEngine
import MetaTrader5 as mt5

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("mt5_bot.log"),
            logging.StreamHandler()
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting MT5 XAUUSD AI Trading Bot...")

    try:
        data_fetcher = MT5DataFetcher()
        execution_manager = MT5ExecutionManager()
        ai_engine = AIEngine()
        
        symbol = "XAUUSD"
        
        while True:
            # 1. Fetch MT5 Technicals (Local, no rate limits, runs every 10s)
            technicals = data_fetcher.get_technical_indicators(symbol, mt5.TIMEFRAME_M15)
            if not technicals:
                logger.warning(f"Could not fetch technicals for {symbol}. Retrying...")
                time.sleep(10)
                continue
                
            # 2. Pure Algorithmic Rules (Math first)
            algo_decision = data_fetcher.check_algorithmic_entry(technicals)
            signal = algo_decision['signal']
            
            # 3. If Math Triggers, get Macro & AI Approval
            if signal in ["BUY", "SELL"]:
                logger.info(f"Algorithmic Math Signal: {signal}. Checking Macro & AI...")
                
                # Fetch macro only when needed to prevent Yahoo Finance rate-limiting
                macro = data_fetcher.get_macro_context()
                
                ai_approval = ai_engine.evaluate_xauusd_macro(signal, macro)
                logger.info(f"AI Macro Filter Result: {ai_approval}")
                
                if ai_approval == "APPROVED":
                    trade_payload = {
                        "decision": signal,
                        "stop_loss_price": algo_decision['sl'],
                        "take_profit_price": algo_decision['tp']
                    }
                    execution_manager.execute_trade(symbol, trade_payload, technicals['current_price'])
                else:
                    logger.info("AI Rejected the algorithmic setup. Waiting for better conditions.")
            
            # Active monitoring: Sleep only 10 seconds before checking math again
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Bot manually stopped.")
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}", exc_info=True)
    finally:
        try:
            execution_manager.shutdown()
        except:
            pass

if __name__ == "__main__":
    main()
