import os
import logging
from dotenv import load_dotenv

load_dotenv()

class Config:
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_PAPER = os.getenv("ALPACA_PAPER", "True").lower() == "true"
    
    # Email Settings
    EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # MetaTrader 5 Credentials
    MT5_LOGIN = os.getenv("MT5_LOGIN", "")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")
    
    # OANDA Credentials
    OANDA_API_KEY = os.getenv("OANDA_API_KEY", "")
    OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")
    
    # Advanced Risk Management
    MAX_RISK_PERCENT = float(os.getenv("RISK_TOLERANCE_PERCENT", "0.02")) # Max 2% of portfolio risked per trade
    MIN_POSITION_SIZE_USD = 100.0

    @classmethod
    def validate(cls):
        missing = []
        if not cls.ALPACA_API_KEY:
            missing.append("ALPACA_API_KEY")
        if not cls.ALPACA_SECRET_KEY:
            missing.append("ALPACA_SECRET_KEY")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        handlers=[
            logging.FileHandler("trading_bot.log"),
            logging.StreamHandler()
        ]
    )
    # Suppress verbose logs from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
