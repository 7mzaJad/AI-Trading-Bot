import logging
import json
from google import genai
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from config import Config

logger = logging.getLogger(__name__)

class TradeDecision(BaseModel):
    chain_of_thought: str = Field(description="Step-by-step reasoning for the trade decision.")
    decision: str = Field(description="Exactly one of: BUY, SELL, or HOLD.")
    confidence: int = Field(description="Confidence level between 0 and 100.")
    stop_loss_price: float = Field(description="Calculated stop loss price if BUY. 0.0 if HOLD/SELL.")
    take_profit_price: float = Field(description="Calculated take profit price if BUY. 0.0 if HOLD/SELL.")

class AIEngine:
    def __init__(self):
        Config.validate()
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_name = "gemini-1.5-flash"

    def evaluate_stock(self, ticker: str, news: List[Dict[str, str]], technicals: Dict[str, Any], market_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"AI evaluating {ticker}...")
        

        news_text = "\n".join([f"- {item['title']}" for item in news])
        tech_text = json.dumps(technicals, indent=2)
        market_text = json.dumps(market_context, indent=2)

        prompt = f"""
You are an institutional quant trader. Evaluate '{ticker}'.

Market Context (SPY):
{market_text}

Stock News:
{news_text}

Technical Indicators:
{tech_text}

Rules:
1. If Market Context is BEARISH, heavily lean towards HOLD or SELL.
2. If news is highly positive AND Market is BULLISH AND price is above SMA_20, output BUY.
3. If BUY, calculate a realistic Stop Loss (below current price) and Take Profit (above current price) based on daily volatility.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TradeDecision,
                ),
            )
            
            result = json.loads(response.text)
            logger.info(f"AI Decision for {ticker}: {result.get('decision')} | Conf: {result.get('confidence')}")
            logger.info(f"Reasoning: {result.get('chain_of_thought')}")
            
            return result
        except Exception as e:
            logger.error(f"Error evaluating {ticker} via AI: {e}")
            return {"decision": "HOLD"}

    def evaluate_xauusd_macro(self, algo_signal: str, macro: Dict[str, Any]) -> str:
        logger.info(f"AI evaluating Macro context for algorithmic {algo_signal} signal...")
        
        macro_text = json.dumps(macro, indent=2)

        prompt = f"""
You are an elite Macro Economist. 
My algorithmic technical rules have just triggered a '{algo_signal}' on Gold (XAUUSD).
I need you to look at the US Dollar (DXY) and US 10-Year Treasury Yields (^TNX) and tell me if they support this trade.

Macro Factors (Gravity):
{macro_text}

RULES:
1. If DXY and Yields are both RISING, gold is under severe bearish pressure. A BUY should be REJECTED. A SELL should be APPROVED.
2. If DXY and Yields are both FALLING, gold has bullish tailwinds. A BUY should be APPROVED. A SELL should be REJECTED.
3. If they are mixed (NEUTRAL), default to APPROVED (let the technicals play out).

Respond with exactly one word: APPROVED or REJECTED. Do not add punctuation or explanation.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="text/plain",
                ),
            )
            
            result = response.text.strip().upper()
            if "APPROVED" in result:
                return "APPROVED"
            return "REJECTED"
        except Exception as e:
            logger.error(f"Error evaluating Macro via AI: {e}")
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                logger.warning("Gemini AI Rate Limit Exhausted! Bypassing Macro Filter and trusting mathematical algorithm -> APPROVED.")
                return "APPROVED"
            # Fail safe: if AI is down for other reasons, reject to protect capital
            return "REJECTED"

