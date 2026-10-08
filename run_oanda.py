import time
import logging
from config import Config
from oanda_data_fetcher import OandaDataFetcher
from oanda_execution import OandaExecutionManager
from ai_engine import AIEngine

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("oanda_bot.log"),
            logging.StreamHandler()
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting OANDA XAU_USD AI Trading Bot...")

    try:
        data_fetcher = OandaDataFetcher()
        execution_manager = OandaExecutionManager()
        ai_engine = AIEngine()
        
        symbol = "XAU_USD" # OANDA uses XAU_USD, not XAUUSD
        
        while True:
            try:
                # 1. Fetch OANDA Technicals (REST API)
                technicals = data_fetcher.get_technical_indicators(symbol)
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
                    
                    # Fetch macro only when needed
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
                
                # Active monitoring: Sleep 15 seconds to be gentle on OANDA REST API limits
                time.sleep(15)
                
            except Exception as loop_e:
                logger.error(f"Network or data error in main loop: {loop_e}. Retrying in 60s...")
                time.sleep(60)

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
