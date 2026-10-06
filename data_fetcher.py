import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.historical.stock import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd
import logging
from config import Config

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        Config.validate()
        self.data_client = StockHistoricalDataClient(
            Config.ALPACA_API_KEY, 
            Config.ALPACA_SECRET_KEY
        )

    def get_stock_news(self, ticker: str, num_articles: int = 5) -> List[Dict[str, str]]:
        """Fetches the latest news using yfinance."""
        logger.info(f"Fetching news for {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            if not news:
                return []
            
            return [{
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", "")
            } for item in news[:num_articles]]
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return []

    def get_latest_price(self, ticker: str) -> float:
        """Gets real-time latest quote from Alpaca."""
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=ticker, feed=DataFeed.IEX)
            latest_quote = self.data_client.get_stock_latest_quote(request_params)
            return float(latest_quote[ticker].ask_price)
        except Exception as e:
            logger.error(f"Error fetching latest quote for {ticker}: {e}")
            return 0.0

    def get_technical_indicators(self, ticker: str) -> Dict[str, Any]:
        """Calculates basic technical indicators using Alpaca Historical Data."""
        logger.info(f"Calculating technicals for {ticker}...")
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=100)
            
            request_params = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
                feed=DataFeed.IEX
            )
            
            bars = self.data_client.get_stock_bars(request_params)
            if not bars.data or ticker not in bars.data:
                return {}

            # Convert to Pandas DataFrame
            df = pd.DataFrame([{"Close": bar.close, "Volume": bar.volume} for bar in bars.data[ticker]])
            
            if len(df) < 20:
                return {}

            # Calculate SMA
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            
            # Calculate RSI (14-day)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI_14'] = 100 - (100 / (1 + rs))
            
            # Calculate basic volatility for stop loss estimation
            df['Daily_Return'] = df['Close'].pct_change()
            volatility = df['Daily_Return'].std() * 100

            latest = df.iloc[-1]
            return {
                "current_price": latest['Close'],
                "sma_20": latest['SMA_20'] if not pd.isna(latest['SMA_20']) else None,
                "rsi_14": latest['RSI_14'] if not pd.isna(latest['RSI_14']) else None,
                "daily_volatility_percent": volatility if not pd.isna(volatility) else None
            }
        except Exception as e:
            logger.error(f"Error fetching market data for {ticker}: {e}")
            return {}

    def get_market_context(self) -> Dict[str, Any]:
        """Analyzes SPY to determine broader market health."""
        logger.info("Fetching macro market context (SPY)...")
        technicals = self.get_technical_indicators("SPY")
        if not technicals:
            return {"status": "UNKNOWN"}
            
        current = technicals.get("current_price", 0)
        sma = technicals.get("sma_20", 0)
        
        status = "BULLISH" if current > sma else "BEARISH"
        return {
            "symbol": "SPY",
            "status": status,
            "current_price": current,
            "sma_20": sma
        }
