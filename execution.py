import logging
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from config import Config

logger = logging.getLogger(__name__)

class ExecutionManager:
    def __init__(self):
        Config.validate()
        self.client = TradingClient(
            Config.ALPACA_API_KEY, 
            Config.ALPACA_SECRET_KEY, 
            paper=Config.ALPACA_PAPER
        )

    def get_account_status(self):
        account = self.client.get_account()
        return {
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
        }

    def is_market_open(self) -> bool:
        clock = self.client.get_clock()
        return clock.is_open

    def time_until_open(self) -> float:
        clock = self.client.get_clock()
        if clock.is_open:
            return 0.0
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        time_to_open = (clock.next_open - now).total_seconds()
        return max(0.0, time_to_open)

    def get_positions(self):
        positions = self.client.get_all_positions()
        return {p.symbol: float(p.qty) for p in positions}

    def calculate_position_size(self, current_price: float, stop_loss: float, equity: float) -> int:
        if stop_loss >= current_price or stop_loss <= 0:
            return 0
            
        risk_amount = equity * Config.MAX_RISK_PERCENT
        risk_per_share = current_price - stop_loss
        
        shares = int(risk_amount // risk_per_share)
        
        # Ensure we don't exceed buying power (checked later, but roughly here)
        cost = shares * current_price
        if cost < Config.MIN_POSITION_SIZE_USD:
            return 0
            
        return shares

    def execute_trade(self, ticker: str, evaluation: dict, current_price: float):
        decision = evaluation.get("decision", "HOLD")
        
        if decision == "HOLD":
            return False

        account = self.get_account_status()
        positions = self.get_positions()
        current_qty = positions.get(ticker, 0)

        if decision == "SELL" and current_qty > 0:
            logger.info(f"Selling {current_qty} shares of {ticker}...")
            try:
                order_data = MarketOrderRequest(
                    symbol=ticker,
                    qty=current_qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC
                )
                self.client.submit_order(order_data)
                logger.info(f"Successfully placed SELL order for {ticker}.")
                return True
            except Exception as e:
                logger.error(f"Error selling {ticker}: {e}")
                return False

        if decision == "BUY":
            stop_loss = evaluation.get("stop_loss_price", 0.0)
            take_profit = evaluation.get("take_profit_price", 0.0)
            
            shares = self.calculate_position_size(current_price, stop_loss, account['equity'])
            cost = shares * current_price
            
            if shares <= 0 or cost > account['buying_power']:
                logger.warning(f"Cannot buy {ticker}. Calculated shares: {shares}, Cost: ${cost}, BP: ${account['buying_power']}")
                return False

            logger.info(f"Buying {shares} shares of {ticker} (OTO Bracket Order)...")
            try:
                order_data = MarketOrderRequest(
                    symbol=ticker,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
                    stop_loss=StopLossRequest(stop_price=round(stop_loss, 2))
                )
                self.client.submit_order(order_data)
                logger.info(f"Successfully placed BRACKET BUY order for {ticker}. SL: {stop_loss}, TP: {take_profit}")
                
                # Send Email Alert
                self.send_email_alert(
                    subject=f"AI Bot: BOUGHT {ticker}",
                    body=f"Order executed to buy {shares} shares of {ticker} at current price ${current_price}.\nStop Loss: ${stop_loss}\nTake Profit: ${take_profit}\nReasoning: {evaluation.get('chain_of_thought')}"
                )
                return True
            except Exception as e:
                logger.error(f"Error executing bracket order for {ticker}: {e}")
                return False
        
        return False

    def send_email_alert(self, subject: str, body: str):
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        sender = Config.EMAIL_SENDER
        password = Config.EMAIL_PASSWORD
        receiver = Config.EMAIL_RECEIVER
        
        if not sender or not password or not receiver:
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = receiver
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Successfully sent email alert: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
