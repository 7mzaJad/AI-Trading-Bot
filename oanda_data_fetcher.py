import logging
import yfinance as yf
import requests
import pandas as pd
import ta
from typing import Dict, Any
from datetime import datetime, timezone
from config import Config

logger = logging.getLogger(__name__)

class OandaDataFetcher:
    def __init__(self):
        Config.validate()
        self.api_key = Config.OANDA_API_KEY
        self.account_id = Config.OANDA_ACCOUNT_ID
        env = Config.OANDA_ENVIRONMENT.lower()
        self.base_url = "https://api-fxtrade.oanda.com/v3" if env == "live" else "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Datetime-Format": "UNIX"
        }

    def get_macro_context(self) -> Dict[str, Any]:
        """Fetches Macro Data (DXY and 10Y Yields) to understand US Dollar gravity."""
        try:
            macro_tickers = yf.Tickers('^TNX DX-Y.NYB')
            dxy_data = macro_tickers.tickers['DX-Y.NYB'].history(period='5d')
            tnx_data = macro_tickers.tickers['^TNX'].history(period='5d')
            
            if dxy_data.empty or tnx_data.empty:
                return {"status": "UNKNOWN"}

            dxy_current = dxy_data['Close'].iloc[-1]
            dxy_prev = dxy_data['Close'].iloc[-2]
            tnx_current = tnx_data['Close'].iloc[-1]
            tnx_prev = tnx_data['Close'].iloc[-2]

            dxy_trend = "RISING" if dxy_current > dxy_prev else "FALLING"
            tnx_trend = "RISING" if tnx_current > tnx_prev else "FALLING"
            
            status = "NEUTRAL"
            if dxy_trend == "RISING" and tnx_trend == "RISING":
                status = "BEARISH_FOR_GOLD"
            elif dxy_trend == "FALLING" and tnx_trend == "FALLING":
                status = "BULLISH_FOR_GOLD"

            return {
                "dxy_current": float(dxy_current),
                "dxy_trend": dxy_trend,
                "tnx_current": float(tnx_current),
                "tnx_trend": tnx_trend,
                "status": status
            }
        except Exception as e:
            logger.error(f"Error fetching macro context: {e}")
            return {"status": "UNKNOWN"}

    def _fetch_candles(self, instrument: str, granularity: str, count: int) -> pd.DataFrame:
        url = f"{self.base_url}/instruments/{instrument}/candles"
        params = {
            "count": count,
            "price": "M",
            "granularity": granularity
        }
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            if response.status_code in [500, 502, 503, 504]:
                logger.error(f"OANDA API is down or in maintenance (Status {response.status_code}).")
            else:
                logger.error(f"OANDA API Error: {response.text[:200]}")
            return pd.DataFrame()
            
        data = response.json().get('candles', [])
        if not data:
            return pd.DataFrame()
            
        parsed = []
        for c in data:
            if not c['complete']:
                pass # usually we keep the incomplete one for current price
            parsed.append({
                "time": pd.to_datetime(float(c['time']), unit='s'),
                "open": float(c['mid']['o']),
                "high": float(c['mid']['h']),
                "low": float(c['mid']['l']),
                "close": float(c['mid']['c']),
                "tick_volume": float(c['volume'])
            })
            
        return pd.DataFrame(parsed)

    def _calculate_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates Anchored Daily VWAP"""
        df['date'] = df['time'].dt.date
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vp'] = df['typical_price'] * df['tick_volume']
        
        df['cum_vp'] = df.groupby('date')['vp'].cumsum()
        df['cum_vol'] = df.groupby('date')['tick_volume'].cumsum()
        df['VWAP'] = df['cum_vp'] / df['cum_vol']
        return df

    def get_technical_indicators(self, symbol: str) -> Dict[str, Any]:
        """Calculates Institutional Strategy variables using OANDA candles."""
        try:
            df_1h = self._fetch_candles(symbol, "H1", 250)
            if df_1h.empty: return {}
            
            df_1h['EMA_200_1H'] = ta.trend.ema_indicator(df_1h['close'], window=200)
            ema_200_1h = df_1h.iloc[-1]['EMA_200_1H']
            close_1h = df_1h.iloc[-1]['close']

            df_15m = self._fetch_candles(symbol, "M15", 300)
            if df_15m.empty: return {}
            
            df_15m['EMA_200_15M'] = ta.trend.ema_indicator(df_15m['close'], window=200)
            df_15m['EMA_50_15M'] = ta.trend.ema_indicator(df_15m['close'], window=50)
            df_15m['ATR'] = ta.volatility.average_true_range(df_15m['high'], df_15m['low'], df_15m['close'], window=14)
            df_15m = self._calculate_vwap(df_15m)

            latest_15m = df_15m.iloc[-1]
            
            # Use RSI as well for momentum confirmation
            df_15m['RSI'] = ta.momentum.rsi(df_15m['close'], window=14)
            rsi = df_15m.iloc[-1]['RSI']

            return {
                "current_price": float(latest_15m['close']),
                "low": float(latest_15m['low']),
                "high": float(latest_15m['high']),
                "close_1h": float(close_1h),
                "ema_200_1h": float(ema_200_1h),
                "ema_200_15m": float(latest_15m['EMA_200_15M']),
                "ema_50_15m": float(latest_15m['EMA_50_15M']),
                "vwap": float(latest_15m['VWAP']),
                "atr_14": float(latest_15m['ATR']),
                "rsi_14": float(rsi)
            }
        except Exception as e:
            logger.error(f"Error calculating OANDA technicals for {symbol}: {e}")
            return {}

    def check_algorithmic_entry(self, technicals: Dict[str, Any]) -> Dict[str, Any]:
        """Pure Python mathematical rules for entry. Requires Trend Pullback."""
        
        price = technicals['current_price']
        low = technicals['low']
        high = technicals['high']
        close_1h = technicals['close_1h']
        ema_200_1h = technicals['ema_200_1h']
        ema_200_15m = technicals['ema_200_15m']
        ema_50_15m = technicals['ema_50_15m']
        vwap = technicals['vwap']
        atr = technicals['atr_14']
        
        signal = "HOLD"
        
        # BUY RULES
        if (close_1h > ema_200_1h and 
            price > ema_200_15m and 
            price > vwap and 
            low <= ema_50_15m and 
            price > ema_50_15m):
            signal = "BUY"
                
        # SELL RULES
        elif (close_1h < ema_200_1h and 
              price < ema_200_15m and 
              price < vwap and 
              high >= ema_50_15m and 
              price < ema_50_15m):
            signal = "SELL"
                
        if signal == "HOLD":
            return {"signal": "HOLD", "sl": 0.0, "tp": 0.0}
            
        sl_distance = 1.5 * atr
        tp_distance = 3.0 * atr
        
        if signal == "BUY":
            sl_price = price - sl_distance
            tp_price = price + tp_distance
        else:
            sl_price = price + sl_distance
            tp_price = price - tp_distance
            
        return {
            "signal": signal,
            "sl": round(sl_price, 3),
            "tp": round(tp_price, 3)
        }
